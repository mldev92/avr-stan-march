#!/usr/bin/env python3
"""
AVR Dialer Service
Manages outbound call campaigns and initiates calls via Asterisk AMI
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Index, Boolean, Text
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

# Database setup (uses same database as trace service)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///./dialer.db" if os.getenv("DB_TYPE") == "sqlite" 
    else f"postgresql://{os.getenv('DB_USER', 'avr')}:{os.getenv('DB_PASSWORD', 'avr')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'avr_trace')}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class NumberDatabase(Base):
    __tablename__ = "number_database"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    email = Column(String)
    status = Column(String, default="pending", index=True)  # 'pending', 'called', 'answered', 'busy', 'no-answer', 'completed', 'failed'
    last_call_time = Column(DateTime)
    call_count = Column(Integer, default=0)
    campaign_id = Column(String, index=True)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DialerCampaign(Base):
    __tablename__ = "dialer_campaigns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="draft", index=True)  # 'draft', 'active', 'paused', 'completed'
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    max_calls_per_hour = Column(Integer, default=100)
    retry_count = Column(Integer, default=3)
    retry_delay = Column(Integer, default=300)  # seconds
    caller_id = Column(String)
    caller_name = Column(String)
    context = Column(String, default="outbound")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CampaignCall(Base):
    __tablename__ = "campaign_calls"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, nullable=False, index=True)
    number_id = Column(String, nullable=False, index=True)
    call_trace_id = Column(String)  # Reference to trace service
    attempt_number = Column(Integer, default=1)
    scheduled_time = Column(DateTime)
    actual_call_time = Column(DateTime)
    status = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_calls_per_hour: int = Field(default=100, ge=1, le=1000)
    retry_count: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=300, ge=60)  # minimum 60 seconds
    caller_id: Optional[str] = None
    caller_name: Optional[str] = None
    context: str = Field(default="outbound")

class NumberImport(BaseModel):
    campaign_id: str
    numbers: List[dict]  # [{"phone_number": "...", "name": "...", "email": "...", "metadata": {...}}]

class CallInitiate(BaseModel):
    campaign_id: str
    number_id: str

# FastAPI App
app = FastAPI(
    title="AVR Dialer Service",
    description="Outbound call campaign management for AVR",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
ami_url = os.getenv("AMI_URL", "http://avr-ami:6006")
trace_url = os.getenv("TRACE_URL", "http://avr-trace:6007")
max_concurrent_calls = int(os.getenv("MAX_CONCURRENT_CALLS", "10"))
calls_per_hour = int(os.getenv("CALLS_PER_HOUR", "100"))

# Active campaigns
active_campaigns = {}
campaign_tasks = {}

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def initiate_call_via_ami(
    phone_number: str,
    campaign_id: str,
    number_id: str,
    caller_id: str,
    caller_name: str,
    context: str = "outbound"
):
    """Initiate an outbound call via AMI service"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Format caller ID as expected by AMI service
            callerid_str = f"{caller_name} <{caller_id}>" if caller_name else caller_id
            
            # Use AMI service to originate call (matches avr-ami API format)
            response = await client.post(
                f"{ami_url}/originate",
                json={
                    "channel": f"PJSIP/{phone_number}@trunk",  # Adjust trunk name as needed
                    "exten": phone_number,
                    "context": context,
                    "priority": 1,
                    "callerid": callerid_str
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Call originated successfully: {result.get('message')}")
                
                # Generate a temporary UUID - actual UUID will come from Asterisk via AMI events
                # The trace service will update this when it receives AMI events
                temp_uuid = str(uuid.uuid4())
                
                # Notify trace service about the call initiation
                try:
                    await client.post(
                        f"{trace_url}/api/calls/start",
                        json={
                            "call_uuid": temp_uuid,
                            "direction": "outbound",
                            "caller_id": caller_id,
                            "called_number": phone_number,
                            "caller_name": caller_name,
                            "context": context,
                            "metadata": {
                                "campaign_id": campaign_id,
                                "number_id": number_id,
                                "status": "initiating"
                            }
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify trace service: {e}")
                
                return {"status": "success", "call_uuid": temp_uuid, "message": result.get("message")}
            else:
                logger.error(f"AMI originate failed: {response.status_code} - {response.text}")
                return {"status": "error", "message": response.text}
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        return {"status": "error", "message": str(e)}

async def run_campaign(campaign_id: str, db: Session):
    """Main campaign execution loop"""
    logger.info(f"Starting campaign {campaign_id}")
    
    while True:
        try:
            campaign = db.query(DialerCampaign).filter(
                DialerCampaign.id == campaign_id,
                DialerCampaign.status == "active"
            ).first()
            
            if not campaign:
                logger.info(f"Campaign {campaign_id} no longer active, stopping")
                break
            
            # Get pending numbers for this campaign
            numbers = db.query(NumberDatabase).filter(
                NumberDatabase.campaign_id == campaign_id,
                NumberDatabase.status == "pending"
            ).limit(campaign.max_calls_per_hour).all()
            
            if not numbers:
                logger.info(f"No pending numbers for campaign {campaign_id}")
                await asyncio.sleep(60)  # Wait 1 minute before checking again
                continue
            
            # Initiate calls
            for number in numbers:
                # Check rate limit
                if campaign.max_calls_per_hour > 0:
                    # Simple rate limiting - in production, use a proper rate limiter
                    await asyncio.sleep(3600 / campaign.max_calls_per_hour)
                
                # Create campaign call record
                campaign_call = CampaignCall(
                    campaign_id=campaign_id,
                    number_id=number.id,
                    scheduled_time=datetime.utcnow(),
                    status="initiating"
                )
                db.add(campaign_call)
                
                # Update number status
                number.status = "called"
                number.last_call_time = datetime.utcnow()
                number.call_count += 1
                db.commit()
                
                # Initiate call
                result = await initiate_call_via_ami(
                    phone_number=number.phone_number,
                    campaign_id=campaign_id,
                    number_id=number.id,
                    caller_id=campaign.caller_id or "unknown",
                    caller_name=campaign.caller_name or "AVR Agent",
                    context=campaign.context
                )
                
                if result.get("status") == "success":
                    campaign_call.actual_call_time = datetime.utcnow()
                    campaign_call.status = "initiated"
                    campaign_call.call_trace_id = result.get("call_uuid")
                else:
                    campaign_call.status = "failed"
                    number.status = "failed"
                    logger.error(f"Failed to initiate call to {number.phone_number}: {result.get('message')}")
                
                db.commit()
                
                # Wait between calls
                await asyncio.sleep(campaign.retry_delay)
            
            # Wait before next batch
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in campaign loop for {campaign_id}: {e}")
            await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AVR Dialer Service")
    logger.info(f"Database: {DATABASE_URL}")
    logger.info(f"AMI URL: {ami_url}")
    logger.info(f"Trace URL: {trace_url}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AVR Dialer Service")
    # Stop all campaign tasks
    for task in campaign_tasks.values():
        task.cancel()

app.router.lifespan_context = lifespan

# API Endpoints
@app.get("/")
async def root():
    return {
        "service": "AVR Dialer Service",
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

@app.post("/api/campaigns")
async def create_campaign(request: CampaignCreate, db: Session = Depends(get_db)):
    """Create a new campaign"""
    try:
        campaign = DialerCampaign(
            name=request.name,
            description=request.description,
            max_calls_per_hour=request.max_calls_per_hour,
            retry_count=request.retry_count,
            retry_delay=request.retry_delay,
            caller_id=request.caller_id,
            caller_name=request.caller_name,
            context=request.context,
            status="draft"
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
        logger.info(f"Created campaign: {campaign.name} ({campaign.id})")
        return {"status": "success", "campaign_id": campaign.id, "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status
        }}
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Get campaign details"""
    campaign = db.query(DialerCampaign).filter(DialerCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get statistics
    total_numbers = db.query(NumberDatabase).filter(
        NumberDatabase.campaign_id == campaign_id
    ).count()
    
    pending_numbers = db.query(NumberDatabase).filter(
        NumberDatabase.campaign_id == campaign_id,
        NumberDatabase.status == "pending"
    ).count()
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status,
        "max_calls_per_hour": campaign.max_calls_per_hour,
        "retry_count": campaign.retry_count,
        "retry_delay": campaign.retry_delay,
        "caller_id": campaign.caller_id,
        "caller_name": campaign.caller_name,
        "total_numbers": total_numbers,
        "pending_numbers": pending_numbers
    }

@app.get("/api/campaigns")
async def list_campaigns(db: Session = Depends(get_db)):
    """List all campaigns"""
    campaigns = db.query(DialerCampaign).order_by(DialerCampaign.created_at.desc()).all()
    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in campaigns
        ]
    }

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a campaign"""
    campaign = db.query(DialerCampaign).filter(DialerCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status == "active":
        return {"status": "already_active", "campaign_id": campaign_id}
    
    campaign.status = "active"
    campaign.start_time = datetime.utcnow()
    db.commit()
    
    # Start campaign task
    task = asyncio.create_task(run_campaign(campaign_id, db))
    campaign_tasks[campaign_id] = task
    
    logger.info(f"Started campaign: {campaign.name} ({campaign_id})")
    return {"status": "success", "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Pause a campaign"""
    campaign = db.query(DialerCampaign).filter(DialerCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "paused"
    db.commit()
    
    # Cancel campaign task
    if campaign_id in campaign_tasks:
        campaign_tasks[campaign_id].cancel()
        del campaign_tasks[campaign_id]
    
    logger.info(f"Paused campaign: {campaign.name} ({campaign_id})")
    return {"status": "success", "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Stop a campaign"""
    campaign = db.query(DialerCampaign).filter(DialerCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "completed"
    campaign.end_time = datetime.utcnow()
    db.commit()
    
    # Cancel campaign task
    if campaign_id in campaign_tasks:
        campaign_tasks[campaign_id].cancel()
        del campaign_tasks[campaign_id]
    
    logger.info(f"Stopped campaign: {campaign.name} ({campaign_id})")
    return {"status": "success", "campaign_id": campaign_id}

@app.post("/api/numbers/import")
async def import_numbers(request: NumberImport, db: Session = Depends(get_db)):
    """Import phone numbers for a campaign"""
    try:
        # Verify campaign exists
        campaign = db.query(DialerCampaign).filter(DialerCampaign.id == request.campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        imported = 0
        skipped = 0
        
        for number_data in request.numbers:
            phone_number = number_data.get("phone_number")
            if not phone_number:
                skipped += 1
                continue
            
            # Check if number already exists
            existing = db.query(NumberDatabase).filter(
                NumberDatabase.phone_number == phone_number,
                NumberDatabase.campaign_id == request.campaign_id
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            number = NumberDatabase(
                phone_number=phone_number,
                name=number_data.get("name"),
                email=number_data.get("email"),
                campaign_id=request.campaign_id,
                status="pending",
                metadata=number_data.get("metadata", {})
            )
            db.add(number)
            imported += 1
        
        db.commit()
        logger.info(f"Imported {imported} numbers for campaign {request.campaign_id}")
        return {
            "status": "success",
            "imported": imported,
            "skipped": skipped
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing numbers: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns/{campaign_id}/numbers")
async def get_campaign_numbers(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get numbers for a campaign"""
    query = db.query(NumberDatabase).filter(NumberDatabase.campaign_id == campaign_id)
    
    if status:
        query = query.filter(NumberDatabase.status == status)
    
    total = query.count()
    numbers = query.order_by(NumberDatabase.created_at.desc()).limit(limit).offset(offset).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "numbers": [
            {
                "id": n.id,
                "phone_number": n.phone_number,
                "name": n.name,
                "email": n.email,
                "status": n.status,
                "call_count": n.call_count,
                "last_call_time": n.last_call_time.isoformat() if n.last_call_time else None
            }
            for n in numbers
        ]
    }

@app.post("/api/calls/initiate")
async def initiate_call(request: CallInitiate, db: Session = Depends(get_db)):
    """Manually initiate a call"""
    try:
        # Get campaign and number
        campaign = db.query(DialerCampaign).filter(DialerCampaign.id == request.campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        number = db.query(NumberDatabase).filter(NumberDatabase.id == request.number_id).first()
        if not number:
            raise HTTPException(status_code=404, detail="Number not found")
        
        # Initiate call
        result = await initiate_call_via_ami(
            phone_number=number.phone_number,
            campaign_id=request.campaign_id,
            number_id=request.number_id,
            caller_id=campaign.caller_id or "unknown",
            caller_name=campaign.caller_name or "AVR Agent",
            context=campaign.context
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "6008"))
    uvicorn.run(app, host="0.0.0.0", port=port)

