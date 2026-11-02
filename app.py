import os,hashlib,uuid
from datetime import datetime,timedelta
from pathlib import Path
from typing import Optional,List
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Form
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field,ConfigDict
from sqlalchemy import create_engine,Column,Integer,String,DateTime,ForeignKey,Text,Boolean
from sqlalchemy.orm import sessionmaker,declarative_base
from passlib.context import CryptContext
from jose import jwt,JWTError

SECRET=os.environ.get("SECRET_KEY")
if not SECRET or len(SECRET) < 32:
    raise SystemExit("FATAL: SECRET_KEY must be set and at least 32 chars. "
                     "Run: export SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))')")
UPLOAD_DIR="/tmp/uploads"
Path(UPLOAD_DIR).mkdir(exist_ok=True)

engine=create_engine("sqlite:////tmp/vault.db",connect_args={"check_same_thread":False})
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)
Base=declarative_base()

def gdb():
    db=Session()
    try: yield db
    finally: db.close()

class U(Base):
    __tablename__="u"
    id=Column(Integer,primary_key=True)
    email=Column(String,unique=True,index=True)
    full_name=Column(String)
    hashed_password=Column(String)
    national_id=Column(String,unique=True)
    created_at=Column(DateTime,default=datetime.utcnow)

class D(Base):
    __tablename__="d"
    id=Column(Integer,primary_key=True)
    owner_id=Column(Integer,ForeignKey("u.id"),index=True)
    doc_type=Column(String)
    title=Column(String)
    issuer=Column(String)
    issue_date=Column(String)
    file_path=Column(String)
    file_hash=Column(String,index=True)
    verified=Column(Boolean,default=False)
    created_at=Column(DateTime,default=datetime.utcnow)

class A(Base):
    __tablename__="a"
    id=Column(Integer,primary_key=True)
    user_id=Column(Integer,ForeignKey("u.id"),index=True)
    action=Column(String)
    detail=Column(Text)
    created_at=Column(DateTime,default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

class UC(BaseModel):
    email:EmailStr
    full_name:str=Field(min_length=2,max_length=120)
    password:str=Field(min_length=8,max_length=128)
    national_id:Optional[str]=None

class UO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:int; email:EmailStr; full_name:str; created_at:datetime

class DO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:int; doc_type:str; title:str; issuer:Optional[str]
    issue_date:Optional[str]; verified:bool; file_hash:str; created_at:datetime

class TO(BaseModel):
    access_token:str; token_type:str="bearer"

class PO(BaseModel):
    user:UO; documents:List[DO]; summary:str

pwd=CryptContext(schemes=["pbkdf2_sha256"],deprecated="auto")
oa=OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def cu(t:str=Depends(oa),db=Depends(gdb)):
    try:
        p=jwt.decode(t,SECRET,algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401,"bad token")
    u=db.query(U).filter(U.email==p.get("sub")).first()
    if not u: raise HTTPException(401,"no user")
    return u

app = FastAPI(title="CareerVault", redirect_slashes=False)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("", include_in_schema=False)
@app.get("/")
def h(): return {"status":"ok"}

@app.post("/api/auth/register",response_model=UO,status_code=201)
def reg(p:UC,db=Depends(gdb)):
    if db.query(U).filter(U.email==p.email).first(): raise HTTPException(400,"exists")
    u=U(email=p.email,full_name=p.full_name,hashed_password=pwd.hash(p.password),national_id=p.national_id)
    db.add(u); db.commit(); db.refresh(u); return u

@app.post("/api/auth/login",response_model=TO)
def li(f:OAuth2PasswordRequestForm=Depends(),db=Depends(gdb)):
    u=db.query(U).filter(U.email==f.username).first()
    if not u or not pwd.verify(f.password,u.hashed_password): raise HTTPException(401,"bad creds")
    e=datetime.utcnow()+timedelta(minutes=60)
    return {"access_token":jwt.encode({"sub":u.email,"exp":e},SECRET,algorithm="HS256"),"token_type":"bearer"}

TY={"education","financial","achievement","identity"}
MX=20*1024*1024

@app.post("/api/documents",response_model=DO,status_code=201)
async def up(doc_type:str=Form(...),title:str=Form(...),issuer:str=Form(""),issue_date:str=Form(""),file:UploadFile=File(...),db=Depends(gdb),user:U=Depends(cu)):
    if doc_type not in TY: raise HTTPException(422,"bad type")
    data=await file.read()
    if not data or len(data)>MX: raise HTTPException(413,"size")
    name=f"{uuid.uuid4().hex}.bin"
    path=os.path.join(UPLOAD_DIR,name)
    with open(path,"wb") as fh: fh.write(data)
    d=D(owner_id=user.id,doc_type=doc_type,title=title,issuer=issuer or None,issue_date=issue_date or None,file_path=path,file_hash=hashlib.sha256(data).hexdigest(),verified=True)
    db.add(d); db.add(A(user_id=user.id,action="upload",detail=title)); db.commit(); db.refresh(d); return d

@app.get("/api/documents",response_model=List[DO])
def ls(db=Depends(gdb),user:U=Depends(cu)):
    return db.query(D).filter(D.owner_id==user.id).all()

@app.get("/api/profile",response_model=PO)
def pr(db=Depends(gdb),user:U=Depends(cu)):
    docs=db.query(D).filter(D.owner_id==user.id).all()
    v=[d for d in docs if d.verified]
    cnt={}
    for d in v: cnt[d.doc_type]=cnt.get(d.doc_type,0)+1
    sm=f"{len(v)} verified: "+", ".join(f"{k}={n}" for k,n in cnt.items()) if v else "No verified documents."
    return {"user":user,"documents":docs,"summary":sm}

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)
