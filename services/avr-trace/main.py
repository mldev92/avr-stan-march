#!/usr/bin/env python3
"""
AVR Trace Service
Tracks and logs all calls (incoming and outgoing) in the AVR system
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Index, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import httpx
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///./trace.db" if os.getenv("DB_TYPE") == "sqlite" 
    else f"postgresql://{os.getenv('DB_USER', 'avr')}:{os.getenv('DB_PASSWORD', 'avr')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'avr_trace')}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class CallTrace(Base):
    __tablename__ = "call_traces"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    call_uuid = Column(String, unique=True, nullable=False, index=True)
    direction = Column(String, nullable=False, index=True)  # 'inbound' or 'outbound'
    caller_id = Column(String)
    called_number = Column(String, index=True)
    caller_name = Column(String)
    start_time = Column(DateTime, nullable=False, index=True)
    answer_time = Column(DateTime)
    end_time = Column(DateTime)
    duration = Column(Integer)  # in seconds
    status = Column(String, nullable=False, index=True)  # 'ringing', 'answered', 'busy', 'no-answer', 'failed', 'completed'
    hangup_cause = Column(String)
    channel = Column(String)
    context = Column(String)
    extension = Column(String)
    trunk = Column(String)
    recording_url = Column(Text)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CallEvent(Base):
    __tablename__ = "call_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    call_trace_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    event_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class CallStartRequest(BaseModel):
    call_uuid: str
    direction: str = Field(..., pattern="^(inbound|outbound)$")
    caller_id: Optional[str] = None
    called_number: str
    caller_name: Optional[str] = None
    channel: Optional[str] = None
    context: Optional[str] = None
    extension: Optional[str] = None
    trunk: Optional[str] = None
    metadata: Optional[dict] = {}

class CallUpdateRequest(BaseModel):
    status: Optional[str] = None
    answer_time: Optional[datetime] = None
    metadata: Optional[dict] = None

class CallEndRequest(BaseModel):
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    hangup_cause: Optional[str] = None
    status: Optional[str] = None
    recording_url: Optional[str] = None

class CallEventRequest(BaseModel):
    event_type: str
    event_time: Optional[datetime] = None
    event_data: Optional[dict] = {}

# FastAPI App
app = FastAPI(
    title="AVR Trace Service",
    description="Call tracking and logging service for AVR",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# AMI Client for listening to events
ami_url = os.getenv("AMI_URL", "http://avr-ami:6006")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AVR Trace Service")
    logger.info(f"Database: {DATABASE_URL}")
    logger.info(f"AMI URL: {ami_url}")
    logger.info("Trace service ready - waiting for call events via API or webhooks")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AVR Trace Service")

app.router.lifespan_context = lifespan

# API Endpoints
@app.get("/")
async def root():
    return {
        "service": "AVR Trace Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/api/calls/start")
async def start_call(request: CallStartRequest, db: Session = Depends(get_db)):
    """Start tracking a new call"""
    try:
        # Check if call already exists
        existing = db.query(CallTrace).filter(CallTrace.call_uuid == request.call_uuid).first()
        if existing:
            logger.warning(f"Call {request.call_uuid} already exists, updating")
            existing.direction = request.direction
            existing.caller_id = request.caller_id
            existing.called_number = request.called_number
            existing.caller_name = request.caller_name
            existing.channel = request.channel
            existing.context = request.context
            existing.extension = request.extension
            existing.status = "ringing"
            existing.metadata = request.metadata or {}
            existing.updated_at = datetime.utcnow()
            db.commit()
            return {"status": "updated", "call_uuid": request.call_uuid}
        
        call_trace = CallTrace(
            call_uuid=request.call_uuid,
            direction=request.direction,
            caller_id=request.caller_id,
            called_number=request.called_number,
            caller_name=request.caller_name,
            channel=request.channel,
            context=request.context,
            extension=request.extension,
            trunk=request.trunk,
            start_time=datetime.utcnow(),
            status="ringing",
            metadata=request.metadata or {}
        )
        db.add(call_trace)
        db.commit()
        db.refresh(call_trace)
        
        logger.info(f"Started tracking call {request.call_uuid} ({request.direction})")
        return {"status": "success", "call_uuid": request.call_uuid, "id": call_trace.id}
    except Exception as e:
        logger.error(f"Error starting call tracking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/calls/{call_uuid}")
async def update_call(call_uuid: str, request: CallUpdateRequest, db: Session = Depends(get_db)):
    """Update call information"""
    try:
        call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
        if not call_trace:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if request.status:
            call_trace.status = request.status
        if request.answer_time:
            call_trace.answer_time = request.answer_time
        if request.metadata:
            if call_trace.metadata:
                call_trace.metadata.update(request.metadata)
            else:
                call_trace.metadata = request.metadata
        call_trace.updated_at = datetime.utcnow()
        
        db.commit()
        return {"status": "success", "call_uuid": call_uuid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating call: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calls/{call_uuid}/end")
async def end_call(call_uuid: str, request: CallEndRequest, db: Session = Depends(get_db)):
    """End call tracking"""
    try:
        call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
        if not call_trace:
            raise HTTPException(status_code=404, detail="Call not found")
        
        end_time = request.end_time or datetime.utcnow()
        call_trace.end_time = end_time
        
        if request.duration is not None:
            call_trace.duration = request.duration
        elif call_trace.start_time:
            call_trace.duration = int((end_time - call_trace.start_time).total_seconds())
        
        if request.hangup_cause:
            call_trace.hangup_cause = request.hangup_cause
        
        if request.status:
            call_trace.status = request.status
        elif not call_trace.status or call_trace.status == "ringing":
            call_trace.status = "completed" if request.hangup_cause == "16" else "failed"
        
        if request.recording_url:
            call_trace.recording_url = request.recording_url
        
        call_trace.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Ended tracking call {call_uuid} (duration: {call_trace.duration}s, status: {call_trace.status})")
        return {"status": "success", "call_uuid": call_uuid, "duration": call_trace.duration}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending call: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/calls/{call_uuid}")
async def get_call(call_uuid: str, db: Session = Depends(get_db)):
    """Get call details"""
    call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
    if not call_trace:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        "id": call_trace.id,
        "call_uuid": call_trace.call_uuid,
        "direction": call_trace.direction,
        "caller_id": call_trace.caller_id,
        "called_number": call_trace.called_number,
        "caller_name": call_trace.caller_name,
        "start_time": call_trace.start_time.isoformat() if call_trace.start_time else None,
        "answer_time": call_trace.answer_time.isoformat() if call_trace.answer_time else None,
        "end_time": call_trace.end_time.isoformat() if call_trace.end_time else None,
        "duration": call_trace.duration,
        "status": call_trace.status,
        "hangup_cause": call_trace.hangup_cause,
        "channel": call_trace.channel,
        "context": call_trace.context,
        "extension": call_trace.extension,
        "recording_url": call_trace.recording_url,
        "metadata": call_trace.metadata
    }

@app.get("/api/calls")
async def list_calls(
    direction: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List calls with filters"""
    query = db.query(CallTrace)
    
    if direction:
        query = query.filter(CallTrace.direction == direction)
    if status:
        query = query.filter(CallTrace.status == status)
    if start_date:
        query = query.filter(CallTrace.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(CallTrace.start_time <= datetime.fromisoformat(end_date))
    
    total = query.count()
    calls = query.order_by(CallTrace.start_time.desc()).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "calls": [
            {
                "call_uuid": c.call_uuid,
                "direction": c.direction,
                "caller_id": c.caller_id,
                "called_number": c.called_number,
                "start_time": c.start_time.isoformat() if c.start_time else None,
                "duration": c.duration,
                "status": c.status
            }
            for c in calls
        ]
    }

