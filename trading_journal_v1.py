# trading_journal_v1_updated.py
import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ----------------------------
# 1. Cloud Database Connection
# ----------------------------
# Connect to the Google Sheet defined in secrets.toml
conn = st.connection("gsheets", type=GSheetsConnection)

def load_journal():
    """Loads the journal from Google Sheets to ensure all users see the same data."""
    try:
        # Read data from the sheet named 'Sheet1'
        df = conn.read(worksheet="Sheet1")
        # If the sheet is empty or new, return empty list
        if df.empty:
            return []
        # Clean up empty rows that might occur
        df = df.dropna(how="all")
        # Convert back to list of dicts to match your original structure
        return df.to_dict('records')
    except Exception:
        return []

def save_to_cloud(journal_data):
    """Saves the entire journal list to Google Sheets."""
    try:
        df = pd.DataFrame(journal_data)
        # Update the sheet immediately
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear() # Clear cache so updates show immediately
    except Exception as e:
        st.error(f"Error saving to cloud: {e}")

# ----------------------------
# Initialize journal (Sync with Cloud)
# ----------------------------
# We load fresh from cloud on every app rerun
if "journal" not in st.session_state:
    st.session_state.journal = load_journal()
else:
    # Optional: Force refresh to ensure we see other people's trades
    st.session_state.journal = load_journal()

# ----------------------------
# Confluence Scoring Function (YOUR ORIGINAL LOGIC)
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
    # Check if planned direction is valid
    if planned_direction not in ["Buy", "Sell"]:
        planned_direction = "None"

    # --- HTF Alignment (20%) ---
    # 3 timeframes: Weekly, Daily, 4H
    htf_timeframes = ["Weekly", "Daily", "4H"]
    htf_match_count = 0
    for tf in htf_timeframes:
        if aligns(htf_trends.get(tf, "None"), planned_direction):
            htf_match_count += 1
    # Positive points if at least 2 of 3 align
    if htf_match_count >= 2:
        pos_details["HTF Alignment"] = weights["HTF Alignment"]
        score += weights["HTF Alignment"]
    else:
        pos_details["HTF Alignment"] = 0

    # --- LTF Alignment (25%) ---
    # 4 timeframes: 1H, 30M, 15M, 5M
    ltf_major = ["1H", "30M"]
    ltf_minor = ["15M", "5M"]
    ltf_major_aligned = all(aligns(ltf_trends.get(tf, "None"), planned_direction) for tf in ltf_major)
    ltf_major_misaligned = all(not aligns(ltf_trends.get(tf, "None"), planned_direction) for tf in ltf_major)

    ltf_score = 0
    ltf_pos = 0
    ltf_neg = 0

    if ltf_major_aligned:
        # Major positive contribution
        ltf_pos += weights["LTF Alignment"] * 0.7  # 70% of LTF weight
        # Minor timeframes contribute minor positive or negative
        for tf in ltf_minor:
            if aligns(ltf_trends.get(tf, "None"), planned_direction):
                ltf_pos += (weights["LTF Alignment"] * 0.3) / 2  # split minor weight
            else:
                ltf_neg += (weights["LTF Alignment"] * 0.3) / 2
    elif ltf_major_misaligned:
        # Major negative contribution
        ltf_neg += weights["LTF Alignment"] * 0.7
        # Minor timeframes contribute minor negative or positive
        for tf in ltf_minor:
            if aligns(ltf_trends.get(tf, "None"), planned_direction):
                ltf_pos += (weights["LTF Alignment"] * 0.3) / 2
            else:
                ltf_neg += (weights["LTF Alignment"] * 0.3) / 2
    else:
        # Mixed major timeframes - neutral base
        # Minor timeframes contribute minor positive or negative
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
    # Check if planned direction matches dominant HTF trend (majority)
    # We'll reuse htf_match_count from HTF Alignment
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
    # For Buy: HL preferred > HH; for Sell: LH preferred > LL
    # 1H and 30M dominant, 15M and 5M secondary
    structure_score = 0
    structure_pos = 0
    structure_neg = 0

    # Define preferred structures
    preferred_structures = {
        "Buy": ["HL", "HH"],
        "Sell": ["LH", "LL"]
    }
    secondary_structures = {
        "Buy": ["HH", "HL"],
        "Sell": ["LL", "LH"]
    }

    # Function to score one timeframe expected structure
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
        neg_details["Structure Change"] = -10  # Penalize structure change mildly
        score -= 10
    else:
        pos_details["No Structure Change"] = 10
        score += 10

    # Limit score 0-100
    score = max(min(score, 100), 0)

    return round(score,2), pos_details, neg_details

