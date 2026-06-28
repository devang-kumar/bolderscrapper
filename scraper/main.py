import os
import time
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from sqlalchemy import text, or_
from models import SessionLocal, JobPosting, engine, Base
from utils import (
    clean_job_record,
    clean_text,
    extract_rate_details,
    infer_industry,
    infer_job_function,
    infer_language,
    infer_rate_type,
    infer_role_category,
    infer_seniority,
    normalize_country,
    normalize_rate,
    split_env_list,
)
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs

Base.metadata.create_all(bind=engine)

def ensure_schema():
    columns = {
        "source_job_id": "VARCHAR(255)",
        "job_url": "VARCHAR(1024)",
        "location_raw": "VARCHAR(255)",
        "description": "TEXT",
    }
    try:
        with engine.begin() as conn:
            for column, column_type in columns.items():
                conn.execute(text(f"ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS {column} {column_type};"))
    except Exception as e:
        print(f"Schema migration skipped: {e}")

ensure_schema()

def save_jobs(db, jobs_data):
    seen = set()
    saved = 0
    for data in jobs_data:
        data = clean_job_record(data)
        title = data.get("role_title", "")
        company = data.get("company_name", "")
        posted_date = data.get("posted_date") or datetime.now().date()
        dedupe_key = (
            data.get("source", "").lower(),
            (data.get("source_job_id") or data.get("job_url") or "").lower(),
            title.lower(),
            company.lower(),
            data.get("country", "").lower(),
            posted_date.isoformat() if hasattr(posted_date, "isoformat") else str(posted_date),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        existing_filters = []
        if data.get("source_job_id"):
            existing_filters.append(JobPosting.source_job_id == data.get("source_job_id"))
        if data.get("job_url"):
            existing_filters.append(JobPosting.job_url == data.get("job_url"))
        if existing_filters:
            existing = (
                db.query(JobPosting.id)
                .filter(JobPosting.source == data.get("source"))
                .filter(or_(*existing_filters))
                .first()
            )
            if existing:
                continue

        job = JobPosting(
            source=data["source"],
            role_title=title,
            company_name=company,
            source_job_id=data.get("source_job_id"),
            job_url=data.get("job_url"),
            location_raw=data.get("location_raw"),
            description=data.get("description"),
            role_category=infer_role_category(title),
            job_function=infer_job_function(title),
            industry=infer_industry(company, title),
            seniority_level=infer_seniority(title),
            company_size=data.get("company_size", "unknown"),
            employment_type=data.get("employment_type", "permanent"),
            work_type=data.get("work_type", "remote"),
            country=data.get("country", "Unknown"),
            language_required=data.get("language_required") or infer_language(title),
            rate_raw=data.get("rate_raw"),
            rate_normalized_eur_day=normalize_rate(data.get("rate_raw"), data.get("rate_type")),
            rate_type=data.get("rate_type"),
            skills=data.get("skills", []),
            posted_date=posted_date,
            scraped_date=datetime.now().date()
        )
        db.add(job)
        saved += 1
    db.commit()
    return saved

def scrape_freelancer(db):
    print("Scraping Freelancer API...")
    try:
        url = "https://www.freelancer.com/api/projects/0.1/projects/active"
        keywords = split_env_list(os.getenv("FREELANCER_KEYWORDS"), "developer,data,marketing,design")
        limit = int(os.getenv("FREELANCER_LIMIT", "10"))
        jobs = []
        for query in keywords:
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
                    "source_job_id": project.get("id"),
                    "job_url": f"https://www.freelancer.com/projects/{project.get('seo_url')}" if project.get("seo_url") else None,
                    "role_title": project.get("title"),
                    "company_name": company_name,
                    "country": project.get("currency", {}).get("country", "Unknown"),
                    "employment_type": "freelance",
                    "work_type": "remote",
                    "rate_raw": str(project.get("budget", {}).get("minimum")) if project.get("budget", {}).get("minimum") else None,
                    "rate_type": "project",
                    "skills": skills,
                    "description": project.get("preview_description") or project.get("description"),
                    "posted_date": posted_date
                })
            time.sleep(1)
        saved = save_jobs(db, jobs)
        print(f"Saved {saved} jobs from Freelancer.")
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
        locations = split_env_list(os.getenv("LINKEDIN_LOCATIONS"), "Netherlands,Germany,France")
        keywords = split_env_list(os.getenv("LINKEDIN_KEYWORD"), "engineer")
        jobs = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        for location in locations:
            for keyword in keywords:
                url = f"https://www.linkedin.com/jobs/search?keywords={quote_plus(keyword)}&location={quote_plus(location)}"
                res = requests.get(url, headers=headers, timeout=15)
                res.raise_for_status()
                soup = BeautifulSoup(res.text, "html.parser")

                cards = soup.find_all("div", class_="base-card")
                if not cards:
                    cards = soup.find_all("div", class_="base-search-card__info")

                for card in cards:
                    info = card.find("div", class_="base-search-card__info") or card
                    title_elem = info.find("h3", class_="base-search-card__title")
                    company_elem = info.find("h4", class_="base-search-card__subtitle")
                    if not title_elem or not company_elem:
                        continue

                    link_elem = card.find("a", href=True)
                    location_elem = info.find("span", class_="job-search-card__location")
                    time_elem = info.find("time", class_="job-search-card__listdate") or info.find("time")

                    work_type_elem = info.find("span", class_="job-search-card__remote")
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
                        "source_job_id": card.get("data-entity-urn"),
                        "job_url": link_elem["href"] if link_elem else None,
                        "role_title": title_elem.text.strip(),
                        "company_name": company_elem.text.strip(),
                        "location_raw": location_elem.text.strip() if location_elem else location,
                        "country": COUNTRY_MAP.get(location, location[:2].upper()),
                        "employment_type": "permanent",
                        "work_type": work_type,
                        "rate_raw": None,
                        "rate_type": "annual",
                        "posted_date": time_elem.get("datetime") if time_elem else None,
                    })
                time.sleep(2)
        saved = save_jobs(db, jobs)
        print(f"Saved {saved} jobs from LinkedIn.")
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")

