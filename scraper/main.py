import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from models import SessionLocal, JobPosting, engine, Base
from utils import infer_seniority, infer_industry, infer_job_function, infer_role_category, normalize_rate, infer_language
from datetime import datetime, timedelta

Base.metadata.create_all(bind=engine)

def save_jobs(db, jobs_data):
    for data in jobs_data:
        title = data.get("role_title", "")
        company = data.get("company_name", "")
        posted_date = data.get("posted_date") or datetime.now().date()

        job = JobPosting(
            source=data["source"],
            role_title=title,
            company_name=company,
            role_category=infer_role_category(title),
            job_function=infer_job_function(title),
            industry=infer_industry(company, title),
            seniority_level=infer_seniority(title),
            company_size=data.get("company_size", "unknown"),
            employment_type=data.get("employment_type", "permanent"),
            work_type=data.get("work_type", "remote"),
            country=data.get("country", "Unknown"),
            language_required=infer_language(title),
            rate_raw=data.get("rate_raw"),
            rate_normalized_eur_day=normalize_rate(data.get("rate_raw"), data.get("rate_type")),
            rate_type=data.get("rate_type"),
            skills=data.get("skills", []),
            posted_date=posted_date,
            scraped_date=datetime.now().date()
        )
        db.add(job)
    db.commit()

def scrape_freelancer(db):
    print("Scraping Freelancer API...")
    try:
        url = "https://www.freelancer.com/api/projects/0.1/projects/active"
        keywords = os.getenv("FREELANCER_KEYWORDS", "developer,data,marketing,design").split(",")
        limit = int(os.getenv("FREELANCER_LIMIT", "10"))
        jobs = []
        for query in keywords:
            query = query.strip()
            if not query:
                continue
            params = {"query": query, "limit": limit, "user_details": True}
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            
            users = data.get("result", {}).get("users", {})
            
            for project in data.get("result", {}).get("projects", []):
                owner_id = str(project.get("owner_id", ""))
                owner = users.get(owner_id, {}) if users else {}
                company_name = owner.get("username") or owner.get("company_name") or project.get("username") or "Freelancer Client"

                skills = [s.get("name", "") for s in (project.get("skills", []) or []) if s.get("name")]
                submit_raw = project.get("submit_datetime") or project.get("bid_datetime")
                posted_date = None
                if submit_raw:
                    try:
                        posted_date = datetime.fromisoformat(submit_raw.replace("Z", "+00:00")).date()
                    except (ValueError, TypeError):
                        pass

                jobs.append({
                    "source": "Freelancer",
                    "role_title": project.get("title"),
                    "company_name": company_name,
                    "country": project.get("currency", {}).get("country", "Unknown"),
                    "employment_type": "freelance",
                    "work_type": "remote",
                    "rate_raw": str(project.get("budget", {}).get("minimum")) if project.get("budget", {}).get("minimum") else None,
                    "rate_type": "project",
                    "skills": skills,
                    "posted_date": posted_date
                })
            time.sleep(1)
        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from Freelancer.")
    except Exception as e:
        print(f"Error scraping Freelancer: {e}")

COUNTRY_MAP = {
    "Netherlands": "NL", "Germany": "DE", "France": "FR",
    "Belgium": "BE", "Spain": "ES", "Italy": "IT",
    "Austria": "AT", "Switzerland": "CH", "United Kingdom": "GB",
    "Ireland": "IE", "Sweden": "SE", "Denmark": "DK",
    "Norway": "NO", "Finland": "FI", "Poland": "PL",
    "Portugal": "PT", "Luxembourg": "LU", "Czech Republic": "CZ"
}

