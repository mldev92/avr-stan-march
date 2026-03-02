# Trace Service Analysis & Dialer Integration

## Executive Summary

This document analyzes the design and implementation of a **Trace Service** for the AVR (Agent Voice Response) platform that can handle both **incoming** and **outgoing** calls, with integration to a dialer service based on a number database.

## 1. Trace Service Architecture

### 1.1 Purpose

The Trace Service is a centralized call tracking and logging system that:
- Records all call events (incoming and outgoing)
- Stores call metadata (caller ID, called number, duration, status)
- Tracks call flow through the AVR system
- Provides analytics and reporting capabilities
- Enables integration with dialer services for outbound campaigns

### 1.2 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Trace Service                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Event Listener│  │  Data Store  │  │  API Server  │   │
│  │               │  │              │  │              │   │
│  │ - AMI Events  │  │ - PostgreSQL │  │ - REST API   │   │
│  │ - ARI Events  │  │ - SQLite     │  │ - Webhooks   │   │
│  │ - Core Events│  │ - MongoDB    │  │ - GraphQL    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ Asterisk│         │ AVR Core│         │ Dialer  │
    │   AMI   │         │         │         │ Service │
    └─────────┘         └─────────┘         └─────────┘
```

### 1.3 Data Model

#### Call Record Schema

```sql
CREATE TABLE call_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_uuid VARCHAR(255) UNIQUE NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    caller_id VARCHAR(50),
    called_number VARCHAR(50),
    caller_name VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    answer_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER, -- in seconds
    status VARCHAR(20) NOT NULL, -- 'ringing', 'answered', 'busy', 'no-answer', 'failed', 'completed'
    hangup_cause VARCHAR(50),
    channel VARCHAR(255),
    context VARCHAR(100),
    extension VARCHAR(50),
    trunk VARCHAR(100),
    recording_url TEXT,
    metadata JSONB, -- Additional flexible data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_trace_id UUID REFERENCES call_traces(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'NewChannel', 'DialBegin', 'DialEnd', 'Hangup', etc.
    event_time TIMESTAMP NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_call_traces_uuid ON call_traces(call_uuid);
CREATE INDEX idx_call_traces_direction ON call_traces(direction);
CREATE INDEX idx_call_traces_start_time ON call_traces(start_time);
CREATE INDEX idx_call_events_trace_id ON call_events(call_trace_id);
```

#### Number Database Schema (for Dialer)

```sql
CREATE TABLE number_database (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'called', 'answered', 'busy', 'no-answer', 'completed', 'failed'
    last_call_time TIMESTAMP,
    call_count INTEGER DEFAULT 0,
    campaign_id UUID,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dialer_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft', -- 'draft', 'active', 'paused', 'completed'
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    max_calls_per_hour INTEGER,
    retry_count INTEGER DEFAULT 3,
    retry_delay INTEGER DEFAULT 300, -- seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE campaign_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES dialer_campaigns(id),
    number_id UUID REFERENCES number_database(id),
    call_trace_id UUID REFERENCES call_traces(id),
    attempt_number INTEGER DEFAULT 1,
    scheduled_time TIMESTAMP,
    actual_call_time TIMESTAMP,
    status VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_number_database_status ON number_database(status);
CREATE INDEX idx_number_database_campaign ON number_database(campaign_id);
CREATE INDEX idx_campaign_calls_campaign ON campaign_calls(campaign_id);
```

## 2. Trace Service for Incoming Calls

### 2.1 Current Flow (Incoming)

```
Incoming Call → Asterisk → AVR Core → ASR/LLM/TTS → Response
     │              │           │
     └──────────────┴───────────┘
              │
         AMI Events
              │
         Trace Service (to be added)
```

### 2.2 Integration Points

#### 2.2.1 AMI Event Subscription

The Trace Service subscribes to Asterisk AMI events:

```python
# Example AMI event types to track
AMI_EVENTS = [
    'Newchannel',      # New call initiated
    'Newstate',        # Channel state change
    'DialBegin',       # Dial attempt started
    'DialEnd',         # Dial attempt ended
    'BridgeEnter',     # Channel entered bridge
    'BridgeLeave',     # Channel left bridge
    'Hangup',          # Call ended
    'UserEvent',       # Custom events from dialplan
]
```

#### 2.2.2 AVR Core Integration

AVR Core can send custom events to Trace Service:

```javascript
// Example: AVR Core sending call start event
POST http://avr-trace:6007/api/calls/start
{
    "call_uuid": "uuid-from-asterisk",
    "direction": "inbound",
    "caller_id": "+1234567890",
    "called_number": "5001",
    "channel": "PJSIP/1000-00000001",
    "context": "demo"
}
```

## 3. Trace Service for Outgoing Calls (Dialer Integration)

### 3.1 Dialer Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Dialer Service                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Number DB    │  │ Campaign     │  │ Call         │     │
│  │ Manager      │  │ Manager      │  │ Scheduler    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ Number  │         │ Campaign│         │ Asterisk│
    │Database │         │ Config  │         │   AMI   │
    └─────────┘         └─────────┘         └─────────┘
```

### 3.2 Outbound Call Flow

```
Dialer Service → Number DB → Campaign → Asterisk AMI → Outbound Call
     │              │            │            │              │
     │              │            │            │              ▼
     │              │            │            │         AVR Core
     │              │            │            │              │
     └──────────────┴────────────┴────────────┴──────────────┘
                              │
                         Trace Service
```

### 3.3 Implementation Steps

#### Step 1: Create Trace Service Container

Create `docker-compose-trace.yml`:

```yaml
services:
  avr-trace:
    image: agentvoiceresponse/avr-trace  # or build from source
    platform: linux/x86_64
    container_name: avr-trace
    restart: always
    environment:
      - PORT=6007
      - DB_TYPE=postgresql  # or sqlite, mongodb
      - DB_HOST=avr-trace-db
      - DB_PORT=5432
      - DB_NAME=avr_trace
      - DB_USER=avr
      - DB_PASSWORD=${TRACE_DB_PASSWORD:-avr}
      - AMI_URL=http://avr-ami:6006
      - CORE_URL=http://avr-core:5001
    ports:
      - 6007:6007
    networks:
      - avr
    depends_on:
      - avr-trace-db

  avr-trace-db:
    image: postgres:15-alpine
    container_name: avr-trace-db
    restart: always
    environment:
      - POSTGRES_DB=avr_trace
      - POSTGRES_USER=avr
      - POSTGRES_PASSWORD=${TRACE_DB_PASSWORD:-avr}
    volumes:
      - ./trace-data:/var/lib/postgresql/data
    networks:
      - avr
```

#### Step 2: Dialer Service Implementation

Create `docker-compose-dialer.yml`:

```yaml
services:
  avr-dialer:
    image: agentvoiceresponse/avr-dialer  # or build from source
    platform: linux/x86_64
    container_name: avr-dialer
    restart: always
    environment:
      - PORT=6008
      - DB_TYPE=postgresql
      - DB_HOST=avr-trace-db
      - DB_PORT=5432
      - DB_NAME=avr_trace
      - DB_USER=avr
      - DB_PASSWORD=${TRACE_DB_PASSWORD:-avr}
      - AMI_URL=http://avr-ami:6006
      - TRACE_URL=http://avr-trace:6007
      - MAX_CONCURRENT_CALLS=10
      - CALLS_PER_HOUR=100
    ports:
      - 6008:6008
    networks:
      - avr
    depends_on:
      - avr-trace-db
      - avr-trace
```

#### Step 3: Asterisk Dialplan for Outbound Calls

Update `extensions.conf`:

```ini
[outbound]
; Outbound dialing context
exten => _X.,1,NoOp(Outbound call to ${EXTEN})
 same => n,Set(UUID=${SHELL(uuidgen | tr -d '\n')})
 same => n,Set(CALLERID(num)=${CALLERID_NUM})
 same => n,Set(CALLERID(name)=${CALLERID_NAME})
 same => n,UserEvent(CallStart,Direction: outbound,CallUUID: ${UUID},CalledNumber: ${EXTEN})
 same => n,Dial(PJSIP/${EXTEN}@trunk,30,tT)
 same => n,GotoIf($["${DIALSTATUS}" = "ANSWER"]?answered:notanswered)
 
answered:
 same => n,NoOp(Call answered)
 same => n,Set(UUID=${SHELL(uuidgen | tr -d '\n')})
 same => n,UserEvent(CallAnswered,CallUUID: ${UUID})
 same => n,GoSub(avr,s,1(avr-core:5001))
 same => n,Hangup()

notanswered:
 same => n,NoOp(Call not answered: ${DIALSTATUS})
 same => n,UserEvent(CallNotAnswered,CallUUID: ${UUID},Status: ${DIALSTATUS})
 same => n,Hangup()
```

## 4. API Endpoints

### 4.1 Trace Service API

#### Call Tracking

```http
# Start tracking a call
POST /api/calls/start
Content-Type: application/json

{
    "call_uuid": "uuid-string",
    "direction": "inbound" | "outbound",
    "caller_id": "+1234567890",
    "called_number": "5001",
    "channel": "PJSIP/1000-00000001",
    "context": "demo",
    "metadata": {}
}

# Update call status
PATCH /api/calls/{call_uuid}
Content-Type: application/json

{
    "status": "answered",
    "answer_time": "2024-01-01T12:00:00Z",
    "metadata": {}
}

# End call tracking
POST /api/calls/{call_uuid}/end
Content-Type: application/json

{
    "end_time": "2024-01-01T12:05:00Z",
    "duration": 300,
    "hangup_cause": "NORMAL_CLEARING",
    "status": "completed"
}

# Get call details
GET /api/calls/{call_uuid}

# List calls with filters
GET /api/calls?direction=outbound&status=completed&start_date=2024-01-01&end_date=2024-01-31
```

#### Event Logging

```http
# Log call event
POST /api/calls/{call_uuid}/events
Content-Type: application/json

{
    "event_type": "DialBegin",
    "event_time": "2024-01-01T12:00:00Z",
    "event_data": {
        "channel": "PJSIP/1000-00000001",
        "destination": "+1234567890"
    }
}
```

### 4.2 Dialer Service API

#### Campaign Management

```http
# Create campaign
POST /api/campaigns
Content-Type: application/json

{
    "name": "Q1 Sales Campaign",
    "description": "First quarter sales outreach",
    "max_calls_per_hour": 100,
    "retry_count": 3,
    "retry_delay": 300
}

# Start campaign
POST /api/campaigns/{campaign_id}/start

# Pause campaign
POST /api/campaigns/{campaign_id}/pause

# Stop campaign
POST /api/campaigns/{campaign_id}/stop
```

#### Number Database Management

```http
# Import numbers
POST /api/numbers/import
Content-Type: application/json

{
    "campaign_id": "uuid",
    "numbers": [
        {
            "phone_number": "+1234567890",
            "name": "John Doe",
            "email": "john@example.com",
            "metadata": {}
        }
    ]
}

# Get numbers for campaign
GET /api/campaigns/{campaign_id}/numbers?status=pending

# Update number status
PATCH /api/numbers/{number_id}
Content-Type: application/json

{
    "status": "called",
    "last_call_time": "2024-01-01T12:00:00Z"
}
```

#### Call Initiation

```http
# Initiate outbound call
POST /api/calls/initiate
Content-Type: application/json

{
    "campaign_id": "uuid",
    "number_id": "uuid",
    "caller_id": "+1987654321",
    "caller_name": "Sales Team",
    "context": "outbound",
    "extension": "+1234567890"
}
```

## 5. Implementation Example: Python Trace Service

### 5.1 Basic Structure

```python
# avr-trace/main.py
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from datetime import datetime
import uuid
import httpx

app = FastAPI()
Base = declarative_base()

# Database models
class CallTrace(Base):
    __tablename__ = "call_traces"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    call_uuid = Column(String, unique=True, nullable=False)
    direction = Column(String, nullable=False)
    caller_id = Column(String)
    called_number = Column(String)
    start_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False)
    metadata = Column(JSON)

# Pydantic models
class CallStartRequest(BaseModel):
    call_uuid: str
    direction: str
    caller_id: str = None
    called_number: str
    channel: str = None
    context: str = None
    metadata: dict = {}

class CallEndRequest(BaseModel):
    end_time: datetime
    duration: int
    hangup_cause: str
    status: str

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trace.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

@app.post("/api/calls/start")
async def start_call(request: CallStartRequest):
    db = SessionLocal()
    try:
        call_trace = CallTrace(
            call_uuid=request.call_uuid,
            direction=request.direction,
            caller_id=request.caller_id,
            called_number=request.called_number,
            start_time=datetime.utcnow(),
            status="ringing",
            metadata=request.metadata
        )
        db.add(call_trace)
        db.commit()
        return {"status": "success", "call_uuid": request.call_uuid}
    finally:
        db.close()

@app.post("/api/calls/{call_uuid}/end")
async def end_call(call_uuid: str, request: CallEndRequest):
    db = SessionLocal()
    try:
        call_trace = db.query(CallTrace).filter(
            CallTrace.call_uuid == call_uuid
        ).first()
        if not call_trace:
            raise HTTPException(status_code=404, detail="Call not found")
        
        call_trace.end_time = request.end_time
        call_trace.duration = request.duration
        call_trace.status = request.status
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.get("/api/calls/{call_uuid}")
async def get_call(call_uuid: str):
    db = SessionLocal()
    try:
        call_trace = db.query(CallTrace).filter(
            CallTrace.call_uuid == call_uuid
        ).first()
        if not call_trace:
            raise HTTPException(status_code=404, detail="Call not found")
        return call_trace
    finally:
        db.close()
```

### 5.2 AMI Event Listener

```python
# avr-trace/ami_listener.py
import asyncio
import httpx
from asterisk.ami import AMIClient, AMIClientAdapter
from asterisk.ami import SimpleAction

class AMIEventListener:
    def __init__(self, ami_host, ami_port, ami_username, ami_password, trace_url):
        self.ami_host = ami_host
        self.ami_port = ami_port
        self.ami_username = ami_username
        self.ami_password = ami_password
        self.trace_url = trace_url
        self.client = None
        
    async def connect(self):
        self.client = AMIClient(address=self.ami_host, port=self.ami_port)
        future = self.client.login(username=self.ami_username, secret=self.ami_password)
        if future.response.is_error():
            raise Exception("AMI login failed")
        
        # Subscribe to events
        action = SimpleAction(
            'Events',
            EventMask='on'
        )
        self.client.send_action(action)
        
    def on_event(self, event):
        """Handle AMI events"""
        event_name = event.name
        
        if event_name == 'Newchannel':
            self.handle_new_channel(event)
        elif event_name == 'Hangup':
            self.handle_hangup(event)
        elif event_name == 'DialBegin':
            self.handle_dial_begin(event)
        elif event_name == 'DialEnd':
            self.handle_dial_end(event)
            
    async def handle_new_channel(self, event):
        """Handle new channel event"""
        call_uuid = event.get('Uniqueid')
        direction = 'inbound' if event.get('Context') != 'outbound' else 'outbound'
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.trace_url}/api/calls/start",
                json={
                    "call_uuid": call_uuid,
                    "direction": direction,
                    "caller_id": event.get('CallerIDNum'),
                    "called_number": event.get('Exten'),
                    "channel": event.get('Channel'),
                    "context": event.get('Context')
                }
            )
    
    async def handle_hangup(self, event):
        """Handle hangup event"""
        call_uuid = event.get('Uniqueid')
        duration = int(event.get('Duration', 0))
        hangup_cause = event.get('Cause')
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.trace_url}/api/calls/{call_uuid}/end",
                json={
                    "end_time": datetime.utcnow().isoformat(),
                    "duration": duration,
                    "hangup_cause": hangup_cause,
                    "status": "completed" if hangup_cause == "16" else "failed"
                }
            )
```

## 6. Dialer Service Implementation

### 6.1 Campaign Scheduler

```python
# avr-dialer/scheduler.py
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import NumberDatabase, Campaign, CampaignCall

class DialerScheduler:
    def __init__(self, db: Session, ami_client, trace_url):
        self.db = db
        self.ami_client = ami_client
        self.trace_url = trace_url
        self.running = False
        
    async def start_campaign(self, campaign_id: str):
        """Start a dialer campaign"""
        campaign = self.db.query(Campaign).filter(
            Campaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise ValueError("Campaign not found")
        
        campaign.status = "active"
        campaign.start_time = datetime.utcnow()
        self.db.commit()
        
        self.running = True
        asyncio.create_task(self.run_campaign(campaign_id))
        
    async def run_campaign(self, campaign_id: str):
        """Main campaign loop"""
        while self.running:
            # Get pending numbers
            numbers = self.db.query(NumberDatabase).filter(
                NumberDatabase.campaign_id == campaign_id,
                NumberDatabase.status == "pending"
            ).limit(campaign.max_calls_per_hour).all()
            
            # Initiate calls
            for number in numbers:
                await self.initiate_call(campaign_id, number.id)
                await asyncio.sleep(campaign.retry_delay)
            
            # Wait before next batch
            await asyncio.sleep(3600)  # 1 hour
            
    async def initiate_call(self, campaign_id: str, number_id: str):
        """Initiate an outbound call"""
        number = self.db.query(NumberDatabase).filter(
            NumberDatabase.id == number_id
        ).first()
        
        campaign = self.db.query(Campaign).filter(
            Campaign.id == campaign_id
        ).first()
        
        # Use AMI to originate call
        action = SimpleAction(
            'Originate',
            Channel=f"PJSIP/{number.phone_number}@trunk",
            Context="outbound",
            Exten=number.phone_number,
            Priority=1,
            CallerID=f"{campaign.caller_id} <{campaign.caller_name}>",
            Variable=f"CampaignID={campaign_id},NumberID={number_id}"
        )
        
        response = self.ami_client.send_action(action)
        
        # Create campaign call record
        campaign_call = CampaignCall(
            campaign_id=campaign_id,
            number_id=number_id,
            scheduled_time=datetime.utcnow(),
            status="initiated"
        )
        self.db.add(campaign_call)
        
        # Update number status
        number.status = "called"
        number.last_call_time = datetime.utcnow()
        number.call_count += 1
        self.db.commit()
```

## 7. Integration Checklist

### 7.1 Trace Service Setup

- [ ] Create Trace Service container
- [ ] Set up database (PostgreSQL/SQLite)
- [ ] Implement AMI event listener
- [ ] Create REST API endpoints
- [ ] Add webhook support for AVR Core
- [ ] Implement call event logging
- [ ] Add call analytics endpoints

### 7.2 Dialer Service Setup

- [ ] Create Dialer Service container
- [ ] Implement number database schema
- [ ] Create campaign management API
- [ ] Implement call scheduler
- [ ] Add rate limiting (calls per hour)
- [ ] Implement retry logic
- [ ] Add call result tracking

### 7.3 Asterisk Configuration

- [ ] Update extensions.conf for outbound context
- [ ] Configure PJSIP trunk for outbound calls
- [ ] Set up caller ID configuration
- [ ] Enable AMI event subscriptions
- [ ] Test outbound call flow

### 7.4 AVR Core Integration

- [ ] Add trace service URL to AVR Core config
- [ ] Implement call start event sending
- [ ] Implement call end event sending
- [ ] Add metadata passing to trace service

## 8. Testing

### 8.1 Test Incoming Call Tracking

```bash
# 1. Start services
docker-compose -f docker-compose-trace.yml up -d

# 2. Make incoming call via SIP client
# 3. Check trace service logs
docker logs avr-trace

# 4. Query call record
curl http://localhost:6007/api/calls/{call_uuid}
```

### 8.2 Test Outgoing Call Tracking

```bash
# 1. Start dialer service
docker-compose -f docker-compose-dialer.yml up -d

# 2. Create campaign
curl -X POST http://localhost:6008/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Campaign", "max_calls_per_hour": 10}'

# 3. Import numbers
curl -X POST http://localhost:6008/api/numbers/import \
  -H "Content-Type: application/json" \
  -d '{"campaign_id": "...", "numbers": [...]}'

# 4. Start campaign
curl -X POST http://localhost:6008/api/campaigns/{id}/start

# 5. Monitor calls
curl http://localhost:6007/api/calls?direction=outbound
```

## 9. Best Practices

1. **Database Indexing**: Ensure proper indexes on frequently queried fields
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Error Handling**: Robust error handling for AMI connection failures
4. **Logging**: Comprehensive logging for debugging and auditing
5. **Monitoring**: Set up monitoring for service health
6. **Backup**: Regular database backups for call records
7. **Privacy**: Ensure compliance with data protection regulations (GDPR, etc.)

## 10. Future Enhancements

- Real-time call monitoring dashboard
- Advanced analytics and reporting
- Integration with CRM systems
- Call recording storage
- Sentiment analysis integration
- Automated callback scheduling
- Multi-tenant support
- Webhook notifications for call events

