import hashlib
import hmac
import io
import logging
import json
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from config import SQLITE_DB_PATH, BASE_DIR, HOST, PORT
from graph.state import CVProfile
from nodes.parse_cv import extract_profile
from nodes.score_match import score_job_posting
from scrapers.live_scraper import scrape_remotive_by_query,scrape_himalayas_by_query,scrape_remoteok_by_query,scrape_arbeitnow_by_query,relevant_listing

@asynccontextmanager
async def lifespan(app):
    setup_db()
    yield
app=FastAPI(title='SCOUTY - Personalized Job Search',version='5.1.4',lifespan=lifespan)

def db():
    connection=sqlite3.connect(SQLITE_DB_PATH,timeout=20)
    connection.row_factory=sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection

def setup_db():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,profile_json TEXT NOT NULL DEFAULT '{}',telegram_chat_id TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,data_json TEXT NOT NULL,seen_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS user_jobs(user_id INTEGER NOT NULL,job_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'New',PRIMARY KEY(user_id,job_id),FOREIGN KEY(user_id) REFERENCES users(id),FOREIGN KEY(job_id) REFERENCES jobs(id));''')

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),260000).hex()
def verify(password,stored):
    try:
        salt,_=stored.split(':',1)
        return hmac.compare_digest(hash_password(password,salt),stored)
    except (ValueError,TypeError):return False

def current_user(request:Request):
    token=request.cookies.get('scouty_session')
    if not token:raise HTTPException(401,'Please sign in')
    hashed=hashlib.sha256(token.encode()).hexdigest()
    with db() as c:
        row=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?',(hashed,datetime.now(timezone.utc).isoformat())).fetchone()
    if not row:raise HTTPException(401,'Session expired; sign in again')
    return dict(row)

class Auth(BaseModel):
    email:str
    password:str

def set_session(response,user_id):
    token=secrets.token_urlsafe(32)
    expires=datetime.now(timezone.utc)+timedelta(days=14)
    with db() as c:c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,expires.isoformat()))
    response.set_cookie('scouty_session',token,max_age=14*86400,httponly=True,samesite='lax',secure=False)

@app.post('/api/register')
def register(data:Auth,response:Response):
    email=data.email.strip().lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):raise HTTPException(422,'Valid email required')
    if len(data.password)<8:raise HTTPException(422,'Password must have at least 8 characters')
    try:
        with db() as c:
            cur=c.execute('INSERT INTO users(email,password_hash,profile_json) VALUES(?,?,?)',(email,hash_password(data.password),CVProfile(email=email).model_dump_json()))
            uid=cur.lastrowid
    except sqlite3.IntegrityError:raise HTTPException(409,'Email already registered')
    set_session(response,uid)
    return {'ok':True}

@app.post('/api/login')
def login(data:Auth,response:Response):
    with db() as c:row=c.execute('SELECT * FROM users WHERE email=?',(data.email.strip().lower(),)).fetchone()
    if not row or not verify(data.password,row['password_hash']):raise HTTPException(401,'Invalid email or password')
    set_session(response,row['id']);return {'ok':True}

@app.post('/api/logout')
def logout(request:Request,response:Response):
    token=request.cookies.get('scouty_session')
    if token:
        with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('scouty_session');return {'ok':True}

@app.get('/api/profile')
def get_profile(request:Request):
    u=current_user(request)
    return json.loads(u['profile_json'])

@app.put('/api/profile')
def put_profile(profile:CVProfile,request:Request):
    u=current_user(request)
    with db() as c:c.execute('UPDATE users SET profile_json=? WHERE id=?',(profile.model_dump_json(),u['id']))
    return {'ok':True,'profile':profile.model_dump()}

@app.post('/api/profile/upload')
async def upload_profile(request:Request,file:UploadFile=File(...)):
    u=current_user(request)
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024:raise HTTPException(413,'CV must be below 5 MB')
    ext=Path(file.filename or '').suffix.lower()
    if ext not in ('.pdf','.docx','.txt'):raise HTTPException(415,'Only PDF, DOCX, TXT supported')
    try:
        if ext=='.pdf':
            from pypdf import PdfReader
            text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages[:12])
        elif ext=='.docx':
            from docx import Document
            doc=Document(io.BytesIO(content))
            text='\n'.join([p.text for p in doc.paragraphs]+[cell.text for table in doc.tables for row in table.rows for cell in row.cells])
        else:text=content.decode('utf-8-sig')
    except Exception as exc:
        logging.exception('CV import failure')
        raise HTTPException(422,f'Could not read this CV ({type(exc).__name__}). Try a valid PDF/DOCX/TXT file; scanned PDFs need OCR.')
    if len(text.strip())<20:raise HTTPException(422,'Not enough readable text found in CV')
    profile=extract_profile(text,file.filename or '')
    # Preserve user-entered fields on upload; extracted fields are suggestions.
    old=CVProfile.model_validate_json(u['profile_json'])
    for key in ('title','location','university','graduation_year','target_role','years_experience','seniority',
                'languages','location_preference','domains','experience','education','projects'):
        if not getattr(profile,key):setattr(profile,key,getattr(old,key))
    profile.skills=list(dict.fromkeys(profile.skills+old.skills))
    profile.name=profile.name or old.name
    profile.phone=profile.phone or old.phone
    profile.email=profile.email or old.email or u['email']
    with db() as c:c.execute('UPDATE users SET profile_json=? WHERE id=?',(profile.model_dump_json(),u['id']))
    return {'ok':True,'profile':profile.model_dump(),'message':'Please review and correct the extracted fields before searching.'}

@app.get('/api/profile/download')
def cv_pdf(request:Request):
    profile=CVProfile.model_validate(get_profile(request))
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from xml.sax.saxutils import escape
        buf=io.BytesIO()
        regular='Helvetica'; bold='Helvetica-Bold'
        # Windows fonts can support many characters; default fonts are safe fallbacks.
        font_candidates=[(Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/arialbd.ttf')),
                         (Path('C:/Windows/Fonts/segoeui.ttf'),Path('C:/Windows/Fonts/segoeuib.ttf'))]
        for path_regular,path_bold in font_candidates:
            if path_regular.is_file() and path_bold.is_file():
                try:
                    pdfmetrics.registerFont(TTFont('ScoutRegular',str(path_regular)))
                    pdfmetrics.registerFont(TTFont('ScoutBold',str(path_bold)))
                    regular='ScoutRegular';bold='ScoutBold';break
                except Exception:
                    logging.exception('Font registration failed')
        styles={
            'name':ParagraphStyle('cvname',fontName=bold,fontSize=20,leading=25,textColor=colors.HexColor('#242a44'),spaceAfter=10),
            'contact':ParagraphStyle('cvcontact',fontName=regular,fontSize=9,leading=14,textColor=colors.HexColor('#536078'),spaceAfter=15,wordWrap='CJK'),
            'heading':ParagraphStyle('cvheading',fontName=bold,fontSize=11,leading=15,textColor=colors.HexColor('#4f46e5'),spaceBefore=14,spaceAfter=6),
            'body':ParagraphStyle('cvbody',fontName=regular,fontSize=9.5,leading=15,spaceAfter=5,wordWrap='CJK')}
        def safe(value):
            value=str(value or '')
            # Standard core fonts do not support arbitrary Unicode.
            if regular=='Helvetica':value=value.encode('latin-1','replace').decode('latin-1')
            return escape(value).replace('\n','<br/>')
        story=[Paragraph(safe(profile.name or 'Your Name'),styles['name'])]
        contact=' | '.join(filter(None,[profile.title,profile.email,profile.phone,profile.location]))
        if contact:story.append(Paragraph(safe(contact),styles['contact']))
        sections=[('PROFESSIONAL SUMMARY',profile.summary),('SKILLS',', '.join(profile.skills)),
                  ('EXPERIENCE',profile.experience),('EDUCATION',profile.education or profile.university),
                  ('PROJECTS',profile.projects),('LANGUAGES',', '.join(profile.languages))]
        for heading,content in sections:
            if str(content or '').strip():
                story.append(Paragraph(heading,styles['heading']))
                for paragraph in str(content).split('\n\n'):
                    if paragraph.strip():story.append(Paragraph(safe(paragraph),styles['body']))
        document=SimpleDocTemplate(buf,pagesize=A4,rightMargin=48,leftMargin=48,
                                   topMargin=46,bottomMargin=45,title='SCOUTY CV')
        document.build(story)
        buf.seek(0)
        return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="scouty_cv.pdf"','Cache-Control':'no-store'})
    except Exception:
        logging.exception('CV PDF generation failure')
        raise HTTPException(500,'CV generation failed. Check the CMD console for the detailed error, and ensure reportlab is installed.')

class SearchRequest(BaseModel):
    query:str=Field(min_length=2,max_length=100)
    source:str="all"

@app.post('/api/search')
async def search(request:Request,data:SearchRequest):
    u=current_user(request)
    if data.source not in ('all','remotive','himalayas','remoteok','arbeitnow'):
        raise HTTPException(422,'Invalid provider')
    q=data.query.strip()
    providers={'remoteok':(scrape_remoteok_by_query,'https://remoteok.com/'),
               'arbeitnow':(scrape_arbeitnow_by_query,'https://www.arbeitnow.com/'),
               'remotive':(scrape_remotive_by_query,'https://remotive.com/remote-jobs/'),
               'himalayas':(scrape_himalayas_by_query,'https://himalayas.app/jobs')}
    chosen=['himalayas','remotive','remoteok','arbeitnow'] if data.source=='all' else [data.source]
    jobs=[]; failures=[]; stats={}; successful=[]
    # Fetch providers concurrently so one slow feed does not delay others.
    async def fetch_one(source):
        fn,_=providers[source]
        try:
            incoming=await fn(q)
            return source,[job for job in incoming if relevant_listing(q,job.title,job.description)],None
        except Exception as exc:
            logging.warning('Provider %s error: %s',source,exc)
            return source,[],str(exc)[:160]
    import asyncio
    for source,accepted,error in await asyncio.gather(*(fetch_one(source) for source in chosen)):
        if error:
            failures.append(source+': '+error)
        else:
            stats[source]=len(accepted)
            successful.append(source)
            jobs.extend(accepted)
    unique={j.url:j for j in jobs if j.url.startswith('https://')}
    jobs=list(unique.values())
    provider_url=providers[data.source][1] if data.source!='all' else 'https://himalayas.app/jobs'
    if not jobs:
        # A completed search replaces stale ordinary results, even when empty.
        # Saved and Applied listings remain intact.
        with db() as c:
            c.execute("DELETE FROM user_jobs WHERE user_id=? AND status='New'", (u['id'],))
        if not successful:
            message='The selected provider(s) could not be reached; previous unsaved results were cleared. See the provider errors.'
            state='provider_error'
        else:
            message='The API responded, but no closely relevant jobs were found for this query. Previous unsaved results were cleared; saved/applied jobs remain.'
            state='no_matches'
        if failures:message+=' Errors: '+'; '.join(failures)
        return {'ok':False,'count':0,'status':state,'message':message,'search_url':provider_url,'sources':stats,'warnings':failures}
    now=datetime.now(timezone.utc).isoformat()
    with db() as c:
        # New search replaces the user's current results; statuses for saved/applied
        # are preserved. Existing saved/applied jobs stay available in their tabs.
        c.execute("DELETE FROM user_jobs WHERE user_id=? AND status='New'", (u['id'],))
        for job in jobs:
            c.execute('INSERT INTO jobs(id,data_json,seen_at) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data_json=excluded.data_json,seen_at=excluded.seen_at',(job.id,job.model_dump_json(),now))
            c.execute('INSERT OR IGNORE INTO user_jobs(user_id,job_id) VALUES(?,?)',(u['id'],job.id))
    return {'ok':True,'status':'results','count':len(jobs),'message':f'Found {len(jobs)} closely relevant listings. Saved/applied jobs stay available. Check application eligibility on the source site.' + ((' Partial provider issues: '+ '; '.join(failures)) if failures else ''),'search_url':provider_url,'sources':stats,'warnings':failures}

@app.post('/api/scrape')
async def scrape(request:Request,data:Optional[SearchRequest]=None):
    return await search(request,data or SearchRequest(query='Data Science Intern'))

def scored_jobs(request):
    u=current_user(request)
    profile=CVProfile.model_validate_json(u['profile_json'])
    with db() as c:
        rows=c.execute('SELECT j.data_json,uj.status FROM user_jobs uj JOIN jobs j ON j.id=uj.job_id WHERE uj.user_id=? ORDER BY j.seen_at DESC',(u['id'],)).fetchall()
    from graph.state import JobPosting
    result=[]
    for row in rows:
        scored=score_job_posting(JobPosting.model_validate_json(row['data_json']),profile).model_dump()
        scored['status']=row['status']
        scored['saved']=row['status']=='Saved';scored['applied']=row['status']=='Applied'
        result.append(scored)
    return sorted(result,key=lambda item:item['score'],reverse=True)

@app.get('/api/jobs')
def jobs(request:Request):return scored_jobs(request)

@app.get('/api/stats')
def stats(request:Request):
    jobs=scored_jobs(request)
    intern=[j for j in jobs if j['job']['job_type']=='Internship']
    return {'total_jobs':len(jobs),'total_internships':len(intern),'total_junior_jobs':len(jobs)-len(intern),'high_matches':sum(x['score']>=70 for x in jobs),'saved_count':sum(x['status']=='Saved' for x in jobs),'applied_count':sum(x['status']=='Applied' for x in jobs)}

class StatusUpdate(BaseModel):
    status:str
@app.post('/api/jobs/{job_id}/status')
def update_status(job_id:str,data:StatusUpdate,request:Request):
    u=current_user(request)
    if data.status not in ('New','Saved','Applied','Interviewing','Rejected'):raise HTTPException(422,'Invalid status')
    with db() as c:
        result=c.execute('UPDATE user_jobs SET status=? WHERE user_id=? AND job_id=?',(data.status,u['id'],job_id))
        if not result.rowcount:raise HTTPException(404,'Listing not found')
    return {'ok':True}

# Opt-in read-only LangGraph workflow. Original endpoints stay unchanged.
class AgentAnalyzeRequest(BaseModel):
    cv_text: str = Field(default='', max_length=20000)
    jobs: list[dict] = Field(default_factory=list, max_length=100)

@app.post('/api/agents/analyze')
def agent_analyze(data: AgentAnalyzeRequest, request: Request):
    u = current_user(request)
    from graph.agent_workflow import build_graph
    from graph.state import JobPosting
    try:
        validated = [JobPosting.model_validate(job).model_dump() for job in data.jobs]
    except Exception as exc:
        raise HTTPException(422, 'Invalid job data') from exc
    try:
        graph = build_graph()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    # Existing saved profile is used unless caller deliberately supplies CV text.
    state = {'jobs': validated, 'cv_text': data.cv_text, 'trace': []}
    if not data.cv_text.strip():
        state['profile'] = CVProfile.model_validate_json(u['profile_json']).model_dump()
    result = graph.invoke(state)
    return {'ok': True, 'profile': result['profile'], 'shortlist': result['shortlist'],
            'summary': result['summary'], 'trace': result['trace']}

# Experimental opt-in LLM specialists. Existing APIs and scoring remain unchanged.
class AgenticAnalyzeRequest(AgentAnalyzeRequest):
    llm_enabled: bool = False

@app.post('/api/agents/advanced')
def advanced_agent_analyze(data: AgenticAnalyzeRequest, request: Request):
    u = current_user(request)
    from graph.agentic_workflow import build_agentic_graph
    from graph.state import JobPosting
    try:
        validated = [JobPosting.model_validate(job).model_dump() for job in data.jobs]
    except Exception as exc:
        raise HTTPException(422, 'Invalid job data') from exc
    try:
        graph = build_agentic_graph()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    state = {'jobs':validated, 'cv_text':data.cv_text, 'trace':[], 'llm_enabled':data.llm_enabled, 'llm_used':False}
    if not data.cv_text.strip():
        state['profile'] = CVProfile.model_validate_json(u['profile_json']).model_dump()
    result = graph.invoke(state)
    return {'ok':True, 'profile':result['profile'], 'shortlist':result['shortlist'],
            'summary':result['summary'], 'recommendations':result.get('recommendations',[]),
            'review':result['review'], 'trace':result['trace'],
            'llm_status':result.get('llm_status',''), 'llm_used':result.get('llm_used',False)}

app.mount('/static',StaticFiles(directory=BASE_DIR/'static'),name='static')
@app.get('/')
def index():
    # The direct /static/index.html route is the canonical, verified new UI.
    # Redirecting avoids serving any legacy root template by mistake.
    return RedirectResponse(url='/static/index.html?v=scouty-5-1-4', status_code=307,
        headers={'Cache-Control':'no-store, max-age=0'})

@app.get('/api/version')
def version():
    return {'app':'SCOUTY','version':'5.1.4','frontend':'/static/index.html',
            'root_redirect':True,'code_path':str(Path(__file__).resolve())}
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host=HOST,port=PORT)