def scrape_linkedin(db):
    print("Scraping LinkedIn (Public)...")
    try:
        locations_str = os.getenv("LINKEDIN_LOCATIONS", "Netherlands,Germany,France")
        locations = [loc.strip() for loc in locations_str.split(",") if loc.strip()]
        keyword = os.getenv("LINKEDIN_KEYWORD", "engineer")
        jobs = []
        for location in locations:
            url = f"https://www.linkedin.com/jobs/search?keywords={keyword}&location={location}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            
            job_cards = soup.find_all("div", class_="base-search-card__info")
            for card in job_cards:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                if not title_elem or not company_elem:
                    continue

                time_elem = card.find("time", class_="job-search-card__listdate")
                posted_date = None
                if time_elem and time_elem.get("datetime"):
                    try:
                        posted_date = datetime.fromisoformat(time_elem["datetime"].replace("Z", "+00:00")).date()
                    except (ValueError, TypeError):
                        pass

                work_type_elem = card.find("span", class_="job-search-card__remote")
                work_type = "hybrid"
                if work_type_elem:
                    wt = work_type_elem.text.strip().lower()
                    if "remote" in wt:
                        work_type = "remote"
                    elif "on-site" in wt or "onsite" in wt:
                        work_type = "onsite"
                    elif "hybrid" in wt:
                        work_type = "hybrid"

                jobs.append({
                    "source": "LinkedIn",
                    "role_title": title_elem.text.strip(),
                    "company_name": company_elem.text.strip(),
                    "country": COUNTRY_MAP.get(location, location[:2].upper()),
                    "employment_type": "permanent",
                    "work_type": work_type,
                    "rate_raw": None,
                    "rate_type": "annual",
                    "posted_date": posted_date
                })
            time.sleep(2)
        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from LinkedIn.")
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")

def scrape_eures(db):
    print("Scraping EURES API...")
    try:
        url = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
        keywords_str = os.getenv("EURES_KEYWORDS", "developer,data scientist,marketing,designer,engineer")
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        results_per_page = int(os.getenv("EURES_RESULTS_PER_PAGE", "10"))
        jobs = []
        for keyword in keywords:
            payload = {
                "resultsPerPage": results_per_page,
                "page": 1,
                "sortSearch": "MOST_RECENT",
                "keywords": [{"keyword": keyword, "specificSearchCode": "EVERYWHERE"}],
                "publicationPeriod": None,
                "occupationUris": [],
                "skillUris": [],
                "requiredExperienceCodes": [],
                "positionScheduleCodes": [],
                "sectorCodes": [],
                "educationAndQualificationLevelCodes": [],
                "positionOfferingCodes": [],
                "locationCodes": [],
                "euresFlagCodes": [],
                "otherBenefitsCodes": [],
                "requiredLanguages": [],
                "minNumberPost": None,
                "sessionId": "bolders-scraper",
                "requestLanguage": "en"
            }
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()

            for jv in data.get("jvs", []):
                employer = jv.get("employer", {}) or {}
                location_map = jv.get("locationMap", {}) or {}
                countries = list(location_map.keys()) if location_map else ["EU"]
                country = countries[0] if countries else "EU"

                offering_code = jv.get("positionOfferingCode", "")
                emp_type = "permanent"
                if offering_code == "contract":
                    emp_type = "contract"
                elif offering_code == "traineeship":
                    emp_type = "internship"

                schedule_code = jv.get("positionScheduleCode", "")
                work_type = "onsite"
                if schedule_code == "remote":
                    work_type = "remote"
                elif schedule_code == "hybrid":
                    work_type = "hybrid"

                skills = [s.get("name", "") for s in (jv.get("skillRefs", []) or []) if s.get("name")]

                posted_date = None
                pub_date = jv.get("publicationDate") or jv.get("publicationDateTime")
                if pub_date:
                    try:
                        posted_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00")).date()
                    except (ValueError, TypeError):
                        pass

                salary_min = jv.get("minimumSalary")
                salary_max = jv.get("maximumSalary")
                salary_currency = jv.get("currencyCode", "EUR")
                salary_period = jv.get("salaryPeriod", "YEAR")
                rate_raw = None
                rate_type = "annual"
                if salary_min is not None or salary_max is not None:
                    if salary_min is not None and salary_max is not None:
                        rate_raw = f"{salary_currency} {salary_min}-{salary_max}/{salary_period.lower()}"
                    elif salary_min is not None:
                        rate_raw = f"{salary_currency} {salary_min}/{salary_period.lower()}"
                    elif salary_max is not None:
                        rate_raw = f"{salary_currency} {salary_max}/{salary_period.lower()}"
                    rate_type_map = {"HOUR": "hourly", "DAY": "daily", "WEEK": "weekly", "MONTH": "monthly", "YEAR": "annual"}
                    rate_type = rate_type_map.get(salary_period, "annual") if salary_period else "annual"

                jobs.append({
                    "source": "EURES",
                    "role_title": jv.get("title", "Unknown"),
                    "company_name": employer.get("name", "Unknown"),
                    "country": country,
                    "employment_type": emp_type,
                    "work_type": work_type,
                    "rate_raw": rate_raw,
                    "rate_type": rate_type,
                    "skills": skills,
                    "posted_date": posted_date
                })
            time.sleep(0.5)
        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from EURES.")
    except Exception as e:
        print(f"Error scraping EURES: {e}")

