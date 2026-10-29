import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
import app
from scrapers.live_scraper import relevant_listing,scrape_himalayas_by_query
from graph.state import JobPosting

assert relevant_listing('Python Developer','Python Developer')
assert not relevant_listing('Python Developer','Senior React Full-stack Developer','Experience with Python preferred')
assert not relevant_listing('Python Developer','Senior .NET Developer','Python experience a plus')
assert not relevant_listing('Python Developer','Senior Shopify Developer','Using Python in reporting')
assert relevant_listing('Python Developer','Backend Engineer','We need an engineer with Python experience building APIs')
assert not relevant_listing('Python Developer','Freelance Copywriter','Python Python Python')

class FakeResponse:
 def raise_for_status(self): pass
 def json(self): return {'jobs':[{'title':'Python Developer','companyName':'Example Corp','applicationLink':'https://himalayas.app/jobs/python-developer','locationRestrictions':[{'name':'Egypt','alpha2':'EG'}],'pubDate':1790000000000,'description':'<p>Python developer sought</p>'},{'title':'React Developer','companyName':'Not Python','applicationLink':'https://himalayas.app/jobs/react-developer','description':'Python mentioned once'}]}
class FakeClient:
 def __init__(self,**kwargs):pass
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def get(self,*args,**kwargs):return FakeResponse()

async def test():
 with patch('scrapers.live_scraper.httpx.AsyncClient',FakeClient):
  result=await scrape_himalayas_by_query('Python Developer')
 assert len(result)==1 and result[0].location=='Egypt' and result[0].source=='Himalayas',result
 with tempfile.TemporaryDirectory() as temp:
  with patch.object(app,'SQLITE_DB_PATH',Path(temp)/'local.db'):
   app.setup_db()
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
    assert (await c.post('/api/register',json={'email':'test@example.com','password':'secure-password'})).status_code==200
    async def remotive(q):return [JobPosting(id='bad',title='React Developer',description='Python nice to have',company='Bad',url='https://remotive.com/jobs/bad',source='Remotive'),JobPosting(id='good',title='Python Developer',company='Good',url='https://remotive.com/jobs/good',source='Remotive')]
    async def himalayas(q):return result
    with patch.object(app,'scrape_remotive_by_query',remotive),patch.object(app,'scrape_himalayas_by_query',himalayas),patch.object(app,'scrape_remoteok_by_query',lambda q: asyncio.sleep(0,result=[])),patch.object(app,'scrape_arbeitnow_by_query',lambda q: asyncio.sleep(0,result=[])):
     response=(await c.post('/api/search',json={'query':'Python Developer','source':'all'})).json()
    assert response['ok'] and response['count']==2,response
    names=[j['job']['title'] for j in (await c.get('/api/jobs')).json()]
    assert names==['Python Developer','Python Developer'],names
 print('V6 TESTS PASSED')
asyncio.run(test())
