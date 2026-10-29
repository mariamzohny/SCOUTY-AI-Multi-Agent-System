import hashlib
import re
from datetime import datetime, timezone, timedelta
import json
import time
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from bs4 import BeautifulSoup
import httpx
from graph.state import JobPosting

def relevant_listing(query: str, title: str, description: str = "") -> bool:
    """Conservative title-first relevance for many job families, not only developers."""
    norm=lambda t: re.sub(r"[^a-z0-9+#.]+", " ", t.casefold()).strip()
    q=norm(query); t=norm(title); d=norm(description)[:1500]
    if not q or not t: return False
    aliases={
      'frontend': ('frontend','front end','front-end'),
      'backend': ('backend','back end','back-end'),
      'fullstack': ('fullstack','full stack','full-stack'),
      'ai': ('ai','artificial intelligence','machine learning','ml'),
      'ml': ('ml','machine learning'),
      'data': ('data','analytics','analyst'),
      'devops': ('devops','site reliability','sre'),
      'qa': ('qa','quality assurance','software tester'),
      'ux': ('ux','user experience'),
      'ui': ('ui','user interface'),
      'internship': ('intern','internship','trainee'),
      'intern': ('intern','internship','trainee'),
      'developer': ('developer','engineer','programmer'),
      'engineer': ('engineer','developer'),
      'analyst': ('analyst','analytics'),
      'scientist': ('scientist',),
      'designer': ('designer','design'),
      'manager': ('manager','management'),
      'writer': ('writer','copywriter','content creator'),
    }
    stop={'senior','junior','remote','job','jobs','entry','level','position','hiring','full','time','part','mid','middle'}
    tokens=[w for w in q.split() if w not in stop]
    if not tokens: return False
    def contains(s, text):
        return any(re.search(r'(?<!\w)'+re.escape(a).replace(r'\ ',r'\s+')+r'(?!\w)',text) for a in aliases.get(s,(s,)))
    matched=[w for w in tokens if contains(w,t)]
    if len(matched)==len(tokens): return True
    # Skill-only queries can match a generic role if the skill is central
    # in the beginning of the job's requirements, not buried as incidental.
    job_roles=('engineer','developer','analyst','scientist','designer','manager','writer','intern','qa','specialist','administrator','consultant','researcher','architect','technician')
    role_tokens={'developer','engineer','analyst','scientist','designer','manager','writer','intern','internship','specialist','consultant','researcher'}
    tech_tokens=[w for w in tokens if w not in role_tokens]
    unmatched=[w for w in tokens if w not in matched]
    if len(unmatched)!=1 or unmatched[0] not in tech_tokens or not any(contains(x,t) for x in job_roles): return False
    skill=unmatched[0]
    if len(tokens)>1 and any(w in role_tokens and not contains(w,t) for w in tokens):return False
    other={'python','java','javascript','typescript','react','angular','vue','shopify','php','ruby','.net','c#','rails','node','golang','rust','flutter','swift','kotlin'} - {skill}
    if skill in {'python','java','javascript','typescript','react','angular','vue','shopify','php','ruby','.net','node','golang','rust'} and any(contains(x,t) for x in other): return False
    return contains(skill,d[:550]) and (contains(skill,d[:180]) or re.search(r'(?i)(?:required|must have|strong experience|proficien(?:t|cy)|expertise|primary|core skills).{0,75}'+re.escape(skill),d[:700]) is not None)

# Public providers work better with a concise keyword than a multiword role phrase.
# Always apply relevance filtering to the original user query, not the broad API query.
def primary_api_term(query: str) -> str:
    words = re.findall(r"[a-z0-9+#.]+", query.lower())
    stop = {'developer','engineer','software','senior','junior','remote','job','jobs',
            'entry','level','full','stack','intern','internship','specialist','position'}
    terms = [x for x in words if x not in stop]
    return ' '.join(terms[:3]) if terms else query.strip()

async def scrape_himalayas_by_query(query: str) -> list[JobPosting]:
    """Himalayas official search API; paginate instead of inspecting only page one."""
    output=[]; seen=set(); key=primary_api_term(query)
    async with httpx.AsyncClient(timeout=25,follow_redirects=True) as client:
        for page in range(1, 4):
            response=await client.get('https://himalayas.app/jobs/api/search',
                                      params={'q':key,'sort':'relevant','page':page})
            response.raise_for_status()
            data=response.json()
            items=data.get('jobs') or []
            if not isinstance(items,list):
                raise ValueError('Unexpected Himalayas JSON response: missing jobs list')
            for item in items:
                title=str(item.get('title') or '').strip()
                url=str(item.get('applicationLink') or item.get('url') or '').strip()
                if not url.startswith('https://') or url in seen:continue
                raw=item.get('description') or item.get('excerpt') or ''
                desc=BeautifulSoup(str(raw),'html.parser').get_text(' ',strip=True)[:5000]
                if not relevant_listing(query,title,desc):continue
                seen.add(url)
                company=item.get('companyName') or 'Not specified'
                locations=item.get('locationRestrictions') or []
                location=', '.join(str(x.get('name') or x.get('alpha2') or 'Unknown') if isinstance(x,dict) else str(x) for x in locations[:5]) if isinstance(locations,list) and locations else 'Remote (location eligibility unverified)'
                posted=item.get('pubDate') or item.get('publishedAt') or 'Date unverified'
                if isinstance(posted,(int,float)):
                    posted=datetime.fromtimestamp(posted/1000 if posted>1e11 else posted,tz=timezone.utc).isoformat()
                output.append(JobPosting(id=hashlib.sha256(('himalayas:'+url).encode()).hexdigest()[:24],title=title,company=company,location=location,url=url,source='Himalayas',posted_date=str(posted),job_type='Internship' if re.search(r'intern|trainee',title,re.I) else 'Job',description=desc))
            if data.get('hasNextPage') is False or len(items)<20:break
    return output

