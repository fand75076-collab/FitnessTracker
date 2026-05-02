package com.fitness.tracker;

import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class WorkoutDatabase extends SQLiteOpenHelper {
    private static final String DB_NAME = "workout.db";
    private static final int DB_VERSION = 2;
    private static final String PREFS_NAME = "workout_seed";
    private static final String KEY_BUNDLED_SIGNATURE = "bundled_signature";
    private static final SimpleDateFormat DATE_TIME = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA);

    private final Context appContext;
    private boolean bundledSyncAttempted = false;

    WorkoutDatabase(Context context) {
        super(context.getApplicationContext(), DB_NAME, null, DB_VERSION);
        this.appContext = context.getApplicationContext();
        copyBundledDatabaseIfMissing();
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL(
                "CREATE TABLE IF NOT EXISTS workout_sets (" +
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                        "completed_at TEXT NOT NULL, " +
                        "body_part TEXT NOT NULL, " +
                        "exercise_name TEXT NOT NULL, " +
                        "weight_kg REAL NOT NULL, " +
                        "reps INTEGER NOT NULL, " +
                        "set_number INTEGER NOT NULL, " +
                        "notes TEXT DEFAULT '', " +
                        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        );
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_completed_at ON workout_sets(completed_at)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_exercise_name ON workout_sets(exercise_name)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_day_exercise ON workout_sets(completed_at, exercise_name, weight_kg, reps)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_day_exercise ON workout_sets(completed_at, exercise_name, weight_kg, reps)");
        }
    }

    @Override
    public void onOpen(SQLiteDatabase db) {
        super.onOpen(db);
        db.execSQL("PRAGMA journal_mode=WAL");
        db.execSQL("PRAGMA busy_timeout=5000");
        syncBundledDatabase(db);
    }

    SQLiteDatabase openDb() {
        return getWritableDatabase();
    }

    private void copyBundledDatabaseIfMissing() {
        File dbFile = appContext.getDatabasePath(DB_NAME);
        if (dbFile.exists()) {
            return;
        }

        File parent = dbFile.getParentFile();
        if (parent != null && !parent.exists()) {
            //noinspection ResultOfMethodCallIgnored
            parent.mkdirs();
        }

        long copiedBytes = 0;
        try (InputStream input = appContext.getAssets().open(DB_NAME);
             FileOutputStream output = new FileOutputStream(dbFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) > 0) {
                output.write(buffer, 0, read);
                copiedBytes += read;
            }
            output.flush();
            seedPrefs().edit().putString(KEY_BUNDLED_SIGNATURE, "fresh:" + copiedBytes).apply();
        } catch (IOException ignored) {
            if (dbFile.exists() && dbFile.length() == 0) {
                //noinspection ResultOfMethodCallIgnored
                dbFile.delete();
            }
        }
    }

    private void syncBundledDatabase(SQLiteDatabase db) {
        if (bundledSyncAttempted) {
            return;
        }
        bundledSyncAttempted = true;

        File bundled = copyBundledDatabaseToCache();
        if (bundled == null) {
            return;
        }

        String signature = bundledSignature(bundled);
        if (signature.isEmpty() || signature.equals(seedPrefs().getString(KEY_BUNDLED_SIGNATURE, ""))) {
            //noinspection ResultOfMethodCallIgnored
            bundled.delete();
            return;
        }

        boolean attached = false;
        try {
            db.execSQL("ATTACH DATABASE ? AS bundled", new Object[]{bundled.getAbsolutePath()});
            attached = true;
            db.beginTransaction();
            db.execSQL(
                    "INSERT INTO workout_sets (completed_at, body_part, exercise_name, weight_kg, reps, set_number, notes, created_at) " +
                            "SELECT b.completed_at, b.body_part, b.exercise_name, b.weight_kg, b.reps, b.set_number, " +
                            "IFNULL(b.notes, ''), IFNULL(b.created_at, CURRENT_TIMESTAMP) " +
                            "FROM bundled.workout_sets b " +
                            "WHERE NOT EXISTS (" +
                            "SELECT 1 FROM workout_sets w " +
                            "WHERE w.completed_at = b.completed_at " +
                            "AND w.exercise_name = b.exercise_name " +
                            "AND w.weight_kg = b.weight_kg " +
                            "AND w.reps = b.reps " +
                            "AND w.set_number = b.set_number " +
                            "AND IFNULL(w.notes, '') = IFNULL(b.notes, '')" +
                            ")"
            );
            db.setTransactionSuccessful();
            seedPrefs().edit().putString(KEY_BUNDLED_SIGNATURE, signature).apply();
        } catch (RuntimeException ignored) {
            // Keep the user's existing database usable even if the bundled seed cannot be merged.
        } finally {
            if (db.inTransaction()) {
                db.endTransaction();
            }
            if (attached) {
                try {
                    db.execSQL("DETACH DATABASE bundled");
                } catch (RuntimeException ignored) {
                    // Ignore detach failures during best-effort seed sync cleanup.
                }
            }
            //noinspection ResultOfMethodCallIgnored
            bundled.delete();
        }
    }

    private File copyBundledDatabaseToCache() {
        File outputFile = new File(appContext.getCacheDir(), "bundled-" + DB_NAME);
        try (InputStream input = appContext.getAssets().open(DB_NAME);
             FileOutputStream output = new FileOutputStream(outputFile, false)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) > 0) {
                output.write(buffer, 0, read);
            }
            output.flush();
            return outputFile;
        } catch (IOException ignored) {
            if (outputFile.exists()) {
                //noinspection ResultOfMethodCallIgnored
                outputFile.delete();
            }
            return null;
        }
    }

    private String bundledSignature(File bundled) {
        SQLiteDatabase seedDb = null;
        Cursor cursor = null;
        try {
            seedDb = SQLiteDatabase.openDatabase(bundled.getAbsolutePath(), null, SQLiteDatabase.OPEN_READONLY);
            cursor = seedDb.rawQuery(
                    "SELECT COUNT(*), MIN(completed_at), MAX(completed_at), MAX(id) FROM workout_sets",
                    null
            );
            if (!cursor.moveToNext()) {
                return "";
            }
            return bundled.length() + ":" + cursor.getLong(0) + ":" + cursor.getString(1) + ":" + cursor.getString(2) + ":" + cursor.getLong(3);
        } catch (RuntimeException ignored) {
            return "";
        } finally {
            if (cursor != null) {
                cursor.close();
            }
            if (seedDb != null) {
                seedDb.close();
            }
        }
    }

    private SharedPreferences seedPrefs() {
        return appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    List<WorkoutSet> allSets() {
        List<WorkoutSet> sets = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT id, completed_at, body_part, exercise_name, weight_kg, reps, set_number, notes " +
                        "FROM workout_sets ORDER BY datetime(completed_at) DESC, id DESC",
                null
        );
        try {
            while (cursor.moveToNext()) {
                sets.add(readSet(cursor));
            }
        } finally {
            cursor.close();
        }
        return sets;
    }

    List<WorkoutSet> recentSets(int limit) {
        List<WorkoutSet> sets = new ArrayList<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT id, completed_at, body_part, exercise_name, weight_kg, reps, set_number, notes " +
                        "FROM workout_sets ORDER BY datetime(completed_at) DESC, id DESC LIMIT ?",
                new String[]{String.valueOf(limit)}
        );
        try {
            while (cursor.moveToNext()) {
                sets.add(readSet(cursor));
            }
        } finally {
            cursor.close();
        }
        return sets;
    }

    WorkoutSet getById(long id) {
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT id, completed_at, body_part, exercise_name, weight_kg, reps, set_number, notes " +
                        "FROM workout_sets WHERE id = ?",
                new String[]{String.valueOf(id)}
        );
        try {
            if (cursor.moveToNext()) {
                return readSet(cursor);
            }
            return null;
        } finally {
            cursor.close();
        }
    }

    boolean deleteSet(long id) {
        SQLiteDatabase db = getWritableDatabase();
        return db.delete("workout_sets", "id = ?", new String[]{String.valueOf(id)}) > 0;
    }

    boolean updateSet(long id, String bodyPart, String exercise, double weight, int reps, int setNumber, String notes) {
        String canonical = Normalizer.exercise(exercise);
        validateWorkout(canonical, weight, reps, setNumber);
        SQLiteDatabase db = getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("body_part", Normalizer.bodyPart(canonical, bodyPart));
        values.put("exercise_name", canonical);
        values.put("weight_kg", weight);
        values.put("reps", reps);
        values.put("set_number", setNumber);
        values.put("notes", notes == null ? "" : notes);
        return db.update("workout_sets", values, "id = ?", new String[]{String.valueOf(id)}) > 0;
    }

    private WorkoutSet readSet(Cursor cursor) {
        String rawExercise = cursor.getString(3);
        String exercise = Normalizer.exercise(rawExercise);
        String body = Normalizer.bodyPart(exercise, cursor.getString(2));
        return new WorkoutSet(
                cursor.getLong(0),
                cursor.getString(1),
                body,
                exercise,
                cursor.getDouble(4),
                cursor.getInt(5),
                cursor.getInt(6),
                cursor.getString(7)
        );
    }

    List<String> recentExercises(int limit) {
        LinkedHashMap<String, String> names = new LinkedHashMap<>();
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT exercise_name, MAX(datetime(completed_at)) AS latest FROM workout_sets " +
                        "GROUP BY exercise_name ORDER BY latest DESC LIMIT ?",
                new String[]{String.valueOf(limit * 3)}
        );
        try {
            while (cursor.moveToNext() && names.size() < limit) {
                String name = Normalizer.exercise(cursor.getString(0));
                if (!name.isEmpty() && !names.containsKey(name)) {
                    names.put(name, name);
                }
            }
        } finally {
            cursor.close();
        }
        return new ArrayList<>(names.keySet());
    }

    WorkoutSet lastForExercise(String exercise) {
        List<String> aliases = Normalizer.aliasesFor(exercise);
        if (aliases.isEmpty()) {
            return null;
        }
        StringBuilder placeholders = new StringBuilder();
        for (int i = 0; i < aliases.size(); i++) {
            if (i > 0) placeholders.append(",");
            placeholders.append("?");
        }
        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT id, completed_at, body_part, exercise_name, weight_kg, reps, set_number, notes " +
                        "FROM workout_sets WHERE exercise_name IN (" + placeholders + ") " +
                        "ORDER BY datetime(completed_at) DESC, id DESC LIMIT 1",
                aliases.toArray(new String[0])
        );
        try {
            return cursor.moveToNext() ? readSet(cursor) : null;
        } finally {
            cursor.close();
        }
    }

    int nextSetNumber(String exercise, String timestamp) {
        List<String> aliases = Normalizer.aliasesFor(exercise);
        if (aliases.isEmpty()) {
            return 1;
        }
        StringBuilder placeholders = new StringBuilder();
        for (int i = 0; i < aliases.size(); i++) {
            if (i > 0) placeholders.append(",");
            placeholders.append("?");
        }
        Date anchor = parseDate(timestamp);
        long startMillis = anchor.getTime() - 90L * 60L * 1000L;
        String start = DATE_TIME.format(new Date(startMillis));

        String[] args = new String[aliases.size() + 2];
        for (int i = 0; i < aliases.size(); i++) {
            args[i] = aliases.get(i);
        }
        args[aliases.size()] = start;
        args[aliases.size() + 1] = timestamp;

        SQLiteDatabase db = getReadableDatabase();
        Cursor cursor = db.rawQuery(
                "SELECT MAX(set_number) FROM workout_sets WHERE exercise_name IN (" + placeholders + ") " +
                        "AND datetime(completed_at) >= datetime(?) AND datetime(completed_at) <= datetime(?)",
                args
        );
        try {
            if (cursor.moveToNext() && !cursor.isNull(0)) {
                return cursor.getInt(0) + 1;
            }
            return 1;
        } finally {
            cursor.close();
        }
    }

    long insertSet(String completedAt, String bodyPart, String exercise, double weight, int reps, int setNumber, String notes) {
        String canonical = Normalizer.exercise(exercise);
        validateWorkout(canonical, weight, reps, setNumber);
        SQLiteDatabase db = getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("completed_at", completedAt);
        values.put("body_part", Normalizer.bodyPart(canonical, bodyPart));
        values.put("exercise_name", canonical);
        values.put("weight_kg", weight);
        values.put("reps", reps);
        values.put("set_number", setNumber);
        values.put("notes", notes == null ? "" : notes);
        return db.insertOrThrow("workout_sets", null, values);
    }

    Map<String, Double> volumeByMonth(List<WorkoutSet> sets) {
        LinkedHashMap<String, Double> map = new LinkedHashMap<>();
        List<WorkoutSet> chronological = new ArrayList<>(sets);
        for (int i = chronological.size() - 1; i >= 0; i--) {
            WorkoutSet set = chronological.get(i);
            String period = set.completedAt.length() >= 7 ? set.completedAt.substring(0, 7) : set.completedAt;
            Double old = map.get(period);
            map.put(period, (old == null ? 0 : old) + set.volumeKg());
        }
        return map;
    }

    Map<String, Double> volumeByBodyPart(List<WorkoutSet> sets) {
        LinkedHashMap<String, Double> map = new LinkedHashMap<>();
        for (WorkoutSet set : sets) {
            Double old = map.get(set.bodyPart);
            map.put(set.bodyPart, (old == null ? 0 : old) + set.volumeKg());
        }
        return map;
    }

    List<WorkoutSet> prRecords() {
        LinkedHashMap<String, WorkoutSet> bestByExercise = new LinkedHashMap<>();
        for (WorkoutSet set : allSets()) {
            WorkoutSet old = bestByExercise.get(set.exerciseName);
            if (old == null
                    || set.estimatedOneRepMax() > old.estimatedOneRepMax()
                    || (set.estimatedOneRepMax() == old.estimatedOneRepMax()
                    && set.completedAt.compareTo(old.completedAt) > 0)) {
                bestByExercise.put(set.exerciseName, set);
            }
        }

        List<WorkoutSet> prs = new ArrayList<>(bestByExercise.values());
        prs.sort(Comparator.comparingDouble(WorkoutSet::estimatedOneRepMax).reversed());
        return prs;
    }

    private void validateWorkout(String exercise, double weight, int reps, int setNumber) {
        if (exercise == null || exercise.trim().isEmpty()) {
            throw new IllegalArgumentException("动作不能为空");
        }
        if (weight < 0 || weight > 500) {
            throw new IllegalArgumentException("重量不合理");
        }
        if (reps < 1 || reps > 200) {
            throw new IllegalArgumentException("次数不合理");
        }
        if (setNumber < 1 || setNumber > 50) {
            throw new IllegalArgumentException("组序号不合理");
        }
    }

    static String nowText() {
        return DATE_TIME.format(new Date());
    }

    static Date parseDate(String value) {
        try {
            return DATE_TIME.parse(value.replace("T", " "));
        } catch (ParseException e) {
            return new Date();
        }
    }
}
