import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="QMath Compliance Analytics", layout="wide", page_icon="📊")

# ── Data structure ───────────────────────────────────────────────────────────
PERIODS = {
    "Dec 31": "dec31",
    "Jan 27": "jan27",
    "Feb 10": "feb10",
    "Feb 17": "feb17",
    "Feb 22": "feb22",
    "Live":   "live",
}

OFFENSE_DISPLAY = {
    "Trial Late Login":       "trial_late_login",
    "Class No Show":          "class_no_show",
    "Class Late Login":       "class_late_login",
    "Trial No Show":          "trial_no_show",
    "Trial Not Acknowledged": "trial_not_acknowledged",
}

RATING_COLORS = {
    "Red":    "#e74c3c",
    "Amber":  "#f39c12",
    "Yellow": "#f1c40f",
    "Green":  "#2ecc71",
}

# ── Load & rename data ───────────────────────────────────────────────────────
def load_data(file):
    raw = pd.read_csv(file, header=None, dtype=str) if file.name.endswith(".csv") \
          else pd.read_excel(file, header=None, dtype=str)

    header_row = 0
    for i, row in raw.iterrows():
        if any("db id" in str(v).strip().lower() for v in row.values):
            header_row = i
            break

    df = raw.iloc[header_row + 1:].reset_index(drop=True)

    new_cols = ["db_id", "teacher_name", "teacher_contact", "comms_contact", "cd_name"]
    for key in PERIODS.values():
        for s in ["trial_late_login", "class_no_show", "class_late_login",
                  "trial_no_show", "trial_not_acknowledged", "total_offenses", "rating"]:
            new_cols.append(f"{key}_{s}")

    # Pad new_cols if CSV has more columns than expected
    while len(new_cols) < len(df.columns):
        new_cols.append(f"extra_col_{len(new_cols)}")
    df.columns = new_cols[:len(df.columns)]

    for col in df.columns:
        if "rating" not in col and col not in [
            "db_id", "teacher_name", "teacher_contact", "comms_contact", "cd_name"
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for key in PERIODS.values():
        rcol = f"{key}_rating"
        if rcol in df.columns:
            df[rcol] = df[rcol].astype(str).str.strip().str.capitalize()
            df[rcol] = df[rcol].replace({"Nan": "", "None": "", "Na": ""})

    # Forward-fill blank ratings across periods
    # If Feb 22 is blank → carry forward Feb 17's rating, and so on
    rating_cols = [f"{key}_rating" for key in PERIODS.values() if f"{key}_rating" in df.columns]
    df[rating_cols] = df[rating_cols].replace("", pd.NA)
    df[rating_cols] = df[rating_cols].ffill(axis=1)
    df[rating_cols] = df[rating_cols].fillna("")

    df = df.dropna(subset=["teacher_name"])
    df = df[df["teacher_name"].astype(str).str.strip() != ""]
    return df

# ── App ──────────────────────────────────────────────────────────────────────
st.title("📊 QMath Compliance Analytics")

uploaded = st.file_uploader(
    "Upload your compliance CSV or Excel file", type=["csv", "xlsx", "xls"]
)
if uploaded:
    st.session_state["df"] = load_data(uploaded)

if "df" not in st.session_state:
    st.info("Upload your compliance data above to get started.")
    st.stop()

df = st.session_state["df"]

# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.header("🔍 Filters")
cd_list      = ["All CDs"] + sorted(df["cd_name"].dropna().unique().tolist())
selected_cd  = st.sidebar.selectbox("Cluster Director", cd_list)
period_label = st.sidebar.selectbox("View Period", list(PERIODS.keys()), index=5)
period_key   = PERIODS[period_label]
rcol         = f"{period_key}_rating"
tcol         = f"{period_key}_total_offenses"

filtered = df.copy()
if selected_cd != "All CDs":
    filtered = filtered[filtered["cd_name"] == selected_cd]

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Overview KPIs
# ════════════════════════════════════════════════════════════════════════════
st.subheader(f"📈 Overview — {period_label}")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Teachers", len(filtered))

if rcol in filtered.columns:
    rc = filtered[rcol].str.lower().value_counts()
    k2.metric("🔴 Red",    int(rc.get("red",    0)))
    k3.metric("🟠 Amber",  int(rc.get("amber",  0)))
    k4.metric("🟡 Yellow", int(rc.get("yellow", 0)))
    k5.metric("🟢 Green",  int(rc.get("green",  0)))

if tcol in filtered.columns:
    k6.metric("Total Offenses", int(filtered[tcol].sum()))

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Offense Breakdown (Clickable)
# ════════════════════════════════════════════════════════════════════════════
st.subheader(f"⚠️ Offense Breakdown — {period_label}")
st.caption("Click any bar to see which teachers committed that offense.")

offense_rows = []
for label, suffix in OFFENSE_DISPLAY.items():
    col = f"{period_key}_{suffix}"
    if col in filtered.columns:
        offense_rows.append({
            "Offense Type":      label,
            "Teachers Affected": int((filtered[col] > 0).sum()),
            "Total Count":       int(filtered[col].sum()),
        })

if offense_rows:
    off_df  = pd.DataFrame(offense_rows).sort_values("Total Count")
    fig_off = px.bar(
        off_df, x="Total Count", y="Offense Type",
        orientation="h",
        color="Total Count",
        color_continuous_scale=["#f39c12", "#e74c3c"],
        text="Total Count",
        hover_data=["Teachers Affected"],
    )
    fig_off.update_traces(textposition="outside")
    fig_off.update_layout(
        xaxis_title="Total Offense Count",
        coloraxis_showscale=False,
        height=320,
    )

    off_event = st.plotly_chart(fig_off, on_select="rerun", use_container_width=True)

    selected_offense = None
    if off_event and off_event.selection and off_event.selection.points:
        pt = off_event.selection.points[0]
        selected_offense = pt.get("label") or pt.get("y")

    if selected_offense:
        suffix = OFFENSE_DISPLAY.get(selected_offense, "")
        col    = f"{period_key}_{suffix}"
        if col in filtered.columns:
            drill = filtered[filtered[col] > 0].copy()
            drill = drill[["db_id", "teacher_name", "cd_name", col, rcol]].sort_values(col, ascending=False)
            drill.columns = ["DB ID", "Teacher Name", "CD", f"{selected_offense} Count", "Rating"]
            st.markdown(f"**{len(drill)} teachers with '{selected_offense}' in {period_label}:**")
            st.dataframe(drill, use_container_width=True, hide_index=True)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Extreme Offense Makers
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🚨 Extreme Offense Makers")

c_n, c_r = st.columns([1, 2])
with c_n:
    top_n = st.slider("Show Top N teachers", 10, 200, 50, step=10)
with c_r:
    extreme_ratings = st.multiselect(
        "Filter by Rating", ["Red", "Amber", "Yellow", "Green"],
        default=["Red", "Amber"]
    )

extreme_df = filtered.copy()
if tcol in extreme_df.columns:
    if extreme_ratings and rcol in extreme_df.columns:
        extreme_df = extreme_df[extreme_df[rcol].isin(extreme_ratings)]
    extreme_df = extreme_df.sort_values(tcol, ascending=False).head(top_n)

    show  = ["db_id", "teacher_name", "cd_name"]
    remap = {"db_id": "DB ID", "teacher_name": "Teacher Name", "cd_name": "CD"}

    for label, suffix in OFFENSE_DISPLAY.items():
        c = f"{period_key}_{suffix}"
        if c in extreme_df.columns:
            show.append(c)
            remap[c] = label

    show.extend([tcol, rcol])
    remap[tcol] = "Total Offenses"
    remap[rcol] = "Rating"
    show = [c for c in show if c in extreme_df.columns]

    st.dataframe(
        extreme_df[show].rename(columns=remap).reset_index(drop=True),
        use_container_width=True,
    )
    st.caption(f"Top {len(extreme_df)} teachers by total offenses — {period_label}")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Rating Trend + Distribution
# ════════════════════════════════════════════════════════════════════════════
c1, c2 = st.columns(2)

with c1:
    st.subheader("📉 Rating Trendline Across Periods")
    trend_rows = []
    for label, key in PERIODS.items():
        rc_ = f"{key}_rating"
        if rc_ in filtered.columns:
            counts = filtered[rc_].str.lower().value_counts()
            for r in ["red", "amber", "yellow", "green"]:
                trend_rows.append({"Period": label, "Rating": r.capitalize(),
                                   "Teachers": int(counts.get(r, 0))})
    if trend_rows:
        trend_df = pd.DataFrame(trend_rows)
        fig_trend = px.line(
            trend_df, x="Period", y="Teachers", color="Rating",
            color_discrete_map=RATING_COLORS,
            markers=True,
            category_orders={"Rating": ["Red", "Amber", "Yellow", "Green"]},
        )
        fig_trend.update_traces(line=dict(width=3), marker=dict(size=8))
        fig_trend.update_layout(xaxis_title="", legend_title="Rating", hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)

with c2:
    st.subheader(f"🎯 {period_label} Rating Split")
    if rcol in filtered.columns:
        live_r = filtered[rcol].str.capitalize().value_counts().reset_index()
        live_r.columns = ["Rating", "Count"]
        live_r = live_r[live_r["Rating"].isin(RATING_COLORS)]
        fig_pie = px.pie(
            live_r, names="Rating", values="Count",
            color="Rating", color_discrete_map=RATING_COLORS,
        )
        fig_pie.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — CD Performance (Clickable)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("👥 Cluster Director Performance")
st.caption("Click any CD bar to see all their teachers.")

if "cd_name" in filtered.columns and rcol in filtered.columns:
    cd_total = filtered.groupby("cd_name").size().reset_index(name="Total")
    cd_grp   = filtered.groupby(["cd_name", rcol]).size().reset_index(name="Count")
    cd_grp[rcol] = cd_grp[rcol].str.capitalize()
    cd_grp   = cd_grp[cd_grp[rcol].isin(RATING_COLORS)]
    cd_grp   = cd_grp.merge(cd_total, on="cd_name")
    cd_grp["Pct"] = (cd_grp["Count"] / cd_grp["Total"] * 100).round(1)
    cd_grp["Label"] = cd_grp["Pct"].astype(str) + "%"

    view_toggle = st.radio("View as", ["Percentage", "Count"], horizontal=True)

    if view_toggle == "Percentage":
        fig_cd = px.bar(
            cd_grp, x="Pct", y="cd_name", color=rcol,
            orientation="h", barmode="stack",
            text="Label",
            color_discrete_map=RATING_COLORS,
            labels={"cd_name": "Cluster Director", rcol: "Rating", "Pct": "% of Teachers"},
            category_orders={rcol: ["Red", "Amber", "Yellow", "Green"]},
        )
        fig_cd.update_layout(xaxis_title="% of Teachers", xaxis=dict(range=[0, 100]))
    else:
        fig_cd = px.bar(
            cd_grp, x="Count", y="cd_name", color=rcol,
            orientation="h", barmode="stack",
            text="Count",
            color_discrete_map=RATING_COLORS,
            labels={"cd_name": "Cluster Director", rcol: "Rating"},
            category_orders={rcol: ["Red", "Amber", "Yellow", "Green"]},
        )
        fig_cd.update_layout(xaxis_title="Number of Teachers")

    fig_cd.update_traces(textposition="inside")
    fig_cd.update_layout(
        yaxis=dict(autorange="reversed"),
        yaxis_title="",
        legend_title="Rating",
    )

    cd_event = st.plotly_chart(fig_cd, on_select="rerun", use_container_width=True)

    selected_cd_click = None
    if cd_event and cd_event.selection and cd_event.selection.points:
        pt = cd_event.selection.points[0]
        selected_cd_click = pt.get("label") or pt.get("y")

    if selected_cd_click:
        cd_teachers = filtered[filtered["cd_name"] == selected_cd_click].copy()
        show_cd = ["db_id", "teacher_name"]
        if tcol in cd_teachers.columns:
            show_cd.append(tcol)
        if rcol in cd_teachers.columns:
            show_cd.append(rcol)
        cd_teachers = cd_teachers[show_cd].sort_values(
            tcol if tcol in cd_teachers.columns else "teacher_name", ascending=False
        )
        rename_cd = {"db_id": "DB ID", "teacher_name": "Teacher Name",
                     tcol: "Total Offenses", rcol: "Rating"}
        st.markdown(f"**{len(cd_teachers)} teachers under {selected_cd_click}:**")
        st.dataframe(cd_teachers.rename(columns=rename_cd), use_container_width=True, hide_index=True)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Teacher Profile Search
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔍 Teacher Profile")
st.caption("Search by teacher name or DB ID to see their full history across all periods.")

search = st.text_input("Search", placeholder="Type a name or DB ID...")

if search:
    mask = (
        filtered["teacher_name"].astype(str).str.contains(search, case=False, na=False) |
        filtered["db_id"].astype(str).str.contains(search, case=False, na=False)
    )
    results = filtered[mask]

    if len(results) == 0:
        st.warning("No teacher found.")
    else:
        for _, t in results.iterrows():
            with st.expander(
                f"📋  {t['teacher_name']}  |  DB ID: {t['db_id']}  |  CD: {t['cd_name']}"
            ):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown("**Period-by-period summary:**")
                    summary = []
                    for label, key in PERIODS.items():
                        summary.append({
                            "Period":         label,
                            "Total Offenses": t.get(f"{key}_total_offenses", 0),
                            "Rating":         t.get(f"{key}_rating", ""),
                        })
                    st.dataframe(
                        pd.DataFrame(summary), use_container_width=True, hide_index=True
                    )

                with col_b:
                    st.markdown("**Live offense breakdown:**")
                    live_b = []
                    for label, suffix in OFFENSE_DISPLAY.items():
                        val = t.get(f"live_{suffix}", 0)
                        if pd.notna(val) and float(val) > 0:
                            live_b.append({"Offense": label, "Count": int(float(val))})
                    if live_b:
                        fig_lb = px.pie(
                            pd.DataFrame(live_b), names="Offense", values="Count",
                            color_discrete_sequence=px.colors.sequential.RdBu,
                        )
                        fig_lb.update_traces(textinfo="percent+label")
                        st.plotly_chart(fig_lb, use_container_width=True)
                    else:
                        st.success("No live offenses recorded.")
