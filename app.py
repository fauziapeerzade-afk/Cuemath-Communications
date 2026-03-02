import streamlit as st
import pandas as pd
import plotly.express as px
from twilio.rest import Client
from datetime import datetime, timedelta

st.set_page_config(page_title="QMath Communications", layout="wide", page_icon="📢")

# ── Twilio credentials ──────────────────────────────────────────────────────
try:
    ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
    AUTH_TOKEN  = st.secrets["TWILIO_AUTH_TOKEN"]
    FROM_NUMBER = st.secrets["TWILIO_WHATSAPP_NUMBER"]
except Exception:
    st.sidebar.title("⚙️ Twilio Settings")
    ACCOUNT_SID = st.sidebar.text_input("Account SID", type="password")
    AUTH_TOKEN  = st.sidebar.text_input("Auth Token",  type="password")
    FROM_NUMBER = st.sidebar.text_input("WhatsApp Number", placeholder="whatsapp:+14155238886")

# ── Default offense templates ────────────────────────────────────────────────
DEFAULT_TEMPLATES = {
    "Class No Show":
        "Hi {teacher_name}, this is to inform you that you have been marked for a *Class No Show* on {date}. "
        "Please ensure you attend all scheduled classes. Repeated offenses may impact your compliance rating. "
        "For queries, contact your Cluster Director.",
    "Class Late Login":
        "Hi {teacher_name}, you have been marked for *Class Late Login* on {date}. "
        "Please ensure you log in on time for all your sessions. "
        "For queries, contact your Cluster Director.",
    "Trial No Show":
        "Hi {teacher_name}, you have been marked for a *Trial No Show* on {date}. "
        "Trials are critical for student acquisition. Please ensure you attend all assigned trials. "
        "For queries, contact your Cluster Director.",
    "Trial Late Login":
        "Hi {teacher_name}, you have been marked for *Trial Late Login* on {date}. "
        "Please ensure timely login for all trial sessions. "
        "For queries, contact your Cluster Director.",
    "Trial Not Acknowledged":
        "Hi {teacher_name}, you have a *Trial Not Acknowledged* from {date}. "
        "Please acknowledge all assigned trials promptly to avoid further offenses. "
        "For queries, contact your Cluster Director.",
}

BRAND_COLOR = "#FF4B4B"

