# trading_journal_v1_updated_with_sheets.py
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Initialize journal (in-memory)
# ----------------------------
if "journal" not in st.session_state:
    st.session_state.journal = []

# ----------------------------
# Google Sheets Setup
# ----------------------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "service_account.json"  # Path to your JSON
SPREADSHEET_NAME = "Trading Journal"

try:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(SPREADSHEET_NAME).sheet1
    gsheet_available = True
except Exception as e:
    st.warning(f"Google Sheets not available: {e}")
    gsheet_available = False

# Load existing trades from Google Sheets
if gsheet_available:
    try:
        records = sheet.get_all_records()
        if records:
            st.session_state.journal = records
    except Exception as e:
        st.warning(f"Failed to load from Google Sheets: {e}")

# ----------------------------
# Confluence Scoring Function
# ----------------------------
def calculate_confluence(planned_direction, htf_trends, ltf_trends, ltf_expected, fib_level, candle_type,
                         session, structure_change, ob_sd_conflict, liquidity_sweep):
    score = 0
    pos_details = {}
    neg_details = {}

    # Weights
    weights = {
        "HTF Alignment": 20,
        "LTF Alignment": 25,
        "Planned Direction": 15,
        "Expected LTF Structure": 10,
        "Fib Level Tapped": 10,
        "Entry Candle Confirmation": 10,
        "OB/SD Conflict": -10,
        "Liquidity Sweep": -10,
        "Session Favorability": 20
    }

    # Helper function to check trend alignment with planned direction
    def aligns(trend, direction):
        if direction == "Buy":
            return trend == "Bullish"
        elif direction == "Sell":
            return trend == "Bearish"
        return False

    # --- Planned Direction ---
    if planned_direction not in ["Buy", "Sell"]:
        planned_direction = "None"

    # --- HTF Alignment (20%) ---
    htf_timeframes = ["Weekly", "Daily", "4H"]
    htf_match_count = 0
    for tf in htf_timeframes:
        if aligns(htf_trends.get(tf, "None"), planned_direction):
            htf_match_count += 1
    if htf_match_count >= 2:
        pos_details["HTF Alignment"] = weights["HTF Alignment"]
        score += weights["HTF Alignment"]
    else:
        pos_details["HTF Alignment"] = 0

    # --- LTF Alignment (25%) ---
    ltf_major = ["1H", "30M"]
    ltf_minor = ["15M", "5M"]
    ltf_major_aligned = all(aligns(ltf_trends.get(tf, "None"), planned_direction) for tf in ltf_major)
    ltf_major_misaligned = all(not aligns(ltf_trends.get(tf, "None"), planned_direction) for tf in ltf_major)

    ltf_score = 0
    ltf_pos = 0
    ltf_neg = 0

    if ltf_major_aligned:
        ltf_pos += weights["LTF Alignment"] * 0.7
        for tf in ltf_minor:
            if aligns(ltf_trends.get(tf, "None"), planned_direction):
                ltf_pos += (weights["LTF Alignment"] * 0.3) / 2
            else:
                ltf_neg += (weights["LTF Alignment"] * 0.3) / 2
    elif ltf_major_misaligned:
        ltf_neg += weights["LTF Alignment"] * 0.7
        for tf in ltf_minor:
            if aligns(ltf_trends.get(tf, "None"), planned_direction):
                ltf_pos += (weights["LTF Alignment"] * 0.3) / 2
            else:
                ltf_neg += (weights["LTF Alignment"] * 0.3) / 2
    else:
        for tf in ltf_minor:
            if aligns(ltf_trends.get(tf, "None"), planned_direction):
                ltf_pos += (weights["LTF Alignment"] * 0.3) / 2
            else:
                ltf_neg += (weights["LTF Alignment"] * 0.3) / 2

    ltf_score = ltf_pos - ltf_neg
    pos_details["LTF Alignment"] = round(max(ltf_score, 0), 2)
    neg_details["LTF Alignment"] = round(min(ltf_score, 0), 2)
    score += ltf_score

    # --- Planned Trade Direction (15%) ---
    if planned_direction != "None":
        if htf_match_count >= 2:
            pos_details["Planned Trade Direction Alignment"] = weights["Planned Direction"]
            score += weights["Planned Direction"]
        else:
            neg_details["Planned Trade Direction Alignment"] = -weights["Planned Direction"]
            score -= weights["Planned Direction"]
    else:
        pos_details["Planned Trade Direction Alignment"] = 0

    # --- Expected LTF Structure (10%) ---
    structure_score = 0
    structure_pos = 0
    structure_neg = 0

    def score_structure(tf):
        actual = ltf_expected.get(f"{tf} Expected", "None")
        if actual == "None":
            return 0
        if planned_direction == "Buy":
            if actual == "HL":
                return weights["Expected LTF Structure"] * 0.4 if tf in ["1H", "30M"] else weights["Expected LTF Structure"] * 0.15
            elif actual == "HH":
                return weights["Expected LTF Structure"] * 0.3 if tf in ["1H", "30M"] else weights["Expected LTF Structure"] * 0.1
            elif actual in ["LH", "LL"]:
                return -weights["Expected LTF Structure"] * 0.4 if tf in ["1H", "30M"] else -weights["Expected LTF Structure"] * 0.15
            else:
                return 0
        elif planned_direction == "Sell":
            if actual == "LH":
                return weights["Expected LTF Structure"] * 0.4 if tf in ["1H", "30M"] else weights["Expected LTF Structure"] * 0.15
            elif actual == "LL":
                return weights["Expected LTF Structure"] * 0.3 if tf in ["1H", "30M"] else weights["Expected LTF Structure"] * 0.1
            elif actual in ["HL", "HH"]:
                return -weights["Expected LTF Structure"] * 0.4 if tf in ["1H", "30M"] else -weights["Expected LTF Structure"] * 0.15
            else:
                return 0
        return 0

    for tf in ["1H", "30M", "15M", "5M"]:
        val = score_structure(tf)
        if val > 0:
            structure_pos += val
        else:
            structure_neg += val

    structure_score = structure_pos + structure_neg
    pos_details["Expected LTF Structure"] = round(structure_pos, 2)
    neg_details["Expected LTF Structure"] = round(structure_neg, 2)
    score += structure_score

    # --- Fib Level Tapped (10%) ---
    if fib_level != "None":
        pos_details["Fib Level Tapped"] = weights["Fib Level Tapped"]
        score += weights["Fib Level Tapped"]
    else:
        neg_details["Fib Level Missed"] = -weights["Fib Level Tapped"]
        score -= weights["Fib Level Tapped"]

    # --- Entry Candle Confirmation (10%) ---
    if candle_type != "None":
        pos_details["Entry Candle Confirmation"] = weights["Entry Candle Confirmation"]
        score += weights["Entry Candle Confirmation"]
    else:
        neg_details["Entry Candle Failed"] = -weights["Entry Candle Confirmation"]
        score -= weights["Entry Candle Confirmation"]

    # --- OB / SD Conflict (-10%) ---
    if ob_sd_conflict:
        neg_details["OB/SD Conflict"] = weights["OB/SD Conflict"]
        score -= weights["OB/SD Conflict"]
    else:
        pos_details["OB/SD Clear"] = abs(weights["OB/SD Conflict"])
        score += abs(weights["OB/SD Conflict"])

    # --- Liquidity Sweep (-10%) ---
    if liquidity_sweep:
        neg_details["Liquidity Sweep"] = weights["Liquidity Sweep"]
        score -= weights["Liquidity Sweep"]
    else:
        pos_details["No Liquidity Sweep"] = abs(weights["Liquidity Sweep"])
        score += abs(weights["Liquidity Sweep"])

    # --- Session Favorability (20%) ---
    if session != "None":
        pos_details["Session Favorability"] = weights["Session Favorability"]
        score += weights["Session Favorability"]
    else:
        neg_details["Session Weak"] = -weights["Session Favorability"]
        score -= weights["Session Favorability"]

    # --- Structure Change (against bias) ---
    if structure_change:
        neg_details["Structure Change"] = -10
        score -= 10
    else:
        pos_details["No Structure Change"] = 10
        score += 10

    score = max(min(score, 100), 0)
    return round(score,2), pos_details, neg_details

