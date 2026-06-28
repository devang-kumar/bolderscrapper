import os
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Date, ARRAY, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bolders:password@localhost:5432/job_market")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False)
    source_job_id = Column(String(255))
    job_url = Column(String(1024))
    role_title = Column(String(255), nullable=False)
    company_name = Column(String(255))
    location_raw = Column(String(255))
    description = Column(Text)
    role_category = Column(String(255))
    job_function = Column(String(255))
    industry = Column(String(255))
    seniority_level = Column(String(255))
    company_size = Column(String(255))
    employment_type = Column(String(255))
    work_type = Column(String(255))
    country = Column(String(255))
    language_required = Column(String(255))
    rate_raw = Column(String(255))
    rate_normalized_eur_day = Column(Numeric)
    rate_type = Column(String(255))
    skills = Column(ARRAY(Text))
    posted_date = Column(Date)
    scraped_date = Column(Date, default=datetime.date.today)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
