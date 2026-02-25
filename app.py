import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import json
import re
import os
import time  # 追加
from google.api_core import exceptions  # 追加

# --- 1. 初期設定 ---
st.set_page_config(page_title="Gemini Egogram AI", layout="wide")

st.markdown("""
    <style>
    [data-testid="stVerticalBlock"] > div:has(div.fixed-header) {
        position: sticky;
        top: 2.875rem;
        z-index: 999;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("APIキーが設定されていません。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
# 現在利用可能な安定モデルを指定
model = genai.GenerativeModel('gemini-2.0-flash')

if 'ego_scores' not in st.session_state:
    st.session_state.ego_scores = {"CP": 10.0, "NP": 10.0, "A": 10.0, "FC": 10.0, "AC": 10.0}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0

# --- 2. AI分析ロジック (リトライ機能付き) ---
def analyze_input_gemini(user_text, current_scores):
    prompt = f"""
    あなたは熟練の心理カウンセラーです。エゴグラム理論（CP, NP, A, FC, AC）に基づき分析します。
    現在のスコア: {current_scores}
    ユーザーの新しい発言から性格傾向を読み取り、現在のスコアに対する「変化量（-2.0〜+2.0）」を算出してください。
    出力は必ず以下のJSON形式のみで行ってください。
    {{
        "delta": {{"CP": 0.5, "NP": -0.2, "A": 1.0, "FC": 0.0, "AC": -0.5}},
        "reason": "分析理由",
        "reply": "ユーザーへの共感と、次の側面を引き出すための短い質問"
    }}
    ユーザーの発言: "{user_text}"
    """
    
    # 429エラー対策：最大3回までリトライ
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                raise ValueError("JSON解析失敗")
        
        except exceptions.ResourceExhausted:
            if attempt < 2:
                # 15秒待機してからリトライ
                wait_time = 16
                st.warning(f"現在混雑しています。{wait_time}秒後に自動で再試行します... (試行 {attempt + 1}/3)")
                time.sleep(wait_time)
                continue
            else:
                st.error("Geminiの無料枠が一時的に制限されています。数分待ってから再度お試しください。")
                return None
        except Exception as e:
            st.error(f"予期せぬエラーが発生しました: {e}")
            return None

# --- 3. UIレイアウト ---
col_chat, col_graph = st.columns([1.2, 1])

with col_graph:
    st.markdown('<div class="fixed-header">', unsafe_allow_html=True)
    st.subheader("📊 あなたの心の形（エゴグラム）")
    
    df = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', 'スコア'])
    opacity = min(0.3 + (st.session_state.message_count * 0.1), 1.0)
    
    fig = go.Figure(go.Bar(
        x=df['指標'], y=df['スコア'],
        marker_color='rgba(255, 99, 132, ' + str(opacity) + ')',
        marker_line_color='rgb(150, 0, 0)', marker_line_width=1.5
    ))
    fig.update_layout(yaxis=dict(range=[0, 20]), height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    st.progress(min(st.session_state.message_count * 10, 100))
    st.caption(f"分析の深まり度: {st.session_state.message_count * 10}%")
    st.markdown('</div>', unsafe_allow_html=True)

with col_chat:
    st.subheader("💬 Geminiとの対話")
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    if prompt := st.chat_input("今の気持ちを話してください"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.spinner("Geminiが分析中..."):
            result = analyze_input_gemini(prompt, st.session_state.ego_scores)
            
            if result:
                notices = []
                for key in st.session_state.ego_scores:
                    delta = result["delta"].get(key, 0)
                    if delta >= 0.5: notices.append(f"⬆️ {key} が上昇")
                    elif delta <= -0.5: notices.append(f"⬇️ {key} が低下")
                    
                    new_val = st.session_state.ego_scores[key] + delta
                    st.session_state.ego_scores[key] = max(0, min(20, new_val))
                
                st.session_state.message_count += 1
                st.session_state.chat_history.append({"role": "assistant", "content": result["reply"]})
                
                for n in notices:
                    st.toast(n, icon="💡")
                st.rerun()