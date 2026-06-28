import html
import re
import unicodedata
from datetime import date, datetime, timedelta

from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

COUNTRY_ALIASES = {
    "austria": "AT",
    "at": "AT",
    "belgium": "BE",
    "be": "BE",
    "czech republic": "CZ",
    "czechia": "CZ",
    "cz": "CZ",
    "denmark": "DK",
    "dk": "DK",
    "finland": "FI",
    "fi": "FI",
    "france": "FR",
    "fr": "FR",
    "germany": "DE",
    "de": "DE",
    "ireland": "IE",
    "ie": "IE",
    "italy": "IT",
    "it": "IT",
    "luxembourg": "LU",
    "lu": "LU",
    "netherlands": "NL",
    "nederland": "NL",
    "nl": "NL",
    "norway": "NO",
    "no": "NO",
    "poland": "PL",
    "pl": "PL",
    "portugal": "PT",
    "pt": "PT",
    "spain": "ES",
    "es": "ES",
    "sweden": "SE",
    "se": "SE",
    "switzerland": "CH",
    "ch": "CH",
    "united kingdom": "GB",
    "uk": "GB",
    "gb": "GB",
}

SKILL_HINTS = [
    "python", "sql", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "django", "flask", "fastapi", "spring", "aws", "azure", "gcp", "docker",
    "kubernetes", "terraform", "linux", "postgresql", "mysql", "mongodb", "redis",
    "spark", "airflow", "tableau", "power bi", "excel", "machine learning", "ai",
    "nlp", "data analysis", "data engineering", "devops", "ci/cd", "figma", "seo",
    "content marketing", "salesforce", "sap", "agile", "scrum",
]

MOJIBAKE_REPLACEMENTS = {
    "\u00e2\u201a\u00ac": "\u20ac",
    "\u00c2\u00a3": "\u00a3",
    "\u00c2\u00a5": "\u00a5",
    "\u00c2\u00a9": "\u00a9",
    "\u00c2\u00ae": "\u00ae",
    "\u00c2": "",
    "\u00c3\u00a4": "\u00e4",
    "\u00c3\u00b6": "\u00f6",
    "\u00c3\u00bc": "\u00fc",
    "\u00c3\u201e": "\u00c4",
    "\u00c3\u2013": "\u00d6",
    "\u00c3\u0153": "\u00dc",
    "\u00c3\u0178": "\u00df",
    "\u00c3\u00a9": "\u00e9",
    "\u00c3\u00a8": "\u00e8",
    "\u00c3\u00aa": "\u00ea",
    "\u00c3\u00a1": "\u00e1",
    "\u00c3 ": "\u00e0",
    "\u00c3\u00b3": "\u00f3",
    "\u00c3\u00b4": "\u00f4",
    "\u00c3\u00b1": "\u00f1",
}

RATE_TYPE_KEYWORDS = {
    "hourly": ["hour", "hr", "uur", "stunde", "heure"],
    "daily": ["day", "daily", "dag", "tag", "jour"],
    "weekly": ["week", "weekly", "woche", "semaine"],
    "monthly": ["month", "monthly", "maand", "monat", "mois"],
    "annual": ["year", "annual", "annum", "yearly", "yr", "jaar", "jahr", "an"],
}


def clean_text(value, default=None, max_length=None):
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)

    value = html.unescape(value)
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        value = value.replace(bad, good)
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    if not value or value.lower() in {"none", "null", "nan", "n/a", "not specified"}:
        return default
    if max_length and len(value) > max_length:
        value = value[: max_length - 3].rstrip() + "..."
    return value


def split_env_list(value, default=""):
    raw = value if value is not None else default
    items = []
    for item in str(raw).split(","):
        cleaned = clean_text(item)
        if cleaned:
            items.append(cleaned)
    return items


def normalize_country(value, default="Unknown"):
    cleaned = clean_text(value)
    if not cleaned:
        return default
    lowered = cleaned.lower()
    if lowered in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[lowered]
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned.upper()
    return cleaned


