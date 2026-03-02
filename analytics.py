import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Cuemath Compliance Analytics", layout="wide", page_icon="📊")

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
    "Orange": "#e67e22",
    "Yellow": "#f1c40f",
    "Green":  "#2ecc71",
}

LICENSES = ["NAM", "APAC", "IME", "EUK"]

# Standard CD reason categories — your CDs should log one of these
REASON_CATEGORIES = [
    "Personal Reason",
    "Internet Issue",
    "Teacher Lapse",
    "Technical Issue",
    "Emergency / Health",
    "Student No Show",
    "System Error",
    "Other",
]


def load_data(file):
    raw = pd.read_csv(file, header=None, dtype=str) if file.name.endswith(".csv") \
          else pd.read_excel(file, header=None, dtype=str)

    header_row = 0
    for i, row in raw.iterrows():
        if any("db id" in str(v).strip().lower() for v in row.values):
            header_row = i
            break

    col_names_row = raw.iloc[header_row]

    period_filled = []
    if header_row > 0:
        last_p = ""
        for v in raw.iloc[header_row - 1]:
            s = str(v).strip()
            if s and s.lower() not in ["nan", "none", ""]:
                last_p = s
            period_filled.append(last_p)
    else:
        period_filled = [""] * len(col_names_row)

    df = raw.iloc[header_row + 1:].reset_index(drop=True)

    PERIOD_DETECT = {}
    for label, key in PERIODS.items():
        PERIOD_DETECT[label.lower()] = key
        PERIOD_DETECT[key.lower()]   = key

    OFFENSE_DETECT = [
        ("trial late login",       "trial_late_login"),
        ("trial not acknowledged", "trial_not_acknowledged"),
        ("trial no show",          "trial_no_show"),
        ("class late login",       "class_late_login"),
        ("class no show",          "class_no_show"),
        ("total offense",          "total_offenses"),
        ("total",                  "total_offenses"),
        ("rating",                 "rating"),
    ]

    STATIC_DETECT = [
        ("db id",            "db_id"),
        ("dbid",             "db_id"),
        ("teacher name",     "teacher_name"),
        ("comms contact",    "comms_contact"),
        ("teacher contact",  "teacher_contact"),
        ("licence",          "license_region"),
        ("license",          "license_region"),
        ("cd name",          "cd_name"),
        ("cluster director", "cd_name"),
        ("cluster",          "cd_name"),
        ("cd remark",        "cd_remarks"),
        ("remark",           "cd_remarks"),
        ("miss reason",      "cd_remarks"),
        ("reason for miss",  "cd_remarks"),
        ("reason",           "cd_remarks"),
        ("comment",          "cd_remarks"),
        ("cd note",          "cd_remarks"),
        ("note",             "cd_remarks"),
    ]

    new_cols      = []
    col_map_debug = []

    for idx in range(len(col_names_row)):
        col_val    = str(col_names_row.iloc[idx]).strip().lower()
        period_val = (period_filled[idx] if idx < len(period_filled) else "").lower().strip()
        orig_col   = str(col_names_row.iloc[idx]).strip()
        orig_per   = period_filled[idx] if idx < len(period_filled) else ""

        static = None
        for k, v in STATIC_DETECT:
            if k in col_val:
                static = v
                break
        if static:
            new_cols.append(static)
            col_map_debug.append((orig_col, orig_per, static))
            continue

        period_key_found = None
        for k, v in PERIOD_DETECT.items():
            if k in period_val:
                period_key_found = v
                break

        offense_found = None
        for k, v in OFFENSE_DETECT:
            if k in col_val:
                offense_found = v
                break

        if period_key_found and offense_found:
            mapped = f"{period_key_found}_{offense_found}"
        else:
            mapped = f"extra_col_{idx}"

        new_cols.append(mapped)
        col_map_debug.append((orig_col, orig_per, mapped))

    extra_count = sum(1 for c in new_cols if c.startswith("extra_col"))
    if extra_count > len(new_cols) * 0.4:
        new_cols = [
            "db_id", "teacher_name", "teacher_contact",
            "comms_contact", "license_region", "cd_name",
        ]
        for key in PERIODS.values():
            for s in ["trial_late_login", "class_no_show", "class_late_login",
                      "trial_no_show", "trial_not_acknowledged", "total_offenses", "rating"]:
                new_cols.append(f"{key}_{s}")
        new_cols.append("cd_remarks")
        col_map_debug = [(c, "positional fallback", c) for c in new_cols]

    while len(new_cols) < len(df.columns):
        new_cols.append(f"extra_col_{len(new_cols)}")
    df.columns = new_cols[:len(df.columns)]

    for col in df.columns:
        if "rating" not in col and col not in [
            "db_id", "teacher_name", "teacher_contact",
            "comms_contact", "license_region", "cd_name", "cd_remarks",
        ] and not col.startswith("extra_col"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for key in PERIODS.values():
        rcol_n = f"{key}_rating"
        if rcol_n in df.columns:
            df[rcol_n] = df[rcol_n].astype(str).str.strip().str.capitalize()
            df[rcol_n] = df[rcol_n].replace({"Nan": "", "None": "", "Na": "", "Amber": "Orange"})

    rating_cols = [f"{key}_rating" for key in PERIODS.values() if f"{key}_rating" in df.columns]
    df[rating_cols] = df[rating_cols].replace("", pd.NA)
    df[rating_cols] = df[rating_cols].ffill(axis=1)
    df[rating_cols] = df[rating_cols].fillna("")

    df = df.dropna(subset=["teacher_name"])
    df = df[df["teacher_name"].astype(str).str.strip() != ""]
    return df, col_map_debug


# ════════════════════════════════════════════════════════════════════════════
# App Header
# ════════════════════════════════════════════════════════════════════════════
st.title("📊 Cuemath Compliance Analytics")
st.caption("Upload your compliance data below, set your filters in the sidebar, and click Apply.")

# ── File Uploaders ────────────────────────────────────────────────────────────
up1, up2 = st.columns(2)

with up1:
    st.markdown("#### 📂 Active Compliance Data")
    uploaded = st.file_uploader(
        "Upload weekly compliance CSV or Excel",
        type=["csv", "xlsx", "xls"],
        key="main_upload",
        help="This is your main compliance tracker — one row per teacher."
    )
    if uploaded:
        df_loaded, col_debug = load_data(uploaded)
        st.session_state["df"]        = df_loaded
        st.session_state["col_debug"] = col_debug
        st.success(f"✅ {len(df_loaded)} teachers loaded.")

with up2:
    st.markdown("#### 📂 Reverted / Deleted Cases *(optional)*")
    rev_uploaded = st.file_uploader(
        "Upload reversed compliance CSV or Excel",
        type=["csv", "xlsx", "xls"],
        key="rev_upload",
        help="Cases that were reversed or deleted. Same format as your active compliance file."
    )
    if rev_uploaded:
        rev_loaded, _ = load_data(rev_uploaded)
        st.session_state["reverted_df"] = rev_loaded
        st.success(f"✅ {len(rev_loaded)} reverted records loaded.")

if "df" not in st.session_state:
    st.info("👆 Upload your active compliance data above to get started.")
    st.stop()

df          = st.session_state["df"]
col_debug   = st.session_state.get("col_debug", [])
reverted_df = st.session_state.get("reverted_df", None)

# Column mapping verification
with st.expander("🔎 Verify Column Mapping — click to confirm offense types are detected correctly"):
    if col_debug:
        debug_show = [(o, p, m) for o, p, m in col_debug if not m.startswith("extra_col")]
        debug_df   = pd.DataFrame(debug_show, columns=["Your Column Header", "Period", "Mapped As"])
        st.dataframe(debug_df, use_container_width=True, hide_index=True)
        extra_n = sum(1 for _, _, m in col_debug if m.startswith("extra_col"))
        if extra_n > 0:
            st.caption(f"{extra_n} extra/unmapped columns hidden above.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# Sidebar — Filters (form with Apply button) + Settings
# ════════════════════════════════════════════════════════════════════════════
st.sidebar.header("🔍 Filters")
st.sidebar.caption("Select your filters then click **Apply**.")

cd_list = ["All CDs"] + sorted(df["cd_name"].dropna().unique().tolist())

with st.sidebar.form("global_filters"):
    selected_cd  = st.selectbox("Cluster Director", cd_list)
    period_label = st.selectbox("View Period", list(PERIODS.keys()), index=5)
    st.form_submit_button("✅ Apply Filters", use_container_width=True)

period_key = PERIODS[period_label]
rcol       = f"{period_key}_rating"
tcol       = f"{period_key}_total_offenses"

# Column settings (outside form — these are one-time setup)
extra_cols      = [c for c in df.columns if c.startswith("extra_col")]
known_static    = ["db_id", "teacher_name", "teacher_contact", "comms_contact",
                   "license_region", "cd_name", "cd_remarks"]
period_prefixes = list(PERIODS.values())
other_cols      = [
    c for c in df.columns
    if c not in extra_cols and c not in known_static
    and not any(c.startswith(k) for k in period_prefixes)
]

st.sidebar.markdown("---")
st.sidebar.markdown("**⚙️ Column Settings**")

rem_options = ["— not mapped —", "cd_remarks"] + extra_cols + other_cols
rem_default = 1 if "cd_remarks" in df.columns else 0
remarks_col = st.sidebar.selectbox("CD Remarks Column", rem_options, index=rem_default)
remarks_col = None if remarks_col == "— not mapped —" else remarks_col
if rem_default == 1:
    st.sidebar.caption("✅ Auto-detected from your sheet.")

lic_options = ["— not mapped —", "license_region"] + extra_cols + other_cols
lic_default = 1 if "license_region" in df.columns else 0
license_col = st.sidebar.selectbox("License / Region Column", lic_options, index=lic_default, key="lic")
license_col = None if license_col == "— not mapped —" else license_col
if lic_default == 1:
    st.sidebar.caption("✅ Auto-detected from your sheet.")

st.sidebar.markdown("---")
comms_app_url = st.sidebar.text_input(
    "📨 Communications App URL",
    placeholder="https://your-comms-app.streamlit.app"
)

filtered = df.copy()
if selected_cd != "All CDs":
    filtered = filtered[filtered["cd_name"] == selected_cd]

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Overview KPIs
# ════════════════════════════════════════════════════════════════════════════
st.subheader(f"📈 Overview — {period_label}")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Teachers", len(filtered))

if rcol in filtered.columns:
    rc = filtered[rcol].str.lower().value_counts()
    k2.metric("🔴 Red",    int(rc.get("red",    0)))
    k3.metric("🟠 Orange", int(rc.get("orange", 0)))
    k4.metric("🟡 Yellow", int(rc.get("yellow", 0)))
    k5.metric("🟢 Green",  int(rc.get("green",  0)))

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Reverted Compliance Comparison
# ════════════════════════════════════════════════════════════════════════════
if reverted_df is not None:
    st.subheader("🔄 Active vs Reverted Compliance — Period Comparison")
    st.caption("Compares how many teachers had active cases vs how many were reversed each period.")

    rev_filtered = reverted_df.copy()
    if selected_cd != "All CDs" and "cd_name" in rev_filtered.columns:
        rev_filtered = rev_filtered[rev_filtered["cd_name"] == selected_cd]

    # Build period-by-period comparison
    comp_rows = []
    for label, key in PERIODS.items():
        act_col = f"{key}_total_offenses"
        active  = int((filtered[act_col].fillna(0) > 0).sum()) if act_col in filtered.columns else 0
        reverted = int((rev_filtered[act_col].fillna(0) > 0).sum()) if act_col in rev_filtered.columns else 0
        comp_rows.append({"Period": label, "Active Cases": active, "Reverted Cases": reverted})

    comp_df = pd.DataFrame(comp_rows)
    total_active   = int(comp_df["Active Cases"].sum())
    total_reverted = int(comp_df["Reverted Cases"].sum())
    total_all      = total_active + total_reverted
    rev_rate       = round(total_reverted / total_all * 100, 1) if total_all > 0 else 0

    ck1, ck2, ck3 = st.columns(3)
    ck1.metric("Total Active Cases",   total_active)
    ck2.metric("Total Reverted Cases", total_reverted)
    ck3.metric("Overall Reversal Rate", f"{rev_rate}%")

    fig_comp = px.bar(
        comp_df.melt(id_vars="Period", value_vars=["Active Cases", "Reverted Cases"],
                     var_name="Type", value_name="Count"),
        x="Period", y="Count", color="Type", barmode="group", text="Count",
        color_discrete_map={"Active Cases": "#e74c3c", "Reverted Cases": "#2ecc71"},
    )
    fig_comp.update_traces(textposition="outside")
    fig_comp.update_layout(xaxis_title="", yaxis_title="Number of Teachers",
                           legend_title="", hovermode="x unified")
    st.plotly_chart(fig_comp, use_container_width=True)

    # Offense type reversal breakdown for selected period
    st.markdown(f"**Reversal breakdown by Offense Type — {period_label}:**")
    rev_off_rows = []
    for label, suffix in OFFENSE_DISPLAY.items():
        col = f"{period_key}_{suffix}"
        if col in rev_filtered.columns:
            rev_off_rows.append({
                "Offense Type":    label,
                "Reverted Count":  int(rev_filtered[col].fillna(0).sum()),
                "Teachers":        int((rev_filtered[col].fillna(0) > 0).sum()),
            })
    if rev_off_rows:
        rev_off_df = pd.DataFrame(rev_off_rows).sort_values("Reverted Count", ascending=False)
        fig_rev_off = px.bar(
            rev_off_df, x="Reverted Count", y="Offense Type", orientation="h",
            color="Reverted Count", color_continuous_scale=["#a8e6cf", "#2ecc71"],
            text="Reverted Count",
        )
        fig_rev_off.update_traces(textposition="outside")
        fig_rev_off.update_layout(coloraxis_showscale=False, height=280,
                                  xaxis_title="Number of Reverted Cases")
        st.plotly_chart(fig_rev_off, use_container_width=True)

    st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Export for Messaging
# ════════════════════════════════════════════════════════════════════════════
with st.expander("📨 Download Teacher List for Communications App", expanded=False):
    st.caption("Filter the teachers you want to message, then download a CSV ready to upload to the Communications App.")

    ex1, ex2, ex3 = st.columns([2, 2, 2])
    with ex1:
        export_ratings = st.multiselect(
            "Filter by Rating",
            ["Red", "Orange", "Yellow", "Green"],
            default=["Red", "Orange"],
            key="exp_ratings"
        )
    with ex2:
        export_offenses = st.multiselect(
            "Filter by Offense Type",
            list(OFFENSE_DISPLAY.keys()),
            default=list(OFFENSE_DISPLAY.keys()),
            key="exp_offenses"
        )
    with ex3:
        export_min = st.number_input(
            "Min offense count per type", min_value=1, value=1, step=1, key="exp_min"
        )

    export_df = filtered.copy()
    if export_ratings and rcol in export_df.columns:
        export_df = export_df[export_df[rcol].isin(export_ratings)]

    export_rows = []
    for _, row in export_df.iterrows():
        for offense_label, suffix in OFFENSE_DISPLAY.items():
            if offense_label not in export_offenses:
                continue
            col = f"{period_key}_{suffix}"
            try:
                val = float(row.get(col, 0)) if pd.notna(row.get(col, 0)) else 0
            except Exception:
                val = 0
            if val >= export_min:
                export_rows.append({
                    "DB ID":         row.get("db_id", ""),
                    "Teacher Name":  row.get("teacher_name", ""),
                    "Phone Number":  str(row.get("teacher_contact", "")).strip(),
                    "CD Name":       row.get("cd_name", ""),
                    "Offense Type":  offense_label,
                    "Offense Count": int(val),
                    "Period":        period_label,
                    "Rating":        row.get(rcol, ""),
                })

    if export_rows:
        export_out = pd.DataFrame(export_rows)
        st.success(
            f"**{len(export_out)} rows** ready — "
            f"{export_out['Teacher Name'].nunique()} unique teachers."
        )
        st.dataframe(export_out.head(20), use_container_width=True, hide_index=True)
        if len(export_out) > 20:
            st.caption(f"Showing first 20 of {len(export_out)} rows.")
        csv_bytes = export_out.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV for Communications App",
            data=csv_bytes,
            file_name=f"teachers_for_messaging_{period_label.replace(' ', '_')}.csv",
            mime="text/csv",
        )
        if comms_app_url:
            st.markdown(
                f"Once downloaded, open your **[Communications App]({comms_app_url})**, "
                f"upload this file, map the columns, and send."
            )
    else:
        st.warning("No teachers match the current export filters.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Recent Offenses (Delta)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🆕 Recent Offenses")
st.caption("New offenses added between a base period and Live. Use this to identify who needs immediate action.")

period_keys_list = list(PERIODS.keys())

with st.form("recent_offense_filters"):
    r1, r2, r3 = st.columns([2, 2, 2])
    with r1:
        base_period_label = st.selectbox(
            "Compare Live from:", [p for p in period_keys_list if p != "Live"], index=4
        )
    with r2:
        recent_offense_filter = st.multiselect(
            "Offense Type", list(OFFENSE_DISPLAY.keys()),
            default=list(OFFENSE_DISPLAY.keys())
        )
    with r3:
        min_recent = st.selectbox("Min recent offenses", [1, 2, 3, 4, 5], index=0)
    st.form_submit_button("🔍 Apply", use_container_width=False)

base_key = PERIODS[base_period_label]

delta_df = filtered.copy()
for label, suffix in OFFENSE_DISPLAY.items():
    live_col = f"live_{suffix}"
    base_col = f"{base_key}_{suffix}"
    if live_col in delta_df.columns and base_col in delta_df.columns:
        delta_df[f"recent_{suffix}"] = (
            delta_df[live_col].fillna(0) - delta_df[base_col].fillna(0)
        ).clip(lower=0)
    elif live_col in delta_df.columns:
        delta_df[f"recent_{suffix}"] = delta_df[live_col].fillna(0)

recent_suffix_cols = [f"recent_{s}" for s in OFFENSE_DISPLAY.values()
                      if f"recent_{s}" in delta_df.columns]
if recent_suffix_cols:
    delta_df["recent_total"] = delta_df[recent_suffix_cols].sum(axis=1)
    recent_teachers = delta_df[delta_df["recent_total"] >= min_recent].copy()

    if recent_offense_filter:
        selected_suffixes = [OFFENSE_DISPLAY[o] for o in recent_offense_filter if o in OFFENSE_DISPLAY]
        mask = delta_df[[f"recent_{s}" for s in selected_suffixes
                         if f"recent_{s}" in delta_df.columns]].sum(axis=1) >= min_recent
        recent_teachers = delta_df[mask].copy()

    ra, rb, rc_ = st.columns(3)
    ra.metric("Total Recent Offenses",   int(recent_teachers["recent_total"].sum()))
    rb.metric("Unique Teachers Affected", len(recent_teachers))
    rc_.metric("Base Period", base_period_label)

    split_rows = []
    for label, suffix in OFFENSE_DISPLAY.items():
        col = f"recent_{suffix}"
        if col in recent_teachers.columns:
            split_rows.append({
                "Offense Type": label,
                "Count":        int(recent_teachers[col].sum()),
                "Teachers":     int((recent_teachers[col] > 0).sum()),
            })
    if split_rows:
        split_df = pd.DataFrame(split_rows).sort_values("Count", ascending=False)
        fig_recent = px.bar(
            split_df, x="Count", y="Offense Type", orientation="h",
            color="Count", color_continuous_scale=["#f39c12", "#e74c3c"],
            text="Count", hover_data=["Teachers"],
        )
        fig_recent.update_traces(textposition="outside")
        fig_recent.update_layout(
            xaxis_title="Recent Offense Count", coloraxis_showscale=False, height=280
        )
        st.plotly_chart(fig_recent, use_container_width=True)

    st.markdown(f"**Teacher List — {base_period_label} → Live**")
    show_recent  = ["db_id", "teacher_name", "cd_name", rcol, "recent_total"]
    rename_recent = {
        "db_id": "DB ID", "teacher_name": "Teacher Name", "cd_name": "CD",
        rcol: "Current Rating", "recent_total": "Recent Offenses",
    }
    for label, suffix in OFFENSE_DISPLAY.items():
        col = f"recent_{suffix}"
        if col in recent_teachers.columns:
            show_recent.append(col)
            rename_recent[col] = label
    show_recent = [c for c in show_recent if c in recent_teachers.columns]
    st.dataframe(
        recent_teachers[show_recent].rename(columns=rename_recent)
        .sort_values("Recent Offenses", ascending=False).reset_index(drop=True),
        use_container_width=True, hide_index=True
    )
    st.caption(f"{len(recent_teachers)} teachers with {min_recent}+ recent offense(s)")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Total Offenses Breakdown
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📋 Total Offenses Breakdown")

with st.form("total_offense_filters"):
    t1, t2 = st.columns([2, 2])
    with t1:
        offense_type_filter = st.multiselect(
            "Offense Type",
            list(OFFENSE_DISPLAY.keys()),
            default=list(OFFENSE_DISPLAY.keys()),
        )
    with t2:
        if license_col and license_col in filtered.columns:
            lic_options_vals = ["All Licenses"] + sorted(
                filtered[license_col].dropna().astype(str).unique().tolist()
            )
        else:
            lic_options_vals = ["All Licenses"] + LICENSES
        selected_license = st.selectbox("License / Region", lic_options_vals)
    st.form_submit_button("🔍 Apply", use_container_width=False)

tot_df = filtered.copy()
if license_col and license_col in tot_df.columns and selected_license != "All Licenses":
    tot_df = tot_df[tot_df[license_col] == selected_license]

tot_rows = []
for label, suffix in OFFENSE_DISPLAY.items():
    if label not in offense_type_filter:
        continue
    col = f"{period_key}_{suffix}"
    if col in tot_df.columns:
        tot_rows.append({
            "Offense Type":      label,
            "Total Count":       int(tot_df[col].sum()),
            "Teachers Affected": int((tot_df[col] > 0).sum()),
            "Avg per Teacher":   round(tot_df[col].mean(), 2),
        })

if tot_rows:
    tot_summary = pd.DataFrame(tot_rows).sort_values("Total Count", ascending=False)
    st.dataframe(tot_summary, use_container_width=True, hide_index=True)

    fig_tot = px.bar(
        tot_summary, x="Total Count", y="Offense Type", orientation="h",
        color="Total Count", color_continuous_scale=["#f39c12", "#e74c3c"],
        text="Total Count",
    )
    fig_tot.update_traces(textposition="outside")
    fig_tot.update_layout(xaxis_title="Total Offenses", coloraxis_showscale=False, height=280)
    st.plotly_chart(fig_tot, use_container_width=True)

if not license_col:
    st.info("Add a 'License' column to your sheet to enable license-based filtering.")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Offense Breakdown (Clickable)
# ════════════════════════════════════════════════════════════════════════════
st.subheader(f"⚠️ Offense Breakdown — {period_label}")
st.caption("Click any bar to drill down and see which teachers committed that offense.")

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
        off_df, x="Total Count", y="Offense Type", orientation="h",
        color="Total Count", color_continuous_scale=["#f39c12", "#e74c3c"],
        text="Total Count", hover_data=["Teachers Affected"],
    )
    fig_off.update_traces(textposition="outside")
    fig_off.update_layout(
        xaxis_title="Total Offense Count", coloraxis_showscale=False, height=320
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
# SECTION 7 — Rating Trendline + Split
# ════════════════════════════════════════════════════════════════════════════
c1, c2 = st.columns(2)

with c1:
    st.subheader("📉 Rating Trendline")
    trend_rows = []
    for label, key in PERIODS.items():
        rc_ = f"{key}_rating"
        if rc_ in filtered.columns:
            counts = filtered[rc_].str.lower().value_counts()
            for r in ["red", "orange", "yellow", "green"]:
                trend_rows.append({"Period": label, "Rating": r.capitalize(),
                                   "Teachers": int(counts.get(r, 0))})
    if trend_rows:
        trend_df = pd.DataFrame(trend_rows)
        fig_trend = px.line(
            trend_df, x="Period", y="Teachers", color="Rating",
            color_discrete_map=RATING_COLORS, markers=True,
            category_orders={"Rating": ["Red", "Orange", "Yellow", "Green"]},
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
# SECTION 8 — Extreme Offense Makers
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🚨 Extreme Offense Makers")

c_n, c_r2 = st.columns([1, 2])
with c_n:
    top_n = st.slider("Show Top N teachers", 10, 200, 50, step=10)
with c_r2:
    extreme_ratings = st.multiselect(
        "Filter by Rating", ["Red", "Orange", "Yellow", "Green"],
        default=["Red", "Orange"], key="extreme_rating_filter"
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
# SECTION 9 — Teacher History Table
# ════════════════════════════════════════════════════════════════════════════
st.subheader("📅 Teacher History Across All Periods")
st.caption("Full view of each teacher's offense count and rating across every period.")

hist_cols  = ["db_id", "teacher_name", "cd_name"]
hist_remap = {"db_id": "DB ID", "teacher_name": "Teacher", "cd_name": "CD"}

for label, key in PERIODS.items():
    tc  = f"{key}_total_offenses"
    rc2 = f"{key}_rating"
    if tc in filtered.columns:
        hist_cols.append(tc)
        hist_remap[tc] = f"{label} Offenses"
    if rc2 in filtered.columns:
        hist_cols.append(rc2)
        hist_remap[rc2] = f"{label} Rating"

hist_cols = [c for c in hist_cols if c in filtered.columns]
st.dataframe(
    filtered[hist_cols].rename(columns=hist_remap).reset_index(drop=True),
    use_container_width=True,
)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 10 — CD Performance (Clickable)
# ════════════════════════════════════════════════════════════════════════════
st.subheader("👥 Cluster Director Performance")
st.caption("Click any CD bar to see all their teachers.")

if "cd_name" in filtered.columns and rcol in filtered.columns:
    cd_total = filtered.groupby("cd_name").size().reset_index(name="Total")
    cd_grp   = filtered.groupby(["cd_name", rcol]).size().reset_index(name="Count")
    cd_grp[rcol] = cd_grp[rcol].str.capitalize()
    cd_grp   = cd_grp[cd_grp[rcol].isin(RATING_COLORS)]
    cd_grp   = cd_grp.merge(cd_total, on="cd_name")
    cd_grp["Pct"]   = (cd_grp["Count"] / cd_grp["Total"] * 100).round(1)
    cd_grp["Label"] = cd_grp["Pct"].astype(str) + "%"

    view_toggle = st.radio("View as", ["Percentage", "Count"], horizontal=True)

    if view_toggle == "Percentage":
        fig_cd = px.bar(
            cd_grp, x="Pct", y="cd_name", color=rcol,
            orientation="h", barmode="stack", text="Label",
            color_discrete_map=RATING_COLORS,
            labels={"cd_name": "Cluster Director", rcol: "Rating", "Pct": "% of Teachers"},
            category_orders={rcol: ["Red", "Orange", "Yellow", "Green"]},
        )
        fig_cd.update_layout(xaxis_title="% of Teachers", xaxis=dict(range=[0, 100]))
    else:
        fig_cd = px.bar(
            cd_grp, x="Count", y="cd_name", color=rcol,
            orientation="h", barmode="stack", text="Count",
            color_discrete_map=RATING_COLORS,
            labels={"cd_name": "Cluster Director", rcol: "Rating"},
            category_orders={rcol: ["Red", "Orange", "Yellow", "Green"]},
        )
        fig_cd.update_layout(xaxis_title="Number of Teachers")

    fig_cd.update_traces(textposition="inside")
    fig_cd.update_layout(yaxis=dict(autorange="reversed"), yaxis_title="", legend_title="Rating")

    cd_event = st.plotly_chart(fig_cd, on_select="rerun", use_container_width=True, key="cd_perf_chart")

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
# SECTION 11 — CD Remarks & Reasons Analysis
# ════════════════════════════════════════════════════════════════════════════
st.subheader("💬 CD Remarks & Offense Reasons")
st.caption(
    "This section reads the reasons your CDs have logged against each teacher's miss. "
    "Standard categories: **Personal Reason, Internet Issue, Teacher Lapse, "
    "Technical Issue, Emergency / Health, Student No Show, System Error, Other.**"
)

if remarks_col and remarks_col in filtered.columns:
    rem1, rem2 = st.columns([2, 2])
    with rem1:
        remarks_period = st.selectbox(
            "Period for remarks analysis",
            list(PERIODS.keys()), index=5, key="rem_period"
        )
    with rem2:
        min_off_remarks = st.number_input(
            "Min total offenses to include", min_value=0, value=1, step=1
        )

    rem_key  = PERIODS[remarks_period]
    rem_tcol = f"{rem_key}_total_offenses"
    rem_df   = filtered.copy()
    if rem_tcol in rem_df.columns:
        rem_df = rem_df[pd.to_numeric(rem_df[rem_tcol], errors="coerce") >= min_off_remarks]

    rem_df = rem_df[rem_df[remarks_col].notna()]
    rem_df = rem_df[rem_df[remarks_col].astype(str).str.strip().str.lower() != ""]
    rem_df = rem_df[rem_df[remarks_col].astype(str).str.strip().str.lower() != "nan"]

    st.markdown(f"**{len(rem_df)} teachers with remarks logged for {remarks_period}**")

    # ── Reason frequency — primary chart ─────────────────────────────────
    reason_counts = rem_df[remarks_col].astype(str).str.strip().value_counts().reset_index()
    reason_counts.columns = ["Reason", "Teachers"]

    # Flag which reasons match standard categories
    std_lower = [r.lower() for r in REASON_CATEGORIES]
    reason_counts["Category"] = reason_counts["Reason"].apply(
        lambda x: "Standard" if x.lower() in std_lower else "Custom / Free Text"
    )

    fig_rem = px.bar(
        reason_counts, x="Teachers", y="Reason", orientation="h",
        color="Category",
        color_discrete_map={"Standard": "#3498db", "Custom / Free Text": "#e67e22"},
        text="Teachers",
        category_orders={"Reason": reason_counts["Reason"].tolist()},
    )
    fig_rem.update_traces(textposition="outside")
    fig_rem.update_layout(
        xaxis_title="Number of Teachers",
        yaxis=dict(autorange="reversed"),
        legend_title="Reason Type",
        height=max(320, len(reason_counts) * 42),
    )
    st.plotly_chart(fig_rem, use_container_width=True)

    st.caption(
        "🔵 Blue = standard category  |  🟠 Orange = free-text entry from CD. "
        "Ask your CDs to use the standard categories listed above for cleaner reporting."
    )

    # ── CD-wise breakdown ────────────────────────────────────────────────
    st.markdown("**Which CD's teachers gave each reason:**")
    cd_reason_df = (
        rem_df.groupby([remarks_col, "cd_name"]).size()
        .reset_index(name="Teachers")
        .rename(columns={remarks_col: "Reason", "cd_name": "CD Name"})
    )
    cd_reason_df = cd_reason_df.sort_values(["Reason", "Teachers"], ascending=[True, False])

    fig_cd_rem = px.bar(
        cd_reason_df, x="Teachers", y="Reason", color="CD Name",
        orientation="h", barmode="stack",
        height=max(350, len(cd_reason_df["Reason"].unique()) * 50),
    )
    fig_cd_rem.update_layout(
        xaxis_title="Number of Teachers",
        yaxis=dict(autorange="reversed"),
        legend_title="Cluster Director",
    )
    st.plotly_chart(fig_cd_rem, use_container_width=True, key="cd_remarks_chart")

    # ── Drill into one reason ────────────────────────────────────────────
    st.markdown("**See all teachers for a specific reason:**")
    reason_select = st.selectbox(
        "Select reason", ["— select —"] + reason_counts["Reason"].tolist()
    )
    if reason_select != "— select —":
        reason_teachers = rem_df[rem_df[remarks_col].astype(str).str.strip() == reason_select]
        show_rem = ["db_id", "teacher_name", "cd_name", rcol]
        if rem_tcol in reason_teachers.columns:
            show_rem.append(rem_tcol)
        show_rem = [c for c in show_rem if c in reason_teachers.columns]
        rename_rem = {
            "db_id": "DB ID", "teacher_name": "Teacher", "cd_name": "CD",
            rcol: "Rating", rem_tcol: "Total Offenses",
        }
        st.markdown(f"**{len(reason_teachers)} teachers — {reason_select}:**")
        st.dataframe(
            reason_teachers[show_rem].rename(columns=rename_rem).reset_index(drop=True),
            use_container_width=True, hide_index=True
        )
else:
    st.info(
        "CD Remarks column not yet mapped. In the sidebar under **⚙️ Column Settings**, "
        "select the column that contains your CD remarks or reasons."
    )
    st.markdown("**Standard reason categories your CDs should use:**")
    st.dataframe(
        pd.DataFrame({"Category": REASON_CATEGORIES}),
        use_container_width=True, hide_index=True
    )

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# SECTION 12 — Teacher Profile Search
# ════════════════════════════════════════════════════════════════════════════
st.subheader("🔍 Teacher Profile")
st.caption("Search by teacher name or DB ID to see their full history and live offense breakdown.")

search = st.text_input("Search", placeholder="Type a name or DB ID...")

if search:
    mask = (
        filtered["teacher_name"].astype(str).str.contains(search, case=False, na=False) |
        filtered["db_id"].astype(str).str.contains(search, case=False, na=False)
    )
    results = filtered[mask]

    if len(results) == 0:
        st.warning("No teacher found. Try a different name or DB ID.")
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
                    if comms_app_url:
                        st.markdown(f"[📨 Open in Communications App]({comms_app_url})")
                    else:
                        st.caption("Add your Communications App URL in the sidebar to enable this link.")

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
