from __future__ import annotations

from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from fitness_tracker.analytics import (
    aggregate_body_part,
    aggregate_volume,
    build_body_part_science_table,
    build_exercise_trend,
    build_max_weight_progress,
    build_progression_candidates,
    build_pr_records,
    build_recovery_alerts,
    build_rep_zone_distribution,
    build_science_summary,
    build_session_summary,
    build_summary_metrics,
    summarize_latest_max_weight_progress,
)
from fitness_tracker.db import (
    ValidationError,
    add_workout_set,
    delete_workout_set,
    export_to_csv,
    get_exercise_last_values,
    get_recent_exercises,
    initialize_db,
    load_import_summary,
    load_imported_sets,
    load_workout_sets,
    update_workout_set,
)
from fitness_tracker.ui import (
    apply_apple_design,
    body_part_bar_chart,
    exercise_trend_chart,
    progress_bar_chart,
    rep_zone_chart,
    render_display_table,
    render_hero,
    render_metric_card,
    render_section,
    science_volume_chart,
    volume_area_chart,
)

BODY_PARTS = ["胸", "背", "腿", "肩", "手臂", "核心", "有氧", "全身", "其他"]
GRAIN_OPTIONS = {"天": "day", "周": "week", "月": "month"}
SESSION_GAP_MINUTES = 90


def combine_timestamp(input_date, input_time: time) -> datetime:
    return datetime.combine(input_date, input_time)


def format_progress_metric(summary: dict[str, object]) -> tuple[str, str | None, str]:
    if summary["weight_change_pct"] is None:
        return "暂无", None, "本周期暂无超过上一周期的动作"

    value = f"{summary['weight_change_pct']:.1f}%"
    delta = f"{summary['exercise_name']} +{summary['weight_change_kg']:.1f}kg"
    period = summary["period"]
    period_text = period.strftime("%Y-%m-%d") if hasattr(period, "strftime") else "最近周期"
    help_text = f"{period_text} 提升动作数：{summary['improved_exercises']}"
    return value, delta, help_text


def render_weight_progress_panel(progress: pd.DataFrame) -> None:
    valid = progress[progress["weight_change_pct"].notna()].copy()
    if valid.empty:
        st.info("至少需要同一动作跨两个周期都有记录，才能计算最大重量提升百分比。")
        return

    latest_period = valid["period"].max()
    latest = (
        valid[valid["period"] == latest_period]
        .sort_values(["weight_change_pct", "weight_change_kg"], ascending=[False, False])
        .head(12)
        .copy()
    )
    st.altair_chart(progress_bar_chart(latest), use_container_width=True)

    latest["周期"] = latest["period"].dt.strftime("%Y-%m-%d")
    latest_display = latest.rename(
        columns={
            "exercise_name": "动作",
            "best_weight_kg": "本周期最大重量(kg)",
            "previous_best_weight_kg": "上一周期最大重量(kg)",
            "weight_change_kg": "提升(kg)",
            "weight_change_pct": "提升百分比(%)",
            "sets": "组数",
        }
    )
    latest_display["提升百分比(%)"] = latest_display["提升百分比(%)"].round(1)
    latest_display["提升(kg)"] = latest_display["提升(kg)"].round(1)
    render_display_table(
        latest_display[
            ["周期", "动作", "本周期最大重量(kg)", "上一周期最大重量(kg)", "提升(kg)", "提升百分比(%)", "组数"]
        ]
    )


