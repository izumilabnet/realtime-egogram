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
    if pw == "okok":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 属性入力（サイドバー） ---
st.sidebar.title("👤 プロフィール設定")
gender = st.sidebar.selectbox("性別", ["男性", "女性", "その他", "回答しない"])
age = st.sidebar.number_input("年齢", min_value=0, max_value=120, value=30)

# --- 4. 分析エンジン ---
def get_analysis(text, scores, is_final=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return {"delta": {}, "reply": "APIキーが設定されていません。"}
    
    try:
        client = genai.Client(api_key=api_key)
        model_id = "gemini-2.5-flash"
        user_info = f"属性: {age}歳、{gender}。"

        if is_final:
            prompt_content = f"""
            {user_info}
            累積スコア {scores} に基づき、性格類型、強み・弱み、適職、そして現在のスコア傾向から見た「恋愛アドバイス（パートナー選びや注意点）」を日本語のJSONで返してください。
            """
        else:
            try:
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    base_rules = f.read()
            except:
                base_rules = "ユーザーの発言をエゴグラムに基づき分析してください。"

            prompt_content = f"""
            {base_rules}
            {user_info}
            現在の累積スコア: {scores}
            ユーザーの発言: '{text}'
            
            指示：
            1. 分析：発言からCP, NP, A, FC, ACの増減（-3〜3）を決定。
            2. 応答：ユーザーの心境（例：へとへと、疲れた）に寄り添い、属性を考慮した返答を作成。
            3. 出力：以下のJSON形式のみを出力。
            {{"delta": {{"CP": 0, "NP": 0, "A": 0, "FC": 0, "AC": 0}}, "reply": "返答内容"}}
            """
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_content,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        raw_text = response.text.strip()
        json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        return {"delta": {"CP":0, "NP":0, "A":0, "FC":0, "AC":0}, "reply": raw_text}

    except Exception as e:
        # 定型文ではなく、エラー内容をあえて表示してデバッグしやすくします
        return {"delta": {"CP":0, "NP":0, "A":0, "FC":0, "AC":0}, "reply": f"申し訳ありません、分析中にエラーが発生しました: {str(e)}"}

# --- 5. 画面レイアウト ---
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
    st.plotly_chart(fig, width="stretch")
    st.progress(min(st.session_state.count / 10, 1.0))
    
    if st.session_state.diagnosis:
        st.success("### 🎓 性格・恋愛カルテ")
        diag = st.session_state.diagnosis
        if isinstance(diag, dict):
            for k, v in diag.items():
                if k != "delta":
                    st.markdown(f"**【{k}】**")
                    st.write(v)
                    st.divider()

with 左カラム:
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if st.session_state.count < 10:
        if 入力文字 := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": 入力文字})
            with st.spinner("深層心理を分析中..."):
                結果 = get_analysis(入力文字, st.session_state.scores)
            
            delta = 結果.get("delta", {})
            for key in st.session_state.scores:
                val = delta.get(key, 0)
                try:
                    curr = st.session_state.scores[key]
                    st.session_state.scores[key] = float(max(-10.0, min(10.0, curr + float(val))))
                except: pass
            
            返答 = 結果.get("reply", "...")
            st.session_state.chat.append({"role": "assistant", "content": 返答})
            st.session_state.count += 1
            if st.session_state.count >= 10:
                with st.spinner("最終カルテを生成中..."):
                    st.session_state.diagnosis = get_analysis("", st.session_state.scores, True)
            st.rerun()