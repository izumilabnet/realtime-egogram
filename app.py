import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import re

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

# --- 3. 分析エンジン ---
def get_analysis(text, scores, is_final=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        
        if is_final:
            prompt_content = f"最終スコア {scores} に基づき、性格タイプ名、特徴、適職、アドバイスを日本語のJSONで返してください。"
        else:
            try:
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    base_rules = f.read()
            except:
                base_rules = "エゴグラムの5項目で分析してください。"

            prompt_content = f"""
            {base_rules}
            現在のスコア: {scores}
            発言: '{text}'
            必ず次のJSON形式のみで返せ。説明は不要。
            {{"delta": {{"CP": 0, "NP": 0, "A": 0, "FC": 0, "AC": 0}}, "reply": "返答"}}
            """
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", # 最新安定版に変更
            contents=prompt_content,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # JSON部分だけを抽出する処理を追加（パースエラー対策）
        res_text = response.text.strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"Error: {e}")
        return None

# --- 4. 画面レイアウト ---
with st.sidebar:
    st.title("設定")
    st.selectbox("性別", ["男性", "女性", "その他"], key="g")
    st.selectbox("年齢層", ["10代", "20代", "30代", "40代", "50代以上"], key="a")
    st.divider()
    if st.button("データをリセット"):
        for key in st.session_state.keys(): del st.session_state[key]
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
    # ログに出ていた警告への対策：width='stretch' に変更
    fig.update_layout(
        yaxis=dict(range=[-10, 10], zeroline=True), 
        height=350, 
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig, width='stretch') 
    st.progress(st.session_state.count / 10)
    
    if st.session_state.diagnosis:
        st.success("### 診断結果")
        st.write(st.session_state.diagnosis.get("summary", "分析完了"))

with 左カラム:
    for メッセージ in st.session_state.chat:
        with st.chat_message(メッセージ["role"]):
            st.write(メッセージ["content"])

    if st.session_state.count < 10:
        if 入力文字 := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": 入力文字})
            
            with st.spinner("AI分析中..."):
                結果 = get_analysis(入力文字, st.session_state.scores)
            
            # 失敗時の初期値
            返答メッセージ = "お話しいただきありがとうございます。その時、どのようなお気持ちでしたか？"
            
            if 結果 and isinstance(結果, dict):
                delta = 結果.get("delta", {})
                if isinstance(delta, dict):
                    for k in st.session_state.scores:
                        val = delta.get(k, 0)
                        # 数値計算の安全性を確保
                        try:
                            st.session_state.scores[k] = max(-10.0, min(10.0, float(st.session_state.scores[k]) + float(val)))
                        except: pass
                
                if "reply" in 結果:
                    返答メッセージ = 結果["reply"]

            st.session_state.chat.append({"role": "assistant", "content": 返答メッセージ})
            st.session_state.count += 1
            
            if st.session_state.count == 10:
                with st.spinner("最終診断中..."):
                    st.session_state.diagnosis = get_analysis("", st.session_state.scores, True)
            
            st.rerun()