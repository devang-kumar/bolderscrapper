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

# --- SIDEBAR FILTERS ---
st.sidebar.header("🎯 Filters")

def multiselect_filter(col_name, title):
    unique_vals = sorted(df[col_name].dropna().unique().tolist())
    if unique_vals:
        selected = st.sidebar.multiselect(title, unique_vals, default=unique_vals)
        return selected
    return []

selected_countries = multiselect_filter("country", "📍 Country")
selected_sources = multiselect_filter("source", "🌐 Source")
selected_industries = multiselect_filter("industry", "🏢 Industry")
selected_functions = multiselect_filter("job_function", "⚙️ Job Function")
selected_seniority = multiselect_filter("seniority_level", "📈 Seniority")
selected_emp_type = multiselect_filter("employment_type", "💼 Employment Type")
selected_work_type = multiselect_filter("work_type", "🏠 Work Type")

# Apply filters
filtered_df = df[
    (df["country"].isin(selected_countries)) &
    (df["source"].isin(selected_sources)) &
    (df["industry"].isin(selected_industries)) &
    (df["job_function"].isin(selected_functions)) &
    (df["seniority_level"].isin(selected_seniority)) &
    (df["employment_type"].isin(selected_emp_type)) &
    (df["work_type"].isin(selected_work_type))
]

# --- DASHBOARD KPIs ---
st.markdown("### Key Metrics")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Jobs Found", len(filtered_df))

top_country = filtered_df["country"].mode()[0] if not filtered_df.empty else "N/A"
kpi2.metric("Top Hiring Country", top_country)

top_industry = filtered_df["industry"].mode()[0] if not filtered_df.empty else "N/A"
kpi3.metric("Top Industry", top_industry)

valid_rates = filtered_df.dropna(subset=['rate_normalized_eur_day'])
avg_rate = f"€{valid_rates['rate_normalized_eur_day'].mean():.2f}" if not valid_rates.empty else "N/A"
kpi4.metric("Avg Daily Rate", avg_rate)

st.markdown("---")

# --- DASHBOARD TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Market Overview", "💰 Rate Analysis", "📋 Raw Data"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        fig_country = px.histogram(filtered_df, x="country", color="source", title="Job Demand by Country", template="plotly_white")
        fig_country.update_layout(xaxis_title="Country", yaxis_title="Number of Jobs", hovermode="x unified")
        st.plotly_chart(fig_country, use_container_width=True)

    with col2:
        fig_ind = px.histogram(filtered_df, y="industry", color="job_function", title="Jobs by Industry & Function", orientation='h', template="plotly_white")
        fig_ind.update_layout(yaxis_title="Industry", xaxis_title="Number of Jobs")
        st.plotly_chart(fig_ind, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig_emp = px.pie(filtered_df, names="employment_type", title="Employment Type Breakdown", hole=0.4, template="plotly_white")
        st.plotly_chart(fig_emp, use_container_width=True)
    
    with col4:
        fig_work = px.pie(filtered_df, names="work_type", title="Work Type Breakdown", hole=0.4, template="plotly_white")
        st.plotly_chart(fig_work, use_container_width=True)

with tab2:
    if not valid_rates.empty:
        col5, col6 = st.columns(2)
        with col5:
            fig_rate = px.box(valid_rates, x="seniority_level", y="rate_normalized_eur_day", color="job_function", title="Daily Rates by Seniority (EUR)", template="plotly_white")
            st.plotly_chart(fig_rate, use_container_width=True)
        with col6:
            fig_rate_hist = px.histogram(valid_rates, x="rate_normalized_eur_day", nbins=20, title="Distribution of Daily Rates", template="plotly_white")
            st.plotly_chart(fig_rate_hist, use_container_width=True)
    else:
        st.warning("No valid rate data available for the current selection. Adjust filters to see rate insights.")

with tab3:
    st.subheader("Raw Data Export")
    st.dataframe(filtered_df, use_container_width=True)
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Filtered Data to CSV",
        data=csv,
        file_name='job_market_export.csv',
        mime='text/csv',
    )
