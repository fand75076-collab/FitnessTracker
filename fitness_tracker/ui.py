from __future__ import annotations

from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


APPLE_BLUE = "#007AFF"
APPLE_GREEN = "#30D158"
APPLE_ORANGE = "#FF9F0A"
APPLE_RED = "#FF453A"
INK = "#111827"
MUTED = "#667085"
GRID = "rgba(17, 24, 39, 0.08)"
CHART_THEME = "light"
CHART_TOKENS = {
    "light": {
        "ink": INK,
        "muted": MUTED,
        "grid": GRID,
        "tick": "rgba(17, 24, 39, 0.12)",
        "neutral": "#D0D5DD",
    },
    "dark": {
        "ink": "#e5e7eb",
        "muted": "#9ca3af",
        "grid": "rgba(255, 255, 255, 0.08)",
        "tick": "rgba(255, 255, 255, 0.14)",
        "neutral": "rgba(148, 163, 184, 0.54)",
    },
}


_STATIC_DIR = Path(__file__).resolve().with_name("static")


def apply_apple_design(theme: str = "light") -> None:
    global CHART_THEME

    normalized_theme = theme if theme in CHART_TOKENS else "light"
    CHART_THEME = normalized_theme
    css_path = _STATIC_DIR / f"theme_{normalized_theme}.css"
    if not css_path.exists():
        css_path = _STATIC_DIR / "theme_light.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hero(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        range_text = "等待第一组训练"
        set_text = "0 组"
        exercise_text = "0 个动作"
    else:
        range_text = (
            f"{dataframe['completed_at'].min().strftime('%Y.%m.%d')} - "
            f"{dataframe['completed_at'].max().strftime('%Y.%m.%d')}"
        )
        set_text = f"{len(dataframe):,} 组"
        exercise_text = f"{dataframe['exercise_name'].nunique()} 个动作"

    st.markdown(
        f"""
        <section class="ft-hero">
          <div class="ft-eyebrow">Personal Training Intelligence</div>
          <div class="ft-hero-title">健身趋势<br/>实时计算</div>
          <p class="ft-hero-subtitle">
            每一组训练都会进入同一条时间线。系统自动合并动作错字、计算训练量、PR、最大重量提升，并用更清晰的图形呈现长期趋势。
          </p>
          <div class="ft-hero-meta">
            <span class="ft-pill">数据范围 {escape(range_text)}</span>
            <span class="ft-pill">{escape(set_text)}</span>
            <span class="ft-pill">{escape(exercise_text)}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, detail: str = "", tone: str = "blue") -> None:
    st.markdown(
        f"""
        <div class="ft-card">
            <div class="ft-card-label">{escape(label)}</div>
            <div class="ft-card-value">{escape(value)}</div>
            <div class="ft-card-delta {escape(tone)}">{escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, copy: str = "") -> None:
    if copy:
        st.markdown(
            f"""
            <div class="ft-section-title">{escape(title)}</div>
            <p class="ft-section-copy">{escape(copy)}</p>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="ft-section-title">{escape(title)}</div>', unsafe_allow_html=True)


def render_display_table(dataframe: pd.DataFrame, max_rows: int | None = None) -> None:
    if dataframe.empty:
        st.info("暂无数据。")
        return

    table_df = dataframe.head(max_rows).copy() if max_rows else dataframe.copy()
    headers = "".join(f"<th>{escape(str(column))}</th>" for column in table_df.columns)
    rows = []
    for _, row in table_df.iterrows():
        cells = "".join(f"<td>{escape(_format_table_value(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")

    st.markdown(
        f"""
        <div class="ft-table-shell">
            <table class="ft-table">
                <thead><tr>{headers}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _format_table_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, float):
        return f"{value:,.1f}" if abs(value - round(value)) > 0.00001 else f"{value:,.0f}"
    return str(value)


def apple_chart(chart: alt.Chart) -> alt.Chart:
    tokens = CHART_TOKENS.get(CHART_THEME, CHART_TOKENS["light"])
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            domain=False,
            gridColor=tokens["grid"],
            labelColor=tokens["muted"],
            labelFont="-apple-system, BlinkMacSystemFont, Segoe UI",
            titleColor=tokens["muted"],
            titleFont="-apple-system, BlinkMacSystemFont, Segoe UI",
            titleFontWeight=600,
            tickColor=tokens["tick"],
        )
        .configure_legend(
            orient="bottom",
            labelColor=tokens["ink"],
            title=None,
            labelFont="-apple-system, BlinkMacSystemFont, Segoe UI",
            symbolSize=90,
        )
        .properties(background="rgba(0,0,0,0)")
    )


def volume_area_chart(dataframe: pd.DataFrame) -> alt.Chart:
    base = alt.Chart(dataframe).encode(
        x=alt.X("period:T", title=None),
        y=alt.Y("volume_kg:Q", title="训练量 kg"),
        tooltip=[
            alt.Tooltip("period:T", title="周期", format="%Y-%m-%d"),
            alt.Tooltip("volume_kg:Q", title="训练量", format=",.0f"),
            alt.Tooltip("sets:Q", title="组数", format=",.0f"),
        ],
    )
    area = base.mark_area(
        interpolate="monotone",
        opacity=0.18,
        color=APPLE_BLUE,
        line=False,
    )
    line = base.mark_line(interpolate="monotone", strokeWidth=3.5, color=APPLE_BLUE)
    points = base.mark_circle(size=54, color=APPLE_BLUE, opacity=0.82)
    return apple_chart((area + line + points).properties(height=320))


