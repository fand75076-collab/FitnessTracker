package com.fitness.tracker;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.util.AttributeSet;
import android.view.View;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class TrendChartView extends View {
    private final Paint axisPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint linePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path linePath = new Path();
    private final Path fillPath = new Path();
    private final List<String> labels = new ArrayList<>();
    private final List<Double> values = new ArrayList<>();

    public TrendChartView(Context context) {
        super(context);
        init();
    }

    public TrendChartView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        axisPaint.setColor(Color.argb(36, 17, 24, 39));
        axisPaint.setStrokeWidth(2);
        linePaint.setColor(Color.rgb(0, 122, 255));
        linePaint.setStrokeWidth(7);
        linePaint.setStyle(Paint.Style.STROKE);
        linePaint.setStrokeCap(Paint.Cap.ROUND);
        linePaint.setStrokeJoin(Paint.Join.ROUND);
        fillPaint.setColor(Color.argb(38, 0, 122, 255));
        fillPaint.setStyle(Paint.Style.FILL);
        textPaint.setColor(Color.rgb(102, 112, 133));
        textPaint.setTextSize(28);
    }

    void setData(Map<String, Double> data) {
        labels.clear();
        values.clear();
        for (Map.Entry<String, Double> entry : data.entrySet()) {
            labels.add(entry.getKey());
            values.add(entry.getValue());
        }
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int width = getWidth();
        int height = getHeight();
        int left = 42;
        int right = width - 24;
        int top = 28;
        int bottom = height - 46;

        canvas.drawLine(left, bottom, right, bottom, axisPaint);
        if (values.size() < 2) {
            canvas.drawText("训练量趋势会在有足够记录后显示", left, height / 2f, textPaint);
            return;
        }

        double max = 0;
        for (Double value : values) {
            max = Math.max(max, value);
        }
        if (max <= 0) {
            return;
        }

        linePath.reset();
        fillPath.reset();
        for (int i = 0; i < values.size(); i++) {
            float x = left + (right - left) * (i / (float) (values.size() - 1));
            float y = bottom - (float) ((values.get(i) / max) * (bottom - top));
            if (i == 0) {
                linePath.moveTo(x, y);
                fillPath.moveTo(x, bottom);
                fillPath.lineTo(x, y);
            } else {
                linePath.lineTo(x, y);
                fillPath.lineTo(x, y);
            }
        }
        fillPath.lineTo(right, bottom);
        fillPath.close();
        canvas.drawPath(fillPath, fillPaint);
        canvas.drawPath(linePath, linePaint);

        canvas.drawText(labels.get(0), left, height - 10, textPaint);
        String last = labels.get(labels.size() - 1);
        canvas.drawText(last, right - textPaint.measureText(last), height - 10, textPaint);
    }
}
