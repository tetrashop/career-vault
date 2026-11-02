import os, hashlib, uuid, json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext
from jose import jwt, JWTError

# --- تنظیمات ---
SECRET = os.environ.get("SECRET_KEY")
if not SECRET or len(SECRET) < 32:
    raise SystemExit("FATAL: SECRET_KEY must be set and >= 32 chars.")

# استفاده از /tmp برای Vercel
UPLOAD_DIR = "/tmp/uploads"
Path(UPLOAD_DIR).mkdir(exist_ok=True)

DB_URL = "sqlite:////tmp/vault.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

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
    # فیلدهای جدید پروفایل
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
    level = Column(String) # e.g., Beginner, Intermediate, Advanced, Expert

class Project(Base):
    __tablename__ = "project"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("u.id"), index=True)
    name = Column(String)
    url = Column(String, nullable=True)
    description = Column(Text)

Base.metadata.create_all(bind=engine)

# --- مدل‌های Pydantic (اعتبارسنجی) ---
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

# --- ابزارهای امنیتی ---
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

app = FastAPI(title="CareerVault Pro", version="2.0", redirect_slashes=False)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- اندپوینت‌های احراز هویت ---
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

# --- اندپوینت‌های رزومه (Profile, Exp, Skills, Projects) ---
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

# --- اندپوینت‌های اسناد (مثل قبل) ---
TY = {"education", "financial", "achievement", "identity"}
@app.post("/api/documents")
async def up(doc_type: str = Form(...), title: str = Form(...), issuer: str = Form(""), issue_date: str = Form(""), file: UploadFile = File(...), db=Depends(gdb), user=Depends(cu)):
    if doc_type not in TY: raise HTTPException(422, "Bad type")
    data = await file.read()
    if not data or len(data) > 20*1024*1024: raise HTTPException(413, "Size error")
    
    name = f"{uuid.uuid4().hex}.bin"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as fh: fh.write(data)
    
    d = D(owner_id=user.id, doc_type=doc_type, title=title, issuer=issuer or None, issue_date=issue_date or None, file_path=path, file_hash=hashlib.sha256(data).hexdigest(), verified=True)
    db.add(d); db.commit(); return {"id": d.id, "file_hash": d.file_hash}

# --- اندپوینت خروجی نهایی (Full Resume & JSON Resume) ---
@app.get("/api/resume")
def get_full_resume(db=Depends(gdb), user=Depends(cu)):
    exps = db.query(Experience).filter(Experience.owner_id == user.id).all()
    skills = db.query(Skill).filter(Skill.owner_id == user.id).all()
    projs = db.query(Project).filter(Project.owner_id == user.id).all()
    docs = db.query(D).filter(D.owner_id == user.id).all()
    
    return {
        "basics": {
            "name": user.full_name, "email": user.email, "phone": user.phone,
            "location": user.location, "linkedin": user.linkedin, "github": user.github,
            "bio": user.bio
        },
        "experience": [{"title": e.title, "company": e.company, "start": e.start_date, "end": e.end_date, "description": e.description} for e in exps],
        "skills": [{"name": s.name, "level": s.level} for s in skills],
        "projects": [{"name": p.name, "url": p.url, "description": p.description} for p in projs],
        "verified_documents_count": len([d for d in docs if d.verified])
    }

@app.get("/api/resume/json-resume")
def get_json_resume(db=Depends(gdb), user=Depends(cu)):
    # فرمت استاندارد JSON Resume برای سایت‌هایی مثل LinkedIn
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
