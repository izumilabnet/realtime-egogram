import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai  # 新しいライブラリのインポート
from google.genai import types
import json
import re
import os
import time
import random

# --- 1. 初期設定 ---
st.set_page_config(page_title="Gemini Egogram AI", layout="wide")

# APIキー設定
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("APIキーが設定されていません。")
    st.stop()

# 新しいクライアントの初期化
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.0-flash"

# --- セッション状態等の管理は変更なし（省略） ---

# --- 2. AI分析ロジック (最新SDK版) ---
def analyze_input_gemini(user_text, current_scores, is_final=False):
    gender_str = user_gender if user_gender != "（未選択）" else "不明"
    age_str = user_age if user_age != "（未選択）" else "不明"
    context = f"相談者情報: {gender_str}, {age_str}"

    prompt = f"（中略：プロンプト内容は維持）"

    for attempt in range(3):
        try:
            # 最新のSDKによる生成
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json" # 明示的にJSONを指定可能に！
                )
            )
            # textプロパティから直接取得
            return json.loads(response.text)
            
        except Exception as e:
            if "429" in str(e):
                wait = random.randint(15, 25)
                st.warning(f"現在混雑しています。{wait}秒後に再試行します({attempt+1}/3)")
                time.sleep(wait)
                continue
            st.error(f"エラーが発生しました: {e}")
            break
    return None

# --- 3. UI修正 (Warning対策) ---
with tab1:
    # use_container_width=True を width='stretch' に変更
    st.plotly_chart(fig_bar, width='stretch')