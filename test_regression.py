import asyncio,tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
import app
from graph.state import JobPosting
from nodes.parse_cv import extract_profile
from scrapers.live_scraper import relevant_listing

async def run():
 assert relevant_listing('Python Developer','Python Developer')
 assert not relevant_listing('Python Developer','Freelance Copywriter','Copywriting and editing')
 assert not relevant_listing('Python Developer','Senior Shopify Developer','Storefront and checkout')
 assert relevant_listing('Python Developer','Software Engineer','Our stack includes Python developer roles')
 cv=extract_profile('Jane Smith\nPython Developer\njane@example.com\nSkills: Python, SQL\nExperience\nDeveloped APIs\nEducation\nBSc Computer Science\nProjects\nBuilt a platform')
 assert 'Python' in cv.skills and 'Developed APIs' in cv.experience and 'BSc' in cv.education and 'platform' in cv.projects
 with tempfile.TemporaryDirectory() as tmp:
  with patch.object(app,'SQLITE_DB_PATH',Path(tmp)/'regression.db'):
   app.setup_db()
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
    assert (await c.post('/api/register',json={'email':'tester@example.org','password':'longsecret'})).status_code==200
    assert (await c.put('/api/profile',json={'name':'Saved Name','email':'tester@example.org','target_role':'Python Developer','skills':['SQL']})).status_code==200
    r=await c.post('/api/profile/upload',files={'file':('resume.txt',b'Jane Smith\nPython Developer\njane@example.com\nMy Python experience involves SQL, APIs, analytics, Docker.','text/plain')})
    assert r.status_code==200,r.text
    assert r.json()['profile']['target_role']=='Python Developer'
    assert 'SQL' in r.json()['profile']['skills']
    a=JobPosting(id='a',title='Python Developer',company='Example A',url='https://remotive.com/remote-jobs/a',source='Remotive',description='Python SQL')
    b=JobPosting(id='b',title='React Developer',company='Example B',url='https://remotive.com/remote-jobs/b',source='Remotive',description='React JavaScript')
    async def first(q):return [a]
    async def second(q):return [b]
    with patch.object(app,'scrape_remotive_by_query',first):
     assert (await c.post('/api/search',json={'query':'Python','source':'remotive'})).json()['count']==1
    assert len((await c.get('/api/jobs')).json())==1
    with patch.object(app,'scrape_remotive_by_query',second):
     assert (await c.post('/api/search',json={'query':'React','source':'remotive'})).json()['count']==1
    jobs=(await c.get('/api/jobs')).json()
    assert len(jobs)==1 and jobs[0]['job']['id']=='b',jobs
    assert (await c.post('/api/jobs/b/status',json={'status':'Saved'})).status_code==200
    with patch.object(app,'scrape_remotive_by_query',first):
     await c.post('/api/search',json={'query':'Python','source':'remotive'})
    jobs=(await c.get('/api/jobs')).json()
    assert len(jobs)==2 and {x['job']['id'] for x in jobs}=={'a','b'}
    assert (await c.post('/api/telegram/test')).status_code==404
    assert (await c.post('/api/email/test')).status_code==404
 print('REGRESSION TESTS PASSED')

if __name__=='__main__':asyncio.run(run())
