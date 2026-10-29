import asyncio,tempfile
from pathlib import Path
from unittest.mock import patch
import httpx,app
async def run():
 with tempfile.TemporaryDirectory() as d:
  with patch.object(app,'SQLITE_DB_PATH',Path(d)/'test.db'):
   app.setup_db()
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as c:
    await c.post('/api/register',json={'email':'qa@test.com','password':'longpassword'})
    async def empty(q):return []
    async def broken(q):raise RuntimeError('HTTP 503')
    with patch.object(app,'scrape_remotive_by_query',empty):
     x=(await c.post('/api/search',json={'source':'remotive','query':'Python Developer'})).json()
     assert x['status']=='no_matches',x
    with patch.object(app,'scrape_remotive_by_query',broken):
     x=(await c.post('/api/search',json={'source':'remotive','query':'Python Developer'})).json()
     assert x['status']=='provider_error' and '503' in x['message'],x
    with patch.object(app,'scrape_remotive_by_query',broken),patch.object(app,'scrape_himalayas_by_query',empty),patch.object(app,'scrape_remoteok_by_query',empty),patch.object(app,'scrape_arbeitnow_by_query',empty):
     x=(await c.post('/api/search',json={'source':'all','query':'Python Developer'})).json()
     assert x['status']=='no_matches' and len(x['warnings'])==1,x
 print('PROVIDER DIAGNOSTICS PASSED')
asyncio.run(run())
