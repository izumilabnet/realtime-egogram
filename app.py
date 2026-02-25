import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai  # 最新ライブラリ
from google.genai import types
import json
import re
import os
import time
import random

# --- 1. 初期設定 & UIスタイル ---
st.set_page_config(page_title="Gemini Egogram AI", layout="wide")

st.markdown("""
    <style>
    [data-testid="stVerticalBlock"] > div:has(div.fixed-header) {
        position: sticky; top: 2.875rem; z-index: 999;
    }
    .main .block-container { padding-top: 2rem; }
    .reason-text { color: #666; font-size: 0.8rem; font-style: italic; margin-bottom: 15px; }
    .final-card {
        background-color: #f8f9fa; border-radius: 15px; padding: 25px;
        border: 2px solid #ff4b4b; margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .final-title { color: #ff4b4b; font-size: 1.6rem; font-weight: bold; text-align: center; }
    .sidebar-info {
        background-color: #e1f5fe; padding: 12px; border-radius: 8px;
        font-size: 0.85rem; color: #01579b; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# APIキー設定
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("APIキーが環境変数に設定されていません。")
    st.stop()

# 新しいSDKクライアントの初期化
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.0-flash"

# セッション状態の初期化
if 'ego_scores' not in st.session_state:
    st.session_state.ego_scores = {"CP": 10.0, "NP": 10.0, "A": 10.0, "FC": 10.0, "AC": 10.0}
if 'history_data' not in st.session_state:
    st.session_state.history_data = [{"Time": 0, **st.session_state.ego_scores}]
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0
if 'final_diagnosis' not in st.session_state:
    st.session_state.final_diagnosis = None

# --- 2. サイドバー（プロフィール設定） ---
with st.sidebar:
    st.title("👤 診断プロファイル")
    st.markdown("""
        <div class="sidebar-info">
            💡 <b>この情報は診断結果の「言葉選び」を最適化するために使用します。</b><br>
            <span style="font-size: 0.75rem;">※性別や年齢でグラフの形が変わることはありません。</span>
        </div>
    """, unsafe_allow_html=True)
    
    user_gender = st.selectbox("性別", options=["（未選択）", "男性", "女性", "その他", "回答しない"])
    user_age = st.selectbox("年代", options=["（未選択）", "10代", "20代", "30代", "40代", "50代", "60代以上"])
    st.divider()
    if st.button("診断をリセットする"):
        st.session_state.clear()
        st.rerun()

# --- 3. AI分析ロジック (最新SDK & リトライ) ---
def analyze_input_gemini(user_text, current_scores, is_final=False):
    gender_str = user_gender if user_gender != "（未選択）" else "不明"
    age_str = user_age if user_age != "（未選択）" else "不明"
    context = f"相談者情報: {gender_str}, {age_str}"

    if is_final:
        prompt = f"最終診断：属性({context})、スコア:{current_scores}。二つ名、総括、適職、恋愛傾向をJSONで返して。"
    else:
        prompt = f"心理カウンセラーとして属性({context})を分析。現在のスコア:{current_scores}。発言:\"{user_text}\"。変化量delta(-2〜2)と理由、返答をJSONで返して。"
    
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
                wait = random.randint(15, 25)
                st.warning(f"混雑中... {wait}秒後に再試行します({attempt+1}/3)")
                time.sleep(wait)
                continue
            st.error(f"エラーが発生しました: {e}")
            break
    return None

# --- 4. メインレイアウト ---
col_chat, col_graph = st.columns([1.2, 1])

with col_graph:
    st.markdown('<div class="fixed-header">', unsafe_allow_html=True)
    st.subheader("📊 分析グラフ")
    
    # ここでタブを定義（エラー回避の重要ポイント）
    tab1, tab2 = st.tabs(["最新スコア", "変化の履歴"])
    
    with tab1:
        df_bar = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', 'スコア'])
        fig_bar = go.Figure(go.Bar(x=df_bar['指標'], y=df_bar['スコア'], marker_color='rgba(255, 99, 132, 0.7)'))
        fig_bar.update_layout(yaxis=dict(range=[0, 20]), height=300, margin=dict(l=10, r=10, t=10, b=10))
        # 最新の引数 width='stretch' を使用
        st.plotly_chart(fig_bar, width='stretch')

    with tab2:
        df_history = pd.DataFrame(st.session_state.history_data)
        fig_line = go.Figure()
        for col in ["CP", "NP", "A", "FC", "AC"]:
            fig_line.add_trace(go.Scatter(x=df_history["Time"], y=df_history[col], name=col, mode='lines+markers'))
        fig_line.update_layout(yaxis=dict(range=[0, 20]), height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_line, width='stretch')
    
    st.progress(min(st.session_state.message_count * 10, 100))
    st.caption(f"分析の深まり度: {st.session_state.message_count * 10}%")
    st.markdown('</div>', unsafe_allow_html=True)

with col_chat:
    st.subheader("💬 Geminiとの対話")
    if st.session_state.final_diagnosis:
        d = st.session_state.final_diagnosis
        st.markdown(f'<div class="final-card"><div class="final-title">🏆 {d["title"]}</div><p>{d["summary"]}</p><hr><b>💼 適職:</b> {", ".join(d["suitable_jobs"])}<br><b>❤️ 恋愛:</b> {d["romance_tendency"]}</div>', unsafe_allow_html=True)
        st.balloons()

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "reason" in msg: st.markdown(f'<p class="reason-text">💡 分析: {msg["reason"]}</p>', unsafe_allow_html=True)

    if st.session_state.message_count < 10:
        if prompt := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.spinner("Gemini分析中..."):
                result = analyze_input_gemini(prompt, st.session_state.ego_scores)
                if result:
                    for key in st.session_state.ego_scores:
                        st.session_state.ego_scores[key] = max(0, min(20, st.session_state.ego_scores[key] + result["delta"].get(key, 0)))
                    st.session_state.message_count += 1
                    st.session_state.history_data.append({"Time": st.session_state.message_count, **st.session_state.ego_scores})
                    st.session_state.chat_history.append({"role": "assistant", "content": result["reply"], "reason": result["reason"]})
                    if st.session_state.message_count == 10:
                        st.session_state.final_diagnosis = analyze_input_gemini("", st.session_state.ego_scores, is_final=True)
                    st.rerun()