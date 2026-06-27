import streamlit as st
import pandas as pd
import plotly.express as px
import os
import google.generativeai as genai
from sqlalchemy import create_engine
from collections import Counter

st.set_page_config(page_title="EU Job Market Dashboard", layout="wide", page_icon="🌍")

# ─── Premium CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif !important; }

    /* === ANIMATED GRADIENT BACKGROUND === */
    .stApp {
        background: linear-gradient(-45deg, #e0ecff, #f5f7fa, #dce8f7, #e8e0ff);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* === HERO BANNER === */
    .hero-banner {
        background: linear-gradient(135deg, #1a365d 0%, #2b5876 50%, #4e4376 100%);
        border-radius: 20px;
        padding: 40px 48px;
        margin-bottom: 32px;
        box-shadow: 0 20px 60px rgba(43, 88, 118, 0.35);
        position: relative;
        overflow: hidden;
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: -50%; right: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 60%);
        animation: shimmer 8s linear infinite;
    }
    @keyframes shimmer {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: white;
        margin: 0 0 8px 0;
        letter-spacing: -0.5px;
        text-shadow: 0 2px 12px rgba(0,0,0,0.2);
    }
    .hero-subtitle {
        font-size: 1.05rem;
        color: rgba(255,255,255,0.82);
        margin: 0;
        font-weight: 400;
        letter-spacing: 0.2px;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.75rem;
        color: rgba(255,255,255,0.9);
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 14px;
    }

    /* === GLASSMORPHIC KPI CARDS === */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        padding: 22px 20px;
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.6);
        box-shadow: 0 8px 32px rgba(43, 88, 118, 0.08);
        transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 18px 48px rgba(43, 88, 118, 0.18);
        border: 1px solid rgba(255, 255, 255, 0.9);
    }
    [data-testid="stMetricLabel"] {
        font-weight: 600;
        color: #64748b;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        font-weight: 800;
        font-size: 1.7rem !important;
        background: linear-gradient(135deg, #1a365d, #4e4376);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(255, 255, 255, 0.45);
        backdrop-filter: blur(10px);
        padding: 8px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.4);
        box-shadow: inset 0 1px 4px rgba(0,0,0,0.04);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
        font-size: 0.88rem;
        color: #64748b;
        transition: all 0.25s ease;
        border: 1px solid transparent;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.6);
        color: #2b5876;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        box-shadow: 0 4px 16px rgba(43,88,118,0.12) !important;
        color: #1a365d !important;
        border: 1px solid rgba(43,88,118,0.08) !important;
    }

    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.82) !important;
        backdrop-filter: blur(24px);
        border-right: 1px solid rgba(255,255,255,0.6);
    }
    .sidebar-logo {
        font-size: 1.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1a365d, #4e4376);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 4px;
    }
    .sidebar-tagline {
        font-size: 0.75rem;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 20px;
    }

    /* === CHATBOT === */
    .stChatMessage {
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        background: rgba(255, 255, 255, 0.85) !important;
        border: 1px solid rgba(43, 88, 118, 0.15);
        backdrop-filter: blur(12px);
        margin-bottom: 16px;
        padding: 16px;
        animation: slideUp 0.4s ease-out forwards;
        opacity: 0;
        transform: translateY(10px);
    }
    @keyframes slideUp {
        to { opacity: 1; transform: translateY(0); }
    }
    /* Differentiating assistant and user is partly handled by default Streamlit classes */
    .chat-welcome-card {
        background: linear-gradient(135deg, rgba(26,54,93,0.07), rgba(78,67,118,0.07));
        border: 1px solid rgba(43,88,118,0.12);
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 20px;
    }
    .chat-welcome-card h3 { margin: 0 0 8px 0; color: #1a365d; font-size: 1.1rem; }
    .chat-welcome-card p  { margin: 0; color: #64748b; font-size: 0.9rem; }
    .chat-suggestion {
        display: inline-block;
        background: rgba(255,255,255,0.8);
        border: 1px solid rgba(43,88,118,0.15);
        border-radius: 20px;
        padding: 5px 14px;
        font-size: 0.82rem;
        color: #2b5876;
        font-weight: 500;
        margin: 4px 4px 0 0;
        cursor: pointer;
    }

    /* === DATAFRAME === */
    .stDataFrame {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(43,88,118,0.1);
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }

    /* === DOWNLOAD BUTTON === */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1a365d, #2b5876);
        color: white;
        border-radius: 12px;
        font-weight: 600;
        border: none;
        padding: 12px 28px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(43,88,118,0.3);
    }
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(43,88,118,0.4);
    }

    /* === DIVIDER === */
    hr { border-color: rgba(43,88,118,0.1) !important; }

    /* === FOOTER === */
    .dashboard-footer {
        text-align: center;
        padding: 24px;
        color: #94a3b8;
        font-size: 0.8rem;
        font-weight: 500;
        border-top: 1px solid rgba(43,88,118,0.08);
        margin-top: 48px;
    }

    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ─── Hero Banner ─────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <div class="hero-badge">🌍 Live Data &nbsp;|&nbsp; EU Job Market</div>
    <h1 class="hero-title">EU Job Market Intelligence</h1>
    <p class="hero-subtitle">Real-time insights scraped from LinkedIn, Indeed, EURES, Freelancer & more &mdash; all in one place.</p>
