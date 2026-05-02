package com.fitness.tracker;

final class WorkoutSet {
    final long id;
    final String completedAt;
    final String bodyPart;
    final String exerciseName;
    final double weightKg;
    final int reps;
    final int setNumber;
    final String notes;

    WorkoutSet(
            long id,
            String completedAt,
            String bodyPart,
            String exerciseName,
            double weightKg,
            int reps,
            int setNumber,
            String notes
    ) {
        this.id = id;
        this.completedAt = completedAt;
        this.bodyPart = bodyPart;
        this.exerciseName = exerciseName;
        this.weightKg = weightKg;
        this.reps = reps;
        this.setNumber = setNumber;
        this.notes = notes == null ? "" : notes;
    }

    double volumeKg() {
        return weightKg * reps;
    }

    double estimatedOneRepMax() {
        if (reps <= 0 || weightKg <= 0) {
            return 0;
        }
        if (reps == 1) {
            return weightKg;
        }
        double epley = weightKg * (1 + reps / 30.0);
        double brzycki = weightKg * (36.0 / (37.0 - reps));
        double value = reps <= 10 ? Math.min(epley, brzycki) : epley;
        return Math.round(value * 10.0) / 10.0;
    }
}
