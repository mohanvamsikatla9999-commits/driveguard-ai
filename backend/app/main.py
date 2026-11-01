from datetime import datetime, timedelta, timezone
import base64
from threading import Lock
from collections import deque
from pathlib import Path
from typing import Generator

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic_settings import BaseSettings
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

class Settings(BaseSettings):
    database_url: str = "sqlite:///./driveguard.db"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:3000"
    model_config = ConfigDict(env_file="../.env", extra="ignore")

cfg = Settings()
def utcnow(): return datetime.now(timezone.utc).replace(tzinfo=None)
engine = create_engine(cfg.database_url, connect_args={"check_same_thread": False} if cfg.database_url.startswith("sqlite") else {}, pool_pre_ping=True)
DB = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class Base(DeclarativeBase): pass

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True)
    name: Mapped[str]=mapped_column(String(120))
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(20),default="user")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    sessions: Mapped[list["MonitorSession"]]=relationship(back_populates="user",cascade="all, delete-orphan")

class MonitorSession(Base):
    __tablename__="monitoring_sessions"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    started_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    ended_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    status: Mapped[str]=mapped_column(String(20),default="active")
    blinks: Mapped[int]=mapped_column(Integer,default=0)
    yawns: Mapped[int]=mapped_column(Integer,default=0)
    alerts: Mapped[int]=mapped_column(Integer,default=0)
    perclos_sum: Mapped[float]=mapped_column(Float,default=0)
    samples: Mapped[int]=mapped_column(Integer,default=0)
    user: Mapped[User]=relationship(back_populates="sessions")
    events: Mapped[list["Event"]]=relationship(back_populates="session",cascade="all, delete-orphan")

class Event(Base):
    __tablename__="detection_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    session_id: Mapped[int]=mapped_column(ForeignKey("monitoring_sessions.id",ondelete="CASCADE"),index=True)
    kind: Mapped[str]=mapped_column(String(40),index=True)
    severity: Mapped[str]=mapped_column(String(20))
    detail: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow,index=True)
    acknowledged: Mapped[bool]=mapped_column(Boolean,default=False)
    session: Mapped[MonitorSession]=relationship(back_populates="events")

class Preference(Base):
    __tablename__="user_preferences"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),unique=True,index=True)
    ear_threshold: Mapped[float]=mapped_column(Float,default=.21)
    mar_threshold: Mapped[float]=mapped_column(Float,default=.72)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

Base.metadata.create_all(engine)
def db() -> Generator[Session,None,None]:
    s=DB()
    try: yield s
    finally: s.close()
hashing=CryptContext(schemes=["argon2"],deprecated="auto")
oauth=OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def issue_token(user:User):
    return jwt.encode({"sub":str(user.id),"exp":datetime.now(timezone.utc)+timedelta(minutes=cfg.jwt_expire_minutes)},cfg.jwt_secret,algorithm="HS256")
def auth(token:str=Depends(oauth),s:Session=Depends(db)):
    try: uid=int(jwt.decode(token,cfg.jwt_secret,algorithms=["HS256"])["sub"])
    except (JWTError,ValueError,KeyError): raise HTTPException(401,"Invalid or expired session")
    user=s.get(User,uid)
    if not user: raise HTTPException(401,"Invalid or expired session")
    return user
class Register(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    email:EmailStr
    password:str=Field(min_length=10,max_length=128)
class Login(BaseModel): email:EmailStr; password:str
class FrameIn(BaseModel):
    session_id:int
    image:str=Field(min_length=32,max_length=6_000_000)
    ear_threshold:float=Field(default=.21,ge=.12,le=.35)
    mar_threshold:float=Field(default=.72,ge=.3,le=1.2)
    prolonged:bool=False
    blink:bool=False
    yawn_edge:bool=False
    alert_sent:bool=False
class SettingsIn(BaseModel):
    ear_threshold:float=Field(default=.21,ge=.12,le=.35)
    mar_threshold:float=Field(default=.72,ge=.3,le=1.2)

app=FastAPI(title="DRIVEGUARD AI",version="1.0",description="Local-first heuristic driver monitoring prototype")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in cfg.cors_origins.split(",")],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/register",status_code=201)
def register(data:Register,s:Session=Depends(db)):
    email=data.email.lower()
    if s.query(User).filter_by(email=email).first(): raise HTTPException(409,"Email already registered")
    u=User(name=data.name.strip(),email=email,password_hash=hashing.hash(data.password));s.add(u);s.commit();s.refresh(u)
    return {"access_token":issue_token(u),"token_type":"bearer","user":{"id":u.id,"name":u.name,"email":u.email}}
@app.post("/api/auth/login")
def login(data:Login,s:Session=Depends(db)):
    u=s.query(User).filter_by(email=data.email.lower()).first()
    if not u or not hashing.verify(data.password,u.password_hash): raise HTTPException(401,"Email or password is incorrect")
    return {"access_token":issue_token(u),"token_type":"bearer","user":{"id":u.id,"name":u.name,"email":u.email}}