# Remotive recommends only a few API calls per day. Cache by broad query for six hours.
_remotive_cache = {}
async def scrape_remotive_by_query(query: str) -> list[JobPosting]:
    api_url='https://remotive.com/api/remote-jobs'
    key=primary_api_term(query)
    cached=_remotive_cache.get(key)
    if cached and time.monotonic()-cached[0] < 21600:
        items=cached[1]
    else:
        async with httpx.AsyncClient(timeout=25,follow_redirects=True) as client:
            response=await client.get(api_url,params={'search':key})
            response.raise_for_status()
            content=response.json()
        items=content.get('jobs',[])
        if not isinstance(items,list):raise ValueError('Unexpected Remotive response: missing jobs list')
        _remotive_cache[key]=(time.monotonic(),items)
    results=[]
    for item in items:
        url=str(item.get('url') or '')
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname or not (parsed.hostname=='remotive.com' or parsed.hostname.endswith('.remotive.com')):continue
        title=str(item.get('title') or '').strip()
        if not title:continue
        desc=BeautifulSoup(str(item.get('description') or ''),'html.parser').get_text(' ',strip=True)[:5000]
        if not relevant_listing(query,title,desc):continue
        results.append(JobPosting(id=hashlib.sha256(url.encode()).hexdigest()[:24],title=title,company=item.get('company_name') or 'Not specified',location=item.get('candidate_required_location') or 'Remote (check eligibility)',url=url,source='Remotive',posted_date=item.get('publication_date') or 'Date unverified',job_type='Internship' if re.search(r'intern|trainee',title,re.I) else 'Job',description=desc))
    return results


# Remote OK provides a public JSON feed; first element is its license notice.
_remoteok_cache = {}
async def scrape_remoteok_by_query(query: str) -> list[JobPosting]:
    key='feed'; cached=_remoteok_cache.get(key)
    if cached and time.monotonic()-cached[0]<3600:
        items=cached[1]
    else:
        async with httpx.AsyncClient(timeout=25,follow_redirects=True,headers={'User-Agent':'SCOUTY job search (+source links)'}) as client:
            res=await client.get('https://remoteok.com/api')
            res.raise_for_status()
            items=res.json()
        if not isinstance(items,list): raise ValueError('Unexpected Remote OK feed')
        _remoteok_cache[key]=(time.monotonic(),items)
    results=[]
    for item in items:
        if not isinstance(item,dict) or not item.get('position'):continue
        url=str(item.get('url') or '')
        if urlparse(url).hostname not in ('remoteok.com','www.remoteok.com') or not url.startswith('https://'):continue
        title=str(item['position']).strip()
        description=BeautifulSoup(str(item.get('description') or ''),'html.parser').get_text(' ',strip=True)[:5000]
        tags=item.get('tags') if isinstance(item.get('tags'),list) else []
        desc=(title+' '+ ' '.join(map(str,tags))+' '+description)
        if not relevant_listing(query,title,desc):continue
        results.append(JobPosting(id=hashlib.sha256(('remoteok:'+url).encode()).hexdigest()[:24],title=title,company=str(item.get('company') or 'Not specified'),location=str(item.get('location') or 'Remote (check eligibility)'),url=url,source='Remote OK',posted_date=str(item.get('date') or 'Date unverified'),job_type='Internship' if re.search(r'intern|trainee',title,re.I) else 'Job',description=desc))
    return results

# Arbeitnow's free public board feed covers Europe and some remote positions.
_arbeitnow_cache={}
async def scrape_arbeitnow_by_query(query: str) -> list[JobPosting]:
    cached=_arbeitnow_cache.get('feed')
    if cached and time.monotonic()-cached[0]<1800:items=cached[1]
    else:
        items=[]
        async with httpx.AsyncClient(timeout=25,follow_redirects=True) as client:
            url='https://www.arbeitnow.com/api/job-board-api'
            for page in range(1,4):
                response=await client.get(url,params={'page':page})
                response.raise_for_status()
                payload=response.json()
                batch=payload.get('data')
                if not isinstance(batch,list):raise ValueError('Unexpected Arbeitnow feed')
                items.extend(batch)
                if not payload.get('links',{}).get('next'):break
        _arbeitnow_cache['feed']=(time.monotonic(),items)
    results=[]
    for item in items:
        if not isinstance(item,dict):continue
        title=str(item.get('title') or '').strip()
        url=str(item.get('url') or '')
        if not url.startswith('https://') or not title:continue
        desc=BeautifulSoup(str(item.get('description') or ''),'html.parser').get_text(' ',strip=True)[:5000]
        tags=item.get('tags') if isinstance(item.get('tags'),list) else []
        desc+=' '+' '.join(map(str,tags))
        if not relevant_listing(query,title,desc):continue
        stamp=item.get('created_at') or 'Date unverified'
        if isinstance(stamp,(int,float)):stamp=datetime.fromtimestamp(stamp,tz=timezone.utc).isoformat()
        results.append(JobPosting(id=hashlib.sha256(('arbeitnow:'+url).encode()).hexdigest()[:24],title=title,company=str(item.get('company_name') or 'Not specified'),location=str(item.get('location') or ('Remote' if item.get('remote') else 'Not specified')),url=url,source='Arbeitnow',posted_date=str(stamp),job_type='Internship' if re.search(r'intern|trainee',title,re.I) else 'Job',description=desc))
    return results