# ----------------------------
# Streamlit UI
# ----------------------------
st.title("🔥 Trading Journal & Confluence AI - Version 1 (Updated Timeframes & Scoring)")

st.header("1️⃣ New Trade Entry")
trade_number = st.selectbox("Which Trade Number is This?", ["1", "2", "3", "4", "5"])

with st.form("new_trade_form"):
    st.subheader("HTF Trend Alignment")
    htf_trends = {
        "Weekly": st.selectbox("Weekly Trend", ["None", "Bullish", "Bearish"]),
        "Daily": st.selectbox("Daily Trend", ["None", "Bullish", "Bearish"]),
        "4H": st.selectbox("4H Trend", ["None", "Bullish", "Bearish"])
    }

    st.subheader("LTF Structure Alignment")
    ltf_trends = {
        "1H": st.selectbox("1H Trend", ["None", "Bullish", "Bearish"]),
        "30M": st.selectbox("30M Trend", ["None", "Bullish", "Bearish"]),
        "15M": st.selectbox("15M Trend", ["None", "Bullish", "Bearish"]),
        "5M": st.selectbox("5M Trend", ["None", "Bullish", "Bearish"])
    }

    ltf_expected = {}
    ltf_expected["1H Expected"] = st.selectbox("1H Expected Structure", ["None", "HH", "HL", "LH", "LL"])
    ltf_expected["30M Expected"] = st.selectbox("30M Expected Structure", ["None", "HH", "HL", "LH", "LL"])
    ltf_expected["15M Expected"] = st.selectbox("15M Expected Structure", ["None", "HH", "HL", "LH", "LL"])
    ltf_expected["5M Expected"] = st.selectbox("5M Expected Structure", ["None", "HH", "HL", "LH", "LL"])

    st.subheader("Planned Trade Direction")
    planned_direction = st.selectbox("Planned Trade Direction", ["None", "Buy", "Sell"])

    fib_level = st.selectbox("Fibonacci Level Tapped", ["None", "0.618", "0.705", "0.50", "0.382", "0.786"])
    candle_type = st.radio("Entry Candle Confirmation", ["None", "Engulfing", "Wick Rejection", "Momentum"])
    session = st.selectbox("Session Favorability", ["None", "Asia", "London", "NY Pre-Open", "NY Open"])

    structure_change = st.checkbox("Change in Structure (against bias)")
    ob_sd_conflict = st.checkbox("OB / SD Conflict near entry")
    liquidity_sweep = st.checkbox("Liquidity Sweep against trade")

    notes = st.text_area("Notes / Commentary")
    mistakes = st.text_area("Mistakes Made (if any)")
    lessons = st.text_area("Lessons Learned")
    screenshot = st.file_uploader("Upload Trade Screenshot", type=["png", "jpg", "jpeg"])
    result = st.selectbox("Trade Result", ["None", "TP Hit", "SL Hit", "Breakeven"])

    submitted = st.form_submit_button("Calculate Confluence Score")

    if submitted:
        score, pos_details, neg_details = calculate_confluence(
            planned_direction, htf_trends, ltf_trends, ltf_expected, fib_level, candle_type,
            session, structure_change, ob_sd_conflict, liquidity_sweep
        )

        sl = 50
        tp = 100

        st.subheader("✅ Confluence Score")
        st.metric("Score", score)

        st.subheader("Positive Contributors")
        st.json(pos_details)

        st.subheader("Negative Contributors")
        st.json(neg_details)

        st.subheader("Suggested SL / TP")
        st.write(f"SL: {sl} pips | TP: {tp} pips")

        # ----------------------------
        # Save trade
        # ----------------------------
        trade_entry = {
            "DateTime": datetime.now(),
            "Trade Number": trade_number,
            "Planned Direction": planned_direction,
            "Session": session,
            "HTF Trend": htf_trends,
            "LTF Trend": ltf_trends,
            "LTF Expected": ltf_expected,
            "Fibonacci Level": fib_level,
            "Entry Candle": candle_type,
            "Structure Change": structure_change,
            "OB/SD Conflict": ob_sd_conflict,
            "Liquidity Sweep": liquidity_sweep,
            "Confluence Score": score,
            "SL": sl,
            "TP": tp,
            "Notes": notes,
            "Mistakes": mistakes,
            "Lessons": lessons,
            "Screenshot": screenshot.name if screenshot else None,
            "Trade Result": result,
        }
        st.session_state.journal.append(trade_entry)

        if gsheet_available:
            try:
                row = [
                    trade_entry["DateTime"].strftime("%Y-%m-%d %H:%M:%S"),
                    trade_entry["Trade Number"],
                    trade_entry["Planned Direction"],
                    trade_entry["Session"],
                    str(trade_entry["HTF Trend"]),
                    str(trade_entry["LTF Trend"]),
                    str(trade_entry["LTF Expected"]),
                    trade_entry["Fibonacci Level"],
                    trade_entry["Entry Candle"],
                    trade_entry["Structure Change"],
                    trade_entry["OB/SD Conflict"],
                    trade_entry["Liquidity Sweep"],
                    trade_entry["Confluence Score"],
                    trade_entry["SL"],
                    trade_entry["TP"],
                    trade_entry["Notes"],
                    trade_entry["Mistakes"],
                    trade_entry["Lessons"],
                    trade_entry["Screenshot"],
                    trade_entry["Trade Result"]
                ]
                sheet.append_row(row)
                st.success("Trade saved to Google Sheets!")
            except Exception as e:
                st.warning(f"Failed to save to Google Sheets: {e}")
        else:
            st.success("Trade saved to local journal!")

# ----------------------------
# Trade Journal Table
# ----------------------------
st.header("2️⃣ Trade Journal")
if st.session_state.journal:
    df = pd.DataFrame(st.session_state.journal)
    st.dataframe(df)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "trade_journal.csv", "text/csv")
else:
    st.write("No trades yet.")

# ----------------------------
# Analytics Dashboard (Simple)
# ----------------------------
st.header("3️⃣ Analytics Dashboard")
if st.session_state.journal:
    df = pd.DataFrame(st.session_state.journal)

    avg_session = df.groupby("Session")["Confluence Score"].mean()
    st.subheader("Average Confluence Score by Session")
    st.bar_chart(avg_session)

    st.subheader("Confluence Score Distribution")
    st.bar_chart(df["Confluence Score"])

    st.subheader("Trades per Fib Level")
    fib_counts = df["Fibonacci Level"].value_counts()
    st.bar_chart(fib_counts)
else:
    st.write("No analytics available yet.")
