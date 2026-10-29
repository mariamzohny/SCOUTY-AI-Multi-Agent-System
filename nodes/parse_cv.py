import re
from graph.state import CVProfile

KNOWN_SKILLS = ["Python", "SQL", "Java", "JavaScript", "C++", "C#", "HTML", "CSS", "React", "Node.js", "TypeScript", "Pandas", "NumPy", "Scikit-learn", "PyTorch", "TensorFlow", "FastAPI", "Django", "Flask", "Excel", "Power BI", "Tableau", "Docker", "AWS", "Azure", "Git", "Linux", "MongoDB", "PostgreSQL", "MySQL", "NLP", "Machine Learning", "Deep Learning", "Computer Vision", "Data Analysis", "Data Engineering", "Spark", "Hadoop", "R", "Go", "Kubernetes", "ETL", "LLM", "LangChain", "Arabic", "English", "Figma", "Flutter", "REST APIs"]

def extract_profile(text: str, filename: str = "") -> CVProfile:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text)
    phone = re.search(r"(?:\+?\d[\d ()-]{7,}\d)", text)
    skills = [s for s in KNOWN_SKILLS if re.search(r"(?<!\w)"+re.escape(s)+r"(?!\w)", text, re.I)]
    headings = {'experience':r'(?:work|professional|employment)\s+experience|experience',
                'education':r'education|academic\s+background',
                'projects':r'projects|personal\s+projects'}
    sections = {}
    active = None
    for line in lines:
        matched = next((key for key,pattern in headings.items() if re.fullmatch(pattern+r'\s*:?\s*',line,re.I)),None)
        if matched:
            active = matched
            sections.setdefault(active,[])
        elif active:
            if re.fullmatch(r'[A-Za-z ]{3,32}\s*:',line) and not any(re.fullmatch(p+r'\s*:',line,re.I) for p in headings.values()):
                active = None
            else:
                sections[active].append(line)
    name = next((x for x in lines[:4] if 3<=len(x)<65 and '@' not in x and not re.search(r'https?://|\d{5}|\b(?:curriculum vitae|resume|skills|profile)\b',x,re.I)), "")
    title = next((x for x in lines[1:5] if re.search(r'\b(?:developer|engineer|analyst|scientist|designer|intern)\b', x, re.I) and len(x)<90),"")
    return CVProfile(name=name,title=title,email=email.group(0) if email else "",
                     phone=phone.group(0) if phone else "",skills=skills,summary=text[:1800],
                     experience='\n'.join(sections.get('experience',[]))[:5000],
                     education='\n'.join(sections.get('education',[]))[:5000],
                     projects='\n'.join(sections.get('projects',[]))[:5000])