def scrape_eures(db):
    print("Scraping EURES API...")
    try:
        url = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
        keywords = split_env_list(os.getenv("EURES_KEYWORDS"), "developer,data scientist,marketing,designer,engineer")
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
                    "source_job_id": jv.get("id") or jv.get("jobVacancyId"),
                    "job_url": jv.get("url") or jv.get("detailsUrl"),
                    "role_title": jv.get("title", "Unknown"),
                    "company_name": employer.get("name", "Unknown"),
                    "location_raw": ", ".join(location_map.keys()) if location_map else country,
                    "country": country,
                    "employment_type": emp_type,
                    "work_type": work_type,
                    "rate_raw": rate_raw,
                    "rate_type": rate_type,
                    "skills": skills,
                    "description": jv.get("description") or jv.get("jobDescription"),
                    "posted_date": posted_date
                })
            time.sleep(0.5)
        saved = save_jobs(db, jobs)
        print(f"Saved {saved} jobs from EURES.")
    except Exception as e:
        print(f"Error scraping EURES: {e}")

def element_text(root, selectors):
    for selector in selectors:
        try:
            element = root.query_selector(selector)
            if not element:
                continue
            text_value = clean_text(element.inner_text())
            if text_value:
                return text_value
        except Exception:
            continue
    return None

def element_texts(root, selectors, limit=20):
    values = []
    seen = set()
    for selector in selectors:
        try:
            for element in root.query_selector_all(selector):
                text_value = clean_text(element.inner_text())
                key = text_value.lower() if text_value else None
                if not text_value or key in seen:
                    continue
                values.append(text_value)
                seen.add(key)
                if len(values) >= limit:
                    return values
        except Exception:
            continue
    return values

def element_attr(root, selectors, attr_name):
    for selector in selectors:
        try:
            element = root.query_selector(selector)
            if not element:
                continue
            value = clean_text(element.get_attribute(attr_name))
            if value:
                return value
        except Exception:
            continue
    return None

def accept_cookie_banner(page):
    try:
        for button in page.query_selector_all("button"):
            label = clean_text(button.inner_text(), default="").lower()
            if label in {"accept", "accept all", "agree", "i agree", "allow all cookies"}:
                button.click(timeout=1000)
                page.wait_for_timeout(500)
                return
    except Exception:
        pass

def indeed_job_id_from_href(href):
    if not href:
        return None
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    for key in ("jk", "vjk"):
        if params.get(key):
            return clean_text(params[key][0], max_length=255)
    match = re.search(r"(?:jk=|vjk=|jk:)([A-Za-z0-9_-]+)", href)
    return clean_text(match.group(1), max_length=255) if match else None

