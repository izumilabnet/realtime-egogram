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
if 'diagnosis' not in st.session_state: st.session_state.diagnosis = None

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
def get_ai_response(text, scores, is_final=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        model_id = "gemini-2.5-flash"
        
        if is_final:
            prompt = f"エゴグラム診断の最終結果を作成してください。最終スコア: {scores}。以下のJSON形式で返してください: {{\"title\": \"性格タイプの名前\", \"summary\": \"全体的な性格診断\", \"jobs\": \"適職\", \"love\": \"恋愛傾向\"}}"
        else:
            prompt = f"心理分析を行い、各指標を-3から+3の範囲で増減させてください。AC（順応性）の変化も必ず含めること。現在のスコア: {scores}, 発言: '{text}'。以下のJSON形式のみで返してください: {{\"delta\": {{\"CP\": 1, \"NP\": -2, \"A\": 0, \"FC\": 3, \"AC\": -1}}, \"reply\": \"ユーザーへの共感的な返答\"}}"
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. UIレイアウト ---
with st.sidebar:
    st.title("設定")
    st.selectbox("性別", ["男性", "女性", "その他"], key="g")
    st.selectbox("年齢層", ["10代", "20代", "30代", "40代", "50代以上"], key="a")
    st.divider()
    if st.button("データをリセット"):
        st.session_state.clear()
        st.rerun()

左, 右 = st.columns([2, 1])

with 右:
    st.subheader("📊 EQイコライザー")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['項目', '値'])
    # バーの色を正負で分ける
    colors = ['#ff4b4b' if v < 0 else '#1f77b4' for v in df['値']]
    fig = go.Figure(go.Bar(x=df['項目'], y=df['値'], marker_color=colors))
    fig.update_layout(yaxis=dict(range=[-10, 10], zeroline=True), height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width='stretch')
    st.progress(st.session_state.count / 10)
    
    if st.session_state.diagnosis:
        d = st.session_state.diagnosis
        st.success(f"### 診断結果: {d.get('title')}")
        st.info(f"**分析まとめ:**\n{d.get('summary')}")
        st.warning(f"**適職アドバイス:**\n{d.get('jobs')}")
        st.error(f"**恋愛の傾向:**\n{d.get('love')}")

with 左:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.count < 10:
        if inp := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": inp})
            res = get_ai_response(inp, st.session_state.scores)
            
            if isinstance(res, dict):
                # スコア更新（型チェック付き）
                deltas = res.get("delta", {})
                if isinstance(deltas, dict):
                    for k in st.session_state.scores:
                        val = deltas.get(k, 0)
                        try:
                            st.session_state.scores[k] = max(-10, min(10, st.session_state.scores[k] + float(val)))
                        except: pass
                
                st.session_state.chat.append({"role": "assistant", "content": res.get("reply", "...")})
                st.session_state.count += 1
                
                # 10回目で最終診断を取得
                if st.session_state.count == 10:
                    st.session_state.diagnosis = get_ai_response("", st.session_state.scores, True)
                
                st.rerun()