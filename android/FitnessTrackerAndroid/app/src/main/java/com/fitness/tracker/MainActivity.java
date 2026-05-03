package com.fitness.tracker;

import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.viewpager2.widget.ViewPager2;

import com.google.android.material.tabs.TabLayout;
import com.google.android.material.tabs.TabLayoutMediator;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class MainActivity extends AppCompatActivity {
    private static final String[] BODY_PARTS = {"胸", "背", "腿", "肩", "手臂", "核心", "有氧", "全身", "其他"};

    private WorkoutDatabase database;
    private ViewPager2 viewPager;
    private TabLayout tabLayout;

    private View entryView;
    private View dashboardView;
    private View prView;
    private View recentView;

    private AutoCompleteTextView exerciseInput;
    private Spinner bodyPartSpinner;
    private EditText timestampInput;
    private EditText weightInput;
    private EditText repsInput;
    private EditText setInput;
    private EditText notesInput;

    private LinearLayout metricsContainer;
    private TrendChartView trendChart;
    private BarChartView bodyChart;
    private LinearLayout prList;
    private LinearLayout recentList;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        database = new WorkoutDatabase(this);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#F5F7FB"));

        tabLayout = new TabLayout(this);
        tabLayout.setTabMode(TabLayout.MODE_SCROLLABLE);
        tabLayout.setTabGravity(TabLayout.GRAVITY_FILL);
        tabLayout.setBackgroundColor(Color.TRANSPARENT);
        tabLayout.setTabTextColors(Color.parseColor("#667085"), Color.WHITE);
        tabLayout.setSelectedTabIndicatorColor(Color.parseColor("#111827"));
        root.addView(tabLayout, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        viewPager = new ViewPager2(this);
        viewPager.setOffscreenPageLimit(3);
        root.addView(viewPager, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        setupPages();
        setupViewPager();
        new TabLayoutMediator(tabLayout, viewPager, (tab, position) -> {
            String[] titles = {"录入", "总览", "PR", "记录"};
            tab.setText(titles[position]);
        }).attach();

        refreshDashboard();
    }

    private void setupPages() {
        entryView = buildEntryPage();
        dashboardView = buildDashboardPage();
        prView = buildPrPage();
        recentView = buildRecentPage();
    }

    private void setupViewPager() {
        androidx.viewpager2.adapter.FragmentStateAdapter adapter = new androidx.viewpager2.adapter.FragmentStateAdapter(this) {
            @Override
            public int getItemCount() { return 4; }

            @Override
            public androidx.fragment.app.Fragment createFragment(int position) {
                View target;
                switch (position) {
                    case 0: target = entryView; break;
                    case 1: target = dashboardView; break;
                    case 2: target = prView; break;
                    case 3: target = recentView; break;
                    default: target = entryView;
                }
                return PageFragment.newInstance(position, target);
            }
        };
        viewPager.setAdapter(adapter);
    }

    private View buildEntryPage() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        LinearLayout card = cardLayout();
        scrollView.addView(card);

        card.addView(sectionTitle(card, "记录单组训练"));

        timestampInput = input(WorkoutDatabase.nowText(), "完成时间 yyyy-MM-dd HH:mm");
        card.addView(label("完成时间"));
        card.addView(timestampInput);

        List<String> exercises = database.recentExercises(80);
        if (exercises.isEmpty()) exercises.add("杠铃卧推");
        exerciseInput = new AutoCompleteTextView(this);
        ArrayAdapter<String> exerciseAdapter = new ArrayAdapter<>(this, android.R.layout.simple_dropdown_item_1line, exercises);
        exerciseInput.setAdapter(exerciseAdapter);
        exerciseInput.setHint("输入或选择动作");
        exerciseInput.setSingleLine(true);
        exerciseInput.setTextSize(15);
        exerciseInput.setTypeface(Typeface.DEFAULT_BOLD);
        exerciseInput.setPadding(dp(14), 0, dp(14), 0);
        exerciseInput.setMinimumHeight(dp(50));
        exerciseInput.setThreshold(1);
        GradientDrawable exBg = new GradientDrawable();
        exBg.setColor(Color.argb(235, 255, 255, 255));
        exBg.setCornerRadius(dp(16));
        exBg.setStroke(dp(1), Color.argb(28, 17, 24, 39));
        exerciseInput.setBackground(exBg);
        card.addView(label("动作名称"));
        card.addView(exerciseInput, fieldLayoutParams());

        bodyPartSpinner = new Spinner(this);
        bodyPartSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, BODY_PARTS));
        card.addView(label("部位"));
        card.addView(bodyPartSpinner, fieldLayoutParams());

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        weightInput = input("70", "kg");
        weightInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        repsInput = input("10", "次数");
        repsInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        setInput = input("1", "第几组");
        setInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        addMiniField(row, "重量", weightInput);
        addMiniField(row, "次数", repsInput);
        addMiniField(row, "组", setInput);
        card.addView(row);

        notesInput = input("", "可选，例如状态、RPE");
        card.addView(label("备注"));
        card.addView(notesInput);

        Button saveButton = new Button(this);
        saveButton.setText("保存这一组");
        saveButton.setTextColor(Color.WHITE);
        saveButton.setTypeface(Typeface.DEFAULT_BOLD);
        saveButton.setBackground(buttonBackground());
        LinearLayout.LayoutParams saveLp = matchWrapLayoutParams(dp(12), 0);
        saveLp.height = dp(52);
        card.addView(saveButton, saveLp);

        exerciseInput.setOnItemClickListener((parent, view, pos, id) -> applyLastValues());
        saveButton.setOnClickListener(v -> saveWorkout());

        return scrollView;
    }

    private View buildDashboardPage() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setPadding(dp(18), dp(12), dp(18), dp(32));
        scrollView.addView(container);

        metricsContainer = new LinearLayout(this);
        metricsContainer.setOrientation(LinearLayout.VERTICAL);
        container.addView(metricsContainer);
        container.addView(sectionTitle(container, "训练量趋势"));
        trendChart = new TrendChartView(this);
        container.addView(trendChart, fixedHeightLayoutParams(dp(250), dp(10)));
        container.addView(sectionTitle(container, "部位分布"));
        bodyChart = new BarChartView(this);
        container.addView(bodyChart, fixedHeightLayoutParams(dp(300), dp(12)));

        return scrollView;
    }

    private View buildPrPage() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        LinearLayout card = cardLayout();
        scrollView.addView(card);
        card.addView(sectionTitle(card, "个人记录 (PR)"));
        prList = new LinearLayout(this);
        prList.setOrientation(LinearLayout.VERTICAL);
        card.addView(prList);
        return scrollView;
    }

    private View buildRecentPage() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        LinearLayout card = cardLayout();
        scrollView.addView(card);
        card.addView(sectionTitle(card, "最近记录"));
        recentList = new LinearLayout(this);
        recentList.setOrientation(LinearLayout.VERTICAL);
        card.addView(recentList);
        return scrollView;
    }

    private void applyLastValues() {
        String exercise = currentExercise();
        WorkoutSet last = database.lastForExercise(exercise);
        if (last == null) { setInput.setText("1"); return; }
        weightInput.setText(trimNumber(last.weightKg));
        repsInput.setText(String.valueOf(last.reps));
        setInput.setText(String.valueOf(database.nextSetNumber(exercise, timestampInput.getText().toString())));
        setSpinnerValue(bodyPartSpinner, last.bodyPart);
    }

    private void saveWorkout() {
        try {
            String exercise = currentExercise();
            if (exercise.isEmpty()) { Toast.makeText(this, "动作不能为空", Toast.LENGTH_SHORT).show(); return; }
            String timestamp = timestampInput.getText().toString().trim();
            if (!WorkoutDatabase.isValidTimestamp(timestamp)) {
                Toast.makeText(this, "日期格式错误，请使用 yyyy-MM-dd HH:mm", Toast.LENGTH_SHORT).show();
                return;
            }
            double weight = Double.parseDouble(weightInput.getText().toString().trim());
            int reps = Integer.parseInt(repsInput.getText().toString().trim());
            int setNumber = Integer.parseInt(setInput.getText().toString().trim());
            String body = String.valueOf(bodyPartSpinner.getSelectedItem());
            database.insertSet(timestamp, body, exercise, weight, reps, setNumber, notesInput.getText().toString().trim());
            timestampInput.setText(WorkoutDatabase.nowText());
            setInput.setText(String.valueOf(database.nextSetNumber(exercise, timestampInput.getText().toString())));
            notesInput.setText("");
            refreshDashboard();
            Toast.makeText(this, "已记录：" + exercise + " " + trimNumber(weight) + "kg x " + reps, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "保存失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void refreshDashboard() {
        List<WorkoutSet> sets = database.allSets();
        metricsContainer.removeAllViews();
        metricsContainer.addView(sectionTitle(metricsContainer, "趋势总览"));

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
        metricsContainer.addView(metricCard("总组数", String.format(Locale.CHINA, "%,d", sets.size()), "全部历史训练"));
        metricsContainer.addView(metricCard("总训练量", String.format(Locale.CHINA, "%,.0f kg", volume), "重量 x 次数"));
        metricsContainer.addView(metricCard("训练天数", String.valueOf(days.size()), exercises.size() + " 个动作"));
        metricsContainer.addView(metricCard("最高估算 1RM", String.format(Locale.CHINA, "%.1f kg", maxOneRm), "Epley / Brzycki"));

        trendChart.setData(database.volumeByMonth(sets));
        bodyChart.setData(database.volumeByBodyPart(sets));

        prList.removeAllViews();
        List<WorkoutSet> prs = database.prRecords();
        Set<String> seen = new HashSet<>();
        for (WorkoutSet pr : prs) {
            if (seen.contains(pr.exerciseName)) continue;
            seen.add(pr.exerciseName);
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setPadding(dp(12), dp(10), dp(12), dp(10));
            GradientDrawable rowBg = new GradientDrawable();
            rowBg.setColor(Color.WHITE);
            rowBg.setCornerRadius(dp(16));
            rowBg.setStroke(dp(1), Color.argb(18, 17, 24, 39));
            row.setBackground(rowBg);
            LinearLayout.LayoutParams rowLp = matchWrapLayoutParams(0, dp(6));
            row.setLayoutParams(rowLp);

            TextView nameView = textView(pr.exerciseName, 15, Color.parseColor("#111827"), Typeface.BOLD);
            LinearLayout.LayoutParams nameLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 2f);
            row.addView(nameView, nameLp);

            TextView detailView = textView(trimNumber(pr.weightKg) + "kg x " + pr.reps + "  1RM " + String.format(Locale.CHINA, "%.1f", pr.estimatedOneRepMax()) + "kg", 13, Color.parseColor("#667085"), Typeface.NORMAL);
            LinearLayout.LayoutParams detailLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 2f);
            row.addView(detailView, detailLp);

            prList.addView(row);
        }
        if (prs.isEmpty()) {
            prList.addView(textView("暂无 PR 数据", 14, Color.parseColor("#667085"), Typeface.NORMAL));
        }

        recentList.removeAllViews();
        List<WorkoutSet> recent = database.recentSets(30);
        for (WorkoutSet s : recent) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setPadding(dp(10), dp(8), dp(10), dp(8));
            GradientDrawable rowBg2 = new GradientDrawable();
            rowBg2.setColor(Color.WHITE);
            rowBg2.setCornerRadius(dp(16));
            rowBg2.setStroke(dp(1), Color.argb(18, 17, 24, 39));
            row.setBackground(rowBg2);
            LinearLayout.LayoutParams rowLp2 = matchWrapLayoutParams(0, dp(4));
            row.setLayoutParams(rowLp2);

            TextView infoView = textView(s.completedAt.substring(0, Math.min(16, s.completedAt.length())) + " " + s.exerciseName + " " + trimNumber(s.weightKg) + "kg x " + s.reps, 13, Color.parseColor("#111827"), Typeface.NORMAL);
            LinearLayout.LayoutParams infoLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 3f);
            row.addView(infoView, infoLp);

            Button deleteBtn = new Button(this);
            deleteBtn.setText("删除");
            deleteBtn.setTextSize(12);
            deleteBtn.setTextColor(Color.parseColor("#FF453A"));
            deleteBtn.setBackgroundColor(Color.TRANSPARENT);
            deleteBtn.setPadding(dp(8), 0, dp(8), 0);
            deleteBtn.setMinimumHeight(dp(32));
            long setId = s.id;
            deleteBtn.setOnClickListener(v -> confirmDelete(setId));
            LinearLayout.LayoutParams delLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, 0f);
            row.addView(deleteBtn, delLp);

            Button editBtn = new Button(this);
            editBtn.setText("编辑");
            editBtn.setTextSize(12);
            editBtn.setTextColor(Color.parseColor("#007AFF"));
            editBtn.setBackgroundColor(Color.TRANSPARENT);
            editBtn.setPadding(dp(8), 0, dp(8), 0);
            editBtn.setMinimumHeight(dp(32));
            editBtn.setOnClickListener(v -> showEditDialog(setId));
            LinearLayout.LayoutParams editLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, 0f);
            row.addView(editBtn, editLp);

            recentList.addView(row);
        }
        if (recent.isEmpty()) {
            recentList.addView(textView("暂无记录", 14, Color.parseColor("#667085"), Typeface.NORMAL));
        }
    }

    private void confirmDelete(long id) {
        new AlertDialog.Builder(this)
                .setTitle("确认删除")
                .setMessage("确定要删除这条记录吗？")
                .setPositiveButton("删除", (d, w) -> {
                    database.deleteSet(id);
                    refreshDashboard();
                    Toast.makeText(this, "已删除", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void showEditDialog(long id) {
        WorkoutSet s = database.getById(id);
        if (s == null) return;

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(24), dp(16), dp(24), dp(8));

        EditText weightEdit = new EditText(this);
        weightEdit.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        weightEdit.setText(trimNumber(s.weightKg));
        layout.addView(textView("重量 (kg)", 12, Color.parseColor("#667085"), Typeface.BOLD));
        layout.addView(weightEdit);

        EditText repsEdit = new EditText(this);
        repsEdit.setInputType(InputType.TYPE_CLASS_NUMBER);
        repsEdit.setText(String.valueOf(s.reps));
        layout.addView(textView("次数", 12, Color.parseColor("#667085"), Typeface.BOLD));
        layout.addView(repsEdit);

        EditText setEdit = new EditText(this);
        setEdit.setInputType(InputType.TYPE_CLASS_NUMBER);
        setEdit.setText(String.valueOf(s.setNumber));
        layout.addView(textView("第几组", 12, Color.parseColor("#667085"), Typeface.BOLD));
        layout.addView(setEdit);

        new AlertDialog.Builder(this)
                .setTitle("编辑记录 #" + id)
                .setView(layout)
                .setPositiveButton("保存", (d, w) -> {
                    try {
                        double w2 = Double.parseDouble(weightEdit.getText().toString().trim());
                        int r2 = Integer.parseInt(repsEdit.getText().toString().trim());
                        int sn2 = Integer.parseInt(setEdit.getText().toString().trim());
                        database.updateSet(id, s.bodyPart, s.exerciseName, w2, r2, sn2, s.notes);
                        refreshDashboard();
                        Toast.makeText(this, "已更新", Toast.LENGTH_SHORT).show();
                    } catch (Exception ex) {
                        Toast.makeText(this, "更新失败：" + ex.getMessage(), Toast.LENGTH_LONG).show();
                    }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private String currentExercise() {
        return exerciseInput.getText().toString().trim();
    }

    private LinearLayout cardLayout() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(18), dp(18), dp(32));
        card.setBackgroundColor(Color.parseColor("#F5F7FB"));
        return card;
    }

    private TextView sectionTitle(View parent, String value) {
        TextView title = textView(value, 20, Color.parseColor("#111827"), Typeface.BOLD);
        title.setPadding(0, dp(14), 0, dp(10));
        return title;
    }

    private View metricCard(String label, String value, String detail) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(16), dp(18), dp(16));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(22));
        bg.setStroke(dp(1), Color.argb(18, 17, 24, 39));
        card.setBackground(bg);
        card.addView(textView(label, 12, Color.parseColor("#667085"), Typeface.BOLD));
        card.addView(textView(value, 28, Color.parseColor("#111827"), Typeface.BOLD));
        card.addView(textView(detail, 12, Color.parseColor("#667085"), Typeface.NORMAL));
        LinearLayout.LayoutParams lp = matchWrapLayoutParams(0, dp(10));
        card.setLayoutParams(lp);
        return card;
    }

    private TextView label(String value) {
        return textView(value, 12, Color.parseColor("#667085"), Typeface.BOLD);
    }

    private EditText input(String value, String hint) {
        EditText et = new EditText(this);
        et.setText(value);
        et.setHint(hint);
        et.setSingleLine(true);
        et.setTextSize(15);
        et.setTypeface(Typeface.DEFAULT_BOLD);
        et.setPadding(dp(14), 0, dp(14), 0);
        et.setMinimumHeight(dp(50));
        et.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.argb(235, 255, 255, 255));
        bg.setCornerRadius(dp(16));
        bg.setStroke(dp(1), Color.argb(28, 17, 24, 39));
        et.setBackground(bg);
        return et;
    }

    private void addMiniField(LinearLayout row, String label, EditText input) {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.addView(textView(label, 12, Color.parseColor("#667085"), Typeface.BOLD));
        col.addView(input);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        lp.rightMargin = dp(8);
        row.addView(col, lp);
    }

    private TextView textView(String value, int sp, int color, int style) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(sp);
        v.setTextColor(color);
        v.setTypeface(Typeface.DEFAULT, style);
        return v;
    }

    private GradientDrawable buttonBackground() {
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{Color.rgb(17, 24, 39), Color.rgb(48, 56, 70)});
        bg.setCornerRadius(dp(999));
        return bg;
    }

    private LinearLayout.LayoutParams fieldLayoutParams() {
        LinearLayout.LayoutParams lp = matchWrapLayoutParams(0, dp(4));
        lp.height = dp(50);
        return lp;
    }

    private LinearLayout.LayoutParams fixedHeightLayoutParams(int height, int bottomMargin) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height);
        lp.bottomMargin = bottomMargin;
        return lp;
    }

    private LinearLayout.LayoutParams matchWrapLayoutParams(int top, int bottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = top;
        lp.bottomMargin = bottom;
        return lp;
    }

    private void setSpinnerValue(Spinner spinner, String value) {
        for (int i = 0; i < spinner.getCount(); i++) {
            if (String.valueOf(spinner.getItemAtPosition(i)).equals(value)) {
                spinner.setSelection(i);
                return;
            }
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private String trimNumber(double value) {
        if (Math.abs(value - Math.round(value)) < 0.00001) {
            return String.valueOf((long) Math.round(value));
        }
        return String.format(Locale.CHINA, "%.1f", value);
    }

    public static class PageFragment extends androidx.fragment.app.Fragment {
        private static final String ARG_POSITION = "position";
        private View pageView;

        static PageFragment newInstance(int position, View view) {
            PageFragment fragment = new PageFragment();
            fragment.pageView = view;
            Bundle args = new Bundle();
            args.putInt(ARG_POSITION, position);
            fragment.setArguments(args);
            return fragment;
        }

        @Override
        public View onCreateView(android.view.LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
            return pageView;
        }
    }
}