def scrape_indeed(db):
    print("Scraping Indeed with Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            countries_str = os.getenv("INDEED_COUNTRIES", "nl:Netherlands,de:Germany,fr:France")
            country_pairs = [c.strip() for c in countries_str.split(",") if c.strip()]
            query = os.getenv("INDEED_QUERY", "developer")
            max_per_country = int(os.getenv("INDEED_MAX_PER_COUNTRY", "10"))
            jobs = []
            for pair in country_pairs:
                parts = pair.split(":")
                if len(parts) != 2:
                    continue
                code, country_name = parts[0].strip(), parts[1].strip()
                print(f"Scraping Indeed {code.upper()}...")
                try:
                    page.goto(f"https://{code}.indeed.com/jobs?q={query}", timeout=15000)
                    page.wait_for_selector(".job_seen_beacon", timeout=5000)
                    job_elements = page.query_selector_all(".job_seen_beacon")
                    for elem in job_elements[:max_per_country]:
                        title = elem.query_selector("h2.jobTitle").inner_text() if elem.query_selector("h2.jobTitle") else query.capitalize()
                        company = elem.query_selector(".companyName").inner_text() if elem.query_selector(".companyName") else "Unknown"

                        meta_spans = elem.query_selector_all("[data-testid='attribute_snippet_testid'] span")
                        employment_type = "contract"
                        work_type = "remote"
                        salary_raw = None
                        for span in meta_spans:
                            text = span.inner_text().lower()
                            if any(t in text for t in ["full-time", "full time", "fulltime", "permanent"]):
                                employment_type = "permanent"
                            elif any(t in text for t in ["part-time", "part time", "parttime"]):
                                employment_type = "part-time"
                            elif "contract" in text or "temporary" in text:
                                employment_type = "contract"
                            if "remote" in text:
                                work_type = "remote"
                            elif "hybrid" in text:
                                work_type = "hybrid"
                            elif "on-site" in text or "onsite" in text:
                                work_type = "onsite"
                            if any(c in text for c in ["€", "$", "£", "eur", "usd", "k", "/year", "/month", "/hour", "/day", "salary", "wage"]):
                                salary_raw = text

                        date_elem = elem.query_selector("[data-testid='jobsearch-date']")
                        posted_date = None
                        if date_elem:
                            date_text = date_elem.inner_text().lower()
                            if "today" in date_text or "just posted" in date_text:
                                posted_date = datetime.now().date()
                            elif "yesterday" in date_text:
                                posted_date = (datetime.now() - timedelta(days=1)).date()
                            elif "+" in date_text and "day" in date_text:
                                try:
                                    days = int(''.join(filter(str.isdigit, date_text.split("+")[0])))
                                    posted_date = (datetime.now() - timedelta(days=days)).date()
                                except ValueError:
                                    pass

                        rate_type = "monthly"
                        if salary_raw:
                            if "/hour" in salary_raw or "per hour" in salary_raw:
                                rate_type = "hourly"
                            elif "/day" in salary_raw or "per day" in salary_raw:
                                rate_type = "daily"
                            elif "/year" in salary_raw or "per year" in salary_raw or "k" in salary_raw:
                                rate_type = "annual"
                            elif "/week" in salary_raw or "per week" in salary_raw:
                                rate_type = "weekly"

                        jobs.append({
                            "source": "Indeed",
                            "role_title": title,
                            "company_name": company,
                            "country": code.upper(),
                            "employment_type": employment_type,
                            "work_type": work_type,
                            "rate_raw": salary_raw,
                            "rate_type": rate_type,
                            "posted_date": posted_date
                        })
                except Exception as e:
                    print(f"Failed to scrape Indeed {code}: {e}")
            browser.close()
            save_jobs(db, jobs)
            print(f"Saved {len(jobs)} jobs from Indeed.")
    except Exception as e:
        print(f"Playwright error: {e}")

def scrape_kaggle(db):
    print("Scraping open-apply-jobs dataset (Kaggle replacement)...")
    try:
        api_url = "https://huggingface.co/api/datasets/edwarddgao/open-apply-jobs/parquet/default/train"
        res = requests.get(api_url, timeout=10)
        res.raise_for_status()
        parquet_urls = res.json()

        if not parquet_urls:
            print("No parquet files found.")
            return

        max_files = int(os.getenv("KAGGLE_MAX_PARQUET_FILES", "5"))
        dfs = []
        for url in parquet_urls[:max_files]:
            try:
                df = pd.read_parquet(url)
                dfs.append(df)
            except Exception as e:
                print(f"Failed to read {url}: {e}")

        if not dfs:
            print("Failed to read any parquet files.")
            return

        combined = pd.concat(dfs, ignore_index=True)

        days_back = int(os.getenv("KAGGLE_DAYS_BACK", "14"))
        today = pd.Timestamp.now().normalize()
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
        recent = combined[combined["date"] >= today - pd.Timedelta(days=days_back)]

        if recent.empty:
            fallback_rows = int(os.getenv("KAGGLE_FALLBACK_ROWS", "200"))
            recent = combined.head(fallback_rows)
            print(f"No recent data in date window, using first {fallback_rows} rows as fallback.")

        jobs = []
        for _, row in recent.iterrows():
            locations = row.get("locations") or []
            country = "Unknown"
            if locations:
                loc = locations[0] if isinstance(locations, list) else str(locations)
                parts = loc.split(", ")
                country = parts[-1] if len(parts) > 1 else loc

            emp_type = str(row.get("employment_type", "FullTime")).lower()
            if emp_type in ("fulltime", "full_time"):
                emp_type = "permanent"
            elif emp_type == "internship":
                emp_type = "internship"
            elif emp_type == "contract":
                emp_type = "contract"

            remote = row.get("remote")
            if remote is True:
                work_type = "remote"
            elif remote is False:
                work_type = "onsite"
            else:
                work_type = "hybrid"

            salary_min = row.get("salary_min")
            salary_max = row.get("salary_max")
            salary_currency = row.get("salary_currency", "USD")
            salary_period = row.get("salary_period", "YEAR")
            rate_raw = None
            if salary_min is not None and salary_max is not None:
                rate_raw = f"{salary_currency} {salary_min}-{salary_max}/{salary_period.lower()}"
            elif salary_min is not None:
                rate_raw = f"{salary_currency} {salary_min}/{salary_period.lower()}"

            rate_type_map = {"HOUR": "hourly", "DAY": "daily", "WEEK": "weekly", "MONTH": "monthly", "YEAR": "annual"}
            rate_type = rate_type_map.get(salary_period, "annual") if salary_period else "annual"

            skills = row.get("skills") or []
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",") if s.strip()]
            elif not isinstance(skills, list):
                skills = []

            posted_date = None
            if pd.notna(row.get("date")):
                try:
                    posted_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
                except (AttributeError, ValueError):
                    pass

            jobs.append({
                "source": "Kaggle",
                "role_title": row.get("title", "Unknown"),
                "company_name": row.get("source_slug", "Unknown"),
                "country": country,
                "employment_type": emp_type,
                "work_type": work_type,
                "rate_raw": rate_raw,
                "rate_type": rate_type,
                "skills": skills,
                "posted_date": posted_date
            })

        save_jobs(db, jobs)
        print(f"Saved {len(jobs)} jobs from open-apply-jobs dataset.")
    except Exception as e:
        print(f"Error scraping open-apply-jobs dataset: {e}")