def render_science_rules_panel(dataframe: pd.DataFrame) -> None:
    render_section(
        "科学规则诊断",
        "把 ACSM/HHS 的通用训练原则转成可计算指标：频率、部位周组数、次数区间、恢复间隔和渐进加重候选。",
    )
    if dataframe.empty:
        st.info("暂无训练记录，科学诊断会在录入数据后生成。")
        return

    summary = build_science_summary(dataframe)
    body_table = build_body_part_science_table(dataframe)
    rep_distribution = build_rep_zone_distribution(dataframe)
    recovery_alerts = build_recovery_alerts(dataframe).head(8)
    candidates = build_progression_candidates(dataframe).head(10)

    reference_date = summary.get("reference_date")
    reference_text = reference_date.strftime("%Y-%m-%d") if hasattr(reference_date, "strftime") else "最近记录"
    ratio = summary.get("acute_volume_ratio")
    ratio_text = "缺少前期基线" if ratio is None else f"近7天/前4周均值 {ratio}x"

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        render_metric_card(
            "近7天力量频率",
            f"{summary['strength_days_7d']} 天",
            f"HHS底线：每周2天；{summary['frequency_status']}",
            "good" if summary["strength_days_7d"] >= 2 else "hot",
        )
    with col2:
        render_metric_card(
            "近28天覆盖",
            f"{summary['active_body_parts_28d']}/6",
            str(summary["coverage_status"]),
            "blue",
        )
    with col3:
        render_metric_card(
            "8-12次占比",
            f"{summary['rep_8_12_pct']:.1f}%",
            "ACSM常用综合区间",
            "good",
        )
    with col4:
        render_metric_card(
            "负荷变化",
            str(summary["load_status"]),
            ratio_text,
            "hot" if summary["load_status"] == "负荷跳升" else "blue",
        )
    with col5:
        render_metric_card(
            "恢复提示",
            f"{summary['recovery_alerts']}",
            "同部位<48小时次数",
            "hot" if summary["recovery_alerts"] else "good",
        )

    st.caption(f"诊断基准日：{reference_text}。这些规则用于训练趋势提示，不替代医疗或康复建议。")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.caption("近28天各部位平均每周组数（橙色虚线为10组参考线）")
        st.altair_chart(science_volume_chart(body_table), use_container_width=True)
    with chart_right:
        st.caption("近28天次数区间分布")
        st.altair_chart(rep_zone_chart(rep_distribution), use_container_width=True)

    body_display = body_table.rename(
        columns={
            "body_part": "部位",
            "sets": "近28天组数",
            "avg_sets_per_week": "平均每周组数",
            "training_days": "训练天数",
            "volume_kg": "训练量(kg)",
            "avg_reps": "平均次数",
            "rep_8_12_pct": "8-12次占比(%)",
            "days_since_last": "距上次训练(天)",
            "status": "状态",
            "recommendation": "建议",
        }
    )
    render_display_table(
        body_display[
            [
                "部位",
                "近28天组数",
                "平均每周组数",
                "训练天数",
                "训练量(kg)",
                "平均次数",
                "8-12次占比(%)",
                "距上次训练(天)",
                "状态",
                "建议",
            ]
        ]
    )

    lower, upper = st.columns(2)
    with lower:
        st.caption("可考虑加重的动作（连续两次训练平均次数达到12+）")
        if candidates.empty:
            st.info("当前没有明确的加重候选。优先保持动作质量和稳定记录。")
        else:
            candidate_display = candidates.rename(
                columns={
                    "exercise_name": "动作",
                    "latest_session": "最近训练",
                    "latest_weight_kg": "当前重量(kg)",
                    "latest_avg_reps": "最近均次",
                    "previous_avg_reps": "前次均次",
                    "suggested_low_kg": "2%参考(kg)",
                    "suggested_high_kg": "10%上限(kg)",
                    "reason": "依据",
                }
            )
            render_display_table(candidate_display)
    with upper:
        st.caption("恢复间隔提示（同一部位两次训练间隔小于48小时）")
        if recovery_alerts.empty:
            st.success("近似 session 口径下没有发现同部位 <48 小时的恢复间隔提示。")
        else:
            recovery_display = recovery_alerts.rename(
                columns={
                    "body_part": "部位",
                    "previous_session": "前次训练",
                    "current_session": "本次训练",
                    "hours_between": "间隔(小时)",
                    "sets": "本次组数",
                }
            )
            render_display_table(recovery_display)

    st.caption(
        "规则来源：HHS/CDC 成人肌力训练频率建议、ACSM 阻力训练进阶模型、Schoenfeld 等周训练量剂量-反应研究。"
    )