def indeed_search_url(country_code, query, days_back):
    params = f"q={quote_plus(query)}&sort=date"
    if days_back:
        params += f"&fromage={int(days_back)}"
    return f"https://{country_code}.indeed.com/jobs?{params}"

def scrape_indeed_detail(detail_page, job_url):
    details = {}
    if not job_url:
        return details
    try:
        detail_page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
        detail_page.wait_for_timeout(1200)
        accept_cookie_banner(detail_page)

        description = element_text(detail_page, [
            "#jobDescriptionText",
            "[data-testid='jobsearch-JobComponent-description']",
            ".jobsearch-jobDescriptionText",
            "[class*='jobDescription']",
        ])
        title = element_text(detail_page, [
            "[data-testid='jobsearch-JobInfoHeader-title']",
            "h1",
        ])
        company = element_text(detail_page, [
            "[data-testid='inlineHeader-companyName']",
            "[data-testid='company-name']",
            ".jobsearch-InlineCompanyRating a",
            ".jobsearch-CompanyInfoContainer",
        ])
        location = element_text(detail_page, [
            "[data-testid='job-location']",
            "[data-testid='text-location']",
            ".jobsearch-JobInfoHeader-subtitle div",
        ])
        detail_metadata = element_texts(detail_page, [
            "#salaryInfoAndJobType span",
            "[data-testid='jobsearch-JobMetadataHeader-item']",
            "[data-testid='jobsearch-OtherJobDetailsContainer'] div",
            ".jobsearch-JobMetadataHeader-item",
        ])
        rate_raw, rate_type = extract_rate_details(" ".join(detail_metadata), description)

        details.update({
            "role_title": title,
            "company_name": company,
            "location_raw": location,
            "description": description,
            "metadata": " ".join(detail_metadata),
            "rate_raw": rate_raw,
            "rate_type": rate_type,
        })
    except Exception as e:
        print(f"  Indeed detail skipped for {job_url}: {e}")
    return {key: value for key, value in details.items() if value}

def parse_indeed_card(card, base_url, query, country_code, country_name):
    title = element_text(card, [
        "h2.jobTitle span[title]",
        "h2.jobTitle",
        "[data-testid='job-title']",
        "a[data-jk] span[title]",
        "a[data-jk]",
    ])
    company = element_text(card, [
        "[data-testid='company-name']",
        ".companyName",
        "[data-testid='companyName']",
    ])
    location = element_text(card, [
        "[data-testid='text-location']",
        ".companyLocation",
        "[data-testid='job-location']",
    ])
    summary = " ".join(element_texts(card, [
        "[data-testid='job-snippet']",
        ".job-snippet",
        ".underShelfFooter",
    ]))
    metadata_values = element_texts(card, [
        "[data-testid='attribute_snippet_testid']",
        "[data-testid='salary-snippet-container']",
        ".salary-snippet-container",
        ".metadata",
        ".jobMetaDataGroup span",
    ])
    metadata = " ".join(metadata_values)
    posted_text = element_text(card, [
        "[data-testid='myJobsStateDate']",
        "[data-testid='jobsearch-date']",
        ".date",
    ])
    href = element_attr(card, [
        "h2.jobTitle a",
        "a[data-jk]",
        ".jcs-JobTitle",
        "a[href*='viewjob']",
        "a[href*='clk']",
    ], "href")
    job_url = urljoin(base_url, href) if href else None
    source_job_id = (
        element_attr(card, ["a[data-jk]", "[data-jk]"], "data-jk")
        or indeed_job_id_from_href(job_url)
    )
    if source_job_id:
        job_url = f"{base_url}/viewjob?jk={source_job_id}"

    rate_raw, rate_type = extract_rate_details(metadata, summary)

    return {
        "source": "Indeed",
        "source_job_id": source_job_id,
        "job_url": job_url,
        "role_title": title or query.title(),
        "company_name": company or "Unknown",
        "location_raw": location,
        "country": normalize_country(country_name or country_code),
        "employment_type": metadata,
        "work_type": " ".join([location or "", metadata, summary]),
        "rate_raw": rate_raw,
        "rate_type": rate_type,
        "summary": summary,
        "metadata": metadata,
        "posted_text": posted_text,
}