@app.post("/api/auth/logout")
def logout(): return {"ok":True}
@app.get("/api/auth/me")
def me(u:User=Depends(auth)): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role}

def session_data(r:MonitorSession):
    duration=int(((r.ended_at or utcnow())-r.started_at).total_seconds())
    return {"id":r.id,"started_at":r.started_at.isoformat(),"ended_at":r.ended_at.isoformat() if r.ended_at else None,"status":r.status,"duration_seconds":duration,"blinks":r.blinks,"yawns":r.yawns,"alerts":r.alerts,"average_perclos":round(100*r.perclos_sum/max(r.samples,1),1)}
@app.post("/api/monitoring/start")
def start(u:User=Depends(auth),s:Session=Depends(db)):
    r=s.query(MonitorSession).filter_by(user_id=u.id,status="active").first()
    if not r: r=MonitorSession(user_id=u.id);s.add(r);s.commit();s.refresh(r)
    return {"session_id":r.id,"started_at":r.started_at.isoformat()}
@app.post("/api/monitoring/{sid}/stop")
def stop(sid:int,u:User=Depends(auth),s:Session=Depends(db)):
    r=s.query(MonitorSession).filter_by(id=sid,user_id=u.id).first()
    if not r: raise HTTPException(404,"Session not found")
    if r.status=="active": r.status="complete";r.ended_at=utcnow();PERCLOS.pop(r.id,None);s.commit()
    return session_data(r)
@app.get("/api/monitoring/status")
def monitoring_status(u:User=Depends(auth),s:Session=Depends(db)):
    r=s.query(MonitorSession).filter_by(user_id=u.id,status="active").first()
    return {"active":bool(r),"session":session_data(r) if r else None}

LEFT=[33,160,158,133,153,144];RIGHT=[362,385,387,263,373,380]
LANDMARKER=None
LANDMARKER_LAST_MS=0
MESH_LOCK=Lock()
PERCLOS: dict[int, deque] = {}
def distance(a,b): return float(np.linalg.norm(np.asarray(a)-np.asarray(b)))
def eye_aspect_ratio(p): return (distance(p[1],p[5])+distance(p[2],p[4]))/(2*max(distance(p[0],p[3]),1e-6))
def mouth_aspect_ratio(p): return (distance(p[1],p[7])+distance(p[2],p[6])+distance(p[3],p[5]))/(3*max(distance(p[0],p[4]),1e-6))

@app.post("/api/detection/process")
def process(body:FrameIn,u:User=Depends(auth),s:Session=Depends(db)):
    """Process transient JPEG frame; no image is saved."""
    r=s.query(MonitorSession).filter_by(id=body.session_id,user_id=u.id,status="active").first()
    if not r: raise HTTPException(404,"Active session not found")
    try:
        raw=base64.b64decode(body.image.split(",")[-1],validate=True)
        frame=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        if frame is None: raise ValueError()
    except Exception: raise HTTPException(400,"Invalid image frame")
    try:
        global LANDMARKER, LANDMARKER_LAST_MS
        import mediapipe as mp
        model=Path(__file__).parent/"models"/"face_landmarker.task"
        if not model.is_file(): raise FileNotFoundError("face_landmarker.task is missing")
        with MESH_LOCK:
            if LANDMARKER is None:
                options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=2,min_face_detection_confidence=.55,min_face_presence_confidence=.55,min_tracking_confidence=.5)
                LANDMARKER=mp.tasks.vision.FaceLandmarker.create_from_options(options)
            timestamp=max(int(utcnow().timestamp()*1000),LANDMARKER_LAST_MS+1);LANDMARKER_LAST_MS=timestamp
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            result=LANDMARKER.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),timestamp)
    except Exception as e: raise HTTPException(503,f"Landmark engine unavailable: {type(e).__name__}")
    h,w=frame.shape[:2]
    if not result.face_landmarks:
        return {"face_detected":False,"face_count":0,"status":"FACE NOT DETECTED","risk":0,"ear":None,"mar":None,"perclos":round(100*r.perclos_sum/max(r.samples,1),1),"blink":False,"yawn":False,"landmarks":[],"explanation":"Move into view and improve lighting."}
    points=[(p.x*w,p.y*h) for p in result.face_landmarks[0]]
    le=eye_aspect_ratio([points[i] for i in LEFT]);re=eye_aspect_ratio([points[i] for i in RIGHT]);ear=(le+re)/2
    mouth_ids=[61,82,13,312,291,317,14,87]
    mar=mouth_aspect_ratio([points[i] for i in mouth_ids])
    closed=ear<body.ear_threshold;r.samples+=1;r.perclos_sum+=int(closed)
    now=utcnow().timestamp(); window=PERCLOS.setdefault(r.id,deque()); window.append((now,int(closed)))
    while window and window[0][0]<now-30: window.popleft()
    blink=body.blink;yawn=mar>body.mar_threshold and body.yawn_edge
    if blink:r.blinks+=1
    if yawn:r.yawns+=1
    perclos=sum(sample[1] for sample in window)/max(len(window),1)
    prolonged=body.prolonged
    # Risk scoring: prolonged closure is critical (50pts), high PERCLOS (>0.15 = 35pts, >0.25 = 50pts), yawn (20pts)
    risk=min(100,(50 if prolonged else 0)+(50 if perclos>.25 else 35 if perclos>.15 else 0)+(20 if yawn else 0))
    state="MULTIPLE FACES DETECTED" if len(result.face_landmarks)>1 else "DROWSINESS ALERT" if prolonged or risk>=60 else "FATIGUE WARNING" if risk>=30 else "YAWNING" if yawn else "NORMAL BLINK" if blink else "ALERT"
    if len(result.face_landmarks)==1 and risk>=60 and not body.alert_sent:
        severity="critical" if risk>=80 or prolonged else "warning"
        s.add(Event(session_id=r.id,kind="drowsiness",severity=severity,detail=f"Drowsiness detected — risk score {risk}. {'Prolonged eye closure.' if prolonged else ''} {'PERCLOS {:.0f}%.'.format(perclos*100) if perclos>.15 else ''} {'Yawning detected.' if yawn else ''}".strip()));r.alerts+=1
    s.commit()
    lm=result.face_landmarks[0]
    detail="Multiple faces are present; measurements shown for the first detected face only." if len(result.face_landmarks)>1 else "60-second rolling fraction of valid frames below the eye-closure threshold; heuristic, not a validated probability."
    return {"face_detected":True,"face_count":len(result.face_landmarks),"status":state,"risk":risk,"ear":round(ear,3),"left_ear":round(le,3),"right_ear":round(re,3),"mar":round(mar,3),"perclos":round(100*perclos,1),"blink":blink,"yawn":yawn,"landmarks":[[round(p.x,4),round(p.y,4)] for p in lm],"explanation":detail}

