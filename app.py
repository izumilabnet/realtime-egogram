import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os

# --- 1. ページ設定 ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

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

# --- 3. 分析エンジン (Gemini 2.5 Flash) ---
def get_analysis(text, scores):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        model_id = "gemini-2.5-flash"
        
        # AIが確実にJSONだけを返すよう指示を強化
        prompt = f"Analyze psychological state. Scores: {scores}, Input: '{text}'. Return ONLY a JSON object with 'delta' (values -3 to 3) and 'reply' keys."
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # エラーガード：中身が文字列でも辞書でも安全に処理する
        res_data = response.text
        if isinstance(res_data, str):
            res_data = json.loads(res_data)
        return res_data
    except Exception:
        # 通信失敗時もダミーデータを返してアプリを止めない
        return {"delta": {"CP":0,"NP":0,"A":0,"FC":0,"AC":0}, "reply": "解析に少し時間がかかっています。もう一度お話しいただけますか？"}

# --- 4. UIレイアウト ---
with st.sidebar:
    st.title("SETTINGS")
    st.selectbox("Gender", ["Male", "Female", "Other"], key="g")
    st.selectbox("Age", ["10s", "20s", "30s", "40s", "50s+"], key="a")
    st.divider()
    if st.button("RESET"):
        st.session_state.clear()
        st.rerun()

left, right = st.columns([2, 1])

with right:
    st.subheader("📊 EQ Equalizer")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['Key', 'Val'])
    fig = go.Figure(go.Bar(x=df['Key'], y=df['Val'], marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['Val']]))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=350, margin=dict(l=10, r=10, t=10, b=10))
    
    st.plotly_chart(fig, width='stretch')
    st.progress(st.session_state.count / 10)

with left:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.count < 10:
        if inp := st.chat_input("How are you feeling?"):
            st.session_state.chat.append({"role": "user", "content": inp})
            
            # ここで安全にデータを取得
            res = get_analysis(inp, st.session_state.scores)
            
            # --- ここが今回のエラー対策の肝 ---
            if res and isinstance(res, dict):
                deltas = res.get("delta", {})
                for k in st.session_state.scores:
                    # 数値以外が入っていてもエラーにならないようにガード
                    d_val = deltas.get(k, 0)
                    try:
                        d_val = float(d_val)
                    except:
                        d_val = 0
                    st.session_state.scores[k] = max(-10, min(10, st.session_state.scores[k] + d_val))
                
                st.session_state.chat.append({"role": "assistant", "content": res.get("reply", "...")})
                st.session_state.count += 1
                st.rerun()