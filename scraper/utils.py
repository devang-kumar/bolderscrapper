import re
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

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
        # Extract the first numeric value
        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str(rate_raw).replace(',', '').replace(' ', ''))
        if not numbers:
            return None
        val = float(numbers[0])
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