def scrape_malt(db):
    print("Scraping Malt.com with Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            keywords_str = os.getenv("MALT_KEYWORDS", "developer,data scientist,designer,marketing")
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            max_per_keyword = int(os.getenv("MALT_MAX_PER_KEYWORD", "10"))
            locations_str = os.getenv("MALT_LOCATIONS", "netherlands,germany,france")
            locations = [l.strip() for l in locations_str.split(",") if l.strip()]
            jobs = []
            for location in locations:
                for keyword in keywords:
                    print(f"Scraping Malt for '{keyword}' in '{location}'...")
                    try:
                        url = f"https://www.malt.com/s?q={requests.utils.quote(keyword)}&location={requests.utils.quote(location)}"
                        page.goto(url, timeout=20000)
                        page.wait_for_timeout(3000)
                        # Try to find profile/mission cards
                        cards = page.query_selector_all("[data-testid='freelancer-card'], .freelancer-card, .profile-card, article")
                        count = 0
                        for card in cards[:max_per_keyword]:
                            try:
                                # Extract name/title
                                title_el = card.query_selector("h2, h3, [class*='title'], [class*='name']")
                                title = title_el.inner_text().strip() if title_el else f"{keyword.capitalize()} Freelancer"

                                # Extract daily rate
                                rate_el = card.query_selector("[class*='rate'], [class*='price'], [class*='daily']")
                                rate_raw = rate_el.inner_text().strip() if rate_el else None
                                rate_type = "daily"

                                # Extract skills
                                skill_els = card.query_selector_all("[class*='skill'], [class*='tag'], [class*='badge']")
                                skills = [s.inner_text().strip() for s in skill_els if s.inner_text().strip()][:10]

                                # Extract location/country
                                loc_el = card.query_selector("[class*='location'], [class*='city'], [class*='country']")
                                country_text = loc_el.inner_text().strip() if loc_el else location
                                country = COUNTRY_MAP.get(country_text.title(), location[:2].upper())

                                jobs.append({
                                    "source": "Malt",
                                    "role_title": title,
                                    "company_name": "Malt Freelancer",
                                    "country": country,
                                    "employment_type": "freelance",
                                    "work_type": "remote",
                                    "rate_raw": rate_raw,
                                    "rate_type": rate_type,
                                    "skills": skills,
                                    "posted_date": datetime.now().date()
                                })
                                count += 1
                            except Exception:
                                continue
                        print(f"  Found {count} profiles for '{keyword}' in '{location}'")
                    except Exception as e:
                        print(f"  Failed for '{keyword}' in '{location}': {e}")
                    time.sleep(2)
            browser.close()
            save_jobs(db, jobs)
            print(f"Saved {len(jobs)} jobs from Malt.")
    except Exception as e:
        print(f"Playwright error scraping Malt: {e}")


if __name__ == "__main__":
    print("Starting scraper service...")
    db = SessionLocal()
    
    scrape_freelancer(db)
    scrape_linkedin(db)
    scrape_kaggle(db)
    scrape_eures(db)
    scrape_indeed(db)
    scrape_malt(db)
    
    print("Scraping complete.")
    db.close()

