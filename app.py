import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import time

# --- 1. System Config ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

# Session Initialize
if 'auth' not in st.session_state: st.session_state.auth = False
if 'scores' not in st.session_state: st.session_state.scores = {"CP":0.0, "NP":0.0, "A":0.0, "FC":0.0, "AC":0.0}
if 'chat' not in st.session_state: st.session_state.chat = []
if 'count' not in st.session_state: st.session_state.count = 0

# --- 2. Auth Interface ---
if not st.session_state.auth:
    st.title("REALTIME-EGOGRAM")
    if st.text_input("Password", type="password") == "okok":
        if st.button("ENTER"):
            st.session_state.auth = True
            st.rerun()
    st.stop()

# --- 3. AI Analysis ---
def get_analysis(text, scores):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Analysis scores {scores} for input '{text}'. Return JSON: {{'delta':{{'CP':0,'NP':0,'A':0,'FC':0,'AC':0}}, 'reason':'', 'reply':''}}"
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. Main UI ---
with st.sidebar:
    st.title("EGOGRAM SETTINGS")
    st.selectbox("Gender", ["Male", "Female", "Other"])
    st.selectbox("Age", ["10s", "20s", "30s", "40s", "50s+"])
    if st.button("Reset All"):
        st.session_state.clear()
        st.rerun()

left, right = st.columns([2, 1])

with right:
    st.subheader("📊 EQ Equalizer")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['Key', 'Val'])
    fig = go.Figure(go.Bar(x=df['Key'], y=df['Val'], marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['Val']]))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=300)
    st.plotly_chart(fig, use_container_width=True)
    st.progress(st.session_state.count / 10)

with left:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.count < 10:
        if inp := st.chat_input("How are you feeling?"):
            st.session_state.chat.append({"role": "user", "content": inp})
            res = get_analysis(inp, st.session_state.scores)
            if res:
                for k in st.session_state.scores:
                    st.session_state.scores[k] = max(-10, min(10, st.session_state.scores[k] + res.get("delta", {}).get(k, 0)))
                st.session_state.chat.append({"role": "assistant", "content": res.get("reply", "")})
                st.session_state.count += 1
                st.rerun()