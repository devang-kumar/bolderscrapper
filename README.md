<div align="center">

# EU Job Market Intelligence Platform

**A production-grade data pipeline that scrapes, normalises, and visualises the European freelance and permanent job market in real time.**

[![GitHub Actions](https://github.com/devang-kumar/bolderscrapper/actions/workflows/scraper.yml/badge.svg)](https://github.com/devang-kumar/bolderscrapper/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql)](https://postgresql.org)
[![Playwright](https://img.shields.io/badge/Scraping-Playwright-2EAD33?logo=playwright)](https://playwright.dev)
[![Render](https://img.shields.io/badge/Hosted_on-Render-46E3B7?logo=render)](https://render.com)

[**Live Dashboard →**](https://bolderscrapper.onrender.com)

</div>

---

## What Is This?

This platform continuously harvests job and freelance project data from **5 live European sources**, normalises it into a unified schema with inferred fields, stores it in PostgreSQL, and surfaces it through an interactive Streamlit dashboard — all running **100% free** with no Docker required.

It was built as a data engineering solution to answer the question:  
> *"What does the EU job market look like right now — by country, seniority, rate, skill, and contract type?"*

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        GitHub Actions                         │
│           (Free Cron Job — runs daily at 2 AM UTC)            │
└───────────────────────────┬───────────────────────────────────┘
                            │  triggers
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                       Scraper Layer                           │
│                     scraper/main.py                           │
│                                                               │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌────────┐ ┌────────┐    │
│  │Freelancer│ │ LinkedIn │ │ EURES │ │ Indeed │ │  Malt  │    │
│  │   API    │ │  (HTML)  │ │ (API) │ │ (HTML) │ │ (HTML) │    │
│  └────┬─────┘ └────┬─────┘ └──┬────┘ └───┬────┘ └───┬────┘    │
│       └────────────┴──────────┴──────────┴──────────┘         │
│                              │                                │
│                   ┌──────────▼──────────┐                     │
│                   │   Inference Layer   │                     │
│                   │     utils.py        │                     │
│                   │  - seniority        │                     │
│                   │  - industry         │                     │
│                   │  - job_function     │                     │
│                   │  - role_category    │                     │
│                   │  - rate (EUR/day)   │                     │
│                   │  - language         │                     │
│                   └──────────┬──────────┘                     │
└──────────────────────────────┼────────────────────────────────┘
                               │  SQLAlchemy ORM
                               ▼
┌───────────────────────────────────────────────────────────────┐
│              PostgreSQL  (Render Managed DB)                  │
│                    table: job_postings                        │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│               Dashboard Layer  (Streamlit)                    │
│                    dashboard/app.py                           │
│              bolderscrapper.onrender.com                      │
└───────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| Source | Method | What It Provides | Employment Type |
|---|---|---|---|
| **Freelancer.com** | Public REST API | Live active projects, budgets, skills | Freelance |
| **LinkedIn** | HTML scraping (requests + BeautifulSoup) | Job titles, companies, work type, post date | Permanent |
| **EURES** | Official EU REST API | Cross-border EU roles, salary bands, skill URIs | All types |
| **Indeed** | Browser automation (Playwright) | Job listings, employment type, salary | Contract / Permanent |
| **Malt.com** | Browser automation (Playwright) | Freelancer profiles, daily rates, skills | Freelance |
| **Kaggle/HuggingFace** | Parquet dataset via HuggingFace API | Historical job salary baseline data | All types |

---

## Dashboard Features

### Filters (Sidebar)
- **Date Range** — filter all views by `posted_date` (from / to date pickers)
- **Country** — multiselect across all scraped EU countries
- **Source** — filter by data origin (LinkedIn, EURES, Indeed, etc.)
- **Role Category** — engineering, data_ai, creative, marketing, finance, operations, healthcare, legal
- **Industry** — tech, finance, pharma, retail, logistics, other
- **Job Function** — dev, data, design, marketing, ops, finance
- **Seniority Level** — junior, mid, senior, unknown
- **Employment Type** — permanent, contract, freelance, internship
- **Work Type** — remote, hybrid, onsite
- **Language Required** — filter by detected language requirement

### KPI Cards
| Metric | Description |
|---|---|
| Total Jobs Found | Count of jobs matching active filters |
| Top Hiring Country | Mode country code in filtered dataset |
| Top Industry | Most common inferred industry |
| Avg Daily Rate (EUR) | Mean normalised `rate_normalized_eur_day` |
| Jobs with Language Req. | % of postings with an explicit language tag |

### Tabs

#### Market Overview
- **Job Demand by Country** (histogram, coloured by source)
- **Jobs by Industry & Function** (horizontal histogram)
- **Employment Type Breakdown** (donut pie)
- **Work Type Breakdown** (donut pie)
- **Jobs Posted Over Time** (time-series area chart — trend analysis)

#### Rate Analysis
- **Daily Rates by Seniority & Role Category** (box plot — brief requirement)
- **Distribution of Daily Rates** (histogram — spread analysis)
- **Average Daily Rate by Role Category** (bar chart)
- Info callout explaining why LinkedIn/Indeed rows show no rate data

#### Language & Skills
- **% of Postings with Explicit Language Requirement** (donut pie)
- **Top Languages Required** (horizontal bar chart)
- **Top 20 In-Demand Skills** (horizontal bar chart, ranked by frequency)

#### Raw Data
- Full interactive data table (sortable, filterable inline)
- **Export to CSV** button — downloads a clean, Excel-ready file with:
  - Skills array serialised as comma-separated strings
  - Date columns stripped of timestamp noise
  - All active filters applied

---

## Schema

```sql
CREATE TABLE job_postings (
    id                     SERIAL PRIMARY KEY,
    source                 VARCHAR(255) NOT NULL,        -- Freelancer / LinkedIn / EURES / Indeed / Malt / Kaggle
    source_job_id          VARCHAR(255),                 -- source-specific stable job id where available
    job_url                VARCHAR(1024),                -- original listing URL
    role_title             VARCHAR(255) NOT NULL,
    company_name           VARCHAR(255),
    location_raw           VARCHAR(255),                 -- original location string before country normalization
    description            TEXT,                         -- cleaned description/snippet where available
    role_category          VARCHAR(255),                 -- engineering / data_ai / creative / marketing / finance / operations / healthcare / legal / other
    job_function           VARCHAR(255),                 -- dev / data / design / marketing / ops / finance / other
    industry               VARCHAR(255),                 -- tech / finance / pharma / retail / logistics / other
    seniority_level        VARCHAR(255),                 -- junior / mid / senior / unknown
    company_size           VARCHAR(255),
    employment_type        VARCHAR(255),                 -- permanent / contract / freelance / internship
    work_type              VARCHAR(255),                 -- remote / hybrid / onsite
    country                VARCHAR(255),
    language_required      VARCHAR(255),                 -- ISO 639-1 code (EN, DE, FR, NL...)
    rate_raw               VARCHAR(255),                 -- original rate string as scraped
    rate_normalized_eur_day NUMERIC,                     -- computed EUR/day
    rate_type              VARCHAR(255),                 -- hourly / daily / weekly / monthly / annual / project
    skills                 TEXT[],                       -- array of skill tags
    posted_date            DATE,
    scraped_date           DATE
);
```

**Designed for time-series modelling** — `posted_date` and `scraped_date` enable longitudinal trend analysis as data accumulates daily.

---

## Inference Logic

All inference runs at ingest time in [`scraper/utils.py`](scraper/utils.py) with no external API calls — pure keyword matching on the job title and company name.

| Field | Method |
|---|---|
| `seniority_level` | Keyword match on title: `senior/lead/principal` → senior, `junior/graduate/intern` → junior, `mid/associate/medior` → mid |
| `industry` | Keyword match on company + title: `software/tech/data/cloud` → tech, `bank/finance/fintech` → finance, etc. |
| `job_function` | Keyword match on title: `developer/engineer` → dev, `data/analytics/ml` → data, etc. |
| `role_category` | Broader keyword match across 8 categories including healthcare and legal |
| `language_required` | [`langdetect`](https://github.com/Mimino666/langdetect) library applied to the raw job title — returns ISO 639-1 code |
| `rate_normalized_eur_day` | Converts any rate to EUR/day: hourly × 8, monthly ÷ 21, annual ÷ 250, project ÷ 5 |

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| **Language** | Python 3.12 | Industry standard for data engineering and scraping |
| **HTTP Scraping** | `requests` + `BeautifulSoup4` | Lightweight, fast for static HTML pages (LinkedIn) |
| **Browser Automation** | `Playwright` | Handles JavaScript-rendered pages (Indeed, Malt) |
| **Data Processing** | `pandas` + `pyarrow` | DataFrame manipulation and Parquet file reading |
| **Language Detection** | `langdetect` | Offline inference of job title language |
| **ORM / DB** | `SQLAlchemy` + `psycopg2` | Robust PostgreSQL interface with schema management |
| **Database** | PostgreSQL | Relational schema, array column support, time-series ready |
| **Dashboard** | `Streamlit` | Rapid Python-native dashboard with built-in caching |
| **Charts** | `Plotly Express` | Interactive, publication-quality charts |
| **CI / Cron** | GitHub Actions | Free daily scraper scheduling |
| **Hosting** | Render (Web Service) | Managed HTTPS hosting for the Streamlit app |
| **DB Hosting** | Render (PostgreSQL) | Managed database with external connection support |

---

## Project Structure

```
bolderscrapper/
│
├── scraper/
│   ├── main.py           # All scraper functions + entry point
│   ├── models.py         # SQLAlchemy ORM model (JobPosting table)
│   ├── utils.py          # Inference logic (seniority, industry, rate normalisation)
│   └── requirements.txt  # psycopg2, sqlalchemy, playwright, requests, beautifulsoup4, pandas, pyarrow, langdetect
│
├── dashboard/
│   ├── app.py            # Streamlit dashboard (filters, KPIs, 4 tabs, CSV export)
│   ├── requirements.txt  # streamlit, pandas, plotly, psycopg2, sqlalchemy
│   └── .streamlit/
│       └── config.toml   # Light theme, CORS/XSRF disabled for Render proxy
│
├── .github/
│   └── workflows/
│       └── scraper.yml   # GitHub Actions cron job (daily at 2 AM UTC)
│
├── db/
│   └── init.sql          # Initial schema SQL
│
├── .env.example          # Environment variable template
├── .gitignore            # Excludes .env, __pycache__, venv
└── README.md
```

---

## Deployment (No Docker)

### Prerequisites
- GitHub repository (already set up)
- Render account (free tier)

### Step 1 — Create PostgreSQL on Render
New → PostgreSQL → copy the **External Database URL**

### Step 2 — Deploy Dashboard (Web Service)
| Setting | Value |
|---|---|
| Environment | Python 3 |
| Build Command | `pip install -r dashboard/requirements.txt` |
| Start Command | `streamlit run dashboard/app.py --server.port $PORT` |
| Env Var | `DATABASE_URL` = your External DB URL |

### Step 3 — Schedule Scraper (GitHub Actions — Free)
Add `DATABASE_URL` as a **GitHub Repository Secret**:  
`Settings → Secrets and variables → Actions → New repository secret`

The workflow in `.github/workflows/scraper.yml` runs automatically every day at 2 AM UTC.  
You can also trigger it manually from the **Actions → Daily Scraper → Run workflow** button.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | — |
| `FREELANCER_KEYWORDS` | Comma-separated search terms | `developer,data,marketing,design` |
| `FREELANCER_LIMIT` | Results per keyword | `10` |
| `LINKEDIN_KEYWORD` | Comma-separated job keywords for LinkedIn search | `engineer` |
| `LINKEDIN_LOCATIONS` | Comma-separated EU countries | `Netherlands,Germany,France` |
| `EURES_KEYWORDS` | Comma-separated search terms | `developer,data scientist,...` |
| `EURES_RESULTS_PER_PAGE` | Results per keyword | `10` |
| `INDEED_QUERY` | Job query for Indeed | `developer` |
| `INDEED_COUNTRIES` | `code:Name` pairs | `nl:Netherlands,...` |
| `INDEED_MAX_PER_COUNTRY` | Max jobs per country | `10` |
| `INDEED_DAYS_BACK` | Indeed posting age window in days | `14` |
| `KAGGLE_MAX_PARQUET_FILES` | Parquet files to fetch | `5` |
| `KAGGLE_DAYS_BACK` | Days of data to keep | `14` |
| `KAGGLE_FALLBACK_ROWS` | Rows if no recent data | `200` |
| `MALT_KEYWORDS` | Comma-separated search terms | `developer,data scientist,...` |
| `MALT_MAX_PER_KEYWORD` | Max profiles per keyword | `10` |
| `MALT_LOCATIONS` | Comma-separated locations | `netherlands,germany,france` |
| `DASHBOARD_CACHE_TTL` | Streamlit data cache in seconds | `300` |
