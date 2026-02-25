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
            prompt = f"最終スコア {scores} に基づき、エゴグラムのグラフパターンを解釈してください。性格名、全体傾向、適職、対人アドバイスを日本語のJSONで返してください。"
        else:
            # 概念を排除し、特定の言動に対するスコアリングを指示
            prompt = f"""
            以下のルールに従い、ユーザーの発言から各項目の加点・減点（-3から+3）を判定してください。
            
            【加点・減点の判定基準】
            CP（批判的な親）: 規律、批判、理想の追求、他者への指導的態度があればプラス。
            NP（養育的な親）: 許容、同情、世話焼き、優しさがあればプラス。
            A（大人）: 客観的事実の提示、論理的分析、冷静な判断があればプラス。
            FC（自由な子供）: 感情の爆発、好奇心、わがまま、ユーモアがあればプラス。
            AC（順応した子供）: 他者への同調、我慢、遠慮、周囲の期待への適合、自己抑制があれば「必ずプラス」に加点してください。
            
            現在の累積スコア: {scores}
            今回の発言: '{text}'
            
            出力は以下のJSON形式のみとします。余計な解説は一切不要です。
            {{"delta": {{"CP\": 0, \"NP\": 0, \"A\": 0, \"FC\": 0, \"AC\": 0}}, \"reply\": \"ユーザーへの短い返答\"}}
            """
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return None

# --- 4. 画面レイアウト ---
左, 右 = st.columns([2, 1])

with 右:
    st.subheader("📊 EQイコライザー")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['項目', '値'])
    fig = go.Figure(go.Bar(
        x=df['項目'], 
        y=df['値'], 
        marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['値']]
    ))
    fig.update_layout(
        yaxis=dict(range=[-10, 10], zeroline=True, gridcolor='LightGray'),
        xaxis=dict(categoryorder='array', categoryarray=["CP", "NP", "A", "FC", "AC"]),
        height=400, margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor='white'
    )
    st.plotly_chart(fig, width='stretch')
    st.progress(st.session_state.count / 10)
    
    if st.session_state.diagnosis:
        d = st.session_state.diagnosis
        st.success(f"### 診断結果")
        st.write(d.get('summary', ''))

with 左:
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    if st.session_state.count < 10:
        if inp := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": inp})
            res = get_ai_response(inp, st.session_state.scores)
            
            if isinstance(res, dict):
                deltas = res.get("delta", {})
                if isinstance(deltas, dict):
                    for k in st.session_state.scores:
                        val = deltas.get(k, 0)
                        try:
                            # 累積計算（-10から10の範囲内）
                            st.session_state.scores[k] = max(-10, min(10, st.session_state.scores[k] + float(val)))
                        except: pass
                
                st.session_state.chat.append({"role": "assistant", "content": res.get("reply", "...")})
                st.session_state.count += 1
                
                if st.session_state.count == 10:
                    st.session_state.diagnosis = get_ai_response("", st.session_state.scores, True)
                
                st.rerun()

with st.sidebar:
    st.title("REALTIME-EGOGRAM")
    if st.button("診断をリセット"):
        st.session_state.clear()
        st.rerun()