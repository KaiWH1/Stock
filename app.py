import datetime
import requests
import re
import streamlit as st

# =====================================================================
# 🔑 CONFIGURATION: SECURELY LOAD API KEYS FROM STREAMLIT SECRETS
# =====================================================================
# 彻底移除所有明文密匙。本地运行时它会读取 .streamlit/secrets.toml
# 云端运行时它会读取 Streamlit Cloud 后台的 Secrets 
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
# =====================================================================

NEWS_URL = "https://newsapi.org/v2/everything"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

st.set_page_config(page_title="AI Market Intelligence Center", layout="wide")
st.title("📱 Live AI Market Dashboard")

# --- ON-PAGE DISPLAY CONTROLS ---
col_title, col_select = st.columns([3, 1])

with col_title:
    st.write("Fetching real-time rolling market news and generating structured intelligence insights.")

with col_select:
    max_display_count = st.selectbox(
        "Articles per page:",
        options=[1, 3, 5, 10, 15, 20],
        index=2  # Defaults to 5 articles
    )

# Initialize page state tracker
if "current_page" not in st.session_state:
    st.session_state.current_page = 0

# --- OPENROUTER CLOUD AI PROCESSING ---
@st.cache_data(show_spinner=False)
def generate_ai_summary(title, description):
    # ✨ FIXED: 优化了校验逻辑，防止在 Secrets 未正确加载时引发死循环报错
    if not OPENROUTER_API_KEY:
        return "❌ 错误: 未能在 Streamlit Secrets 中找到有效的 `OPENROUTER_API_KEY`！请检查云端 Settings 或本地 secrets.toml。"

    full_text = f"Title: {title}\nDescription: {description}"
    
    system_prompt = (
        "你是一位顶级的国际金融与科技行业研究专家。请阅读以下英文新闻，提取核心商业情报。\n"
        "【特别要求】即使该新闻表面上看似与特定公司无关，你也必须推导其潜在的宏观经济传导路径、对整个上下游产业链的影响，或对相关概念板块的潜在干预效应。\n\n"
        "【输出控制】\n"
        "1. 绝对不要输出任何思维链、思考过程（如 <think> 标签及其中的内容）、前言或过渡性废话。\n"
        "2. 语言要精炼准确，重点突出，避免冗长描述，确保内容能完整展示。\n"
        "你必须直接用中文（简体或繁体）输出以下结构化摘要：\n\n"
        "核心问题: (用一句话精准概括该事件本质)\n"
        "核心数据与发现: (列出关键数字、时间点或事实要点)\n"
        "实质影响: (深度分析：这对相关行业、宏观经济或特定产业链意味着什么？短期与长期的潜在机会/风险是什么？)\n"
        "受影响板块/公司及股票代码: (指明受波及的行业板块、核心企业名称及其美股/港股/A股股票代码。若无提及特定公司，请列出受波及的核心产业集群)"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "openrouter/free",  
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_text}
        ],
        "temperature": 0.1,  
        "max_tokens": 2000    
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            
            # --- HARD SANITIZER FOR THINKING TAGS ---
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content
            
        return f"⚠️ OpenRouter Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"⚠️ Pipeline Request Failed: {str(e)}"

# --- CACHED NEWS FETCH ---
@st.cache_data(ttl=600)  
def fetch_live_news():
    if not NEWS_API_KEY:
        st.error("❌ 错误: 未能在 Streamlit Secrets 中找到有效的 `NEWS_API_KEY`！")
        return []

    params = {
        "q": "market OR finance OR technology",
        "sortBy": "publishedAt",  
        "pageSize": 100,          
        "language": "en",
        "apiKey": NEWS_API_KEY
    }
    try:
        response = requests.get(NEWS_URL, params=params)
        if response.status_code == 200:
            return response.json().get("articles", [])
        return []
    except Exception:
        return []

# --- UI MAIN RENDER LOOP ---
def main():
    st.caption("⚡ **Live Stream Mode Activated:** Sorting live, rolling coverage from current hour going backward.")

    raw_articles = fetch_live_news()

    if not raw_articles:
        st.info("No matching text feeds returned from primary source APIs. Check API limit parameters or query syntax.")
        return

    # Clean out placeholder or removed news articles first
    valid_articles = []
    for art in raw_articles:
        url = art.get("url")
        title = art.get("title")
        desc = art.get("description", "")
        
        if url and title and title != "[Removed]" and desc and len(desc) >= 15:
            valid_articles.append(art)

    # Hard-enforced reverse chronological sort by timestamp strings
    valid_articles = sorted(
        valid_articles, 
        key=lambda x: x.get("publishedAt", ""), 
        reverse=True
    )

    total_articles = len(valid_articles)
    
    # Calculate index boundaries for the selected page slice
    start_idx = st.session_state.current_page * max_display_count
    end_idx = start_idx + max_display_count
    
    # Extract only the items meant for this specific view window
    page_items = valid_articles[start_idx:end_idx]

    if not page_items:
        st.info("No more articles available on this view path.")
        return

    # Render out the specific sliced batch
    for art in page_items:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(art.get("title"))
                published_time = art.get('publishedAt', '')
                formatted_time = published_time.replace('T', ' ').replace('Z', '') if published_time else ''
                st.caption(f"🏛️ {art.get('source', {}).get('name')} | ⏰ Published UTC: `{formatted_time}`")
                st.write(art.get("description", ""))
                st.markdown(f"[Original Link]({art.get('url')})")
            with col2:
                if art.get("urlToImage"):
                    st.image(art.get("urlToImage"), use_container_width=True)
            
            with st.expander("🤖 查看 智能结构化商业分析报告 (中文本地化)", expanded=True):
                with st.spinner("Analyzing text via cloud LPU..."):
                    summary = generate_ai_summary(art.get("title"), art.get("description", ""))
                    st.markdown(summary)

    st.write("---")
    
    # --- PAGINATION NAVIGATION FOOTER ---
    col_prev, col_page_num, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.session_state.current_page > 0:
            if st.button("⬅️ Previous Page"):
                st.session_state.current_page -= 1
                st.rerun()

    with col_page_num:
        current_view_page = st.session_state.current_page + 1
        max_possible_pages = (total_articles + max_display_count - 1) // max_display_count
        st.markdown(f"<p style='text-align: center;'>Page <b>{current_view_page}</b> of {max_possible_pages}</p>", unsafe_allow_html=True)

    with col_next:
        if end_idx < total_articles:
            if st.button("Next Page ➡️"):
                st.session_state.current_page += 1
                st.rerun()

if __name__ == "__main__":
    main()