def render_entry_form() -> None:
    st.subheader("记录单组训练")
    recent_exercises = get_recent_exercises(50)
    exercise_names = list(dict.fromkeys(r["exercise_name"] for r in recent_exercises))
    exercise_body_part_map = {r["exercise_name"]: r["body_part"] for r in recent_exercises}

    quick_mode = st.toggle("快捷模式", value=True, help="开启后可从最近动作中快速选择")

    with st.form("entry_form", clear_on_submit=False):
        last_vals = None
        now = datetime.now()
        left, right = st.columns(2)
        selected_date = left.date_input("训练日期", value=now.date())
        selected_time = right.time_input("训练时间", value=now.time().replace(second=0, microsecond=0))
        selected_timestamp = combine_timestamp(selected_date, selected_time).isoformat(sep=" ", timespec="minutes")

        if quick_mode and exercise_names:
            exercise_name_value = st.selectbox(
                "动作名称",
                options=[""] + exercise_names,
                index=0,
                help="从最近使用的动作中选择，或切换手动模式自由输入",
            )
            if exercise_name_value and exercise_name_value in exercise_body_part_map:
                default_body_part = exercise_body_part_map[exercise_name_value]
                default_index = BODY_PARTS.index(default_body_part) if default_body_part in BODY_PARTS else 0
                body_part_value = st.selectbox("部位", BODY_PARTS, index=default_index)
            else:
                body_part_value = st.selectbox("部位", BODY_PARTS, index=0)

            last_vals = get_exercise_last_values(exercise_name_value, selected_timestamp) if exercise_name_value else None
            weight_value = st.number_input(
                "重量 (kg)",
                min_value=0.0,
                step=2.5,
                value=float(last_vals["weight_kg"]) if last_vals else 70.0,
            )
            reps_value = st.number_input(
                "次数",
                min_value=1,
                step=1,
                value=int(last_vals["reps"]) if last_vals else 10,
            )
            if last_vals:
                auto_set_number = int(last_vals.get("next_set_number", 1))
                set_number_value = st.number_input("第几组", min_value=1, step=1, value=auto_set_number)
            else:
                set_number_value = st.number_input("第几组", min_value=1, step=1, value=1)
        else:
            body_part, exercise_name = st.columns([1, 2])
            body_part_value = body_part.selectbox("部位", BODY_PARTS, index=0)
            exercise_name_value = exercise_name.text_input("动作名称", placeholder="例如：杠铃卧推")

            weight_col, reps_col, set_col = st.columns(3)
            weight_value = weight_col.number_input("重量 (kg)", min_value=0.0, step=2.5, value=70.0)
            reps_value = reps_col.number_input("次数", min_value=1, step=1, value=10)
            set_number_value = set_col.number_input("第几组", min_value=1, step=1, value=1)

        notes_value = st.text_input("备注", placeholder="可选，例如状态、RPE、器械变化")
        submitted = st.form_submit_button("保存这一组", use_container_width=True)

    if submitted:
        if not exercise_name_value or not str(exercise_name_value).strip():
            st.error("动作名称不能为空。")
            return

        record = {
            "completed_at": selected_timestamp,
            "body_part": body_part_value,
            "exercise_name": str(last_vals.get("exercise_name", exercise_name_value) if last_vals else exercise_name_value).strip(),
            "weight_kg": float(weight_value),
            "reps": int(reps_value),
            "set_number": int(set_number_value),
            "notes": notes_value.strip(),
        }
        try:
            add_workout_set(record)
            st.success(
                f"已记录：{record['exercise_name']} {record['weight_kg']:.1f}kg x {record['reps']}，第 {record['set_number']} 组"
            )
            st.rerun()
        except ValidationError as e:
            st.error(str(e))


