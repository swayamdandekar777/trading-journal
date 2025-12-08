# trading_journal_v1_updated.py
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Google Sheets Setup
# ----------------------------
# Your service account JSON details
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "formidable-app-409017",
    "private_key_id": "fbbe19738f6c4b7d0796a45f8f52263b3b44ad81",
    "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCySvZWiyybAaNZ
ROgHX2lZHm6ex+OAgqg6+js7FvvbC7TeMTKh8QiW3uJt18FS+s+ULEUqSHAtbRTs
V31FE9L7+V4YqzavqTCkj+Q1DhhGPh63Ql3qFFMge9ay2NAWMz/h2Pn+43tXXEBy
GyOU+IKZkSq/pyHdV5f5QfidVe0749lMZn3bAXeLFUwSDWJBFpHzy916SPaIt8ft
Ptsy5LNdPZPdzmP5ISM4j6dhjRQpSLox5OPFVKN653UoZJOzYyln2B79SvI67n4k
rq0OQO7KB9Eb+S4ZiaARHKMDB4FpanQSg7zP3npQ/RH9iXdt5kz50l4L790OKVmF
/OxEB3OzAgMBAAECggEABaqyR6/mvAqCSZ0SDuHudEGuXGeYCIaemDlJ1qf1W1H0
7rb7mAAUOM9evQUFhQCpxljd3ektf5Qe/SAOwDpQE2gqoHgYpd6nyCM2qqUHCnyA
92wplf4NYlPtUAPqITqBxkjiMULDsdQhzD6mk96OMBlYFX1XazSUhPyezUlk3+lh
a+MYbGsjRnmP0DU4XF3fPOFFV4YtgOAQ1w08p7f/ouIjJ6YnDxQ89qvmgJd/XZGq
Wgd+iZp4DfnDeDWgmoymoW8lN3n87OnAkV1n+e5momlaz+WEy9Q2MTSz2OlD9FPX
uMddINRGWuCKCayB3fZCn4ylTKBNDoCRz5jjTZrQcQKBgQDjxs0UugPl0aKrF7XI
A9dG0PSco9ZuJGLBWrZ9KR6defBB2sEIIW5Scj1mekpYb8ik3nN32KdJp5qXg5TM
4eVfEX5d9n6X7XT8HHPEoGFjNW+9nohAaAAP0AYn+hMb2yRPVLacZsJALM+ygeuQ
FGZ6ERoPcktGahS9ARtVKSfLCQKBgQDIYoJj52eL33GcNo8VUAWzwRK1nhhxpiLq
59DKkGQ2t3Rl0zTYbzKAxzLFFTmk22q1YPsfWJUPDDmjg/xKDa5QSZi4t0HLoNcZ
LzFHoo0CkgO1cN1dHurGR15e0MaSV1zft+Q+QGGFF2ie/u33wq+PVm+xId1oNYRJ
6PVjrCBr2wKBgCrXzuVSI7+LkeRKnmeTyV9JmGkKLCAleenSjTa3kEmgkP9iDSLh
XuXlFQV8hRVjWUMhkGh/eN/SxbIwDsIGz2T1XmaAIcmj4Xg2RdQ7MnY9q9nnwssS
hMh0oWPNluCLdKXzUjHS5kC57QsvgsZj/+5/3v3+yofhFiuC1MhM6G45AoGBAJaH
IaoIuAkjtgWCGqQI8++fVv2loHknM03BDGBObWmJEGA5c5YumgKRIPtZwW6tARD1
pE9czMR8C4Rg7pF2i352esovp7ZewZaClANbAZBvvWd8PF3qjrSaAjM5pCFkjTjl
vAhjdp5zAj2GBZ872YPUi5zFcrwIj7Kx1DymnchHAoGBAMsXkOZuXir29yw1qCys
zC86xpWvFVLshwa6yte+mvLsfJAfVi8QCm9BEtx1n7pZJaz6jEiWyd7jW+BBDzZa
xlz5jT0XHuKbpE4n4Yiyo/P5qSToWlmOusWpqXxL0dYN6uLRR4FyfAlzw/rrXCAG
nF6sl5oCdYdLzusE/mW8YO1W
-----END PRIVATE KEY-----""",
    "client_email": "swayamstradingjournal@formidable-app-409017.iam.gserviceaccount.com",
    "client_id": "107072845707151606684",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/swayamstradingjournal@formidable-app-409017.iam.gserviceaccount.com"
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
GS_CLIENT = gspread.authorize(CREDS)
SHEET_NAME = "Trading Journal"
try:
    SHEET = GS_CLIENT.open(SHEET_NAME).sheet1
except gspread.SpreadsheetNotFound:
    # If the sheet does not exist, create it
    SHEET = GS_CLIENT.create(SHEET_NAME).sheet1
    # Share with your service account email
    SHEET.share(SERVICE_ACCOUNT_INFO["client_email"], perm_type='user', role='writer')

# ----------------------------
# Initialize journal (in-memory)
# ----------------------------
if "journal" not in st.session_state:
    # Load existing trades from Google Sheets
    try:
        data = SHEET.get_all_records()
        st.session_state.journal = data
    except Exception as e:
        st.session_state.journal = []

# ----------------------------
# (Keep your entire confluence scoring function unchanged)
# ----------------------------
# ... (Paste the calculate_confluence function exactly as in your code)

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
    
    submitted = st.form_submit_button("Calculate Confluence Score")
    
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
        st.session_state.journal.append(trade_entry)
        
        # Save to Google Sheets
        try:
            SHEET.append_row(list(trade_entry.values()))
            st.success("Trade saved to Google Sheets successfully!")
        except Exception as e:
            st.error(f"Error saving to Google Sheets: {e}")
