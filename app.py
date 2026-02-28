import streamlit as st
import pandas as pd
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

# ── App header ───────────────────────────────────────────────────────────────
st.title("📢 QMath Teacher Communications Dashboard")
tab1, tab2, tab3 = st.tabs(["📁 Upload Data", "📊 Filter & Send", "📋 Message Log"])

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
            c1, c2 = st.columns(2)
            with c1:
                name_col    = st.selectbox("📛 Teacher Name",    cols)
                phone_col   = st.selectbox("📱 Phone Number",    cols)
            with c2:
                offense_col = st.selectbox("⚠️ Offense Type",   cols)
                date_col    = st.selectbox("📅 Offense Date",    cols)

            optional_cols = ["— skip —"] + cols
            cd_col = st.selectbox("👤 Cluster Director (optional)", optional_cols)

            if st.button("✅ Save & Go to Dashboard", type="primary"):
                st.session_state["df"]      = df
                st.session_state["col_map"] = {
                    "name":    name_col,
                    "phone":   phone_col,
                    "offense": offense_col,
                    "date":    date_col,
                    "cd":      cd_col if cd_col != "— skip —" else None,
                }
                st.success("Data saved! Switch to the **Filter & Send** tab.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Filter & Send
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    if "df" not in st.session_state:
        st.info("Upload your data in the **Upload Data** tab first.")
    else:
        df      = st.session_state["df"]
        col_map = st.session_state["col_map"]

        st.header("Filter Teachers")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            all_offenses    = df[col_map["offense"]].dropna().unique().tolist()
            offense_filter  = st.multiselect("Offense Type", all_offenses, default=all_offenses)
        with c2:
            filter_date = st.date_input(
                "Offense Date",
                value=(datetime.today() - timedelta(days=1)).date()
            )
        with c3:
            exact_date = st.checkbox("Exact date only", value=True)

        # Apply filters
        filtered = df[df[col_map["offense"]].isin(offense_filter)].copy()
        try:
            filtered[col_map["date"]] = pd.to_datetime(filtered[col_map["date"]], dayfirst=True, errors="coerce")
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
            st.caption("Each offense type uses its own template. Edit any template below. "
                       "Use `{teacher_name}`, `{offense_type}`, `{date}` as variables.")

            # Show editable template for each offense type in the filtered set
            templates = {}
            for offense in filtered[col_map["offense"]].dropna().unique():
                default = DEFAULT_TEMPLATES.get(offense,
                    "Hi {teacher_name}, you have been marked for *{offense_type}* on {date}. "
                    "Please take corrective action. For queries, contact your Cluster Director.")
                templates[offense] = st.text_area(
                    f"Template — {offense}",
                    value=default,
                    height=100,
                    key=f"tpl_{offense}"
                )

            # Preview
            sample = filtered.iloc[0]
            sample_offense = sample[col_map["offense"]]
            sample_date    = str(sample[col_map["date"]])[:10] if col_map["date"] else "N/A"
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
                        phone    = str(row[col_map["phone"]]).strip()
                        if not phone.startswith("+"):
                            phone = "+" + phone

                        msg_body = templates.get(offense, DEFAULT_TEMPLATES.get(offense, "")).format(
                            teacher_name=teacher,
                            offense_type=offense,
                            date=date_str
                        )

                        try:
                            msg = client.messages.create(
                                from_=FROM_NUMBER,
                                to=f"whatsapp:{phone}",
                                body=msg_body
                            )
                            log.append({
                                "Teacher": teacher, "Phone": phone,
                                "Offense": offense, "Date": date_str,
                                "Message": msg_body, "Status": "Sent",
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "SID": msg.sid,
                            })
                            status.success(f"Sent to {teacher}")
                        except Exception as e:
                            log.append({
                                "Teacher": teacher, "Phone": phone,
                                "Offense": offense, "Date": date_str,
                                "Message": msg_body, "Status": f"Failed: {e}",
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "SID": "",
                            })
                            status.error(f"Failed for {teacher}: {e}")

                        progress.progress((i + 1) / len(filtered))

                    st.session_state["log"] = st.session_state.get("log", []) + log
                    sent   = sum(1 for l in log if l["Status"] == "Sent")
                    failed = len(log) - sent
                    st.success(f"✅ Done — {sent} sent, {failed} failed. Check the **Message Log** tab.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Message Log
# ════════════════════════════════════════════════════════════════════════════
with tab3:
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