def render_dashboard(dataframe: pd.DataFrame) -> None:
    render_section("趋势总览", "用时间、训练量、PR 和动作最大重量提升，观察训练系统是否仍在向上。")
    if dataframe.empty:
        st.info("还没有训练记录。先录入第一组数据，图表会自动出现。")
        return

    date_min = dataframe["day"].min().date()
    date_max = dataframe["day"].max().date()
    range_options = {
        "全部": None,
        "近30天": 29,
        "近90天": 89,
        "近180天": 179,
        "近365天": 364,
    }

    filter_range, filter_left, filter_mid, filter_right = st.columns([1, 1.2, 1.2, 1])
    range_label = filter_range.selectbox("显示范围", list(range_options.keys()), index=0)
    range_days = range_options[range_label]
    default_start = date_min if range_days is None else max(date_min, date_max - timedelta(days=range_days))

    start_date = filter_left.date_input("开始日期", value=default_start, min_value=date_min, max_value=date_max)
    end_date = filter_mid.date_input("结束日期", value=date_max, min_value=date_min, max_value=date_max)
    grain_label = filter_right.selectbox("统计粒度", list(GRAIN_OPTIONS.keys()), index=0)
    grain = GRAIN_OPTIONS[grain_label]

    filtered = dataframe[
        (dataframe["day"].dt.date >= start_date) & (dataframe["day"].dt.date <= end_date)
    ].copy()

    if filtered.empty:
        st.warning("当前筛选范围内没有数据。")
        return

    weekly_weight_progress = build_max_weight_progress(filtered, "week")
    monthly_weight_progress = build_max_weight_progress(filtered, "month")
    weekly_summary = summarize_latest_max_weight_progress(weekly_weight_progress)
    monthly_summary = summarize_latest_max_weight_progress(monthly_weight_progress)
    weekly_value, weekly_delta, weekly_help = format_progress_metric(weekly_summary)
    monthly_value, monthly_delta, monthly_help = format_progress_metric(monthly_summary)

    metrics = build_summary_metrics(filtered)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("总组数", f"{metrics.total_sets:,}", "记录到数据库的训练组", "blue")
    with col2:
        render_metric_card("总训练量", f"{metrics.total_volume:,.0f} kg", "重量 x 次数 汇总", "good")
    with col3:
        render_metric_card("训练天数", f"{metrics.active_days}", f"{start_date} 至 {end_date}", "hot")
    with col4:
        render_metric_card("最高估算 1RM", f"{metrics.max_estimated_1rm:,.1f} kg", "Epley / Brzycki 估算", "blue")

    progress_col1, progress_col2 = st.columns(2)
    with progress_col1:
        render_metric_card("最近周最大重量提升", weekly_value, weekly_delta or weekly_help, "good")
    with progress_col2:
        render_metric_card("最近月最大重量提升", monthly_value, monthly_delta or monthly_help, "good")

    volume_trend = aggregate_volume(filtered, grain)
    body_part_trend = aggregate_body_part(filtered)
    exercise_names = sorted(filtered["exercise_name"].unique())
    selected_exercise = st.selectbox("查看单动作趋势", options=exercise_names, index=0)
    exercise_trend = build_exercise_trend(filtered, selected_exercise, grain)

    render_section("训练负荷", "左侧显示训练量随时间变化，右侧显示身体部位的负荷分布。")
    trend_left, trend_right = st.columns(2)
    with trend_left:
        st.caption("训练量趋势")
        st.altair_chart(volume_area_chart(volume_trend), use_container_width=True)
    with trend_right:
        st.caption("部位分布")
        st.altair_chart(body_part_bar_chart(body_part_trend), use_container_width=True)

    render_section(f"{selected_exercise} 表现趋势", "同时观察最大重量、估算 1RM 和总训练量，避免只看单一指标。")
    if not exercise_trend.empty:
        st.altair_chart(exercise_trend_chart(exercise_trend), use_container_width=True)

    render_section("动作最大重量提升百分比", "按周期比较同一动作的最大重量，找出最近真正向上突破的动作。")
    weekly_tab, monthly_tab = st.tabs(["周", "月"])
    with weekly_tab:
        render_weight_progress_panel(weekly_weight_progress)
    with monthly_tab:
        render_weight_progress_panel(monthly_weight_progress)


