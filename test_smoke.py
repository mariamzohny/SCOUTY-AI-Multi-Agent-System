"""Local API smoke tests (no live provider credentials/network required)."""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
import app
from graph.state import JobPosting

async def main():
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(app, 'SQLITE_DB_PATH', Path(directory) / 'smoke.sqlite3'):
            app.setup_db()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://testserver') as client:
                async def check(method, path, expected=200, **kwargs):
                    r=await client.request(method,path,**kwargs)
                    assert r.status_code == expected, (method,path,r.status_code,r.text[:500])
                    print('PASS',method,path,r.status_code)
                    return r
                await check('GET','/',307,follow_redirects=False)
                await check('GET','/static/index.html')
                await check('GET','/static/app.js')
                version=(await check('GET','/api/version')).json()
                assert version['version']=='5.1.4'
                await check('GET','/api/profile',401)
                await check('POST','/api/register',json={'email':'test@example.org','password':'securepass123'})
                await check('POST','/api/register',409,json={'email':'test@example.org','password':'securepass123'})
                await check('GET','/api/profile')
                await check('PUT','/api/profile',json={'name':'Test User','email':'test@example.org','skills':['Python','SQL']})
                upload=await check('POST','/api/profile/upload',files={'file':('mycv.txt',b'Test User | Software engineer, Python, SQL, Git, GitHub, data analysis and APIs.','text/plain')})
                assert upload.json()['ok']
                pdf=await check('GET','/api/profile/download')
                assert pdf.content.startswith(b'%PDF-')
                await check('GET','/api/jobs')
                await check('GET','/api/stats')
                await check('GET','/api/telegram',404)
                await check('PUT','/api/telegram',404,json={'chat_id':'12345'})
                await check('POST','/api/notify',404)
                await check('GET','/api/email/settings',404)
                example=JobPosting(id='smoke001',title='Python Data Intern',company='Example Company',url='https://remotive.com/remote-jobs/example',source='Remotive',description='Python SQL data')
                async def fake_search(query):return [example]
                with patch.object(app,'scrape_remotive_by_query',fake_search):
                    result=(await check('POST','/api/search',json={'query':'Python data','source':'remotive'})).json()
                    assert result['ok'] and result['count']==1
                jobs=(await check('GET','/api/jobs')).json()
                assert len(jobs)==1, jobs
                await check('POST','/api/jobs/smoke001/status',json={'status':'Saved'})
                updated=(await check('GET','/api/jobs')).json()
                assert updated[0]['status']=='Saved'
                async def failing_search(query):raise RuntimeError('Provider inaccessible')
                with patch.object(app,'scrape_remoteok_by_query',failing_search):
                    assert not (await check('POST','/api/search',json={'query':'Data intern','source':'remoteok'})).json()['ok']
                await check('POST','/api/logout')
                await check('GET','/api/profile',401)
                await check('POST','/api/login',json={'email':'test@example.org','password':'securepass123'})
                await check('GET','/api/profile')
                print('ALL SMOKE TESTS PASSED')
if __name__=='__main__':asyncio.run(main())
