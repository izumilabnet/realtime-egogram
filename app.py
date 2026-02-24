import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import json
import re
import os

# --- 1. 初期設定 ---
st.set_page_config(page_title="Gemini Egogram AI", layout="wide")

# APIキーを環境変数から取得（Renderの設定画面で GEMINI_API_KEY を登録してください）
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("APIキーが設定されていません。RenderのEnvironment Variablesに 'GEMINI_API_KEY' を追加してください。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
# 最新かつ高速なモデルを指定
model = genai.GenerativeModel('gemini-2.5-flash')

# セッション状態（データ保持）の初期化
if 'ego_scores' not in st.session_state:
    st.session_state.ego_scores = {"CP": 10.0, "NP": 10.0, "A": 10.0, "FC": 10.0, "AC": 10.0}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'message_count' not in st.session_state:
    st.session_state.message_count = 0

# --- 2. AI分析ロジック (Gemini版) ---
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
    
    response = model.generate_content(prompt)
    
    # JSON抽出の堅牢化
    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    else:
        raise ValueError("AIからのレスポンスを解析できませんでした。")

# --- 3. UIレイアウト ---
st.title("🧠 Gemini 累積型エゴグラム・アナライザー")
st.write("対話を重ねるほど、あなたの心の形が鮮明になります。")

col1, col2 = st.columns([1, 1])

with col2:
    st.subheader("現在のエゴグラム")
    df = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', 'スコア'])
    
    # 累積度に応じて色を濃くする
    opacity = min(0.3 + (st.session_state.message_count * 0.1), 1.0)
    
    fig = go.Figure(go.Bar(
        x=df['指標'], y=df['スコア'],
        marker_color='rgba(255, 99, 132, ' + str(opacity) + ')',
        marker_line_color='rgb(150, 0, 0)', marker_line_width=1.5
    ))
    fig.update_layout(yaxis=dict(range=[0, 20]), margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"分析の深まり度: {st.session_state.message_count * 10}%")

with col1:
    st.subheader("対話ルーム")
    # 履歴の表示
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("今の気持ちを自由に話してみてください"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.spinner("分析中..."):
            try:
                result = analyze_input_gemini(prompt, st.session_state.ego_scores)
                
                # スコアを累積更新
                for key in st.session_state.ego_scores:
                    new_val = st.session_state.ego_scores[key] + result["delta"][key]
                    st.session_state.ego_scores[key] = max(0, min(20, new_val))
                
                st.session_state.message_count += 1
                
                # AI返信の保存と表示
                st.session_state.chat_history.append({"role": "assistant", "content": result["reply"]})
                st.rerun()
                
            except Exception as e:
                st.error(f"分析エラー: {e}")

# 分析が深まった際のアドバイス表示（おまけ）
if st.session_state.message_count >= 10:
    st.success("分析が一定水準に達しました！これが現在のあなたの心のプロファイルです。")