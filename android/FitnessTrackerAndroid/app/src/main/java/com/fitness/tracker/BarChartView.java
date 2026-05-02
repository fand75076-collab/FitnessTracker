package com.fitness.tracker;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class BarChartView extends View {
    private static final class Item {
        final String label;
        final double value;

        Item(String label, double value) {
            this.label = label;
            this.value = value;
        }
    }

    private final Paint barPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF barRect = new RectF();
    private final List<Item> items = new ArrayList<>();

    public BarChartView(Context context) {
        super(context);
        init();
    }

    public BarChartView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        barPaint.setColor(Color.rgb(48, 209, 88));
        textPaint.setColor(Color.rgb(102, 112, 133));
        textPaint.setTextSize(28);
    }

    void setData(Map<String, Double> data) {
        items.clear();
        for (Map.Entry<String, Double> entry : data.entrySet()) {
            items.add(new Item(entry.getKey(), entry.getValue()));
        }
        items.sort(Comparator.comparingDouble((Item item) -> item.value).reversed());
        while (items.size() > 7) {
            items.remove(items.size() - 1);
        }
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (items.isEmpty()) {
            canvas.drawText("暂无部位分布", 32, getHeight() / 2f, textPaint);
            return;
        }
        double max = 0;
        for (Item item : items) {
            max = Math.max(max, item.value);
        }
        int rowHeight = Math.max(58, getHeight() / Math.max(1, items.size()));
        int labelWidth = 116;
        int right = getWidth() - 32;
        for (int i = 0; i < items.size(); i++) {
            Item item = items.get(i);
            float y = 28 + i * rowHeight;
            float barWidth = (float) ((right - labelWidth) * (item.value / max));
            textPaint.setColor(Color.rgb(17, 24, 39));
            canvas.drawText(item.label, 24, y + 34, textPaint);
            barPaint.setColor(colorFor(i));
            barRect.set(labelWidth, y, labelWidth + barWidth, y + 32);
            canvas.drawRoundRect(barRect, 18, 18, barPaint);
        }
    }

    private int colorFor(int index) {
        int[] colors = {
                Color.rgb(0, 122, 255),
                Color.rgb(48, 209, 88),
                Color.rgb(255, 159, 10),
                Color.rgb(100, 210, 255),
                Color.rgb(191, 90, 242),
                Color.rgb(255, 69, 58),
                Color.rgb(142, 142, 147)
        };
        return colors[index % colors.length];
    }
}
