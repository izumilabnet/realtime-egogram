import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from google import genai
from google.genai import types
import json
import os
import time
import random

# --- 1. 初期設定 & 学会発表を意識したUI ---
st.set_page_config(page_title="REALTIME-EGOGRAM", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #fdfdfd; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .reason-text { color: #888; font-size: 0.75rem; font-style: italic; margin-top: -10px; margin-bottom: 15px; padding-left: 10px; }
    .final-card {
        background-color: #ffffff; border-radius: 20px; padding: 25px;
        border: 1px solid #eee; box-shadow: 0 10px 25px rgba(0,0,0,0.05);
    }
    .auth-container { max-width: 600px; margin: 40px auto; text-align: center; padding: 40px; border-radius: 30px; background: white; box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# セッション状態の初期化
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'ego_scores' not in st.session_state: st.session_state.ego_scores = {"CP": 0.0, "NP": 0.0, "A": 0.0, "FC": 0.0, "AC": 0.0}
if 'history_data' not in st.session_state: st.session_state.history_data = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'message_count' not in st.session_state: st.session_state.message_count = 0
if 'final_diagnosis' not in st.session_state: st.session_state.final_diagnosis = None

# --- 2. 認証画面 ---
if not st.session_state.authenticated:
    st.markdown('<div class="auth-container"><h1>REALTIME-EGOGRAM</h1><p>リアルタイム・エゴグラム</p><div style="text-align:left; margin:20px 0; border-left:3px solid #ff4b4b; padding-left:15px; color:#666;">性格は固定された資産ではなく、対話の中で奏でられる旋律（イコライザー）です。</div></div>', unsafe_allow_html=True)
    pw_input = st.text_input("PASSWORD", type="password")
    if st.button("ROOM ENTER"):
        if pw_input == "okok":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# --- 3. 分析ロジック (APIキーチェック含む) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("APIキーが設定されていません。環境変数 GEMINI_API_KEY を確認してください。")
    st.stop()

client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_input_gemini(user_text, current_scores, is_final=False):
    # 学会発表を意識した、より詳細なプロンプト設計
    if is_final:
        prompt = f"エゴグラム最終診断。スコア（-10〜10）: {current_scores}。二つ名、性格総括、適職、恋愛傾向を詳細なJSONで返してください。"
    else:
        prompt = f"心理カウンセリング分析。現在の自我状態（-10〜10）: {current_scores}。発言: \"{user_text}\"。各指標のdelta(-3〜3)と理由、返答をJSON形式で返してください。"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        # 混雑時のリトライ
        time.sleep(1)
        return None

# --- 4. メインUI ---
with st.sidebar:
    st.title("REALTIME-EGOGRAM")
    user_gender = st.selectbox("性別", ["男性", "女性", "その他"])
    user_age = st.selectbox("年代", ["10代", "20代", "30代", "40代", "50代以上"])
    st.divider()
    
    # 学会発表・研究用：データ出力ボタン
    if st.session_state.history_data:
        csv = pd.DataFrame(st.session_state.history_data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📊 診断ログ(CSV)を保存", data=csv, file_name='egogram_research_data.csv', mime='text/csv')
    
    if st.button("セッションをリセット"):
        st.session_state.clear()
        st.rerun()

col_main, col_viz = st.columns([2, 1])

with col_viz:
    st.write("📊 **EQイコライザー**")
    df_bar = pd.DataFrame(list(st.session_state.ego_scores.items()), columns=['指標', '値'])
    
    # 視覚的に分かりやすい動的な配色
    colors = ['rgba(255,99,132,0.7)' if v < 0 else 'rgba(100,149,237,0.7)' for v in df_bar['値']]
    
    fig = go.Figure(go.Bar(x=df_bar['指標'], y=df_bar['値'], marker_color=colors))
    fig.update_layout(
        yaxis=dict(range=[-10, 10], zeroline=True, zerolinewidth=2, zerolinecolor='black'),
        height=300, 
        margin=dict(l=20, r=20, t=10, b=0)
    )
    # width='stretch' は一部環境でエラーになるため、width=None（自動）を基本とします
    st.plotly_chart(fig, key="egogram_chart") 
    
    # 進捗バー (0.0 - 1.0)
    progress_val = float(st.session_state.message_count / 10)
    st.progress(progress_val)
    st.caption(f"Session Depth: {st.session_state.message_count * 10}%")

with col_main:
    if st.session_state.final_diagnosis:
        d = st.session_state.final_diagnosis
        st.markdown(f"""
        <div class="final-card">
            <h3 style='text-align:center;'>🏆 {d.get('title', '診断完了')}</h3>
            <p>{d.get('summary', '')}</p>
            <hr>
            <b>適職例:</b> {", ".join(d.get('suitable_jobs', []))}<br>
            <b>対人傾向:</b> {d.get('romance_tendency', '')}
        </div>
        """, unsafe_allow_html=True)
        st.balloons()
    
    # チャット表示
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "reason" in msg:
                    st.markdown(f'<p class="reason-text">💡 {msg["reason"]}</p>', unsafe_allow_html=True)

    # 入力フォーム
    if st.session_state.message_count < 10 and not st.session_state.final_diagnosis:
        if prompt := st.chat_input("今、何を感じていますか？"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            
            with st.spinner("心の波形を分析中..."):
                res = analyze_input_gemini(prompt, st.session_state.ego_scores)
                
                if res and "delta" in res:
                    # スコア更新
                    for k in st.session_state.ego_scores:
                        change = res["delta"].get(k, 0)
                        st.session_state.ego_scores[k] = max(-10.0, min(10.0, st.session_state.ego_scores[k] + float(change)))
                    
                    st.session_state.message_count += 1
                    # 履歴保存
                    st.session_state.history_data.append({
                        "Step": st.session_state.message_count,
                        "Input": prompt,
                        **st.session_state.ego_scores,
                        "Reason": res.get("reason", "")
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": res.get("reply", ""), 
                        "reason": res.get("reason", "")
                    })
                    
                    if st.session_state.message_count == 10:
                        st.session_state.final_diagnosis = analyze_input_gemini("", st.session_state.ego_scores, True)
                    
                    st.rerun()