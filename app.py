import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os

# --- 1. ページ設定 ---
st.set_page_config(page_title="リアルタイム・エゴグラム", layout="wide")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'scores' not in st.session_state: st.session_state.scores = {"CP":0.0, "NP":0.0, "A":0.0, "FC":0.0, "AC":0.0}
if 'chat' not in st.session_state: st.session_state.chat = []
if 'count' not in st.session_state: st.session_state.count = 0

# --- 2. 認証 ---
if not st.session_state.auth:
    st.title("リアルタイム・エゴグラム")
    pw = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン"):
        if pw == "okok":
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
        
        prompt = f"心理分析。現在のスコア: {scores}, 発言: '{text}'。次の形式のJSONのみ返せ: {{\"delta\": {{\"CP\": 0, \"NP\": 0, \"A\": 0, \"FC\": 0, \"AC\": 0}}, \"reply\": \"返答\"}}"
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        res_text = response.text
        return json.loads(res_text)
    except Exception:
        return None

# --- 4. 画面レイアウト ---
with st.sidebar:
    st.title("設定")
    st.selectbox("性別", ["男性", "女性", "その他"], key="g")
    st.selectbox("年齢層", ["10代", "20代", "30代", "40代", "50代以上"], key="a")
    st.divider()
    if st.button("データをリセット"):
        st.session_state.clear()
        st.rerun()

左カラム, 右カラム = st.columns([2, 1])

with 右カラム:
    st.subheader("📊 EQイコライザー")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['項目', '値'])
    fig = go.Figure(go.Bar(
        x=df['項目'], 
        y=df['値'], 
        marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['値']]
    ))
    fig.update_layout(
        yaxis=dict(range=[-10, 10], zeroline=True), 
        height=350, 
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, width='stretch')
    st.progress(st.session_state.count / 10)

with 左カラム:
    for メッセージ in st.session_state.chat:
        with st.chat_message(メッセージ["role"]):
            st.write(メッセージ["content"])

    if st.session_state.count < 10:
        if 入力文字 := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": 入力文字})
            結果 = get_analysis(入力文字, st.session_state.scores)
            
            返答メッセージ = "お話しいただきありがとうございます。"
            
            # --- ここで徹底的に型チェックを行い、AttributeErrorを回避 ---
            if isinstance(結果, dict):
                # deltaの取得
                数値データ = 結果.get("delta")
                # 数値データが辞書形式の時のみスコア更新
                if isinstance(数値データ, dict):
                    for key in st.session_state.scores:
                        # get()が使えることを確認してから値を抽出
                        変化分 = 数値データ.get(key, 0)
                        try:
                            st.session_state.scores[key] = max(-10, min(10, st.session_state.scores[key] + float(変化分)))
                        except:
                            pass
                
                # 返答の取得
                if "reply" in 結果:
                    返答メッセージ = 結果["reply"]
            else:
                # 結果が辞書でない（単なる数字や文字列だった）場合
                返答メッセージ = "なるほど。もう少し詳しく聞かせていただけますか？"

            st.session_state.chat.append({"role": "assistant", "content": 返答メッセージ})
            st.session_state.count += 1
            st.rerun()