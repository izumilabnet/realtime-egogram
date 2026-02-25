import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import re
import os
import time
import random

# --- 1. 初期設定 & UIスタイル ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #fdfdfd; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .reason-text { color: #888; font-size: 0.75rem; font-style: italic; margin-top: -10px; margin-bottom: 15px; padding-left: 10px; }
    .final-card {
        background-color: #ffffff; border-radius: 20px; padding: 25px;
        border: 1px solid #eee; box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-bottom: 25px;
    }
    .final-title { color: #ff4b4b; font-size: 1.4rem; font-weight: bold; text-align: center; margin-bottom: 15px; }
    
    /* 認証画面 */
    .auth-container { 
        max-width: 600px; margin: 40px auto; text-align: center; 
        padding: 40px; border-radius: 30px; background: white; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
    }
    .app-logo { font-size: 2.2rem; font-weight: 800; color: #333; letter-spacing: 2px; }
    .app-sub-logo { font-size: 1rem; color: #ff4b4b; margin-bottom: 20px; font-weight: 600; }
    .welcome-msg { color: #555; font-size: 0.95rem; line-height: 1.6; text-align: left; margin: 20px 0; padding: 20px; border-left: 3px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# セッション状態の初期化 (±10モデル)
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'ego_scores' not in st.session_state:
    # 初期値は「0（ニュートラル）」
    st.session_state.ego_scores = {"CP": 0.0, "NP": 0.0, "A": 0.0, "FC": 0.0, "AC": 0.0}
if 'history_data' not in st.session_state:
    st.session_state.history_data = [{"Time": 0, **st.session_state.ego_scores}]
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0
if 'final_diagnosis' not in st.session_state:
    st.session_state.final_diagnosis = None

# --- 2. パスワード認証画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.markdown('<div class="app-logo">REALTIME-EGOGRAM</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-sub-logo">リアルタイム・エゴグラム</div>', unsafe_allow_html=True)
    st.markdown('<div class="welcome-msg">ようこそ。性格は固定された資産ではなく、対話の中で奏でられる旋律（イコライザー）です。対話を通じ、今この瞬間のあなたの「心の形」を可視化します。</div>', unsafe_allow_html=True)
    password = st.text_input("PASSWORD", type="password")
    if st.button("ROOM ENTER"):
        if password == "okok":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 3. メインアプリ ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("APIキーを環境変数に設定してください。")
    st.stop()

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.0-flash"

def analyze_input_gemini(user_text, current_scores, is_final=False):
    gender_str = user_gender if user_gender != "（未選択）" else "不明"
    age_str = user_age if user_age != "（未選択）" else "不明"
    context = f"相談者: {gender_str}, {age_str}"

    if is_final:
        # 最終診断プロンプト
        prompt = f"""
        【最終診断：イコライザー・モデル】
        ユーザー属性: {context}
        最終スコア（-10〜+10）: {current_scores}
        
        このスコアを「対話における応答スタイル」として総括してください。
        以下のJSONで返してください。
        {{
            "title": "二つ名（例：静寂の哲学者）",
            "summary": "性格総括（200字程度。プラス/マイナスの振れ幅をどう解釈するか含めて）",
            "suitable_jobs": ["職業1", "職業2", "職業3"],
            "romance_tendency": "恋愛・対人関係の傾向",
            "reply": "最後のご挨拶"
        }}
        """
    else:
        # 逐次分析プロンプト
        prompt = f"""
        【心理分析：イコライザー・モデル】
        相談者: {context}
        現在のスコア（-10〜+10の範囲、0がニュートラル）: {current_scores}
        発言: "{user_text}"

        発言内容に基づき、各指標の「活性（プラス）」または「抑制（マイナス）」への変化量delta（-3.0〜+3.0）を算出し、JSONで返してください。
        {{
            "delta": {{"CP":0, "NP":0, "A":0, "FC":0, "AC":0}},
            "reason": "なぜその指標が活性/抑制されたかの理由",
            "reply": "ユーザーへの共感と次の質問"
        }}
        """
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e):
                time.sleep(random.randint(15, 25))
                continue
            st.error(f"APIエラー: {e}")
            break
    return None

# サイドバー
with st.sidebar:
    st.markdown('<div style="font-size:1.2rem; font-weight:800;">REALTIME-EGOGRAM</div>', unsafe_allow_html=True)
    st.divider()
    user_gender = st.selectbox("性別", options=["（未選択）", "男性", "女性", "その他", "回答しない"])
    user_age = st.selectbox("年代", options=["（未選択）", "10代", "20代", "30代", "40代", "50代", "60代以上"])
    st.divider()
    if st.button("新しく診断を始める"):
        st.session_state.clear()
        st.rerun()

# 3カラムレイアウト
col_spacer_l, col_main, col_viz = st.columns([0.1, 2, 0.9])

# 右カラム：イコライザー視覚化
with col_viz:
    st.write("📊 **EQイコライザー**")
    df_bar = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', '値'])
    
    # 上下に伸びる棒グラフ
    fig_bar = go.Figure(go.Bar(
        x=df_bar['指標'], y=df_bar['値'],
        marker_color=['rgba(255, 99, 132, 0.6)' if v < 0 else 'rgba(100, 149, 237, 0.6)' for v in df_bar['値']]
    ))
    fig_bar.update_layout(
        yaxis=dict(range=[-10, 10], zeroline=True, zerolinewidth=2, zerolinecolor='gray', showticklabels=True),
        height=220, margin=dict(l=20, r=20, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_bar, width='stretch')

    if st.session_state.message_count > 0:
        st.write("📈 **推移**")
        df_history = pd.DataFrame(st.session_state.history_data)
        fig_line = go.Figure()
        for col in ["CP", "NP", "A", "FC", "AC"]:
            fig_line.add_trace(go.Scatter(x=df_history["Time"], y=df_history[col], name=col, mode='lines'))
        fig_line.update_layout(yaxis=dict(range=[-10, 10], showticklabels=False), height=150, margin=dict(l=5, r=5, t=10, b=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_line, width='stretch')
    
    st.progress(min(st.session_state.message_count * 10, 100))
    st.caption(f"SESSION DEPTH: {st.session_state.message_count * 10}%")

# 中央カラム：チャット
with col_main:
    if st.session_state.final_diagnosis:
        d = st.session_state.final_diagnosis
        st.markdown(f'<div class="final-card"><div class="final-title">🏆 {d["title"]}</div><p>{d["summary"]}</p><hr><b>💼 適職:</b> {", ".join(d["suitable_jobs"])}<br><b>❤️ 恋愛:</b> {d["romance_tendency"]}</div>', unsafe_allow_html=True)
        st.balloons()

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "reason" in msg: st.markdown(f'<p class="reason-text">💡 {msg["reason"]}</p>', unsafe_allow_html=True)

    if st.session_state.message_count < 10:
        if prompt := st.chat_input("今、どんなことを感じていますか？"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.spinner("Analyzing..."):
                result = analyze_input_gemini(prompt, st.session_state.ego_scores)
                if result:
                    for key in st.session_state.ego_scores:
                        # ±10の範囲で更新
                        new_val = st.session_state.ego_scores[key] + result["delta"].get(key, 0)
                        st.session_state.ego_scores[key] = max(-10, min(10, new_val))
                    
                    st.session_state.message_count += 1
                    st.session_state.history_data.append({"Time": st.session_state.message_count, **st.session_state.ego_scores})
                    st.session_state.chat_history.append({"role": "assistant", "content": result["reply"], "reason": result["reason"]})
                    
                    if st.session_state.message_count == 10:
                        st.session_state.final_diagnosis = analyze_input_gemini("", st.session_state.ego_scores, is_final=True)
                    st.rerun()