def render_recent_records(dataframe: pd.DataFrame) -> None:
    st.subheader("最近记录")
    if dataframe.empty:
        st.write("暂无记录。")
        return

    tab_view, tab_edit, tab_delete = st.tabs(["查看", "编辑", "删除"])

    with tab_view:
        show_count = st.selectbox("显示条数", [20, 50, 100, 200], index=0, key="view_count")
        recent = dataframe.head(show_count).copy()
        record_columns = [
            "id",
            "completed_at",
            "body_part",
            "exercise_name",
            "weight_kg",
            "reps",
            "set_number",
            "volume_kg",
            "estimated_1rm",
        ]
        if "exercise_name_normalized" in recent.columns and recent["exercise_name_normalized"].any():
            record_columns.append("raw_exercise_name")
        record_columns.append("notes")
        display = recent[record_columns].rename(
            columns={
                "id": "ID",
                "completed_at": "完成时间",
                "body_part": "部位",
                "exercise_name": "动作",
                "weight_kg": "重量(kg)",
                "reps": "次数",
                "set_number": "组序号",
                "volume_kg": "训练量",
                "estimated_1rm": "估算1RM",
                "raw_exercise_name": "原始动作",
                "notes": "备注",
            }
        )
        render_display_table(display)

    with tab_edit:
        editable_ids = dataframe.head(50)["id"].tolist()
        if not editable_ids:
            st.info("没有可编辑的记录。")
        else:
            selected_edit_id = st.selectbox("选择要编辑的记录 ID", options=editable_ids, key="edit_id_select")
            if selected_edit_id:
                row = dataframe[dataframe["id"] == selected_edit_id].iloc[0]
                with st.form("edit_form"):
                    edit_weight = st.number_input("重量 (kg)", min_value=0.0, step=2.5, value=float(row["weight_kg"]))
                    edit_reps = st.number_input("次数", min_value=1, step=1, value=int(row["reps"]))
                    edit_set = st.number_input("第几组", min_value=1, step=1, value=int(row["set_number"]))
                    edit_body = st.selectbox("部位", BODY_PARTS, index=BODY_PARTS.index(row["body_part"]) if row["body_part"] in BODY_PARTS else 0)
                    edit_name = st.text_input("动作名称", value=str(row["exercise_name"]))
                    edit_notes = st.text_input("备注", value=str(row.get("notes", "")))
                    edit_submitted = st.form_submit_button("保存修改", use_container_width=True)

                if edit_submitted:
                    if not edit_name.strip():
                        st.error("动作名称不能为空。")
                    else:
                        try:
                            update_workout_set(int(selected_edit_id), {
                                "weight_kg": edit_weight,
                                "reps": edit_reps,
                                "set_number": edit_set,
                                "body_part": edit_body,
                                "exercise_name": edit_name.strip(),
                                "notes": edit_notes.strip(),
                            })
                            st.success(f"已更新记录 #{selected_edit_id}")
                            st.rerun()
                        except ValidationError as e:
                            st.error(str(e))

    with tab_delete:
        search_term = st.text_input("按动作名称搜索", placeholder="输入动作名称筛选，留空显示全部", key="delete_search")
        if search_term:
            raw_names = dataframe.get("raw_exercise_name", dataframe["exercise_name"]).astype(str)
            filtered_for_delete = dataframe[
                dataframe["exercise_name"].str.contains(search_term, case=False, na=False, regex=False)
                | raw_names.str.contains(search_term, case=False, na=False, regex=False)
            ]
        else:
            filtered_for_delete = dataframe

        if filtered_for_delete.empty:
            st.info("没有匹配的记录。")
        else:
            delete_ids = filtered_for_delete.head(50)["id"].tolist()
            selected_id = st.selectbox("选择要删除的记录 ID", options=delete_ids, key="delete_id_select")
            row_info = filtered_for_delete[filtered_for_delete["id"] == selected_id]
            if not row_info.empty:
                r = row_info.iloc[0]
                st.caption(f"预览：{r['exercise_name']} {r['weight_kg']}kg x {r['reps']}，{r['completed_at']}")

            confirm_delete = st.checkbox("确认删除选中记录", key="confirm_delete")
            if st.button("删除选中记录", type="secondary", disabled=not confirm_delete):
                delete_workout_set(int(selected_id))
                st.success(f"已删除记录 #{selected_id}")
                st.rerun()