def scrape_indeed_legacy(db):
    return scrape_indeed(db)

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
                "source_job_id": row.get("id") or row.get("job_id"),
                "job_url": row.get("url") or row.get("job_url"),
                "role_title": row.get("title", "Unknown"),
                "company_name": row.get("source_slug", "Unknown"),
                "location_raw": ", ".join(locations) if isinstance(locations, list) else str(locations),
                "country": country,
                "employment_type": emp_type,
                "work_type": work_type,
                "rate_raw": rate_raw,
                "rate_type": rate_type,
                "skills": skills,
                "description": row.get("description"),
                "posted_date": posted_date
            })

        saved = save_jobs(db, jobs)
        print(f"Saved {saved} jobs from open-apply-jobs dataset.")
    except Exception as e:
        print(f"Error scraping open-apply-jobs dataset: {e}")

def scrape_malt(db):
    print("Scraping Malt.com with Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            keywords = split_env_list(os.getenv("MALT_KEYWORDS"), "developer,data scientist,designer,marketing")
            max_per_keyword = int(os.getenv("MALT_MAX_PER_KEYWORD", "10"))
            locations = split_env_list(os.getenv("MALT_LOCATIONS"), "netherlands,germany,france")
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
                                link = element_attr(card, ["a[href]"], "href")

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
                                    "job_url": urljoin("https://www.malt.com", link) if link else None,
                                    "role_title": title,
                                    "company_name": "Malt Freelancer",
                                    "location_raw": country_text,
                                    "country": country,
                                    "employment_type": "freelance",
                                    "work_type": "remote",
                                    "rate_raw": rate_raw,
                                    "rate_type": rate_type,
                                    "skills": skills,
                                    "description": card.inner_text(),
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
            saved = save_jobs(db, jobs)
            print(f"Saved {saved} jobs from Malt.")
    except Exception as e:
        print(f"Playwright error scraping Malt: {e}")


def scrape_indeed(db):
    print("Scraping Indeed with Playwright...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1366, "height": 900},
            )
            page = context.new_page()
            detail_page = context.new_page()
            country_pairs = split_env_list(os.getenv("INDEED_COUNTRIES"), "nl:Netherlands,de:Germany,fr:France")
            queries = split_env_list(os.getenv("INDEED_QUERY"), "developer")
            max_per_country = int(os.getenv("INDEED_MAX_PER_COUNTRY", "10"))
            days_back = int(os.getenv("INDEED_DAYS_BACK", "14"))
            jobs = []

            for pair in country_pairs:
                code, country_name = (pair.split(":", 1) + [""])[:2]
                code = clean_text(code, default="").lower()
                country_name = clean_text(country_name, default=code.upper())
                if not code:
                    continue

                base_url = f"https://{code}.indeed.com"
                for query in queries:
                    print(f"Scraping Indeed {code.upper()} for '{query}'...")
                    try:
                        page.goto(indeed_search_url(code, query, days_back), wait_until="domcontentloaded", timeout=25000)
                        page.wait_for_timeout(2500)
                        accept_cookie_banner(page)
                        page.wait_for_selector(".job_seen_beacon, [data-testid='slider_item'], .result", timeout=8000)
                        cards = page.query_selector_all(".job_seen_beacon, [data-testid='slider_item'], .result")
                        count = 0
                        seen_ids = set()

                        for card in cards:
                            if count >= max_per_country:
                                break

                            job = parse_indeed_card(card, base_url, query, code, country_name)
                            job_key = (
                                job.get("source_job_id")
                                or f"{job.get('role_title')}|{job.get('company_name')}|{job.get('location_raw')}"
                            )
                            if job_key in seen_ids:
                                continue
                            seen_ids.add(job_key)

                            detail = scrape_indeed_detail(detail_page, job.get("job_url"))
                            job.update({key: value for key, value in detail.items() if value})
                            if not job.get("rate_type"):
                                job["rate_type"] = infer_rate_type(job.get("rate_raw"))
                            jobs.append(job)
                            count += 1
                            time.sleep(0.3)

                        print(f"  Found {count} Indeed jobs for '{query}' in {code.upper()}")
                    except Exception as e:
                        print(f"Failed to scrape Indeed {code} for '{query}': {e}")
                    time.sleep(1.5)

            context.close()
            browser.close()
            saved = save_jobs(db, jobs)
            print(f"Saved {saved} jobs from Indeed.")
    except Exception as e:
        print(f"Playwright error: {e}")


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

