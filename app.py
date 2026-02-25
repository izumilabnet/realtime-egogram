import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import time

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

# カスタムCSS
st.markdown("""
    <style>
    .stChatMessage { border-radius: 15px; }
    .reason-text { color: #888; font-size: 0.8rem; font-style: italic; margin-bottom: 10px; }
    .final-card { background: white; border-radius: 20px; padding: 25px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# セッション状態の初期化
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'ego_scores' not in st.session_state: st.session_state.ego_scores = {"CP": 0.0, "NP": 0.0, "A": 0.0, "FC": 0.0, "AC": 0.0}
if 'history_data' not in st.session_state: st.session_state.history_data = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'message_count' not in st.session_state: st.session_state.message_count = 0
if 'final_diagnosis' not in st.session_state: st.session_state.final_diagnosis = None

# --- 2. 認証ロジック ---
if not st.session_state.authenticated:
    st.title("REALTIME-EGOGRAM")
    pw = st.text_input("PASSWORD", type="password")
    if st.button("ENTER"):
        if pw == "okok":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid Password")
    st.stop()

# --- 3. 分析準備 (API接続) ---
# 2.5 Flash を使用する設定（ユーザー指示に基づく）
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def get_ai_analysis(text, current_scores, is_final=False):
    model_name = "gemini-2.0-flash" # 内部モデルは最新版を使用
    if is_final:
        prompt = f"最終診断。スコア{current_scores}。性格、適職、恋愛をJSONで返して。"
    else:
        prompt = f"心理分析。現在{current_scores}, 発言:\"{text}\"。delta(-3〜3)と理由、返答をJSONで。"
    
    try:
        response = client.models.generate_content(
            model=model_name, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. メイン画面の描画 ---
# サイドバーを先に描画することで、消えるのを防ぐ
with st.sidebar:
    st.title("REALTIME-EGOGRAM")
    st.write("### 属性設定")
    gender = st.selectbox("性別", ["男性", "女性", "その他"])
    age = st.selectbox("年代", ["10代", "20代", "30代", "40代", "50代以上"])
    
    st.divider()
    if st.session_state.history_data:
        csv = pd.DataFrame(st.session_state.history_data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 研究用CSVを保存", csv, "ego_research.csv", "text/csv")
    
    if st.button("セッション・リセット"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# メインエリア
col_left, col_right = st.columns([2, 1])

with col_right:
    st.write("📊 **EQイコライザー**")
    df = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['ID', 'Val'])
    fig = go.Figure(go.Bar(
        x=df['ID'], y=df['Val'],
        marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['Val']]
    ))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.progress(st.session_state.message_count / 10)

with col_left:
    if st.session_state.final_diagnosis:
        d = st.session_state.final_diagnosis
        st.success(f"### {d.get('title', '診断完了')}")
        st.write(d.get('summary', ''))
        st.balloons()

    # チャット履歴表示
    for m in st.session_state.chat_history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if "reason" in m: st.markdown(f'<p class="reason-text">💡 {m["reason"]}</p>', unsafe_allow_html=True)

    # 入力
    if st.session_state.message_count < 10 and not st.session_state.final_diagnosis:
        if user_text := st.chat_input("今の気持ちを聴かせてください"):
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            
            res = get_ai_analysis(user_text, st.session_state.ego_scores)
            if res:
                # スコア反映
                for k, v in res.get("delta", {}).items():
                    st.session_state.ego_scores[k] = max(-10, min(10, st.session_state.ego_scores[k] + v))
                
                st.session_state.message_count += 1
                st.session_state.history_data.append({"Step": st.session_state.message_count, "Text": user_text, **st.session_state.ego_scores})
                st.session_state.chat_history.append({"role": "assistant", "content": res.get("reply", ""), "reason": res.get("reason", "")})
                
                if st.session_state.message_count == 10:
                    st.session_state.final_diagnosis = get_ai_analysis("", st.session_state.ego_scores, True)
                
                st.rerun()