def render_session_view(dataframe: pd.DataFrame) -> None:
    st.subheader("训练记录（按 Session 分组）")
    if dataframe.empty or "session_id" not in dataframe.columns:
        st.info("还没有训练记录。")
        return

    session_df = build_session_summary(dataframe)
    if session_df.empty:
        st.info("暂无 session 数据。")
        return

    display_df = session_df.rename(columns={
        "session_id": "Session",
        "date": "日期",
        "body_parts": "训练部位",
        "exercise_count": "动作数",
        "total_sets": "总组数",
        "total_volume_kg": "总训练量(kg)",
        "max_weight_kg": "最大重量(kg)",
        "duration_minutes": "时长(分钟)",
    })
    render_display_table(display_df)

    show_sessions = min(20, len(session_df))
    selected_session = st.selectbox(
        "选择 Session 查看详情",
        options=session_df.head(show_sessions)["session_id"].tolist(),
        format_func=lambda sid: f"Session {sid} — {session_df[session_df['session_id'] == sid].iloc[0]['date'].strftime('%Y-%m-%d') if not session_df[session_df['session_id'] == sid].empty else sid}",
    )
    session_detail = dataframe[dataframe["session_id"] == selected_session].sort_values("completed_at")
    if not session_detail.empty:
        detail_display = session_detail[
            ["completed_at", "body_part", "exercise_name", "weight_kg", "reps", "set_number", "volume_kg", "estimated_1rm"]
        ].rename(columns={
            "completed_at": "时间", "body_part": "部位", "exercise_name": "动作",
            "weight_kg": "重量(kg)", "reps": "次数", "set_number": "组序号",
            "volume_kg": "训练量", "estimated_1rm": "估算1RM",
        })
        render_display_table(detail_display)


def render_pr_view(dataframe: pd.DataFrame) -> None:
    st.subheader("个人记录 (PR)")
    if dataframe.empty:
        st.info("还没有训练记录。")
        return

    pr_df = build_pr_records(dataframe)
    if pr_df.empty:
        st.info("暂无 PR 数据。")
        return

    pr_display = pr_df.rename(columns={
        "exercise_name": "动作",
        "pr_weight_kg": "最大重量(kg)",
        "pr_reps": "次数",
        "pr_1rm": "估算1RM(kg)",
        "pr_date": "日期",
        "previous_weight_kg": "前一次最大(kg)",
    })

    pr_display["日期"] = pr_display["日期"].dt.strftime("%Y-%m-%d")
    if "previous_date" in pr_display.columns and pr_display["previous_date"] is not None:
        pr_display["前一次日期"] = pr_display["previous_date"].apply(
            lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else ""
        )

    show_cols = ["动作", "最大重量(kg)", "次数", "估算1RM(kg)", "日期", "前一次最大(kg)"]
    available_cols = [c for c in show_cols if c in pr_display.columns]
    render_display_table(pr_display[available_cols])


def render_name_cleanup_audit(dataframe: pd.DataFrame) -> None:
    st.subheader("动作名称规范化")
    if dataframe.empty or "exercise_name_normalized" not in dataframe.columns:
        st.info("暂无可核查的动作名称。")
        return

    normalized = dataframe[dataframe["exercise_name_normalized"]].copy()
    if normalized.empty:
        st.success("当前没有命中内置错字映射的动作名称。")
        return

    st.caption("历史记录未被直接改写；程序在统计、趋势和动作选项中按标准动作名合并。")
    report = (
        normalized.groupby(["raw_exercise_name", "exercise_name"], as_index=False)
        .agg(sets=("id", "count"), latest=("completed_at", "max"))
        .sort_values(["sets", "latest"], ascending=[False, False])
    )
    report["latest"] = report["latest"].dt.strftime("%Y-%m-%d %H:%M")
    report = report.rename(
        columns={
            "raw_exercise_name": "原始动作",
            "exercise_name": "标准动作",
            "sets": "合并组数",
            "latest": "最近记录",
        }
    )
    render_display_table(report)


