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

# --- 3. 分析エンジン (Gemini 2.5 Flash 固定) ---
def get_analysis(text, scores, is_final=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return None
    try:
        client = genai.Client(api_key=api_key)
        model_id = "gemini-2.5-flash"
        
        if is_final:
            prompt_content = f"最終的なエゴグラムスコア {scores} から、この人物の『存在の質感』と性格類型を分析し、特徴、適職、アドバイスを日本語のJSONで返してください。"
        else:
            try:
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    base_rules = f.read()
            except:
                base_rules = "生命力の指向性（CP:統制、NP:包容、A:客観、FC:放射、AC:収縮）に基づいて分析してください。"

            prompt_content = f"""
            {base_rules}

            【現在の累積力学状態】: {scores}
            【今回のユーザー発言】: '{text}'
            
            指示：表面的な単語ではなく、発言の背後にある「エネルギーの動き」をあなたの知性で自律的に読み取ってください。
            必ず次のJSON形式のみで出力せよ。
            {{"delta": {{"CP": 0, "NP": 0, "A": 0, "FC": 0, "AC": 0}}, "reply": "臨床的な洞察に基づいた返答"}}
            """
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_content,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # JSON部分だけを確実に抽出
        raw_text = response.text.strip()
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(raw_text)
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
        yaxis=dict(range=[-10.1, 10.1], zeroline=True), 
        height=350, 
        margin=dict(l=10, r=10, t=10, b=10)
    )
    # 警告を回避する最新の記述
    st.plotly_chart(fig, use_container_width=True)
    st.progress(st.session_state.count / 10)
    
    if st.session_state.diagnosis:
        st.success("### 診断結果")
        st.write(st.session_state.diagnosis.get("summary", "分析が完了しました。"))

with 左カラム:
    for メッセージ in st.session_state.chat:
        with st.chat_message(メッセージ["role"]):
            st.write(メッセージ["content"])

    if st.session_state.count < 10:
        if 入力文字 := st.chat_input("今の気持ちを教えてください"):
            st.session_state.chat.append({"role": "user", "content": 入力文字})
            
            with st.spinner("深層心理を分析中..."):
                結果 = get_analysis(入力文字, st.session_state.scores)
            
            返答メッセージ = "そのお言葉の背景にあるものを、もう少し聴かせていただけますか？"
            
            if isinstance(結果, dict):
                delta = 結果.get("delta", {})
                if isinstance(delta, dict):
                    for key in st.session_state.scores:
                        change = delta.get(key, 0)
                        try:
                            current_score = float(st.session_state.scores[key])
                            new_score = max(-10.0, min(10.0, current_score + float(change)))
                            st.session_state.scores[key] = new_score
                        except: pass
                
                if "reply" in 結果:
                    返答メッセージ = 結果["reply"]

            st.session_state.chat.append({"role": "assistant", "content": 返答メッセージ})
            st.session_state.count += 1
            
            if st.session_state.count == 10:
                with st.spinner("最終診断を作成中..."):
                    st.session_state.diagnosis = get_analysis("", st.session_state.scores, True)
            
            st.rerun()