</div>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def init_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://bolders:password@db:5432/job_market")
    return create_engine(db_url)

engine = init_connection()

# Auto-migrate: Add company_name column if it doesn't exist
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);"))
        conn.commit()
except Exception as e:
    pass

# Load data
cache_ttl = int(os.getenv("DASHBOARD_CACHE_TTL", "300"))
@st.cache_data(ttl=cache_ttl)
def load_data():
    try:
        query = "SELECT * FROM job_postings"
        df = pd.read_sql(query, engine)
        if 'company_name' in df.columns:
            df['company_name'] = df['company_name'].replace(["None", "none", "", "null", "Null", "NULL"], pd.NA).fillna("Unknown")
        return df
    except Exception as e:
        if "does not exist" not in str(e):
            st.error(f"Error loading data: {e}")
        return pd.DataFrame()

with st.spinner("Fetching latest job data..."):
    df = load_data()

if df.empty:
    st.info("No data found yet. The scrapers might still be running or initializing. Please refresh in a few moments.")
    st.stop()

# Ensure date columns are proper datetime
for col in ["posted_date", "scraped_date"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# --- SIDEBAR FILTERS ---
st.sidebar.markdown('<div class="sidebar-logo">🌍 EUJobs</div><div class="sidebar-tagline">Powered by live scrapers</div>', unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filters")

def multiselect_filter(col_name, title):
    unique_vals = sorted(df[col_name].dropna().unique().tolist())
    if unique_vals:
        selected = st.sidebar.multiselect(title, unique_vals, default=unique_vals)
        return selected
    return []

# Date range filter
st.sidebar.markdown("#### Date Range")
min_date = df["posted_date"].min()
max_date = df["posted_date"].max()
if pd.notna(min_date) and pd.notna(max_date):
    date_from = st.sidebar.date_input("From", value=min_date.date(), min_value=min_date.date(), max_value=max_date.date())
    date_to   = st.sidebar.date_input("To",   value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())
else:
    date_from = None
    date_to   = None

st.sidebar.markdown("---")

selected_countries  = multiselect_filter("country",          "Country")
selected_sources    = multiselect_filter("source",           "Source")
selected_categories = multiselect_filter("role_category",    "Role Category")
selected_industries = multiselect_filter("industry",         "Industry")
selected_functions  = multiselect_filter("job_function",     "Job Function")
selected_seniority  = multiselect_filter("seniority_level",  "Seniority")
selected_emp_type   = multiselect_filter("employment_type",  "Employment Type")
selected_work_type  = multiselect_filter("work_type",        "Work Type")
selected_languages  = multiselect_filter("language_required","Language Required")

# Apply filters
filtered_df = df[
    (df["country"].isin(selected_countries)) &
    (df["source"].isin(selected_sources)) &
    (df["role_category"].isin(selected_categories)) &
    (df["industry"].isin(selected_industries)) &
    (df["job_function"].isin(selected_functions)) &
    (df["seniority_level"].isin(selected_seniority)) &
    (df["employment_type"].isin(selected_emp_type)) &
    (df["work_type"].isin(selected_work_type)) &
    (df["language_required"].isin(selected_languages))
]

# Apply date filter
if date_from and date_to:
    filtered_df = filtered_df[
        (filtered_df["posted_date"].dt.date >= date_from) &
        (filtered_df["posted_date"].dt.date <= date_to)
    ]

# --- DASHBOARD KPIs ---
st.markdown("### Key Metrics")
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Total Jobs Found", len(filtered_df))

top_country = filtered_df["country"].mode()[0] if not filtered_df.empty else "N/A"
kpi2.metric("Top Hiring Country", top_country)

top_industry = filtered_df["industry"].mode()[0] if not filtered_df.empty else "N/A"
kpi3.metric("Top Industry", top_industry)

valid_rates = filtered_df.dropna(subset=["rate_normalized_eur_day"])
avg_rate = f"€{valid_rates['rate_normalized_eur_day'].mean():,.0f}" if not valid_rates.empty else "N/A"
kpi4.metric("Avg Daily Rate (EUR)", avg_rate)

lang_req_pct = (
    filtered_df["language_required"].notna().sum() / len(filtered_df) * 100
    if not filtered_df.empty else 0
)
kpi5.metric("Jobs with Language Req.", f"{lang_req_pct:.1f}%")

st.markdown("---")

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌐 Market Overview", "💰 Rate Analysis", "🗣️ Language & Skills", "📋 Raw Data", "🤖 AI Analyst"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        fig_country = px.histogram(
            filtered_df, x="country", color="source",
            title="Job Demand by Country", template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_country.update_layout(xaxis_title="Country", yaxis_title="Number of Jobs", hovermode="x unified")
        st.plotly_chart(fig_country, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    with col2:
        fig_ind = px.histogram(
            filtered_df, y="industry", color="job_function",
            title="Jobs by Industry & Function", orientation="h", template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_ind.update_layout(yaxis_title="Industry", xaxis_title="Number of Jobs", hovermode="y unified")
        st.plotly_chart(fig_ind, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    col3, col4 = st.columns(2)
    with col3:
        fig_emp = px.pie(
            filtered_df, names="employment_type", title="Employment Type Breakdown", 
            hole=0.4, template="plotly_white", color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_emp.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value} (%{percent})")
        st.plotly_chart(fig_emp, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    with col4:
        fig_work = px.pie(
            filtered_df, names="work_type", title="Work Type Breakdown", 
            hole=0.4, template="plotly_white", color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_work.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value} (%{percent})")
        st.plotly_chart(fig_work, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    # Top Companies chart
    if "company_name" in filtered_df.columns:
        top_companies = (
            filtered_df["company_name"]
            .replace("Unknown", pd.NA)
            .dropna()
            .value_counts()
            .head(10)
            .reset_index()
        )
        top_companies.columns = ["company", "count"]
        if not top_companies.empty:
            fig_companies = px.bar(
                top_companies, x="count", y="company", orientation="h",
                title="🏢 Top Hiring Companies",
                template="plotly_white",
                color="count",
                color_continuous_scale="Blues"
            )
            fig_companies.update_traces(hovertemplate="<b>%{y}</b><br>Jobs Posted: %{x}<extra></extra>")
            fig_companies.update_layout(
                yaxis_title="Company", xaxis_title="Number of Jobs",
                coloraxis_showscale=False, height=380
            )
            st.plotly_chart(fig_companies, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    # Time-series: jobs posted over time
    if "posted_date" in filtered_df.columns:
        ts_df = (
            filtered_df.dropna(subset=["posted_date"])
            .groupby(filtered_df["posted_date"].dt.date)
            .size()
            .reset_index(name="count")
        )
        ts_df.columns = ["date", "count"]
        if not ts_df.empty:
            fig_ts = px.area(
                ts_df, x="date", y="count",
                title="Jobs Posted Over Time", template="plotly_white",
                color_discrete_sequence=["#2b5876"]
            )
            fig_ts.update_traces(mode="lines+markers", hovertemplate="<b>Date</b>: %{x}<br><b>Jobs</b>: %{y}<extra></extra>")
            fig_ts.update_layout(xaxis_title="Date", yaxis_title="Jobs Posted", hovermode="x unified")
            st.plotly_chart(fig_ts, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

with tab2:
    if not valid_rates.empty:
        col5, col6 = st.columns(2)
        with col5:
            fig_rate = px.box(
                valid_rates,
                x="seniority_level", y="rate_normalized_eur_day", color="role_category",
                title="Daily Rates by Seniority & Role Category (EUR/day)",
                template="plotly_white", color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_rate.update_layout(xaxis_title="Seniority Level", yaxis_title="EUR / Day", hovermode="x unified")
            st.plotly_chart(fig_rate, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

        with col6:
            fig_rate_hist = px.histogram(
                valid_rates, x="rate_normalized_eur_day", nbins=20,
                title="Distribution of Daily Rates (EUR/day)",
                template="plotly_white", color_discrete_sequence=["#2b5876"]
            )
            fig_rate_hist.update_layout(xaxis_title="EUR / Day", yaxis_title="Count")
            st.plotly_chart(fig_rate_hist, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

        rate_by_cat = (
            valid_rates.groupby("role_category")["rate_normalized_eur_day"]
            .mean().reset_index()
            .sort_values("rate_normalized_eur_day", ascending=False)
        )
        fig_cat_rate = px.bar(
            rate_by_cat, x="role_category", y="rate_normalized_eur_day",
            title="Average Daily Rate by Role Category (EUR/day)",
            template="plotly_white", color="role_category",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_cat_rate.update_traces(hovertemplate="<b>%{x}</b><br>Avg Rate: €%{y:.2f}<extra></extra>")
        fig_cat_rate.update_layout(showlegend=False, xaxis_title="Role Category", yaxis_title="Avg EUR / Day")
        st.plotly_chart(fig_cat_rate, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

        st.info(
            "Note: Rate data is only available for sources that publicly disclose salary/rate information "
            "(Freelancer, EURES, Kaggle). LinkedIn and Indeed listings typically do not include this data — "
            "those rows will show None for rate columns, which is expected."
        )
    else:
        st.warning("No valid rate data available for the current selection. Adjust filters to see rate insights.")

with tab3:
    col7, col8 = st.columns(2)
    with col7:
        lang_df = filtered_df.copy()
        lang_df["has_language"] = lang_df["language_required"].notna().map(
            {True: "Language Required", False: "No Requirement"}
        )
        fig_lang_pct = px.pie(
            lang_df, names="has_language",
            title="% of Postings with Explicit Language Requirement",
            hole=0.45, template="plotly_white",
            color_discrete_map={"Language Required": "#4F8BF9", "No Requirement": "#CBD5E1"}
        )
        st.plotly_chart(fig_lang_pct, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    with col8:
        lang_counts = (
            filtered_df["language_required"].dropna()
            .value_counts().reset_index()
        )
        lang_counts.columns = ["language", "count"]
        if not lang_counts.empty:
            fig_lang_bar = px.bar(
                lang_counts.head(15), x="count", y="language", orientation="h",
                title="Top Languages Required", template="plotly_white",
                color_discrete_sequence=["#4F8BF9"]
            )
            fig_lang_bar.update_layout(yaxis_title="Language", xaxis_title="Number of Jobs")
            st.plotly_chart(fig_lang_bar, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
        else:
            st.info("No explicit language requirements in this selection.")

    skills_flat = []
    for skills_list in filtered_df["skills"].dropna():
        if isinstance(skills_list, list):
            skills_flat.extend([s for s in skills_list if s])
        elif isinstance(skills_list, str) and skills_list:
            skills_flat.extend([s.strip() for s in skills_list.split(",") if s.strip()])

    if skills_flat:
        skill_counts = Counter(skills_flat)
        top_skills = pd.DataFrame(skill_counts.most_common(20), columns=["skill", "count"])
        fig_skills = px.bar(
            top_skills, x="count", y="skill", orientation="h",
            title="Top 20 In-Demand Skills", template="plotly_white",
            color_discrete_sequence=["#4F8BF9"]
        )
        fig_skills.update_layout(yaxis_title="Skill", xaxis_title="Frequency", height=500)
        st.plotly_chart(fig_skills, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
    else:
        st.info("No skills data available for the current selection.")

with tab4:
    st.subheader("Raw Data Export")

    # Prepare a clean export-safe copy of the dataframe
    export_df = filtered_df.copy()

    # Convert list/array columns to comma-separated strings for clean CSV export
    if "skills" in export_df.columns:
        export_df["skills"] = export_df["skills"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else (x if x else "")
        )

    # Convert datetime columns to date strings (remove the 00:00:00 timestamp noise)
    for col in ["posted_date", "scraped_date"]:
        if col in export_df.columns:
            export_df[col] = export_df[col].dt.date

    # Reorder columns to put company_name right after id
    cols = export_df.columns.tolist()
    if "company_name" in cols:
        cols.remove("company_name")
        if "id" in cols:
            idx = cols.index("id") + 1
            cols.insert(idx, "company_name")
        else:
            cols.insert(0, "company_name")
        export_df = export_df[cols]

    # Show the clean dataframe in the UI
    st.dataframe(export_df, use_container_width=True)

    # Generate CSV and provide download
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Export Filtered Data to CSV",
        data=csv_bytes,
        file_name="eu_job_market_export.csv",
        mime="text/csv",
    )

with tab5:
    st.markdown("""
    <div class="chat-welcome-card">
        <h3>🤖 EU Job Market AI Analyst</h3>
        <p>Ask anything about the scraped job data — trends, salaries, top companies, in-demand skills, and more. The AI uses your current filter context.</p>
        <br/>
        <span class="chat-suggestion">💡 What are the top paying industries?</span>
        <span class="chat-suggestion">💡 Which country has the most remote jobs?</span>
        <span class="chat-suggestion">💡 What skills are most in demand?</span>
        <span class="chat-suggestion">💡 Show me average rates by seniority</span>
    </div>
    """, unsafe_allow_html=True)

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        st.warning("⚠️ GEMINI_API_KEY is not set. Please add it to your environment variables or `.env` file to use the chatbot.")
    else:
        genai.configure(api_key=gemini_api_key)

        if "messages" not in st.session_state or len(st.session_state.messages) == 0:
            st.session_state.messages = [{
                "role": "assistant",
                "content": "👋 Hello! I'm your EU Job Market AI Analyst. I have access to the current filtered dataset — ask me about trends, salaries, top companies, or anything you're curious about!"
            }]
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask a question about the jobs or companies..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing data..."):
                    try:
                        # Enhance the prompt with full dataset summary context
                        summary_stats = (
                            f"Total Jobs: {len(export_df)}\n"
                            f"Top Countries: {export_df['country'].value_counts().head(5).to_dict()}\n"
                            f"Top Industries: {export_df['industry'].value_counts().head(5).to_dict()}\n"
                            f"Top Roles: {export_df['role_category'].value_counts().head(5).to_dict()}\n"
                        )
                        if 'rate_normalized_eur_day' in export_df.columns:
                            summary_stats += f"Avg Rate: €{export_df['rate_normalized_eur_day'].mean():.2f}/day\n"

                        context_df = export_df.head(100).copy()
                        context_csv = context_df.to_csv(index=False)
                        
                        system_instruction = (
                            "You are an elite Job Market Intelligence AI. Your task is to analyze the provided European Job Market data.\n"
                            "Think critically step-by-step and provide rich, structured, and insightful answers.\n"
                            "Use the provided Summary Statistics to answer broad queries, and use the Data Sample for specific examples.\n"
                            "If the answer is not in the data, explicitly state that.\n\n"
                            f"--- Summary Statistics of Full Dataset ---\n{summary_stats}\n\n"
                            f"--- Data Sample (First 100 rows) ---\n{context_csv}"
                        )
                        
                        model = genai.GenerativeModel(
                            model_name="gemini-1.5-pro-latest",
                            system_instruction=system_instruction
                        )
                        
                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                        
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Error communicating with Gemini: {e}")
