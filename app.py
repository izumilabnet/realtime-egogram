import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os

# --- 1. ページ設定（最新仕様） ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

# セッション状態の初期化
if 'auth' not in st.session_state: st.session_state.auth = False
if 'scores' not in st.session_state: st.session_state.scores = {"CP":0.0, "NP":0.0, "A":0.0, "FC":0.0, "AC":0.0}
if 'chat' not in st.session_state: st.session_state.chat = []
if 'count' not in st.session_state: st.session_state.count = 0

# --- 2. 認証 ---
if not st.session_state.auth:
    st.title("REALTIME-EGOGRAM")
    if st.text_input("PASSWORD", type="password") == "okok":
        if st.button("ENTER"):
            st.session_state.auth = True
            st.rerun()
    st.stop()

# --- 3. AI分析エンジン ---
def get_analysis(text, scores):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        # 学会発表を意識した精度の高いプロンプト
        prompt = f"Analyze psychological state. Scores: {scores}, Input: '{text}'. Return JSON with delta, reason, and reply."
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. メイン画面レイアウト ---
with st.sidebar:
    st.title("SETTINGS")
    st.selectbox("Gender", ["Male", "Female", "Other"], key="gender")
    st.selectbox("Age", ["10s", "20s", "30s", "40s", "50s+"], key="age")
    st.divider()
    if st.button("RESET"):
        st.session_state.clear()
        st.rerun()

col_chat, col_viz = st.columns([2, 1])

with col_viz:
    st.subheader("📊 EQ Equalizer")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['ID', 'Val'])
    fig = go.Figure(go.Bar(
        x=df['ID'], y=df['Val'],
        marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['Val']]
    ))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=350, margin=dict(l=10, r=10, t=10, b=10))
    
    # 💡 重要：ログの警告に従い、width='stretch' を適用
    st.plotly_chart(fig, width='stretch')
    
    st.progress(st.session_state.count / 10)
    st.caption(f"Progress: {st.session_state.count * 10}%")

with col_chat:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.count < 10:
        if user_input := st.chat_input("How are you feeling?"):
            st.session_state.chat.append({"role": "user", "content": user_input})
            res = get_analysis(user_input, st.session_state.scores)
            if res:
                # スコア更新
                for k in st.session_state.scores:
                    st.session_state.scores[k] = max(-10, min(10, st.session_state.scores[k] + res.get("delta", {}).get(k, 0)))
                st.session_state.chat.append({"role": "assistant", "content": res.get("reply", "")})
                st.session_state.count += 1
                st.rerun()