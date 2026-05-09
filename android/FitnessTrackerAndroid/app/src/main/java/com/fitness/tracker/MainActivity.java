package com.fitness.tracker;

import android.app.AlertDialog;
import android.os.Bundle;
import android.text.InputType;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.viewpager2.adapter.FragmentStateAdapter;
import androidx.viewpager2.widget.ViewPager2;

import com.google.android.material.tabs.TabLayout;
import com.google.android.material.tabs.TabLayoutMediator;

import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public final class MainActivity extends AppCompatActivity {
    private static final String[] BODY_PARTS = {"胸", "背", "腿", "肩", "手臂", "核心", "有氧", "全身", "其他"};

    private WorkoutDatabase database;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        database = new WorkoutDatabase(this);
        setContentView(R.layout.activity_main);

        TabLayout tabLayout = findViewById(R.id.tab_layout);
        ViewPager2 viewPager = findViewById(R.id.view_pager);
        viewPager.setOffscreenPageLimit(3);

        viewPager.setAdapter(new FragmentStateAdapter(this) {
            @Override
            public int getItemCount() { return 4; }

            @Override
            public Fragment createFragment(int position) {
                switch (position) {
                    case 0: return new EntryFragment();
                    case 1: return new DashboardFragment();
                    case 2: return new PrFragment();
                    case 3: return new RecentFragment();
                    default: return new EntryFragment();
                }
            }
        });

        new TabLayoutMediator(tabLayout, viewPager, (tab, position) -> {
            String[] titles = {"录入", "总览", "PR", "记录"};
            tab.setText(titles[position]);
        }).attach();
    }

    WorkoutDatabase getDatabase() { return database; }

    // ─── Entry Fragment ─────────────────────────────────────────────────────────

    public static class EntryFragment extends Fragment {
        private AutoCompleteTextView exerciseInput;
        private Spinner bodyPartSpinner;
        private EditText timestampInput, weightInput, repsInput, setInput, notesInput;

        @Override
        public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
            View view = inflater.inflate(R.layout.page_entry, container, false);
            MainActivity activity = (MainActivity) requireActivity();
            WorkoutDatabase db = activity.getDatabase();

            timestampInput = view.findViewById(R.id.input_timestamp);
            exerciseInput = view.findViewById(R.id.input_exercise);
            bodyPartSpinner = view.findViewById(R.id.spinner_body_part);
            weightInput = view.findViewById(R.id.input_weight);
            repsInput = view.findViewById(R.id.input_reps);
            setInput = view.findViewById(R.id.input_set);
            notesInput = view.findViewById(R.id.input_notes);
            Button saveBtn = view.findViewById(R.id.btn_save);

            timestampInput.setText(WorkoutDatabase.nowText());

            List<String> exercises = db.recentExercises(80);
            if (exercises.isEmpty()) exercises.add("杠铃卧推");
            exerciseInput.setAdapter(new ArrayAdapter<>(requireContext(),
                    android.R.layout.simple_dropdown_item_1line, exercises));

            bodyPartSpinner.setAdapter(new ArrayAdapter<>(requireContext(),
                    android.R.layout.simple_spinner_dropdown_item, BODY_PARTS));

            weightInput.setText("70");
            repsInput.setText("10");
            setInput.setText("1");

            exerciseInput.setOnItemClickListener((parent, v, pos, id) -> applyLastValues(db));
            saveBtn.setOnClickListener(v -> saveWorkout(db));

            return view;
        }

        private void applyLastValues(WorkoutDatabase db) {
            String exercise = exerciseInput.getText().toString().trim();
            WorkoutSet last = db.lastForExercise(exercise);
            if (last == null) { setInput.setText("1"); return; }
            weightInput.setText(trimNumber(last.weightKg));
            repsInput.setText(String.valueOf(last.reps));
            setInput.setText(String.valueOf(db.nextSetNumber(exercise, timestampInput.getText().toString())));
            setSpinnerValue(bodyPartSpinner, last.bodyPart);
        }

        private void saveWorkout(WorkoutDatabase db) {
            try {
                String exercise = exerciseInput.getText().toString().trim();
                if (exercise.isEmpty()) {
                    Toast.makeText(requireContext(), "动作不能为空", Toast.LENGTH_SHORT).show();
                    return;
                }
                String timestamp = timestampInput.getText().toString().trim();
                if (!WorkoutDatabase.isValidTimestamp(timestamp)) {
                    Toast.makeText(requireContext(), "日期格式错误，请使用 yyyy-MM-dd HH:mm", Toast.LENGTH_SHORT).show();
                    return;
                }
                double weight = Double.parseDouble(weightInput.getText().toString().trim());
                int reps = Integer.parseInt(repsInput.getText().toString().trim());
                int setNumber = Integer.parseInt(setInput.getText().toString().trim());
                String body = String.valueOf(bodyPartSpinner.getSelectedItem());
                String notes = notesInput.getText().toString().trim();

                db.insertSet(timestamp, body, exercise, weight, reps, setNumber, notes);
                timestampInput.setText(WorkoutDatabase.nowText());
                setInput.setText(String.valueOf(db.nextSetNumber(exercise, timestampInput.getText().toString())));
                notesInput.setText("");
                Toast.makeText(requireContext(),
                        "已记录：" + exercise + " " + trimNumber(weight) + "kg x " + reps,
                        Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(requireContext(), "保存失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        }

        private void setSpinnerValue(Spinner spinner, String value) {
            for (int i = 0; i < spinner.getCount(); i++) {
                if (String.valueOf(spinner.getItemAtPosition(i)).equals(value)) {
                    spinner.setSelection(i);
                    return;
                }
            }
        }
    }

    // ─── Dashboard Fragment ─────────────────────────────────────────────────────

    public static class DashboardFragment extends Fragment {
        @Override
        public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
            View view = inflater.inflate(R.layout.page_dashboard, container, false);
            MainActivity activity = (MainActivity) requireActivity();
            WorkoutDatabase db = activity.getDatabase();
            List<WorkoutSet> sets = db.allSets();

            // Compute metrics
            double volume = 0;
            double maxOneRm = 0;
            Set<String> days = new HashSet<>();
            Set<String> exercises = new HashSet<>();
            for (WorkoutSet s : sets) {
                volume += s.volumeKg();
                maxOneRm = Math.max(maxOneRm, s.estimatedOneRepMax());
                if (s.completedAt.length() >= 10) days.add(s.completedAt.substring(0, 10));
                exercises.add(s.exerciseName);
            }

            // Bind metric cards
            bindMetric(view.findViewById(R.id.metric_sets), "总组数",
                    String.format(Locale.CHINA, "%,d", sets.size()), "全部历史训练");
            bindMetric(view.findViewById(R.id.metric_volume), "总训练量",
                    String.format(Locale.CHINA, "%,.0f kg", volume), "重量 × 次数");
            bindMetric(view.findViewById(R.id.metric_days), "训练天数",
                    String.valueOf(days.size()), exercises.size() + " 个动作");
            bindMetric(view.findViewById(R.id.metric_1rm), "最高估算 1RM",
                    String.format(Locale.CHINA, "%.1f kg", maxOneRm), "Epley / Brzycki");

            // Charts
            TrendChartView trendChart = view.findViewById(R.id.chart_trend);
            BarChartView bodyChart = view.findViewById(R.id.chart_body);
            trendChart.setData(db.volumeByMonth(sets));
            bodyChart.setData(db.volumeByBodyPart(sets));

            return view;
        }

        private void bindMetric(View card, String label, String value, String detail) {
            ((TextView) card.findViewById(R.id.metric_label)).setText(label);
            ((TextView) card.findViewById(R.id.metric_value)).setText(value);
            ((TextView) card.findViewById(R.id.metric_detail)).setText(detail);
        }
    }

    // ─── PR Fragment ────────────────────────────────────────────────────────────

    public static class PrFragment extends Fragment {
        @Override
        public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
            View view = inflater.inflate(R.layout.page_pr, container, false);
            MainActivity activity = (MainActivity) requireActivity();
            WorkoutDatabase db = activity.getDatabase();
            LinearLayout prList = view.findViewById(R.id.pr_list);

            List<WorkoutSet> prs = db.prRecords();
            Set<String> seen = new HashSet<>();
            for (WorkoutSet pr : prs) {
                if (seen.contains(pr.exerciseName)) continue;
                seen.add(pr.exerciseName);

                View row = inflater.inflate(R.layout.item_pr_row, prList, false);
                ((TextView) row.findViewById(R.id.pr_exercise)).setText(pr.exerciseName);
                ((TextView) row.findViewById(R.id.pr_detail)).setText(
                        trimNumber(pr.weightKg) + "kg × " + pr.reps +
                        "  1RM " + String.format(Locale.CHINA, "%.1f", pr.estimatedOneRepMax()) + "kg");
                prList.addView(row);
            }

            if (prs.isEmpty()) {
                TextView empty = new TextView(requireContext());
                empty.setText("暂无 PR 数据");
                empty.setTextColor(0xFF667085);
                prList.addView(empty);
            }

            return view;
        }
    }

    // ─── Recent Fragment ────────────────────────────────────────────────────────

    public static class RecentFragment extends Fragment {
        @Override
        public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
            View view = inflater.inflate(R.layout.page_recent, container, false);
            MainActivity activity = (MainActivity) requireActivity();
            WorkoutDatabase db = activity.getDatabase();
            LinearLayout recentList = view.findViewById(R.id.recent_list);

            List<WorkoutSet> recent = db.recentSets(30);
            for (WorkoutSet s : recent) {
                View row = inflater.inflate(R.layout.item_recent_row, recentList, false);
                String info = s.completedAt.substring(0, Math.min(16, s.completedAt.length()))
                        + " " + s.exerciseName + " " + trimNumber(s.weightKg) + "kg × " + s.reps;
                ((TextView) row.findViewById(R.id.recent_info)).setText(info);

                long setId = s.id;
                row.findViewById(R.id.btn_edit).setOnClickListener(v -> showEditDialog(db, setId));
                row.findViewById(R.id.btn_delete).setOnClickListener(v -> confirmDelete(db, setId));
                recentList.addView(row);
            }

            if (recent.isEmpty()) {
                TextView empty = new TextView(requireContext());
                empty.setText("暂无记录");
                empty.setTextColor(0xFF667085);
                recentList.addView(empty);
            }

            return view;
        }

        private void confirmDelete(WorkoutDatabase db, long id) {
            new AlertDialog.Builder(requireContext())
                    .setTitle("确认删除")
                    .setMessage("确定要删除这条记录吗？")
                    .setPositiveButton("删除", (d, w) -> {
                        db.deleteSet(id);
                        Toast.makeText(requireContext(), "已删除", Toast.LENGTH_SHORT).show();
                        refreshList();
                    })
                    .setNegativeButton("取消", null)
                    .show();
        }

        private void showEditDialog(WorkoutDatabase db, long id) {
            WorkoutSet s = db.getById(id);
            if (s == null) return;

            LinearLayout layout = new LinearLayout(requireContext());
            layout.setOrientation(LinearLayout.VERTICAL);
            int pad = (int) (24 * getResources().getDisplayMetrics().density);
            layout.setPadding(pad, pad / 2, pad, pad / 3);

            EditText weightEdit = new EditText(requireContext());
            weightEdit.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
            weightEdit.setText(trimNumber(s.weightKg));
            weightEdit.setHint("重量 (kg)");
            layout.addView(weightEdit);

            EditText repsEdit = new EditText(requireContext());
            repsEdit.setInputType(InputType.TYPE_CLASS_NUMBER);
            repsEdit.setText(String.valueOf(s.reps));
            repsEdit.setHint("次数");
            layout.addView(repsEdit);

            EditText setEdit = new EditText(requireContext());
            setEdit.setInputType(InputType.TYPE_CLASS_NUMBER);
            setEdit.setText(String.valueOf(s.setNumber));
            setEdit.setHint("第几组");
            layout.addView(setEdit);

            new AlertDialog.Builder(requireContext())
                    .setTitle("编辑记录 #" + id)
                    .setView(layout)
                    .setPositiveButton("保存", (d, w) -> {
                        try {
                            double w2 = Double.parseDouble(weightEdit.getText().toString().trim());
                            int r2 = Integer.parseInt(repsEdit.getText().toString().trim());
                            int sn2 = Integer.parseInt(setEdit.getText().toString().trim());
                            db.updateSet(id, s.bodyPart, s.exerciseName, w2, r2, sn2, s.notes);
                            Toast.makeText(requireContext(), "已更新", Toast.LENGTH_SHORT).show();
                            refreshList();
                        } catch (Exception ex) {
                            Toast.makeText(requireContext(), "更新失败：" + ex.getMessage(), Toast.LENGTH_LONG).show();
                        }
                    })
                    .setNegativeButton("取消", null)
                    .show();
        }

        private void refreshList() {
            // Re-create fragment view
            if (getView() != null) {
                ViewGroup parent = (ViewGroup) getView().getParent();
                if (parent != null) {
                    parent.removeView(getView());
                }
            }
            getParentFragmentManager().beginTransaction()
                    .detach(this).commitNow();
            getParentFragmentManager().beginTransaction()
                    .attach(this).commitNow();
        }
    }

    // ─── Shared utility ─────────────────────────────────────────────────────────

    static String trimNumber(double value) {
        if (Math.abs(value - Math.round(value)) < 0.00001) {
            return String.valueOf((long) Math.round(value));
        }
        return String.format(Locale.CHINA, "%.1f", value);
    }
}
