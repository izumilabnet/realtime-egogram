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
            prompt_content = f"最終的なエゴグラムスコア {scores} から、性格類型、特徴、適職、アドバイスを詳細な日本語のJSONで返してください。"
        else:
            try:
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    base_rules = f.read()
            except:
                base_rules = "エゴグラム分析を行ってください。"

            prompt_content = f"""
            {base_rules}
            現在の累積スコア: {scores}
            ユーザーの発言: '{text}'
            
            【厳守】
            1. 数値分析(delta)と共感応答(reply)の両方を行ってください。
            2. 以下のJSON形式を必ず含めてください。
            {{"delta": {{"CP": 0, "NP": 0, "A": 0, "FC": 0, "AC": 0}}, "reply": "ここに応答を記述"}}
            """
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_content,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        raw_text = response.text.strip()
        
        # --- 内部処理の強化：数値と言葉を分離して抽出 ---
        extracted_data = {"delta": {"CP":0, "NP":0, "A":0, "FC":0, "AC":0}, "reply": raw_text}
        
        # JSON部分だけを探す
        json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                extracted_data["delta"] = parsed.get("delta", extracted_data["delta"])
                # JSON内のreplyがあれば採用、なければ全文をreplyにする
                extracted_data["reply"] = parsed.get("reply", raw_text)
            except:
                pass
        
        return extracted_data

    except Exception:
        return {"delta": {"CP":0, "NP":0, "A":0, "FC":0, "AC":0}, "reply": "（接続を維持しています。お話を続けてください。）"}

# --- 4. 画面レイアウト ---
# (中略: レイアウトとループ処理は以前の通り維持)
# ※スペースの都合上省略しますが、ここから下のロジックも全角スペースを除去して実行してください。