# ----------------------------
# Streamlit UI
# ----------------------------
st.title("🔥 Trading Journal & Confluence AI - Version 1 (Cloud Shared)")
st.caption("Trades are saved to the shared Google Sheet and visible to all users.")

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

    # LTF trend first
    ltf_trends = {
        "1H": st.selectbox("1H Trend", ["None", "Bullish", "Bearish"]),
        "30M": st.selectbox("30M Trend", ["None", "Bullish", "Bearish"]),
        "15M": st.selectbox("15M Trend", ["None", "Bullish", "Bearish"]),
        "5M": st.selectbox("5M Trend", ["None", "Bullish", "Bearish"])
    }

    # Then ask what is expected to form for selected key timeframes
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
    
    submitted = st.form_submit_button("Calculate Confluence & Save to Cloud")
    
    if submitted:
        score, pos_details, neg_details = calculate_confluence(
            planned_direction, htf_trends, ltf_trends, ltf_expected, fib_level, candle_type,
            session, structure_change, ob_sd_conflict, liquidity_sweep
        )
        
        # Dummy SL/TP (can be replaced with real logic)
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
        
        # Save trade to journal
        trade_entry = {
            "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Trade Number": trade_number,
            "Planned Direction": planned_direction,
            "Session": session,
            # Flatten dicts to strings for CSV/Sheet compatibility
            "HTF Trend": str(htf_trends),
            "LTF Trend": str(ltf_trends),
            "LTF Expected": str(ltf_expected),
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
        
        # Append to session state
        st.session_state.journal.append(trade_entry)
        
        # --- SAVE TO GOOGLE SHEETS ---
        with st.spinner("Syncing to Google Cloud..."):
            save_to_cloud(st.session_state.journal)
        
        st.success("Trade saved to Shared Cloud Journal!")
        # Rerun to show updated table immediately
        st.rerun()

# ----------------------------
# Trade Journal Table
# ----------------------------
st.header("2️⃣ Trade Journal (Shared)")
if st.session_state.journal:
    df = pd.DataFrame(st.session_state.journal)
    st.dataframe(df)
    
    # Simple CSV download (optional)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV Backup", csv, "trade_journal.csv", "text/csv")
else:
    st.write("No trades yet.")

# ----------------------------
# Analytics Dashboard (Simple)
# ----------------------------
st.header("3️⃣ Analytics Dashboard")
if st.session_state.journal:
    df = pd.DataFrame(st.session_state.journal)
    
    # Average Confluence Score by Session
    if "Session" in df.columns and "Confluence Score" in df.columns:
        avg_session = df.groupby("Session")["Confluence Score"].mean()
        st.subheader("Average Confluence Score by Session")
        st.bar_chart(avg_session)
    
    # Confluence Score Distribution
    if "Confluence Score" in df.columns:
        st.subheader("Confluence Score Distribution")
        st.bar_chart(df["Confluence Score"])
    
    # Example: Fib Level Success Rate
    if "Fibonacci Level" in df.columns:
        st.subheader("Trades per Fib Level")
        fib_counts = df["Fibonacci Level"].value_counts()
        st.bar_chart(fib_counts)
else:
    st.write("No analytics available yet.")