@app.post("/api/calls/{call_uuid}/events")
async def log_event(call_uuid: str, request: CallEventRequest, db: Session = Depends(get_db)):
    """Log a call event"""
    try:
        # Verify call exists
        call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
        if not call_trace:
            raise HTTPException(status_code=404, detail="Call not found")
        
        event = CallEvent(
            call_trace_id=call_trace.id,
            event_type=request.event_type,
            event_time=request.event_time or datetime.utcnow(),
            event_data=request.event_data or {}
        )
        db.add(event)
        db.commit()
        
        logger.info(f"Logged event {request.event_type} for call {call_uuid}")
        return {"status": "success", "event_id": event.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging event: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/webhooks/call-event")
async def handle_webhook(request: dict, db: Session = Depends(get_db)):
    """Handle webhook events from AVR Core or other services"""
    try:
        event_type = request.get("type")
        call_uuid = request.get("uuid")
        payload = request.get("payload", {})
        timestamp = request.get("timestamp")
        
        if not call_uuid:
            raise HTTPException(status_code=400, detail="UUID is required")
        
        logger.info(f"Received webhook: {event_type} for call {call_uuid}")
        
        if event_type == "call_start" or event_type == "start":
            # Start or update call tracking
            call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
            
            if not call_trace:
                # Create new call record
                call_trace = CallTrace(
                    call_uuid=call_uuid,
                    direction=payload.get("direction", "inbound"),
                    caller_id=payload.get("caller_id"),
                    called_number=payload.get("called_number"),
                    caller_name=payload.get("caller_name"),
                    channel=payload.get("channel"),
                    context=payload.get("context"),
                    start_time=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
                    status="ringing",
                    metadata=payload
                )
                db.add(call_trace)
            else:
                # Update existing call
                if payload.get("status"):
                    call_trace.status = payload.get("status")
                if payload.get("answer_time"):
                    call_trace.answer_time = datetime.fromisoformat(payload.get("answer_time"))
                call_trace.updated_at = datetime.utcnow()
            
            db.commit()
            return {"status": "success", "call_uuid": call_uuid}
        
        elif event_type == "call_end" or event_type == "end":
            # End call tracking
            call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
            if not call_trace:
                logger.warning(f"Call {call_uuid} not found for end event")
                return {"status": "warning", "message": "Call not found"}
            
            end_time = datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow()
            call_trace.end_time = end_time
            
            if call_trace.start_time:
                call_trace.duration = int((end_time - call_trace.start_time).total_seconds())
            
            if payload.get("status"):
                call_trace.status = payload.get("status")
            elif not call_trace.status or call_trace.status == "ringing":
                call_trace.status = "completed"
            
            if payload.get("hangup_cause"):
                call_trace.hangup_cause = payload.get("hangup_cause")
            
            call_trace.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Ended tracking call {call_uuid} (duration: {call_trace.duration}s)")
            return {"status": "success", "call_uuid": call_uuid}
        
        elif event_type == "call_event" or event_type == "event":
            # Log a call event
            call_trace = db.query(CallTrace).filter(CallTrace.call_uuid == call_uuid).first()
            if call_trace:
                event = CallEvent(
                    call_trace_id=call_trace.id,
                    event_type=payload.get("event_type", "unknown"),
                    event_time=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
                    event_data=payload
                )
                db.add(event)
                db.commit()
                return {"status": "success", "event_id": event.id}
            else:
                return {"status": "warning", "message": "Call not found"}
        
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
            return {"status": "ignored", "message": f"Unknown event type: {event_type}"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "6007"))
    uvicorn.run(app, host="0.0.0.0", port=port)

