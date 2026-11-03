import os, hashlib, uuid, json, re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext
from jose import jwt, JWTError

SECRET = os.environ.get("SECRET_KEY")
if not SECRET or len(SECRET) < 32:
    raise SystemExit("FATAL: SECRET_KEY must be set.")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("FATAL: DATABASE_URL is not set.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
UPLOAD_DIR = "/tmp/uploads"
Path(UPLOAD_DIR).mkdir(exist_ok=True)

def gdb():
    db = Session()
    try: yield db
    finally: db.close()

class U(Base):
    __tablename__ = "u"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    github = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class D(Base):
    __tablename__ = "d"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    doc_type = Column(String)
    title = Column(String)
    issuer = Column(String)
    issue_date = Column(String)
    file_path = Column(String)
    file_hash = Column(String, index=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Experience(Base):
    __tablename__ = "experience"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    title = Column(String)
    company = Column(String)
    start_date = Column(String)
    end_date = Column(String)
    description = Column(Text)

class Skill(Base):
    __tablename__ = "skill"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    name = Column(String)
    level = Column(String)

class Project(Base):
    __tablename__ = "project"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    name = Column(String)
    url = Column(String, nullable=True)
    description = Column(Text)

class ScoreHistory(Base):
    __tablename__ = "score_history"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    overall_score = Column(Float)
    keyword_score = Column(Float)
    impact_score = Column(Float)
    structure_score = Column(Float)
    feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

class UC(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)

class UO(BaseModel):
    id: int; email: EmailStr; full_name: str; created_at: datetime
    model_config = {"from_attributes": True}

class ProfileUpdate(BaseModel):
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    bio: Optional[str] = None

class ExpCreate(BaseModel):
    title: str; company: str; start_date: str; end_date: str; description: str

class SkillCreate(BaseModel):
    name: str; level: str

class ProjCreate(BaseModel):
    name: str; url: Optional[str] = None; description: str

class ScoreRequest(BaseModel):
    job_description: str

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oa = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def cu(t: str = Depends(oa), db=Depends(gdb)):
    try:
        p = jwt.decode(t, SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Invalid token")
    u = db.query(U).filter(U.email == p.get("sub")).first()
    if not u: raise HTTPException(401, "User not found")
    return u

def normalize_persian(text: str) -> str:
    """نرمال‌سازی متن فارسی برای استخراج کلمات بهتر"""
    # تبدیل نیم‌فاصله به فاصله
    text = text.replace("\u200c", " ")
    # حذف علائم نگارشی فارسی
    for ch in "،؛؟!«»:()[]{}":
        text = text.replace(ch, " ")
    # حذف اعراب
    text = re.sub(r'[\u064B-\u065F]', '', text)
    return text

def extract_keywords(text: str) -> set:
    """استخراج کلمات کلیدی از متن فارسی و انگلیسی (نسخه بهبود یافته)"""
    stop_en = {"and","the","a","an","to","of","in","for","with","on","at","is","are","was","were","be","been","being","have","has","had","do","does","did","will","would","could","should","may","might","must","can","this","that","these","those","i","you","he","she","it","we","they","me","him","her","us","them","my","your","his","its","our","their","from","by","as","or","but","if","so","than","then","too","very","just","about","into","through","during","before","after","above","below","between","under","over","looking","least","strong","experience"}
    stop_fa = {"و","در","به","از","که","این","را","با","است","برای","آن","یک","خود","تا","کرد","بر","هم","نیز","یا","شد","اما","اگر","چون","پس","هر","همه","دیگر","بین","زیر","روی","پیش","قبل","بعد","هنگام","وقتی","دنبال","باید","تجربه","داشته","باشد","هستیم","تخصص","دارای","نه","بله","کردن","شدن","بودن","های","ها","ای","آنها","شده"}

    # نرمال‌سازی متن فارسی
    normalized = normalize_persian(text)

    en_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', normalized.lower())) - stop_en
    fa_words = set(re.findall(r'[\u0600-\u06FF]{3,}', normalized)) - stop_fa
    return en_words | fa_words

def calculate_keyword_score(resume_text: str, job_desc: str):
    job_words = extract_keywords(job_desc)
    resume_words = extract_keywords(resume_text)

    if not job_words:
        return 0.0, ["Job description is empty."]

    matched = job_words.intersection(resume_words)
    score = (len(matched) / len(job_words)) * 100

    missing = job_words - matched
    feedback = []
    if missing:
        feedback.append(f"Missing keywords ({len(missing)} total): {', '.join(list(missing)[:5])}")
    else:
        feedback.append("Great keyword match!")
    return round(score, 1), feedback

def calculate_impact_score(experiences):
    if not experiences:
        return 0.0, ["Add at least one work experience."]
    total = 0
    fb = []
    action_verbs_en = {"led","built","designed","developed","created","managed","improved","increased","reduced","launched","implemented","optimized","automated","delivered","achieved","grew","saved","transformed"}
    action_verbs_fa = {"رهبری","ساخت","طراحی","توسعه","ایجاد","مدیریت","بهبود","افزایش","کاهش","راه‌اندازی","پیاده‌سازی","بهینه‌سازی","خودکارسازی","تحویل","دستیابی","رشد","صرفه‌جویی","تحول","اجرا","هدایت","بنیان‌گذاری"}
    result_en = {"increased","reduced","improved","saved","grew","achieved","accelerated","cut","boosted"}
    result_fa = {"افزایش","کاهش","بهبود","صرفه‌جویی","رشد","دستیابی","تسریع","بازیابی","ارتقا"}

    for exp in experiences:
        desc = (exp.description or "").strip()
        s = 0
        first = desc.split()[0].lower() if desc else ""
        first_fa = desc.split()[0] if desc else ""
        if first in action_verbs_en or first_fa in action_verbs_fa:
            s += 30
        else:
            fb.append(f"'{exp.title}': Start with strong action verb.")
        if re.search(r'\d+', desc):
            s += 40
        else:
            fb.append(f"'{exp.title}': Add numbers to quantify impact.")
        if any(k in desc.lower() for k in result_en) or any(k in desc for k in result_fa):
            s += 30
        else:
            fb.append(f"'{exp.title}': Use result-oriented language.")
        total += s
    return round(total / len(experiences), 1), fb

def calculate_structure_score(db, user):
    score = 0
    fb = []
    if user.phone and user.email: score += 25
    else: fb.append("Complete contact info.")
    if user.bio and len(user.bio) > 20: score += 15
    else: fb.append("Add a brief bio.")
    if db.query(Experience).filter(Experience.owner_id == user.id).count(): score += 30
    else: fb.append("Add work experience.")
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    if len(skills) >= 3: score += 15
    elif skills: score += 7; fb.append("Add more skills (3+).")
    else: fb.append("Add 3+ skills.")
    projs = db.query(Project).filter(Project.owner_id == user.id).count()
    docs = db.query(D).filter(D.owner_id == user.id).count()
    if projs or docs: score += 15
    else: fb.append("Add a project or document.")
    return min(score, 100), fb

app = FastAPI(title="CareerVault Pro", version="3.2", redirect_slashes=False)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("", include_in_schema=False)
@app.get("/")
def h(): return {"status":"ok"}

@app.post("/api/auth/register", response_model=UO, status_code=201)
def reg(p: UC, db=Depends(gdb)):
    if db.query(U).filter(U.email == p.email).first(): raise HTTPException(400, "Email exists")
    u = U(email=p.email, full_name=p.full_name, hashed_password=pwd.hash(p.password))
    db.add(u); db.commit(); db.refresh(u); return u

@app.post("/api/auth/login")
def li(f: OAuth2PasswordRequestForm = Depends(), db=Depends(gdb)):
    u = db.query(U).filter(U.email == f.username).first()
    if not u or not pwd.verify(f.password, u.hashed_password): raise HTTPException(401, "Bad creds")
    e = datetime.utcnow() + timedelta(minutes=120)
    return {"access_token": jwt.encode({"sub": u.email, "exp": e}, SECRET, algorithm="HS256"), "token_type": "bearer"}

@app.put("/api/profile/info")
def update_info(p: ProfileUpdate, db=Depends(gdb), user=Depends(cu)):
    for k, v in p.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit(); return {"status": "updated"}

@app.post("/api/profile/experience")
def add_exp(e: ExpCreate, db=Depends(gdb), user=Depends(cu)):
    db.add(Experience(owner_id=user.id, **e.model_dump())); db.commit(); return {"status": "added"}

@app.post("/api/profile/skills")
def add_skill(s: SkillCreate, db=Depends(gdb), user=Depends(cu)):
    db.add(Skill(owner_id=user.id, **s.model_dump())); db.commit(); return {"status": "added"}

@app.post("/api/profile/projects")
def add_proj(p: ProjCreate, db=Depends(gdb), user=Depends(cu)):
    db.add(Project(owner_id=user.id, **p.model_dump())); db.commit(); return {"status": "added"}

@app.post("/api/documents")
async def up(doc_type: str = Form(...), title: str = Form(...), issuer: str = Form(""), issue_date: str = Form(""), file: UploadFile = File(...), db=Depends(gdb), user=Depends(cu)):
    if doc_type not in {"education","financial","achievement","identity"}: raise HTTPException(422, "Bad type")
    data = await file.read()
    if not data or len(data) > 20*1024*1024: raise HTTPException(413, "Size error")
    name = f"{uuid.uuid4().hex}.bin"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as fh: fh.write(data)
    d = D(owner_id=user.id, doc_type=doc_type, title=title, issuer=issuer or None, issue_date=issue_date or None, file_path=path, file_hash=hashlib.sha256(data).hexdigest(), verified=True)
    db.add(d); db.commit(); return {"id": d.id, "file_hash": d.file_hash}

@app.get("/api/resume")
def get_full_resume(db=Depends(gdb), user=Depends(cu)):
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    projs = db.query(Project).filter(Project.owner_id == user.id).all()
    docs = db.query(D).filter(D.owner_id == user.id).all()
    return {
        "basics": {"name": user.full_name, "email": user.email, "phone": user.phone, "location": user.location, "linkedin": user.linkedin, "github": user.github, "bio": user.bio},
        "experience": [{"title": e.title, "company": e.company, "start": e.start_date, "end": e.end_date, "description": e.description} for e in exps],
        "skills": [{"name": s.name, "level": s.level} for s in skills],
        "projects": [{"name": p.name, "url": p.url, "description": p.description} for p in projs],
        "verified_documents_count": len([d for d in docs if d.verified])
    }

@app.get("/api/resume/json-resume")
def get_json_resume(db=Depends(gdb), user=Depends(cu)):
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    projs = db.query(Project).filter(Project.owner_id == user.id).all()
    return {
        "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
        "basics": {"name": user.full_name, "email": user.email, "phone": user.phone, "url": user.linkedin, "summary": user.bio},
        "work": [{"name": e.company, "position": e.title, "startDate": e.start_date, "endDate": e.end_date, "summary": e.description} for e in exps],
        "skills": [{"name": s.name, "level": s.level} for s in skills],
        "projects": [{"name": p.name, "url": p.url, "description": p.description} for p in projs]
    }

@app.post("/api/score")
def score_resume(req: ScoreRequest, db=Depends(gdb), user=Depends(cu)):
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    projs = db.query(Project).filter(Project.owner_id == user.id).all()

    resume_text = f"{user.bio or ''} "
    resume_text += " ".join([f"{e.title} {e.company} {e.description or ''}" for e in exps]) + " "
    resume_text += " ".join([s.name for s in skills]) + " "
    resume_text += " ".join([f"{p.name} {p.description or ''}" for p in projs])

    kw_s, kw_fb = calculate_keyword_score(resume_text, req.job_description)
    imp_s, imp_fb = calculate_impact_score(exps)
    str_s, str_fb = calculate_structure_score(db, user)

    overall = (kw_s * 0.4) + (imp_s * 0.35) + (str_s * 0.25)
    all_fb = kw_fb + imp_fb + str_fb

    db.add(ScoreHistory(owner_id=user.id, overall_score=overall, keyword_score=kw_s, impact_score=imp_s, structure_score=str_s, feedback=json.dumps(all_fb, ensure_ascii=False)))
    db.commit()

    return {"overall_score": round(overall,1), "keyword_score": kw_s, "impact_score": imp_s, "structure_score": str_s, "feedback": all_fb}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
