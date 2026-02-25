import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import time
import random

# --- 1. 初期設定 & 学会発表を意識したUI ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #fdfdfd; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .reason-text { color: #888; font-size: 0.75rem; font-style: italic; margin-top: -10px; margin-bottom: 15px; padding-left: 10px; }
    .final-card {
        background-color: #ffffff; border-radius: 20px; padding: 25px;
        border: 1px solid #eee; box-shadow: 0 10px 25px rgba(0,0,0,0.05);
    }
    .auth-container { max-width: 600px; margin: 40px auto; text-align: center; padding: 40px; border-radius: 30px; background: white; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# セッション状態
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'ego_scores' not in st.session_state: st.session_state.ego_scores = {"CP": 0.0, "NP": 0.0, "A": 0.0, "FC": 0.0, "AC": 0.0}
if 'history_data' not in st.session_state: st.session_state.history_data = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'message_count' not in st.session_state: st.session_state.message_count = 0
if 'final_diagnosis' not in st.session_state: st.session_state.final_diagnosis = None

# --- 2. 認証画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="auth-container"><h1>REALTIME-EGOGRAM</h1><p>リアルタイム・エゴグラム</p><div style="text-align:left; margin:20px 0; border-left:3px solid #ff4b4b; padding-left:15px; color:#666;">性格は固定された資産ではなく、対話の中で奏でられる旋律（イコライザー）です。</div></div>', unsafe_allow_html=True)
    if st.text_input("PASSWORD", type="password") == "okok":
        if st.button("ROOM ENTER"):
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

# --- 3. 分析ロジック (最新ライブラリ対応) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_input_gemini(user_text, current_scores, is_final=False):
    prompt = f"心理分析(-10〜10): 現在:{current_scores}, 発言:\"{user_text}\"。変化量deltaと理由、返答をJSONで。"
    if is_final: prompt = f"最終診断: スコア{current_scores}。性格総括、適職、恋愛傾向をJSONで。"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"分析中にエラーが発生しました。")
        return None

# --- 4. メインUI ---
with st.sidebar:
    st.title("REALTIME-EGOGRAM")
    user_gender = st.selectbox("性別", ["男性", "女性", "その他"])
    user_age = st.selectbox("年代", ["10代", "20代", "30代", "40代", "50代以上"])
    st.divider()
    
    # 学会発表用：データ出力ボタン
    if st.session_state.history_data:
        csv = pd.DataFrame(st.session_state.history_data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 診断ログ(CSV)を保存", data=csv, file_name='egogram_log.csv', mime='text/csv')
    
    if st.button("リセット"):
        st.session_state.clear()
        st.rerun()

col_main, col_viz = st.columns([2, 1])

with col_viz:
    st.write("📊 **EQイコライザー**")
    df_bar = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', '値'])
    fig = go.Figure(go.Bar(x=df_bar['指標'], y=df_bar['値'], marker_color=['rgba(255,99,132,0.6)' if v < 0 else 'rgba(100,149,237,0.6)' for v in df_bar['値']]))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=250, margin=dict(l=20, r=20, t=10, b=0))
    st.plotly_chart(fig, width='stretch') # 最新のwidth設定
    st.progress(st.session_state.message_count * 10)

with col_main:
    if st.session_state.final_diagnosis:
        st.markdown(f'<div class="final-card">🏆 {st.session_state.final_diagnosis["summary"]}</div>', unsafe_allow_html=True)
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "reason" in msg: st.caption(f"💡 {msg['reason']}")

    if st.session_state.message_count < 10:
        if prompt := st.chat_input("今、何を感じていますか？"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            res = analyze_input_gemini(prompt, st.session_state.ego_scores)
            if res:
                for k in st.session_state.ego_scores:
                    st.session_state.ego_scores[k] = max(-10, min(10, st.session_state.ego_scores[k] + res["delta"].get(k, 0)))
                st.session_state.message_count += 1
                st.session_state.history_data.append({"Time": st.session_state.message_count, "Input": prompt, **st.session_state.ego_scores})
                st.session_state.chat_history.append({"role": "assistant", "content": res["reply"], "reason": res["reason"]})
                if st.session_state.message_count == 10:
                    st.session_state.final_diagnosis = analyze_input_gemini("", st.session_state.ego_scores, True)
                st.rerun()