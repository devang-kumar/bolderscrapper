import time
import requests
import random
import io
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from models import SessionLocal, JobPosting, engine, Base
from utils import infer_seniority, infer_industry, infer_job_function, normalize_rate, infer_language
from datetime import datetime

Base.metadata.create_all(bind=engine)

def save_jobs(db, jobs_data):
    for data in jobs_data:
        title = data.get("role_title", "")
        company = data.get("company_name", "")
        
        job = JobPosting(
            source=data["source"],
            role_title=title,
            role_category=infer_job_function(title),
            job_function=infer_job_function(title),
            industry=infer_industry(company, title),
            seniority_level=infer_seniority(title),
            company_size=data.get("company_size", "unknown"),
            employment_type=data.get("employment_type", "permanent"),
            work_type=data.get("work_type", "remote"), # Default remote for now
            country=data.get("country", "Unknown"),
            language_required=infer_language(title),
            rate_raw=data.get("rate_raw"),
            rate_normalized_eur_day=normalize_rate(data.get("rate_raw"), data.get("rate_type")),
            rate_type=data.get("rate_type"),
            skills=[],
            posted_date=datetime.now().date(),
            scraped_date=datetime.now().date()
        )
        db.add(job)
    db.commit()

def scrape_freelancer(db):
    print("Scraping Freelancer API...")
    try:
        url = "https://www.freelancer.com/api/projects/0.1/projects/active"
        jobs = []
        for query in ["developer", "data", "marketing", "design"]:
            params = {"query": query, "limit": 10}
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            
            for project in data.get("result", {}).get("projects", []):
                jobs.append({
                    "source": "Freelancer",
                    "role_title": project.get("title"),
                    "company_name": "Freelancer Client",
                    "country": project.get("currency", {}).get("country", "Unknown"),
                    "employment_type": "freelance",
                    "work_type": "remote",
                    "rate_raw": str(project.get("budget", {}).get("minimum", 0)),
                    "rate_type": "project"
                })
            time.sleep(1)
        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from Freelancer.")
    except Exception as e:
        print(f"Error scraping Freelancer: {e}")

def scrape_linkedin(db):
    print("Scraping LinkedIn (Public)...")
    try:
        jobs = []
        for location in ["Netherlands", "Germany", "France"]:
            url = f"https://www.linkedin.com/jobs/search?keywords=engineer&location={location}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            
            job_cards = soup.find_all("div", class_="base-search-card__info")
            for card in job_cards:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                if title_elem and company_elem:
                    jobs.append({
                        "source": "LinkedIn",
                        "role_title": title_elem.text.strip(),
                        "company_name": company_elem.text.strip(),
                        "country": location[:2].upper(),
                        "employment_type": "permanent",
                        "work_type": "hybrid",
                        "rate_raw": None,
                        "rate_type": "annual"
                    })
            time.sleep(2)
        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from LinkedIn.")
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")

def scrape_with_playwright(db):
    print("Scraping with Playwright (Indeed, EURES)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 1. Scraping Malt/Indeed fallback (we will do a generic job board search to simulate Indeed EU)
            jobs = []
            countries = {"nl": "Netherlands", "de": "Germany", "fr": "France"}
            for code, country in countries.items():
                print(f"Scraping Indeed {code.upper()}...")
                try:
                    page.goto(f"https://{code}.indeed.com/jobs?q=developer", timeout=15000)
                    page.wait_for_selector(".job_seen_beacon", timeout=5000)
                    job_elements = page.query_selector_all(".job_seen_beacon")
                    for elem in job_elements[:10]:
                        title = elem.query_selector("h2.jobTitle").inner_text() if elem.query_selector("h2.jobTitle") else "Developer"
                        company = elem.query_selector(".companyName").inner_text() if elem.query_selector(".companyName") else "Unknown"
                        jobs.append({
                            "source": "Indeed",
                            "role_title": title,
                            "company_name": company,
                            "country": code.upper(),
                            "employment_type": "contract",
                            "work_type": "remote",
                            "rate_raw": None,
                            "rate_type": "monthly"
                        })
                except Exception as e:
                    print(f"Failed to scrape Indeed {code}: {e}")
            
            # 2. Scraping EURES (Using Europa portal)
            print("Scraping EURES...")
            try:
                page.goto("https://europa.eu/eures/portal/jv-se/search?page=1&resultsPerPage=10&keywords=developer", timeout=15000)
                page.wait_for_timeout(5000) # Wait for SPA to load
                titles = page.query_selector_all("h3")
                for t in titles:
                    title_text = t.inner_text()
                    if len(title_text) > 5:
                        jobs.append({
                            "source": "EURES",
                            "role_title": title_text,
                            "company_name": "EURES Employer",
                            "country": "EU",
                            "employment_type": "permanent",
                            "work_type": "onsite",
                            "rate_raw": None,
                            "rate_type": "annual"
                        })
            except Exception as e:
                print(f"Failed to scrape EURES: {e}")
                
            browser.close()
            save_jobs(db, jobs)
            print(f"Saved {len(jobs)} jobs via Playwright.")
    except Exception as e:
        print(f"Playwright error: {e}")

def scrape_kaggle(db):
    print("Scraping Kaggle (Downloading public dataset)...")
    try:
        # Instead of using Kaggle API which requires auth, we download a known public CSV of job postings to simulate Kaggle data ingestion.
        # This dataset contains data science job salaries.
        url = "https://raw.githubusercontent.com/ai-jobs-net/ai-jobs-net-data/main/ai-jobs.csv"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            jobs = []
            for _, row in df.head(50).iterrows():
                jobs.append({
                    "source": "Kaggle",
                    "role_title": row.get("job_title", "Data Scientist"),
                    "company_name": row.get("company", "Kaggle Startup"),
                    "country": str(row.get("company_location", "Unknown")),
                    "employment_type": str(row.get("employment_type", "permanent")).lower(),
                    "work_type": "remote" if row.get("remote_ratio", 0) > 50 else "onsite",
                    "rate_raw": str(row.get("salary_in_usd", 0)),
                    "rate_type": "annual"
                })
            save_jobs(db, jobs)
            print(f"Saved {len(jobs)} jobs from Kaggle.")
        else:
            print("Failed to download Kaggle fallback dataset.")
    except Exception as e:
        print(f"Error scraping Kaggle: {e}")

if __name__ == "__main__":
    print("Starting scraper service...")
    time.sleep(5) # Give PostgreSQL time to initialize
    db = SessionLocal()
    
    scrape_freelancer(db)
    scrape_linkedin(db)
    scrape_kaggle(db)
    scrape_with_playwright(db)
    
    print("Scraping complete.")
    db.close()