# ── App header ───────────────────────────────────────────────────────────────
st.title("📢 QMath Teacher Communications Dashboard")
tab1, tab2, tab3, tab4 = st.tabs([
    "📁 Upload Data",
    "📊 Analytics Dashboard",
    "📤 Filter & Send",
    "📋 Message Log"
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload Data
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Upload Compliance Data")
    st.caption("Upload any CSV or Excel file. You'll map your columns in the next step.")

    uploaded_file = st.file_uploader("Choose file", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") \
                 else pd.read_excel(uploaded_file)
            st.success(f"Loaded **{len(df)} rows** and **{len(df.columns)} columns**")
            st.dataframe(df.head(5), use_container_width=True)

            st.divider()
            st.subheader("Map Your Columns")
            st.caption("Tell us which column contains each key piece of information.")

            cols = df.columns.tolist()
            optional_cols = ["— skip —"] + cols

            c1, c2 = st.columns(2)
            with c1:
                name_col    = st.selectbox("📛 Teacher Name",  cols)
                phone_col   = st.selectbox("📱 Phone Number",  cols)
                offense_col = st.selectbox("⚠️ Offense Type", cols)
            with c2:
                date_col = st.selectbox("📅 Offense Date",  cols)
                cd_col   = st.selectbox("👤 Cluster Director (optional)", optional_cols)
                dbid_col = st.selectbox("🆔 Teacher DBID (optional)",     optional_cols)

            st.divider()
            st.caption("**CD Follow-up Columns** — map these once your CDs start logging call outcomes")
            c3, c4, c5 = st.columns(3)
            with c3:
                cd_connected_col = st.selectbox("📞 CD Connected Y/N (optional)", optional_cols)
            with c4:
                reason_cat_col   = st.selectbox("🏷️ Offense Reason Category (optional)", optional_cols)
            with c5:
                reason_notes_col = st.selectbox("📝 Offense Reason Free Text (optional)", optional_cols)

            if st.button("✅ Save & Go to Dashboard", type="primary"):
                st.session_state["df"]      = df
                st.session_state["col_map"] = {
                    "name":         name_col,
                    "phone":        phone_col,
                    "offense":      offense_col,
                    "date":         date_col,
                    "cd":           cd_col           if cd_col           != "— skip —" else None,
                    "dbid":         dbid_col         if dbid_col         != "— skip —" else None,
                    "cd_connected": cd_connected_col if cd_connected_col != "— skip —" else None,
                    "reason_cat":   reason_cat_col   if reason_cat_col   != "— skip —" else None,
                    "reason_notes": reason_notes_col if reason_notes_col != "— skip —" else None,
                }
                st.success("Data saved! Switch to the **Analytics Dashboard** tab.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Analytics Dashboard
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    if "df" not in st.session_state:
        st.info("Upload your data in the **Upload Data** tab first.")
    else:
        df      = st.session_state["df"]
        col_map = st.session_state["col_map"]

        # Parse dates
        df_dash = df.copy()
        df_dash[col_map["date"]] = pd.to_datetime(
            df_dash[col_map["date"]], dayfirst=True, errors="coerce"
        )
        df_dash = df_dash.dropna(subset=[col_map["date"]])

        if df_dash.empty:
            st.warning(
                "No valid dates found in the date column you mapped. "
                "Please check that the column contains dates (e.g. 2026-02-28 or 28/02/2026)."
            )
            st.stop()

        # ── Dashboard Filters ────────────────────────────────────────────────
        st.subheader("Filters")
        f1, f2, f3 = st.columns([2, 2, 2])

        with f1:
            try:
                min_date = df_dash[col_map["date"]].min().date()
                max_date = df_dash[col_map["date"]].max().date()
            except Exception:
                from datetime import date as dt_date
                min_date = dt_date.today()
                max_date = dt_date.today()
            date_range = st.date_input("Date Range", value=(min_date, max_date))

        with f2:
            offense_options  = df_dash[col_map["offense"]].dropna().unique().tolist()
            selected_offenses = st.multiselect("Offense Type", offense_options, default=offense_options)

        with f3:
            if col_map.get("cd"):
                cd_options  = ["All CDs"] + sorted(df_dash[col_map["cd"]].dropna().unique().tolist())
                selected_cd = st.selectbox("Cluster Director", cd_options)
            else:
                selected_cd = "All CDs"

        # Apply filters
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range[0]

        filtered_dash = df_dash[
            (df_dash[col_map["date"]].dt.date >= start_date) &
            (df_dash[col_map["date"]].dt.date <= end_date)   &
            (df_dash[col_map["offense"]].isin(selected_offenses))
        ].copy()

        if selected_cd != "All CDs" and col_map.get("cd"):
            filtered_dash = filtered_dash[filtered_dash[col_map["cd"]] == selected_cd]

        st.divider()

        # ── KPI Cards ────────────────────────────────────────────────────────
        today          = datetime.today()
        this_month     = filtered_dash[filtered_dash[col_map["date"]].dt.month == today.month]
        four_weeks_ago = today - timedelta(weeks=4)
        last_4w        = filtered_dash[filtered_dash[col_map["date"]] >= four_weeks_ago]
        unique_teachers = filtered_dash[col_map["name"]].nunique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Offenses",    len(filtered_dash))
        k2.metric("This Month",        len(this_month))
        k3.metric("Last 4 Weeks",      len(last_4w))
        k4.metric("Teachers Affected", unique_teachers)

        st.divider()

        # ── Trend Charts ─────────────────────────────────────────────────────
        c_left, c_right = st.columns(2)

        with c_left:
            st.subheader("Monthly Trend")
            monthly = filtered_dash.copy()
            monthly["Month"] = monthly[col_map["date"]].dt.to_period("M").astype(str)
            monthly_counts   = monthly.groupby("Month").size().reset_index(name="Offenses")
            fig_m = px.bar(
                monthly_counts, x="Month", y="Offenses",
                color_discrete_sequence=[BRAND_COLOR],
                text="Offenses"
            )
            fig_m.update_traces(textposition="outside")
            fig_m.update_layout(xaxis_title="", yaxis_title="Offenses", showlegend=False)
            st.plotly_chart(fig_m, use_container_width=True)

        with c_right:
            st.subheader("Weekly Trend (Last 4 Weeks)")
            weekly = last_4w.copy()
            if len(weekly) > 0:
                weekly["Week"] = weekly[col_map["date"]].dt.to_period("W").astype(str)
                weekly_counts  = weekly.groupby("Week").size().reset_index(name="Offenses")
                fig_w = px.bar(
                    weekly_counts, x="Week", y="Offenses",
                    color_discrete_sequence=[BRAND_COLOR],
                    text="Offenses"
                )
                fig_w.update_traces(textposition="outside")
                fig_w.update_layout(xaxis_title="", yaxis_title="Offenses", showlegend=False)
                st.plotly_chart(fig_w, use_container_width=True)
            else:
                st.info("No data in the last 4 weeks.")

        st.divider()

        # ── Breakdown Charts ─────────────────────────────────────────────────
        c_left2, c_right2 = st.columns(2)

        with c_left2:
            st.subheader("Offense Type Breakdown")
            offense_counts = (
                filtered_dash[col_map["offense"]]
                .value_counts()
                .reset_index()
            )
            offense_counts.columns = ["Offense Type", "Count"]
            fig_o = px.bar(
                offense_counts, x="Count", y="Offense Type",
                orientation="h",
                color_discrete_sequence=[BRAND_COLOR],
                text="Count"
            )
            fig_o.update_traces(textposition="outside")
            fig_o.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="Number of Offenses", showlegend=False)
            st.plotly_chart(fig_o, use_container_width=True)

        with c_right2:
            if col_map.get("cd"):
                st.subheader("Offenses by Cluster Director")
                cd_counts = (
                    filtered_dash[col_map["cd"]]
                    .value_counts()
                    .reset_index()
                )
                cd_counts.columns = ["Cluster Director", "Count"]
                fig_cd = px.bar(
                    cd_counts, x="Count", y="Cluster Director",
                    orientation="h",
                    color_discrete_sequence=[BRAND_COLOR],
                    text="Count"
                )
                fig_cd.update_traces(textposition="outside")
                fig_cd.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="", showlegend=False)
                st.plotly_chart(fig_cd, use_container_width=True)
            else:
                st.info("Map the Cluster Director column in Upload Data to see this chart.")

        # ── CD Follow-up & Reason Analysis ───────────────────────────────────
        if col_map.get("cd_connected") or col_map.get("reason_cat"):
            st.divider()
            st.subheader("CD Follow-up Analysis")
            c_fu1, c_fu2 = st.columns(2)

            with c_fu1:
                if col_map.get("cd_connected"):
                    st.markdown("**CD Connection Coverage**")
                    connected_counts = (
                        filtered_dash[col_map["cd_connected"]]
                        .fillna("Not Updated")
                        .value_counts()
                        .reset_index()
                    )
                    connected_counts.columns = ["Status", "Count"]
                    fig_conn = px.pie(
                        connected_counts, names="Status", values="Count",
                        color_discrete_sequence=["#2ecc71", "#e74c3c", "#95a5a6"]
                    )
                    fig_conn.update_traces(textinfo="percent+label")
                    st.plotly_chart(fig_conn, use_container_width=True)

            with c_fu2:
                if col_map.get("reason_cat"):
                    st.markdown("**Offense Reasons (from CD Calls)**")
                    reason_data = filtered_dash[
                        filtered_dash[col_map["reason_cat"]].notna() &
                        (filtered_dash[col_map["reason_cat"]].astype(str).str.strip() != "")
                    ]
                    if len(reason_data) > 0:
                        reason_counts = (
                            reason_data[col_map["reason_cat"]]
                            .value_counts()
                            .reset_index()
                        )
                        reason_counts.columns = ["Reason", "Count"]
                        fig_reason = px.bar(
                            reason_counts, x="Count", y="Reason",
                            orientation="h",
                            color_discrete_sequence=[BRAND_COLOR],
                            text="Count"
                        )
                        fig_reason.update_traces(textposition="outside")
                        fig_reason.update_layout(
                            yaxis=dict(autorange="reversed"),
                            xaxis_title="Number of Cases",
                            showlegend=False
                        )
                        st.plotly_chart(fig_reason, use_container_width=True)
                    else:
                        st.info("No reason data logged yet.")

        st.divider()

        # ── Teacher Lookup ───────────────────────────────────────────────────
        st.subheader("Teacher Lookup")
        st.caption("Search by teacher name or DBID to see all their offenses and CD notes.")
        search = st.text_input("Search", placeholder="Type a name or DBID...")

        display_cols = [col_map["name"]]
        if col_map.get("dbid"):
            display_cols.append(col_map["dbid"])
        display_cols.append(col_map["phone"])
        display_cols.append(col_map["offense"])
        display_cols.append(col_map["date"])
        if col_map.get("cd"):
            display_cols.append(col_map["cd"])
        if col_map.get("cd_connected"):
            display_cols.append(col_map["cd_connected"])
        if col_map.get("reason_cat"):
            display_cols.append(col_map["reason_cat"])
        if col_map.get("reason_notes"):
            display_cols.append(col_map["reason_notes"])

        if search:
            name_match = filtered_dash[col_map["name"]].astype(str).str.contains(search, case=False, na=False)
            dbid_match = (
                filtered_dash[col_map["dbid"]].astype(str).str.contains(search, case=False, na=False)
                if col_map.get("dbid") else pd.Series(False, index=filtered_dash.index)
            )
            result = filtered_dash[name_match | dbid_match]
        else:
            result = filtered_dash

        st.dataframe(
            result[display_cols].sort_values(col_map["date"], ascending=False),
            use_container_width=True
        )
        st.caption(f"Showing {len(result)} offense record(s)")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Filter & Send
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    if "df" not in st.session_state:
        st.info("Upload your data in the **Upload Data** tab first.")
    else:
        df      = st.session_state["df"]
        col_map = st.session_state["col_map"]

        st.header("Filter Teachers & Send Messages")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            all_offenses   = df[col_map["offense"]].dropna().unique().tolist()
            offense_filter = st.multiselect("Offense Type", all_offenses, default=all_offenses)
        with c2:
            filter_date = st.date_input(
                "Offense Date",
                value=(datetime.today() - timedelta(days=1)).date()
            )
        with c3:
            exact_date = st.checkbox("Exact date only", value=True)

        filtered = df[df[col_map["offense"]].isin(offense_filter)].copy()
        try:
            filtered[col_map["date"]] = pd.to_datetime(
                filtered[col_map["date"]], dayfirst=True, errors="coerce"
            )
            if exact_date:
                filtered = filtered[filtered[col_map["date"]].dt.date == filter_date]
            else:
                filtered = filtered[filtered[col_map["date"]].dt.date >= filter_date]
        except Exception:
            pass

        st.subheader(f"Filtered: {len(filtered)} teacher(s)")
        st.dataframe(filtered, use_container_width=True)

        if len(filtered) == 0:
            st.warning("No teachers match the current filters.")
        else:
            st.divider()
            st.subheader("📝 Message Templates")
            st.caption("Each offense type uses its own template. Edit below. "
                       "Use {teacher_name}, {offense_type}, {date} as variables.")

            templates = {}
            for offense in filtered[col_map["offense"]].dropna().unique():
                default = DEFAULT_TEMPLATES.get(offense,
                    "Hi {teacher_name}, you have been marked for *{offense_type}* on {date}. "
                    "Please take corrective action. For queries, contact your Cluster Director.")
                templates[offense] = st.text_area(
                    f"Template — {offense}", value=default, height=100, key=f"tpl_{offense}"
                )

            sample         = filtered.iloc[0]
            sample_offense = sample[col_map["offense"]]
            sample_date    = str(sample[col_map["date"]])[:10]
            preview_msg    = templates[sample_offense].format(
                teacher_name=sample[col_map["name"]],
                offense_type=sample_offense,
                date=sample_date
            )
            st.info(f"**Preview** (for {sample[col_map['name']]}):\n\n{preview_msg}")

            st.divider()
            if st.button(f"🚀 Send to {len(filtered)} teacher(s)", type="primary"):
                if not ACCOUNT_SID or not AUTH_TOKEN or not FROM_NUMBER:
                    st.error("Twilio credentials missing. Add them in the sidebar.")
                else:
                    client   = Client(ACCOUNT_SID, AUTH_TOKEN)
                    log      = []
                    progress = st.progress(0)
                    status   = st.empty()

                    for i, (_, row) in enumerate(filtered.iterrows()):
                        teacher  = str(row[col_map["name"]])
                        offense  = str(row[col_map["offense"]])
                        date_str = str(row[col_map["date"]])[:10]

                        raw_phone = row[col_map["phone"]]
                        try:
                            phone = str(int(float(
                                str(raw_phone).strip().replace(" ", "").replace("-", "")
                            )))
                        except Exception:
                            phone = str(raw_phone).strip().replace(" ", "").replace("-", "")
                        if not phone.startswith("+"):
                            phone = "+" + phone

                        dbid = str(row[col_map["dbid"]]) if col_map.get("dbid") else "N/A"

                        msg_body = templates.get(offense, DEFAULT_TEMPLATES.get(offense, "")).format(
                            teacher_name=teacher, offense_type=offense, date=date_str
                        )

                        try:
                            msg = client.messages.create(
                                from_=FROM_NUMBER, to=f"whatsapp:{phone}", body=msg_body
                            )
                            log.append({
                                "DBID": dbid, "Teacher": teacher, "Phone": phone,
                                "Offense": offense, "Date": date_str,
                                "Message": msg_body, "Status": "Sent",
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "SID": msg.sid,
                            })
                            status.success(f"Sent to {teacher} (DBID: {dbid})")
                        except Exception as e:
                            log.append({
                                "DBID": dbid, "Teacher": teacher, "Phone": phone,
                                "Offense": offense, "Date": date_str,
                                "Message": msg_body, "Status": f"Failed: {e}",
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "SID": "",
                            })
                            status.error(f"Failed for {teacher} (DBID: {dbid}): {e}")

                        progress.progress((i + 1) / len(filtered))

                    st.session_state["log"] = st.session_state.get("log", []) + log
                    sent   = sum(1 for l in log if l["Status"] == "Sent")
                    failed = len(log) - sent
                    st.success(f"✅ Done — {sent} sent, {failed} failed. Check the **Message Log** tab.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Message Log
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Message Log")
    if "log" not in st.session_state or not st.session_state["log"]:
        st.info("No messages sent yet in this session.")
    else:
        log_df = pd.DataFrame(st.session_state["log"])
        st.dataframe(log_df, use_container_width=True)

        csv_data = log_df.to_csv(index=False)
        st.download_button(
            "⬇️ Download Log as CSV",
            data=csv_data,
            file_name=f"qmath_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