def clean_skills(skills, description=None, limit=20):
    values = []
    if isinstance(skills, str):
        values.extend(re.split(r"[,;|/]", skills))
    elif isinstance(skills, (list, tuple, set)):
        values.extend(skills)

    description_text = clean_text(description, default="") or ""
    description_lower = description_text.lower()
    for skill in SKILL_HINTS:
        if re.search(rf"\b{re.escape(skill.lower())}\b", description_lower):
            values.append(skill)

    cleaned = []
    seen = set()
    for value in values:
        item = clean_text(value, max_length=80)
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def normalize_employment_type(value, default="permanent"):
    text = clean_text(value, default="")
    lowered = text.lower()
    if any(word in lowered for word in ["freelance", "freelancer", "self-employed", "zzp"]):
        return "freelance"
    if any(word in lowered for word in ["intern", "trainee", "stage", "apprentice"]):
        return "internship"
    if any(word in lowered for word in ["contract", "temporary", "temp", "fixed-term", "fixed term", "interim"]):
        return "contract"
    if any(word in lowered for word in ["part-time", "part time", "parttime"]):
        return "part-time"
    if any(word in lowered for word in ["full-time", "full time", "fulltime", "permanent", "employee", "vast"]):
        return "permanent"
    return default


def normalize_work_type(value, default="onsite"):
    text = clean_text(value, default="")
    lowered = text.lower()
    if any(word in lowered for word in ["hybrid", "hybride"]):
        return "hybrid"
    if any(word in lowered for word in ["remote", "work from home", "home based", "thuiswerk", "wfh"]):
        return "remote"
    if any(word in lowered for word in ["on-site", "onsite", "on site", "office", "location"]):
        return "onsite"
    return default


def infer_rate_type(text, default=None):
    cleaned = clean_text(text, default="")
    lowered = cleaned.lower()
    for rate_type, terms in RATE_TYPE_KEYWORDS.items():
        if any(re.search(rf"(^|\W){re.escape(term)}s?($|\W)", lowered) for term in terms):
            return rate_type
    if re.search(r"/\s*(h|hr|hour)", lowered):
        return "hourly"
    if re.search(r"/\s*(d|day)", lowered):
        return "daily"
    if re.search(r"/\s*(w|week)", lowered):
        return "weekly"
    if re.search(r"/\s*(m|mo|month)", lowered):
        return "monthly"
    if re.search(r"/\s*(y|yr|year)", lowered):
        return "annual"
    return default


def extract_rate_details(*texts, default_type=None):
    haystack = "\n".join(clean_text(text, default="") or "" for text in texts if text)
    if not haystack:
        return None, default_type

    currency = r"(?:\u20ac|eur|euro|\u00a3|gbp|\$|usd|chf|sek|dkk|nok|pln)"
    number = r"(?:\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d+)?)(?:\s?k)?"
    period_unit = r"(?:hour|hr|day|week|month|year|annum|yr|mo)"
    period = rf"(?:\s*(?:per|/)\s*{period_unit})?"
    pattern = re.compile(
        rf"({currency}\s*{number}(?:\s*(?:-|\u2013|\u2014|to)\s*{currency}?\s*{number})?{period}|"
        rf"{number}\s*(?:-|\u2013|\u2014|to)?\s*{number}?\s*{currency}{period}|"
        rf"{number}(?:\s*(?:-|\u2013|\u2014|to)\s*{number})?\s*(?:per|/)\s*{period_unit})",
        re.IGNORECASE,
    )
    match = pattern.search(haystack)
    if not match:
        return None, default_type
    rate_raw = clean_text(match.group(1), max_length=255)
    return rate_raw, infer_rate_type(rate_raw, default_type)


