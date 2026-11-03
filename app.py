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

# --- تنظیمات ---
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

# --- مدل‌های دیتابیس ---
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

# جدول جدید برای ذخیره نتایج امتیازدهی
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

# --- مدل‌های Pydantic ---
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

class ScoreResponse(BaseModel):
    overall_score: float
    keyword_score: float
    impact_score: float
    structure_score: float
    feedback: List[str]

# --- امنیت ---
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

# --- توابع کمکی امتیازدهی ---
def calculate_keyword_score(resume_text: str, job_desc: str) -> (float, List[str]):
    """محاسبه تطابق کلیدواژه‌ای ساده"""
    # استخراج کلمات کلیدی (بدون کلمات ربط)
    stop_words = {"and", "the", "a", "an", "to", "of", "in", "for", "with", "on", "at", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "from", "by", "as", "or", "but", "if", "so", "than", "then", "too", "very", "just", "about", "into", "through", "during", "before", "after", "above", "below", "between", "under", "over"}
    
    job_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', job_desc.lower())) - stop_words
    resume_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', resume_text.lower())) - stop_words
    
    if not job_words:
        return 0.0, ["Job description is empty."]
    
    matched = job_words.intersection(resume_words)
    score = (len(matched) / len(job_words)) * 100
    
    missing = job_words - matched
    feedback = [f"Missing keywords: {', '.join(list(missing)[:5])}..."] if missing else ["Great keyword match!"]
    return round(score, 1), feedback

def calculate_impact_score(experiences: List[Experience]) -> (float, List[str]):
    """ارزیابی قدرت توصیفات دوزبانه (PARQ) - فارسی + انگلیسی"""
    if not experiences:
        return 0.0, ["Add at least one work experience to get an impact score."]
    
    total_score = 0
    feedback = []
    
    # افعال قوی انگلیسی + فارسی
    action_verbs_en = {"led", "built", "designed", "developed", "created", "managed", "improved", "increased", "reduced", "launched", "implemented", "optimized", "automated", "delivered", "achieved", "grew", "saved", "transformed"}
    action_verbs_fa = {"رهبری", "ساخت", "طراحی", "توسعه", "ایجاد", "مدیریت", "بهبود", "افزایش", "کاهش", "راه‌اندازی", "پیاده‌سازی", "بهینه‌سازی", "خودکارسازی", "تحویل", "دستیابی", "رشد", "صرفه‌جویی", "تحول", "اجرا", "هدایت", "بنیان‌گذاری"}
    
    # کلمات نتیجه‌محور انگلیسی + فارسی
    result_en = {"increased", "reduced", "improved", "saved", "grew", "achieved", "accelerated", "cut", "boosted"}
    result_fa = {"افزایش", "کاهش", "بهبود", "صرفه‌جویی", "رشد", "دستیابی", "تسریع", "بازیابی", "ارتقا"}
    
    for exp in experiences:
        desc = (exp.description or "").strip()
        score = 0
        exp_feedback = []
        
        # 1. آیا با فعل قوی شروع شده؟
        first_word = desc.split()[0].lower() if desc else ""
        first_word_fa = desc.split()[0] if desc else ""
        if first_word in action_verbs_en or first_word_fa in action_verbs_fa:
            score += 30
        else:
            exp_feedback.append(f"'{exp.title}': Start with a strong action verb (e.g., Led, رهبری).")
        
        # 2. آیا عدد یا درصد دارد؟
        if re.search(r'\d+', desc):
            score += 40
        else:
            exp_feedback.append(f"'{exp.title}': Add numbers or percentages to quantify impact.")
        
        # 3. آیا کلمات کلیدی نتیجه‌محور دارد؟
        desc_lower = desc.lower()
        if any(kw in desc_lower for kw in result_en) or any(kw in desc for kw in result_fa):
            score += 30
        else:
            exp_feedback.append(f"'{exp.title}': Use result-oriented language (e.g., increased, افزایش).")
        
        total_score += score
        feedback.extend(exp_feedback)
    
    avg_score = total_score / len(experiences)
    return round(avg_score, 1), feedback

def calculate_structure_score(db: Session, user: U) -> (float, List[str]):
    """ارزیابی کامل بودن ساختار رزومه"""
    score = 0
    feedback = []
    
    # 1. اطلاعات تماس
    if user.phone and user.email:
        score += 25
    else:
        feedback.append("Add phone number and email to complete contact info.")
    
    # 2. بیوگرافی
    if user.bio and len(user.bio) > 20:
        score += 15
    else:
        feedback.append("Add a brief professional bio (at least 20 characters).")
    
    # 3. تجربه کاری
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    if exps:
        score += 30
    else:
        feedback.append("Add at least one work experience.")
    
    # 4. مهارت‌ها
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    if len(skills) >= 3:
        score += 15
    elif skills:
        score += 7
        feedback.append("Add more skills (at least 3 recommended).")
    else:
        feedback.append("Add at least 3 skills.")
    
    # 5. پروژه یا سند
    projs = db.query(Project).filter(Project.owner_id == user.id).all()
    docs = db.query(D).filter(D.owner_id == user.id).all()
    if projs or docs:
        score += 15
    else:
        feedback.append("Add a project or a verified document.")
        
    return min(score, 100), feedback

# --- اپلیکیشن ---
app = FastAPI(title="CareerVault Pro", version="3.0", redirect_slashes=False)
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

# ... (اندپوینت‌های profile/info, experience, skills, projects, documents مانند قبل) ...
# برای صرفه‌جویی در فضا، فرض می‌کنیم این‌ها از نسخه قبلی دست‌نخورده باقی مانده‌اند.
# اما در کد نهایی، باید حتماً آن‌ها را قرار دهید.

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

# --- اندپوینت جدید: امتیازدهی هوشمند ---
@app.post("/api/score", response_model=ScoreResponse)
def score_resume(req: ScoreRequest, db=Depends(gdb), user=Depends(cu)):
    # 1. آماده‌سازی متن رزومه برای تحلیل کلیدواژه‌ای
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    projs = db.query(Project).filter(Project.owner_id == user.id).all()
    
    resume_text = f"{user.bio or ''} "
    resume_text += " ".join([f"{e.title} {e.company} {e.description or ''}" for e in exps]) + " "
    resume_text += " ".join([s.name for s in skills]) + " "
    resume_text += " ".join([f"{p.name} {p.description or ''}" for p in projs])
    
    # 2. محاسبه امتیازها
    keyword_score, kw_feedback = calculate_keyword_score(resume_text, req.job_description)
    impact_score, impact_feedback = calculate_impact_score(exps)
    structure_score, struct_feedback = calculate_structure_score(db, user)
    
    # 3. امتیاز نهایی (وزن‌دهی)
    overall = (keyword_score * 0.4) + (impact_score * 0.35) + (structure_score * 0.25)
    
    # 4. جمع‌آوری بازخوردها
    all_feedback = kw_feedback + impact_feedback + struct_feedback
    
    # 5. ذخیره در تاریخچه
    history = ScoreHistory(
        owner_id=user.id,
        overall_score=overall,
        keyword_score=keyword_score,
        impact_score=impact_score,
        structure_score=structure_score,
        feedback=json.dumps(all_feedback, ensure_ascii=False)
    )
    db.add(history); db.commit()
    
    return {
        "overall_score": round(overall, 1),
        "keyword_score": keyword_score,
        "impact_score": impact_score,
        "structure_score": structure_score,
        "feedback": all_feedback
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
