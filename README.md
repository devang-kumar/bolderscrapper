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

## Hetzner Deployment Guide
This project is fully containerized, making it extremely straightforward to deploy on a Hetzner Cloud VPS.

1. **Provision a Server**: Spin up an Ubuntu 22.04 or 24.04 server on Hetzner Cloud (a CX22 or CPX21 instance is sufficient).
2. **Install Docker**: SSH into the server and install Docker & Docker Compose:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo apt install docker-compose-plugin
   ```
3. **Deploy**:
   ```bash
   git clone <your-private-repo-url>
   cd boldersscraper
   docker compose up --build -d
   ```
4. **Access**: The dashboard will be live at `http://<your-server-ip>:8501`. 
*(Note: For a production environment, it is highly recommended to run this behind a reverse proxy like Caddy or Nginx with Let's Encrypt for HTTPS).*

## Data Source Rationale
1. **Kaggle (CSV Direct Download)**: Instead of using the Kaggle API which requires a persistent `kaggle.json` credential, the scraper natively pulls a public data-science job salary CSV to ingest historical baseline data.
2. **EURES**: The official EU portal is scraped dynamically using Playwright, simulating human interaction to bypass their SPA structure and retrieve official cross-border roles.
3. **Freelancer.com**: Scraped via their public active-projects API, dynamically cycling through tech/design keywords.
4. **LinkedIn / Indeed / Malt**: Scraped using Playwright and Requests with headers to capture live contract and permanent roles across the Netherlands, Germany, and France.

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
