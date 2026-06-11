# EU Job Market Scraper & Dashboard

A data pipeline that harvests European job market data across all employment types, normalizes it into a clean, filterable schema, and surfaces it through a dashboard.

## Setup Instructions
1. Clone the repository.
2. Ensure you have Docker and Docker Compose installed.
3. Run `docker-compose up --build`
4. Access the dashboard at `http://localhost:8501`.

## Stack Justification
- **Scraper**: Python with `playwright` and `requests`. Python is the industry standard for scraping. Playwright handles dynamic content effectively.
- **Database**: PostgreSQL. A robust relational database ideal for structured schema and future extensibility for prediction models.
- **Dashboard**: Streamlit. Allows rapid development of data dashboards in Python with built-in filtering and charts capabilities.
- **Orchestration**: Docker Compose for "works first time" deployment.

## Data Source Rationale
1. **Mock Kaggle Dataset**: Used as a fast, reliable source of historical job postings to ensure the dashboard populates instantly.
2. **EURES**: The official EU portal, providing broad coverage across Europe using their public API.
3. **Malt / Freelancer**: To capture freelance project budgets and rates.
4. **LinkedIn / Indeed**: Captured via Playwright for real-time permanent/contract roles.

## Schema Documentation
- `id`: Primary key
- `source`: The website/API from which the job was scraped
- `role_title`: Job title
- `role_category`: Broad category (e.g. Software, Data)
- `job_function`: Specific function (e.g. data, dev, design)
- `industry`: Inferred industry (e.g. tech, finance)
- `seniority_level`: Inferred seniority (e.g. junior, mid, senior)
- `company_size`: Size of the hiring company
- `employment_type`: permanent / contract / freelance
- `work_type`: remote / hybrid / onsite
- `country`: Country of the job
- `language_required`: Explicit language needed
- `rate_raw`: Raw rate string
- `rate_normalized_eur_day`: Computed numeric EUR/day rate
- `rate_type`: hourly / daily / monthly / annual / project
- `skills`: Array of skills
- `posted_date`: Date the job was posted
- `scraped_date`: Date scraped

## Inference Logic
- **Seniority**: Inferred from `role_title`. E.g., if "senior" or "lead" is in the title, it maps to `senior` or `lead`. If "junior" is present, it maps to `junior`. Default: `unknown`.
- **Industry**: Inferred from `company_name` or job keywords.
- **Rate Normalization**: 
  - Hourly rate * 8 = Daily rate.
  - Monthly rate / 21 = Daily rate.
  - Annual rate / 250 = Daily rate.
