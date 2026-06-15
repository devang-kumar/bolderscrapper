import streamlit as st
import pandas as pd
import plotly.express as px
import os
from sqlalchemy import create_engine

st.set_page_config(page_title="EU Job Market Dashboard", page_icon="🇪🇺", layout="wide")

# Custom CSS for a flawless, light UI
st.markdown("""
<style>
    /* Clean metric cards */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
    }
    /* Hide top padding for a cleaner look */
    .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🇪🇺 EU Job Market Dashboard")
st.markdown("### Interactive Insights into the European Job Market")

# Database connection
@st.cache_resource
def init_connection():
    db_url = os.getenv("DATABASE_URL", "postgresql://bolders:password@db:5432/job_market")
    return create_engine(db_url)

engine = init_connection()

# Load data
cache_ttl = int(os.getenv("DASHBOARD_CACHE_TTL", "300"))
@st.cache_data(ttl=cache_ttl)
def load_data():
    try:
        query = "SELECT * FROM job_postings"
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        # If the table doesn't exist yet, just return empty gracefully instead of showing a scary red error
        if "does not exist" not in str(e):
            st.error(f"Error loading data: {e}")
        return pd.DataFrame()

with st.spinner("Fetching latest job data..."):
    df = load_data()

if df.empty:
    st.info("ℹ️ No data found yet. The scrapers might still be running or initializing. Please refresh in a few moments.")
    st.stop()

# Ensure date columns are proper datetime
for col in ["posted_date", "scraped_date"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎯 Filters")

def multiselect_filter(col_name, title):
    unique_vals = sorted(df[col_name].dropna().unique().tolist())
    if unique_vals:
        selected = st.sidebar.multiselect(title, unique_vals, default=unique_vals)
        return selected
    return []

# Date range filter
st.sidebar.markdown("#### 📅 Date Range")
min_date = df["posted_date"].min()
max_date = df["posted_date"].max()
if pd.notna(min_date) and pd.notna(max_date):
    date_from = st.sidebar.date_input("From", value=min_date.date(), min_value=min_date.date(), max_value=max_date.date())
    date_to = st.sidebar.date_input("To", value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())
else:
    date_from = None
    date_to = None

st.sidebar.markdown("---")

selected_countries  = multiselect_filter("country",          "📍 Country")
selected_sources    = multiselect_filter("source",           "🌐 Source")
selected_categories = multiselect_filter("role_category",    "📂 Role Category")
selected_industries = multiselect_filter("industry",         "🏢 Industry")
selected_functions  = multiselect_filter("job_function",     "⚙️ Job Function")
selected_seniority  = multiselect_filter("seniority_level",  "📈 Seniority")
selected_emp_type   = multiselect_filter("employment_type",  "💼 Employment Type")
selected_work_type  = multiselect_filter("work_type",        "🏠 Work Type")
selected_languages  = multiselect_filter("language_required","🗣️ Language Required")

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
avg_rate = f"€{valid_rates['rate_normalized_eur_day'].mean():.2f}" if not valid_rates.empty else "N/A"
kpi4.metric("Avg Daily Rate", avg_rate)

lang_req_pct = (
    filtered_df["language_required"].notna().sum() / len(filtered_df) * 100
    if not filtered_df.empty else 0
)
kpi5.metric("Jobs with Language Req.", f"{lang_req_pct:.1f}%")

st.markdown("---")

# --- DASHBOARD TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Market Overview", "💰 Rate Analysis", "🌍 Language & Skills", "📋 Raw Data"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        fig_country = px.histogram(
            filtered_df, x="country", color="source",
            title="Job Demand by Country",
            template="plotly_white"
        )
        fig_country.update_layout(xaxis_title="Country", yaxis_title="Number of Jobs", hovermode="x unified")
        st.plotly_chart(fig_country, use_container_width=True)

    with col2:
        fig_ind = px.histogram(
            filtered_df, y="industry", color="job_function",
            title="Jobs by Industry & Function",
            orientation="h", template="plotly_white"
        )
        fig_ind.update_layout(yaxis_title="Industry", xaxis_title="Number of Jobs")
        st.plotly_chart(fig_ind, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig_emp = px.pie(
            filtered_df, names="employment_type",
            title="Employment Type Breakdown",
            hole=0.4, template="plotly_white"
        )
        st.plotly_chart(fig_emp, use_container_width=True)

    with col4:
        fig_work = px.pie(
            filtered_df, names="work_type",
            title="Work Type Breakdown",
            hole=0.4, template="plotly_white"
        )
        st.plotly_chart(fig_work, use_container_width=True)

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
                title="Jobs Posted Over Time",
                template="plotly_white",
                color_discrete_sequence=["#4F8BF9"]
            )
            fig_ts.update_layout(xaxis_title="Date", yaxis_title="Jobs Posted")
            st.plotly_chart(fig_ts, use_container_width=True)

with tab2:
    if not valid_rates.empty:
        col5, col6 = st.columns(2)
        with col5:
            # Brief explicitly requests rate by role_category and seniority
            fig_rate = px.box(
                valid_rates,
                x="seniority_level",
                y="rate_normalized_eur_day",
                color="role_category",
                title="Daily Rates by Seniority & Role Category (EUR/day)",
                template="plotly_white"
            )
            fig_rate.update_layout(xaxis_title="Seniority Level", yaxis_title="EUR / Day")
            st.plotly_chart(fig_rate, use_container_width=True)
        with col6:
            fig_rate_hist = px.histogram(
                valid_rates, x="rate_normalized_eur_day",
                nbins=20,
                title="Distribution of Daily Rates (EUR/day)",
                template="plotly_white",
                color_discrete_sequence=["#4F8BF9"]
            )
            fig_rate_hist.update_layout(xaxis_title="EUR / Day", yaxis_title="Count")
            st.plotly_chart(fig_rate_hist, use_container_width=True)

        # Rate by role category bar chart
        rate_by_cat = (
            valid_rates.groupby("role_category")["rate_normalized_eur_day"]
            .mean()
            .reset_index()
            .sort_values("rate_normalized_eur_day", ascending=False)
        )
        fig_cat_rate = px.bar(
            rate_by_cat, x="role_category", y="rate_normalized_eur_day",
            title="Average Daily Rate by Role Category (EUR/day)",
            template="plotly_white",
            color="role_category"
        )
        fig_cat_rate.update_layout(showlegend=False, xaxis_title="Role Category", yaxis_title="Avg EUR / Day")
        st.plotly_chart(fig_cat_rate, use_container_width=True)
    else:
        st.warning("No valid rate data available for the current selection. Adjust filters to see rate insights.")

with tab3:
    col7, col8 = st.columns(2)
    with col7:
        # % of postings with explicit language requirement (brief requirement)
        lang_df = filtered_df.copy()
        lang_df["has_language"] = lang_df["language_required"].notna().map(
            {True: "Language Required", False: "No Requirement"}
        )
        fig_lang_pct = px.pie(
            lang_df, names="has_language",
            title="% of Postings with Explicit Language Requirement",
            hole=0.45,
            template="plotly_white",
            color_discrete_map={"Language Required": "#4F8BF9", "No Requirement": "#CBD5E1"}
        )
        st.plotly_chart(fig_lang_pct, use_container_width=True)

    with col8:
        # Language breakdown (for those that have one)
        lang_counts = (
            filtered_df["language_required"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        lang_counts.columns = ["language", "count"]
        if not lang_counts.empty:
            fig_lang_bar = px.bar(
                lang_counts.head(15), x="count", y="language",
                orientation="h",
                title="Top Languages Required",
                template="plotly_white",
                color_discrete_sequence=["#4F8BF9"]
            )
            fig_lang_bar.update_layout(yaxis_title="Language", xaxis_title="Number of Jobs")
            st.plotly_chart(fig_lang_bar, use_container_width=True)
        else:
            st.info("No explicit language requirements in this selection.")

    # Skills breakdown
    skills_flat = []
    for skills_list in filtered_df["skills"].dropna():
        if isinstance(skills_list, list):
            skills_flat.extend(skills_list)
    if skills_flat:
        from collections import Counter
        skill_counts = Counter(skills_flat)
        top_skills = pd.DataFrame(skill_counts.most_common(20), columns=["skill", "count"])
        fig_skills = px.bar(
            top_skills, x="count", y="skill",
            orientation="h",
            title="Top 20 In-Demand Skills",
            template="plotly_white",
            color_discrete_sequence=["#4F8BF9"]
        )
        fig_skills.update_layout(yaxis_title="Skill", xaxis_title="Frequency", height=500)
        st.plotly_chart(fig_skills, use_container_width=True)

with tab4:
    st.subheader("Raw Data Export")
    st.dataframe(filtered_df, use_container_width=True)
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Filtered Data to CSV",
        data=csv,
        file_name="job_market_export.csv",
        mime="text/csv",
    )
