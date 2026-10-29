from typing import List
from pydantic import BaseModel, Field

class CVProfile(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    university: str = ""
    graduation_year: str = ""
    target_role: str = ""
    skills: List[str] = Field(default_factory=list)
    years_experience: float = 0
    seniority: str = ""
    languages: List[str] = Field(default_factory=list)
    location_preference: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    summary: str = ""
    experience: str = ""
    education: str = ""
    projects: str = ""

class JobPosting(BaseModel):
    id: str
    title: str
    company: str = "Not specified"
    location: str = "Not specified"
    url: str
    source: str
    posted_date: str = "Date unverified"
    job_type: str = "Job"
    is_open: bool = True
    description: str = ""
    required_skills: List[str] = Field(default_factory=list)

class ScoredJob(BaseModel):
    job: JobPosting
    score: int
    match_level: str
    reasoning: str
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    status: str = "New"
