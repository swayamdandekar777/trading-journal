import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Trading Journal", layout="centered")

# ---------------- GOOGLE SHEETS CONNECTION ----------------

scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service"], scopes=scope
)
client = gspread.authorize(creds)

# YOUR SHEET NAME (MUST MATCH EXACTLY)
sheet = client.open("Trading Journal").sheet1


# ---------------- LOAD EXISTING TRADES ----------------

def load_trades():
    data = sheet.get_all_records()
    if data:
        return pd.DataFrame(data)
    return pd.DataFrame(columns=[
        "date", "trade_no", "screenshot", "mistake",
        "tp_hit", "sl_gone", "HH", "HL", "LH", "LL", "user_id"
    ])

df = load_trades()


# ---------------- UI HEADER ----------------

st.title("📘 XAUUSD Trading Journal")
st.write("Save trades permanently using Google Sheets backend.")


# ---------------- INPUT FORM ----------------

st.subheader("➕ Add New Trade")

trade_no = st.number_input("Trade Number", min_value=1, max_value=5, step=1)
screenshot = st.text_input("Screenshot link (optional)")
mistake = st.text_area("Mistake / Notes (optional)")

tp_hit = st.checkbox("TP Hit")
sl_gone = st.checkbox("SL Hit")

st.write("### Market Structure")
c1, c2, c3, c4 = st.columns(4)
with c1: HH = st.checkbox("HH")
with c2: HL = st.checkbox("HL")
with c3: LH = st.checkbox("LH")
with c4: LL = st.checkbox("LL")


# ---------------- SAVE BUTTON ----------------

if st.button("Save Trade"):
    new_row = [
        str(datetime.now().date()),
        trade_no,
        screenshot,
        mistake,
        tp_hit,
        sl_gone,
        HH,
        HL,
        LH,
        LL,
        "public"     # you can change to user login later
    ]

    sheet.append_row(new_row)
    st.success("✅ Trade saved successfully!")

    st.rerun()


# ---------------- DISPLAY TABLE ----------------

st.subheader("📊 Previous Trades")
st.dataframe(df, use_container_width=True)
