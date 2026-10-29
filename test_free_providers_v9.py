import asyncio
from unittest.mock import patch
from scrapers import live_scraper as s
class Resp:
 def __init__(self,payload):self.payload=payload
 def raise_for_status(self):pass
 def json(self):return self.payload
class Client:
 def __init__(self,**kwargs):pass
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def get(self,url,**kwargs):
  if 'remoteok' in url:return Resp([{'legal':'Terms'}, {'position':'Python Developer','company':'Alpha','url':'https://remoteok.com/remote-jobs/1','tags':['python'],'date':'2026-10-13','description':'<b>Python</b>'},{'position':'React Developer','url':'https://remoteok.com/remote-jobs/2'}])
  if 'arbeitnow' in url:return Resp({'data':[{'title':'Python Developer','company_name':'Bravo','url':'https://www.arbeitnow.com/view/python','description':'Python development','location':'Europe'},{'title':'React Engineer','url':'https://www.arbeitnow.com/view/react'}],'links':{'next':None}})
  raise Exception('unexpected URL')
async def main():
 with patch.object(s.httpx,'AsyncClient',Client):
  a=await s.scrape_remoteok_by_query('Python Developer')
  b=await s.scrape_arbeitnow_by_query('Python Developer')
  assert len(a)==1 and a[0].source=='Remote OK',a
  assert len(b)==1 and b[0].source=='Arbeitnow',b
 print('TWO NEW PROVIDER MOCK TESTS PASS')
asyncio.run(main())
