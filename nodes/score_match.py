import re
from graph.state import CVProfile, JobPosting, ScoredJob
from nodes.parse_cv import KNOWN_SKILLS

def present(skill: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)"+re.escape(skill)+r"(?!\w)",text,re.I))

def score_job_posting(job: JobPosting, profile: CVProfile) -> ScoredJob:
    job_text = job.title+" "+job.description+" "+" ".join(job.required_skills)
    demanded = list(dict.fromkeys([s for s in KNOWN_SKILLS if present(s,job_text)] + job.required_skills))
    matched = [s for s in demanded if any(s.casefold()==u.casefold() for u in profile.skills)]
    missing = [s for s in demanded if s not in matched]
    if demanded:
        skill_fit = len(matched)/len(demanded)
    else:
        skill_fit = None
    target = (profile.target_role or profile.title).strip().lower()
    title = job.title.lower()
    title_words = set(re.findall(r"[a-z]{3,}", target)) - {"engineer", "developer", "intern", "junior", "student", "and"}
    title_fit = bool(title_words and any(w in title for w in title_words))
    junior = bool(re.search(r"intern|trainee|graduate|entry.level|junior",title,re.I))
    senior = bool(re.search(r"senior|staff|principal|lead|director|manager",title,re.I))
    # Conservative and explainable: unknown requirements => no fabricated 98%.
    score = round(70*skill_fit + 20*int(title_fit) + 10*int(junior)) if skill_fit is not None else (25*int(title_fit)+10*int(junior))
    if senior and profile.years_experience < 3: score -= 25
    score = max(0,min(100,score))
    if not profile.skills and not target:score=0
    level = "HIGH" if score>=70 else "MEDIUM" if score>=40 else "LOW"
    reason = (f"Matched {len(matched)} of {len(demanded)} detected skills" if demanded else "Insufficient job requirements to estimate skill fit")
    if title_fit:reason += "; target role aligns"
    if senior:reason += "; seniority may be unsuitable"
    reason += ". Estimated relevance, not an employer assessment."
    return ScoredJob(job=job,score=score,match_level=level,reasoning=reason,matched_skills=matched,missing_skills=missing)