def normalize_date(value, default=None):
    if value is None:
        return default
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = clean_text(value, default="")
    lowered = text.lower()
    today = datetime.now().date()
    if not lowered:
        return default
    if any(term in lowered for term in ["today", "just posted", "posted just", "vandaag", "heute", "aujourd"]):
        return today
    if any(term in lowered for term in ["yesterday", "gisteren", "gestern", "hier"]):
        return today - timedelta(days=1)

    relative = re.search(r"(\d+)\+?\s*(minute|hour|day|week|month)s?", lowered)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit in {"minute", "hour"}:
            return today
        if unit == "day":
            return today - timedelta(days=amount)
        if unit == "week":
            return today - timedelta(days=amount * 7)
        if unit == "month":
            return today - timedelta(days=amount * 30)

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return default


def clean_job_record(data):
    title = clean_text(data.get("role_title") or data.get("title"), default="Unknown", max_length=255)
    company = clean_text(data.get("company_name") or data.get("company"), default="Unknown", max_length=255)
    source = clean_text(data.get("source"), default="Unknown", max_length=255)
    description = clean_text(data.get("description"), default="")
    rate_raw = clean_text(data.get("rate_raw"), max_length=255)
    rate_type = infer_rate_type(data.get("rate_type") or rate_raw, data.get("rate_type"))

    if not rate_raw:
        rate_raw, rate_type = extract_rate_details(
            data.get("summary"),
            data.get("description"),
            data.get("metadata"),
            default_type=rate_type,
        )

    context_text = " ".join(
        clean_text(part, default="") or ""
        for part in [title, company, data.get("employment_type"), data.get("work_type"), data.get("summary"), description]
    )

    return {
        "source": source,
        "source_job_id": clean_text(data.get("source_job_id"), max_length=255),
        "job_url": clean_text(data.get("job_url"), max_length=1024),
        "role_title": title,
        "company_name": company,
        "location_raw": clean_text(data.get("location_raw"), max_length=255),
        "description": clean_text(data.get("description"), max_length=4000),
        "company_size": clean_text(data.get("company_size"), default="unknown", max_length=255),
        "country": normalize_country(data.get("country")),
        "employment_type": normalize_employment_type(data.get("employment_type") or context_text),
        "work_type": normalize_work_type(data.get("work_type") or context_text, default="onsite"),
        "rate_raw": rate_raw,
        "rate_type": rate_type,
        "skills": clean_skills(data.get("skills"), description=context_text),
        "posted_date": normalize_date(data.get("posted_date") or data.get("posted_text")),
    }


def infer_seniority(title):
    if not title:
        return 'unknown'
    title_lower = title.lower()
    if any(word in title_lower for word in ['senior', 'sr', 'lead', 'principal', 'manager', 'director', 'head', 'vp', 'chief', 'chef', 'leiter', 'expert']):
        return 'senior'
    if any(word in title_lower for word in ['junior', 'jr', 'entry', 'graduate', 'intern', 'trainee', 'anfänger', 'stagiaire', 'assistant', 'student']):
        return 'junior'
    if any(word in title_lower for word in ['mid', 'mid-level', 'associate', 'medior']):
        return 'mid'
    return 'unknown'

def infer_industry(company_name, title):
    text = f"{company_name} {title}".lower()
    if any(word in text for word in ['software', 'tech', 'it', 'developer', 'data', 'digital', 'cloud', 'informatique', 'technologie', 'softwareentwicklung']):
        return 'tech'
    if any(word in text for word in ['bank', 'finance', 'fintech', 'investment', 'capital', 'finances', 'versicherung']):
        return 'finance'
    if any(word in text for word in ['health', 'pharma', 'medical', 'clinical', 'care', 'santé', 'gesundheit', 'medizin']):
        return 'pharma'
    if any(word in text for word in ['retail', 'ecommerce', 'shop', 'store', 'commerce', 'einzelhandel']):
        return 'retail'
    if any(word in text for word in ['logistics', 'supply chain', 'transport', 'delivery', 'logistique', 'logistik']):
        return 'logistics'
    return 'other'