@app.get("/api/sessions")
def sessions(u:User=Depends(auth),s:Session=Depends(db)):
    return [session_data(r) for r in s.query(MonitorSession).filter_by(user_id=u.id).order_by(MonitorSession.started_at.desc()).limit(100).all()]
@app.delete("/api/sessions/{sid}")
def delete_session(sid:int,u:User=Depends(auth),s:Session=Depends(db)):
    r=s.query(MonitorSession).filter_by(id=sid,user_id=u.id).first()
    if not r:raise HTTPException(404,"Session not found")
    PERCLOS.pop(r.id,None);s.delete(r);s.commit();return {"deleted":True}
@app.get("/api/alerts")
def alerts(u:User=Depends(auth),s:Session=Depends(db)):
    return [{"id":e.id,"session_id":e.session_id,"kind":e.kind,"severity":e.severity,"detail":e.detail,"created_at":e.created_at.isoformat(),"acknowledged":e.acknowledged} for e in s.query(Event).join(MonitorSession).filter(MonitorSession.user_id==u.id).order_by(Event.created_at.desc()).limit(100).all()]
@app.patch("/api/alerts/{eid}/acknowledge")
def acknowledge(eid:int,u:User=Depends(auth),s:Session=Depends(db)):
    e=s.query(Event).join(MonitorSession).filter(Event.id==eid,MonitorSession.user_id==u.id).first()
    if not e:raise HTTPException(404,"Alert not found")
    e.acknowledged=True;s.commit();return {"acknowledged":True}
@app.get("/api/analytics/overview")
def analytics(u:User=Depends(auth),s:Session=Depends(db)):
    rows=s.query(MonitorSession).filter_by(user_id=u.id).all()
    return {"session_count":len(rows),"total_minutes":round(sum(session_data(r)["duration_seconds"] for r in rows)/60,1),"blinks":sum(r.blinks for r in rows),"yawns":sum(r.yawns for r in rows),"alerts":sum(r.alerts for r in rows),"avg_perclos":round(sum(session_data(r)["average_perclos"] for r in rows)/max(len(rows),1),1)}

@app.get("/api/settings")
def get_settings(u:User=Depends(auth),s:Session=Depends(db)):
    p=s.query(Preference).filter_by(user_id=u.id).first()
    return {"ear_threshold":p.ear_threshold if p else .21,"mar_threshold":p.mar_threshold if p else .72}
@app.put("/api/settings")
def put_settings(body:SettingsIn,u:User=Depends(auth),s:Session=Depends(db)):
    p=s.query(Preference).filter_by(user_id=u.id).first()
    if not p:p=Preference(user_id=u.id);s.add(p)
    p.ear_threshold=body.ear_threshold;p.mar_threshold=body.mar_threshold;s.commit()
    return {"ear_threshold":p.ear_threshold,"mar_threshold":p.mar_threshold}