def body_part_bar_chart(dataframe: pd.DataFrame) -> alt.Chart:
    data = dataframe.copy()
    return apple_chart(
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=10, cornerRadiusBottomRight=10, height=24)
        .encode(
            y=alt.Y("body_part:N", title=None, sort="-x"),
            x=alt.X("volume_kg:Q", title="训练量 kg"),
            color=alt.Color(
                "body_part:N",
                legend=None,
                scale=alt.Scale(
                    range=["#007AFF", "#30D158", "#FF9F0A", "#64D2FF", "#BF5AF2", "#FF453A", "#8E8E93"],
                ),
            ),
            tooltip=[
                alt.Tooltip("body_part:N", title="部位"),
                alt.Tooltip("volume_kg:Q", title="训练量", format=",.0f"),
                alt.Tooltip("sets:Q", title="组数", format=",.0f"),
            ],
        )
        .properties(height=320)
    )


def exercise_trend_chart(dataframe: pd.DataFrame) -> alt.Chart:
    if dataframe.empty:
        return apple_chart(alt.Chart(pd.DataFrame({"period": [], "value": [], "metric": []})).mark_line())

    chart_df = dataframe.rename(
        columns={
            "best_weight_kg": "最大重量",
            "best_estimated_1rm": "估算 1RM",
            "total_volume_kg": "总训练量",
        }
    ).melt(
        id_vars=["period"],
        value_vars=["最大重量", "估算 1RM", "总训练量"],
        var_name="metric",
        value_name="value",
    )
    return apple_chart(
        alt.Chart(chart_df)
        .mark_line(interpolate="monotone", strokeWidth=3.2, point=alt.OverlayMarkDef(size=55, filled=True))
        .encode(
            x=alt.X("period:T", title=None),
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "metric:N",
                scale=alt.Scale(range=[APPLE_BLUE, APPLE_GREEN, APPLE_ORANGE]),
            ),
            tooltip=[
                alt.Tooltip("period:T", title="周期", format="%Y-%m-%d"),
                alt.Tooltip("metric:N", title="指标"),
                alt.Tooltip("value:Q", title="数值", format=",.1f"),
            ],
        )
        .properties(height=340)
    )


def progress_bar_chart(dataframe: pd.DataFrame) -> alt.Chart:
    data = dataframe.copy()
    if data.empty:
        data = pd.DataFrame(columns=["exercise_name", "weight_change_pct", "weight_change_kg"])
    tokens = CHART_TOKENS.get(CHART_THEME, CHART_TOKENS["light"])

    return apple_chart(
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10)
        .encode(
            x=alt.X("exercise_name:N", title=None, sort="-y", axis=alt.Axis(labelAngle=-25)),
            y=alt.Y("weight_change_pct:Q", title="提升百分比 %"),
            color=alt.condition(
                alt.datum.weight_change_pct > 0,
                alt.value(APPLE_GREEN),
                alt.value(tokens["neutral"]),
            ),
            tooltip=[
                alt.Tooltip("exercise_name:N", title="动作"),
                alt.Tooltip("weight_change_pct:Q", title="提升百分比", format=".1f"),
                alt.Tooltip("weight_change_kg:Q", title="提升重量", format=".1f"),
                alt.Tooltip("sets:Q", title="组数", format=",.0f"),
            ],
        )
        .properties(height=310)
    )


def science_volume_chart(dataframe: pd.DataFrame) -> alt.Chart:
    data = dataframe.copy()
    if data.empty:
        data = pd.DataFrame(columns=["body_part", "avg_sets_per_week", "status"])

    bars = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=10, cornerRadiusBottomRight=10, height=24)
        .encode(
            y=alt.Y("body_part:N", title=None, sort=None),
            x=alt.X("avg_sets_per_week:Q", title="平均每周组数"),
            color=alt.Color(
                "status:N",
                legend=None,
                scale=alt.Scale(
                    domain=["增肌量充足", "中等刺激", "健康底线", "刺激不足", "近28天缺失"],
                    range=[APPLE_GREEN, APPLE_BLUE, APPLE_ORANGE, APPLE_RED, "#8E8E93"],
                ),
            ),
            tooltip=[
                alt.Tooltip("body_part:N", title="部位"),
                alt.Tooltip("avg_sets_per_week:Q", title="平均每周组数", format=".1f"),
                alt.Tooltip("training_days:Q", title="训练天数", format=",.0f"),
                alt.Tooltip("rep_8_12_pct:Q", title="8-12次占比", format=".1f"),
                alt.Tooltip("status:N", title="状态"),
            ],
        )
    )
    target = alt.Chart(pd.DataFrame({"x": [10]})).mark_rule(
        color=APPLE_ORANGE,
        strokeDash=[6, 5],
        strokeWidth=2,
    ).encode(x="x:Q")
    return apple_chart((bars + target).properties(height=320))


def rep_zone_chart(dataframe: pd.DataFrame) -> alt.Chart:
    data = dataframe.copy()
    if data.empty:
        data = pd.DataFrame(columns=["rep_zone", "sets", "pct"])

    return apple_chart(
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10)
        .encode(
            x=alt.X("rep_zone:N", title=None, sort=None, axis=alt.Axis(labelAngle=-18)),
            y=alt.Y("sets:Q", title="组数"),
            color=alt.Color(
                "rep_zone:N",
                legend=None,
                scale=alt.Scale(range=[APPLE_BLUE, "#64D2FF", APPLE_GREEN, APPLE_ORANGE, "#8E8E93"]),
            ),
            tooltip=[
                alt.Tooltip("rep_zone:N", title="次数区间"),
                alt.Tooltip("sets:Q", title="组数", format=",.0f"),
                alt.Tooltip("pct:Q", title="占比", format=".1f"),
            ],
        )
        .properties(height=280)
    )