def render_import_audit() -> None:
    st.subheader("导入审计")
    summary = load_import_summary()
    imported_sets = load_imported_sets()

    if summary.empty or imported_sets.empty:
        st.info("还没有导入记录。")
        return

    note_count = int(summary["source_path"].nunique())
    set_count = int(len(imported_sets))
    first_completed = imported_sets["completed_at"].min()
    last_completed = imported_sets["completed_at"].max()
    source_counts = imported_sets["notes"].map(classify_import_source).value_counts()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("来源文件", note_count)
    col2.metric("导入组数", set_count)
    col3.metric("最早训练", first_completed.strftime("%Y-%m-%d"))
    col4.metric("最近训练", last_completed.strftime("%Y-%m-%d"))

    st.caption("导入来源")
    render_display_table(
        source_counts.rename_axis("来源").reset_index(name="组数"),
    )

    by_exercise = (
        imported_sets.groupby("exercise_name", as_index=False)
        .agg(sets=("id", "count"), volume_kg=("volume_kg", "sum"))
        .sort_values(["sets", "volume_kg"], ascending=[False, False])
        .head(20)
    )
    by_body_part = (
        imported_sets.groupby("body_part", as_index=False)
        .agg(sets=("id", "count"), volume_kg=("volume_kg", "sum"))
        .sort_values(["sets", "volume_kg"], ascending=[False, False])
    )

    left, right = st.columns(2)
    left.caption("导入动作 Top 20")
    with left:
        render_display_table(
        by_exercise.rename(
            columns={
                "exercise_name": "动作",
                "sets": "组数",
                "volume_kg": "训练量",
            }
        ),
        )
    right.caption("导入部位分布")
    right.bar_chart(by_body_part.set_index("body_part")["sets"], use_container_width=True)

    source_display = summary.copy()
    source_display["文件名"] = source_display["source_path"].map(lambda value: str(value).replace("/", "\\").split("\\")[-1])
    source_display = source_display.rename(
        columns={
            "source_path": "来源路径",
            "sets": "导入组数",
            "first_imported_at": "首次导入",
            "last_imported_at": "最近导入",
        }
    )

    st.caption("来源笔记")
    render_display_table(
        source_display[["文件名", "导入组数", "首次导入", "最近导入", "来源路径"]],
    )

    recent_display = imported_sets.head(100).rename(
        columns={
            "id": "ID",
            "completed_at": "完成时间",
            "body_part": "部位",
            "exercise_name": "动作",
            "weight_kg": "重量(kg)",
            "reps": "次数",
            "set_number": "组序号",
            "volume_kg": "训练量",
            "notes": "来源",
        }
    )
    st.caption("最近导入的训练组")
    render_display_table(recent_display)


def classify_import_source(notes: str) -> str:
    if str(notes).startswith("Imported from OPPO Cloud"):
        return "OPPO 云便签"
    if str(notes).startswith("Imported from Obsidian"):
        return "Obsidian"
    if str(notes).startswith("Imported from"):
        return "其他导入"
    return "手动录入"


def render_export_button(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        return
    csv_data = export_to_csv(dataframe)
    date_min = dataframe["day"].min().strftime("%Y%m%d")
    date_max = dataframe["day"].max().strftime("%Y%m%d")
    filename = f"workout_data_{date_min}_{date_max}.csv"
    st.download_button(
        label="导出 CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    st.set_page_config(page_title="健身趋势追踪", page_icon="🏋️", layout="wide")

    theme_options = {
        "明亮玻璃": "light",
        "深色玻璃": "dark",
    }
    with st.sidebar:
        st.caption("界面设置")
        selected_theme = st.selectbox(
            "视觉主题",
            list(theme_options.keys()),
            index=0,
            key="theme_select",
            help="切换全局毛玻璃视觉风格，不影响训练数据。",
        )
        st.caption("Apple-inspired glass interface")
    theme = theme_options[selected_theme]
    apply_apple_design(theme=theme)
    initialize_db()

    dataframe = load_workout_sets()
    render_hero(dataframe)

    main_tab, session_tab, pr_tab, audit_tab = st.tabs(["训练面板", "训练记录", "个人记录 (PR)", "导入审计"])

    with main_tab:
        left, right = st.columns([1, 1.4], gap="large")
        with left:
            render_entry_form()
        with right:
            render_dashboard(dataframe)

        st.divider()
        render_science_rules_panel(dataframe)
        st.divider()
        render_recent_records(dataframe)
        render_export_button(dataframe)

    with session_tab:
        render_session_view(dataframe)

    with pr_tab:
        render_pr_view(dataframe)

    with audit_tab:
        render_name_cleanup_audit(dataframe)
        st.divider()
        render_import_audit()


if __name__ == "__main__":
    main()
