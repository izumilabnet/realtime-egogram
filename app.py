import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import time

# --- 1. ページ構成 ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; }
    .reason-text { color: #888; font-size: 0.8rem; font-style: italic; margin-bottom: 15px; }
    .final-card { background: white; border-radius: 20px; padding: 25px; border: 1px solid #eee; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# セッション状態の初期化
for key, val in {
    'authenticated': False,
    'ego_scores': {"CP": 0.0, "NP": 0.0, "A": 0.0, "FC": 0.0, "AC": 0.0},
    'history_data': [],
    'chat_history': [],
    'message_count': 0,
    'final_diagnosis': None
}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. 認証画面 ---
if not st.session_state.authenticated:
    st.title("REALTIME-EGOGRAM")
    st.info("対話を通じて心の旋律（イコライザー）を可視化します。")
    if st.text_input("パスワードを入力してください", type="password") == "okok":
        if st.button("入室する"):
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

# --- 3. 分析エンジン ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("環境変数 GEMINI_API_KEY が見つかりません。")
    st.stop()

client = genai.Client(api_key=API_KEY)

def get_ai_response(text, scores, is_final=False):
    prompt = f"心理分析（-10〜10）: 現在:{scores}, 発言:\"{text}\"。変化量deltaと理由、返答をJSONで。"
    if is_final: prompt = f"最終診断: スコア{scores}。性格総括、適職、恋愛傾向をJSONで。"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. メインレイアウト ---
with st.sidebar:
    st.subheader("REALTIME-EGOGRAM")
    if st.session_state.history_data:
        csv = pd.DataFrame(st.session_state.history_data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 診断データを保存(CSV)", csv, "ego_log.csv", "text/csv")
    if st.button("リセット"):
        st.session_state.clear()
        st.rerun()

main_col, viz_col = st.columns([2, 1])

with viz_col:
    st.write("📊 **EQイコライザー**")
    df = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['ID', 'Val'])
    fig = go.Figure(go.Bar(x=df['ID'], y=df['Val'], marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['Val']]))
    fig.update_layout(yaxis=dict(range=[-10, 10]), height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True) # 修正: widthパラメータを環境に合わせて調整
    st.progress(st.session_state.message_count / 10)

with main_col:
    if st.session_state.final_diagnosis:
        d = st.session_state.final_diagnosis
        st.markdown(f'<div class="final-card"><h3>🏆 {d.get("title", "分析結果")}</h3><p>{d.get("summary", "")}</p></div>', unsafe_allow_html=True)
        st.balloons()

    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if "reason" in m: st.markdown(f'<p class="reason-text">💡 {m["reason"]}</p>', unsafe_allow_html=True)

    if st.session_state.message_count < 10 and not st.session_state.final_diagnosis:
        if user_input := st.chat_input("今、何を感じていますか？"):
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            res = get_ai_response(user_input, st.session_state.ego_scores)
            if res:
                for k, v in res.get("delta", {}).items():
                    st.session_state.ego_scores[k] = max(-10, min(10, st.session_state.ego_scores[k] + v))
                st.session_state.message_count += 1
                st.session_state.history_data.append({"Step": st.session_state.message_count, "Text": user_input, **st.session_state.ego_scores})
                st.session_state.chat_history.append({"role": "assistant", "content": res.get("reply", ""), "reason": res.get("reason", "")})
                if st.session_state.message_count == 10:
                    st.session_state.final_diagnosis = get_ai_response("", st.session_state.ego_scores, True)
                st.rerun()