def infer_job_function(title):
    if not title:
        return 'other'
    title_lower = title.lower()
    if any(word in title_lower for word in ['data', 'analytics', 'machine learning', 'ai', 'statistic', 'données', 'daten']):
        return 'data'
    if any(word in title_lower for word in ['developer', 'engineer', 'programmer', 'frontend', 'backend', 'fullstack', 'développeur', 'ingénieur', 'entwickler']):
        return 'dev'
    if any(word in title_lower for word in ['design', 'ux', 'ui', 'creative', 'art', 'concepteur', 'designer']):
        return 'design'
    if any(word in title_lower for word in ['marketing', 'seo', 'content', 'growth', 'sales', 'vente', 'vertrieb']):
        return 'marketing'
    if any(word in title_lower for word in ['operations', 'ops', 'supply', 'logistics', 'admin', 'opération', 'betrieb']):
        return 'ops'
    if any(word in title_lower for word in ['finance', 'accountant', 'financial', 'comptable', 'buchhalter']):
        return 'finance'
    return 'other'

def infer_role_category(title):
    if not title:
        return 'other'
    title_lower = title.lower()
    if any(word in title_lower for word in ['developer', 'engineer', 'programmer', 'frontend', 'backend', 'fullstack', 'software', 'devops', 'infrastructure', 'cloud', 'développeur', 'ingénieur', 'entwickler', 'it', 'system', 'network', 'security', 'administrator']):
        return 'engineering'
    if any(word in title_lower for word in ['data', 'analytics', 'machine learning', 'ai', 'statistic', 'scientist', 'analyst', 'bi', 'intelligence', 'données', 'daten']):
        return 'data_ai'
    if any(word in title_lower for word in ['design', 'ux', 'ui', 'creative', 'art', 'concepteur', 'designer', 'visual', 'graphic', 'multimedia']):
        return 'creative'
    if any(word in title_lower for word in ['marketing', 'seo', 'content', 'growth', 'sales', 'vente', 'vertrieb', 'social media', 'brand', 'advertising', 'pr']):
        return 'marketing'
    if any(word in title_lower for word in ['finance', 'accountant', 'financial', 'comptable', 'buchhalter', 'audit', 'controller', 'bank', 'investment']):
        return 'finance'
    if any(word in title_lower for word in ['operations', 'ops', 'supply', 'logistics', 'admin', 'opération', 'betrieb', 'hr', 'human resources', 'recruiter', 'coordinate']):
        return 'operations'
    if any(word in title_lower for word in ['health', 'pharma', 'medical', 'clinical', 'care', 'santé', 'gesundheit', 'medizin', 'nurse', 'doctor', 'research', 'lab']):
        return 'healthcare'
    if any(word in title_lower for word in ['legal', 'law', 'attorney', 'lawyer', 'compliance', 'regulatory', 'paralegal']):
        return 'legal'
    return 'other'

def infer_language(text):
    if not text:
        return None
    try:
        lang = detect(text)
        return lang.upper()
    except:
        return None

def normalize_rate(rate_raw, rate_type):
    if not rate_raw:
        return None
    try:
        cleaned = clean_text(rate_raw, default="")
        numbers = re.findall(r"[-+]?(?:\d{1,3}(?:[.,\s]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*k)?", cleaned, flags=re.IGNORECASE)
        if not numbers:
            return None
        raw_number = numbers[0].lower().replace(" ", "")
        multiplier = 1000 if raw_number.endswith("k") else 1
        raw_number = raw_number.rstrip("k")
        if "," in raw_number and "." in raw_number:
            raw_number = raw_number.replace(",", "")
        elif re.search(r"[,.]\d{3}$", raw_number):
            raw_number = raw_number.replace(",", "").replace(".", "")
        elif "," in raw_number:
            raw_number = raw_number.replace(",", ".")
        val = float(raw_number) * multiplier
        if rate_type == 'hourly':
            return val * 8
        if rate_type == 'daily':
            return val
        if rate_type == 'monthly':
            return val / 21
        if rate_type == 'annual':
            return val / 250
        if rate_type == 'project':
            return val / 5 # assuming 5 days project roughly
    except Exception:
        pass
    return None
