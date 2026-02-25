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
        model_id = "gemini-2.5-flash"
        
        if is_final:
            prompt_content = f"最終的なエゴグラムスコア {scores} から、この人物の性格類型、特徴、適職、アドバイスを詳細な日本語の文章（JSON形式）で返してください。"
        else:
            try:
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    base_rules = f.read()
            except:
                base_rules = "生命力の指向性に基づいて分析してください。"

            prompt_content = f"""
            {base_rules}
            現在の累積スコア: {scores}
            今回の発言: '{text}'
            
            必ず次のJSON形式のみで返せ。解説は不要。
            {{"delta": {{"CP": 0, "NP": 0, "A": 0, "FC": 0, "AC": 0}}, "reply": "返答内容"}}
            """
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_content,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        raw_text = response.text.strip()
        # JSON抽出の強化
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        return None

# --- 4. 画面レイアウト ---
左カラム, 右カラム = st.columns([2, 1])

with 右カラム:
    st.subheader("📊 EQイコライザー")
    df = pd.DataFrame(list(st.session_state.scores.items()), columns=['項目', '値'])
    fig = go.Figure(go.Bar(
        x=df['項目'], 
        y=df['値'], 
        marker_color=['#ff4b4b' if v < 0 else '#1f77b4' for v in df['値']]
    ))
    fig.update_layout(yaxis=dict(range=[-10.1, 10.1], zeroline=True), height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.progress(min(st.session_state.count / 10, 1.0))
    
    if st.session_state.diagnosis:
        st.success("### 診断結果")
        # JSONの構造がどうであれ、中身を表示しやすくする
        diag = st.session_state.diagnosis
        if isinstance(diag, dict):
            for k, v in diag.items():
                if k != "delta": st.write(f"**{k}**: {v}")
        else:
            st.write(diag)

with 左カラム:
    for メッセージ in st.session_state.chat:
        with st.chat_message(メッセージ["role"]):
            st.write(メッセージ["content"])

    if st.session_state.count < 10:
        if 入力文字 := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": 入力文字})
            
            with st.spinner("深層心理を分析中..."):
                結果 = get_analysis(入力文字, st.session_state.scores)
            
            if 結果 and isinstance(結果, dict):
                delta = 結果.get("delta", {})
                for key in st.session_state.scores:
                    val = delta.get(key, 0)
                    st.session_state.scores[key] = float(max(-10.0, min(10.0, st.session_state.scores[key] + float(val))))
                返答 = 結果.get("reply", "お話しいただきありがとうございます。続けてお聴かせください。")
            else:
                返答 = "申し訳ありません、少し考えを整理させてください。もう一度詳しく伺えますか？"

            st.session_state.chat.append({"role": "assistant", "content": 返答})
            st.session_state.count += 1
            
            if st.session_state.count >= 10:
                with st.spinner("最終診断中..."):
                    st.session_state.diagnosis = get_analysis("", st.session_state.scores, True)
            
            st.rerun()