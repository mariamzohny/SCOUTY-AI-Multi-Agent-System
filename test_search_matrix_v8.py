import asyncio, tempfile
from pathlib import Path
from unittest.mock import patch
import httpx,app
from graph.state import JobPosting
from scrapers.live_scraper import relevant_listing

cases=[
('Python Developer','Python Developer',True),('Python Developer','Senior React Developer',False),
('Data Analyst','Data Analyst',True),('Data Analyst','Content Writer',False),
('Data Scientist','Senior Data Scientist',True),('Data Scientist','Data Analyst',False),
('AI Engineer','AI Engineer',True),('ML Engineer','Machine Learning Engineer',True),
('Frontend Developer','Front-End Engineer',True),('Backend Developer','Backend Engineer',True),
('React Developer','React Frontend Developer',True),('React Developer','Angular Developer',False),
('QA Engineer','Quality Assurance Engineer',True),('QA Engineer','Data Scientist',False),
('UX Designer','User Experience Designer',True),('UI Designer','User Interface Designer',True),
('Product Manager','Product Manager',True),('Project Manager','Product Manager',False),
('Content Writer','Content Writer',True),('Content Writer','Python Engineer',False),
('Internship','Software Engineering Intern',True),('Internship','Senior Software Engineer',False),
('DevOps Engineer','Site Reliability Engineer',True),('Cybersecurity Analyst','Cybersecurity Analyst',True),
('SQL','SQL Database Analyst',True),('Python','Senior .NET Full-stack Developer',False),
('Mobile Developer','Mobile Developer',True),('Graphic Designer','Graphic Designer',True),
('HR Manager','HR Manager',True),('Sales Executive','Sales Executive',True),
]
async def main():
 for q,t,want in cases:
  got=relevant_listing(q,t)
  assert got==want,(q,t,got,want)
 with tempfile.TemporaryDirectory() as d:
  with patch.object(app,'SQLITE_DB_PATH',Path(d)/'test.db'):
   app.setup_db()
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
    assert (await c.post('/api/register',json={'email':'allroles@testing.org','password':'longpassword'})).status_code==200
    async def result(q):return [JobPosting(id='id1',title='Python Developer',company='Example',url='https://himalayas.app/jobs/1',source='Himalayas',description='Python development')]
    async def empty(q):return []
    async def fail(q):raise RuntimeError('403 Forbidden')
    with patch.object(app,'scrape_himalayas_by_query',result):
     assert (await c.post('/api/search',json={'source':'himalayas','query':'Python Developer'})).json()['count']==1
    assert len((await c.get('/api/jobs')).json())==1
    with patch.object(app,'scrape_himalayas_by_query',empty):
     assert (await c.post('/api/search',json={'source':'himalayas','query':'UX Designer'})).json()['status']=='no_matches'
    assert len((await c.get('/api/jobs')).json())==0, 'stale jobs after empty'
    with patch.object(app,'scrape_himalayas_by_query',result):
     await c.post('/api/search',json={'source':'himalayas','query':'Python Developer'})
    assert (await c.post('/api/jobs/id1/status',json={'status':'Saved'})).status_code==200
    with patch.object(app,'scrape_remoteok_by_query',fail):
     assert (await c.post('/api/search',json={'source':'remoteok','query':'Python Developer'})).json()['status']=='provider_error'
    assert len((await c.get('/api/jobs')).json())==1,'saved listing removed'
 print(f'PASS: {len(cases)} relevance cases + API stale/no-results/provider/saved state')
asyncio.run(main())
