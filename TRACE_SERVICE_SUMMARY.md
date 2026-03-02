# Trace Service & Dialer Integration - Summary

## Overview

This document provides a high-level summary of the Trace Service analysis and dialer integration for AVR (Agent Voice Response). The Trace Service enables comprehensive call tracking for both incoming and outgoing calls, with full integration to a dialer service based on a number database.

## Key Documents

1. **TRACE_SERVICE_ANALYSIS.md** - Comprehensive technical analysis and architecture
2. **TRACE_SERVICE_IMPLEMENTATION.md** - Step-by-step implementation guide
3. **docker-compose-trace.yml** - Docker Compose configuration for trace and dialer services
4. **asterisk/conf/extensions-outbound.conf** - Asterisk dialplan for outbound calls

## Architecture Overview

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Incoming      │         │   Outgoing      │         │   Trace         │
│   Calls         │         │   Calls         │         │   Service       │
│                 │         │   (Dialer)      │         │                 │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                          │                          │
         │                          │                          │
         └──────────────┬───────────┴──────────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   Database   │
                 │  (PostgreSQL)│
                 └──────────────┘
```

## Core Components

### 1. Trace Service (`avr-trace`)
- **Purpose**: Centralized call tracking and logging
- **Port**: 6007
- **Features**:
  - AMI event subscription
  - Call event logging
  - REST API for call queries
  - Database storage (PostgreSQL/SQLite)

### 2. Dialer Service (`avr-dialer`)
- **Purpose**: Outbound call campaign management
- **Port**: 6008
- **Features**:
  - Campaign management
  - Number database management
  - Call scheduling
  - Rate limiting
  - Retry logic

### 3. Database (`avr-trace-db`)
- **Type**: PostgreSQL
- **Purpose**: Store call traces, events, and number database
- **Tables**:
  - `call_traces` - Main call records
  - `call_events` - Detailed event logs
  - `number_database` - Phone numbers for campaigns
  - `dialer_campaigns` - Campaign configurations
  - `campaign_calls` - Campaign call records

## Use Cases

### Incoming Calls
1. Call arrives at Asterisk
2. AMI event triggers Trace Service
3. Call record created in database
4. Events logged throughout call lifecycle
5. Call completion recorded with metadata

### Outgoing Calls
1. Dialer Service reads numbers from database
2. Campaign scheduler initiates calls via AMI
3. Asterisk originates outbound call
4. Trace Service tracks call events
5. Results updated in number database
6. Retry logic handles failed calls

## Quick Integration Steps

### 1. Add to Existing Setup

```bash
# Add trace service to your existing docker-compose
docker-compose -f docker-compose-openai.yml -f docker-compose-trace.yml up -d
```

### 2. Configure Environment

```env
TRACE_DB_PASSWORD=your_password
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100
```

### 3. Update Asterisk

Include outbound context in `extensions.conf`:
```ini
#include "extensions-outbound.conf"
```

### 4. Test

```bash
# Test incoming call tracking
curl http://localhost:6007/api/calls

# Create a campaign
curl -X POST http://localhost:6008/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Campaign", "max_calls_per_hour": 10}'
```

## API Endpoints Summary

### Trace Service (Port 6007)
- `POST /api/calls/start` - Start tracking a call
- `POST /api/calls/{uuid}/end` - End call tracking
- `GET /api/calls/{uuid}` - Get call details
- `GET /api/calls` - List calls with filters
- `POST /api/calls/{uuid}/events` - Log call event

### Dialer Service (Port 6008)
- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns/{id}` - Get campaign details
- `POST /api/campaigns/{id}/start` - Start campaign
- `POST /api/campaigns/{id}/pause` - Pause campaign
- `POST /api/numbers/import` - Import phone numbers
- `GET /api/campaigns/{id}/numbers` - Get campaign numbers
- `POST /api/calls/initiate` - Manually initiate call

## Data Flow

### Incoming Call Flow
```
SIP Call → Asterisk → AMI Event → Trace Service → Database
                ↓
           AVR Core → ASR/LLM/TTS
                ↓
           Trace Service (events)
```

### Outgoing Call Flow
```
Dialer Service → Number DB → Campaign → AMI Originate
                                                    ↓
                                              Asterisk
                                                    ↓
                                              Outbound Call
                                                    ↓
                                              Trace Service
                                                    ↓
                                              Database Update
```

## Key Features

### Trace Service
- ✅ Real-time call tracking
- ✅ Event logging
- ✅ Call analytics
- ✅ Webhook support
- ✅ Multi-direction support (inbound/outbound)

### Dialer Service
- ✅ Campaign management
- ✅ Number database
- ✅ Rate limiting
- ✅ Retry logic
- ✅ Status tracking
- ✅ Scheduling

## Benefits

1. **Unified Tracking**: Single service for all call tracking
2. **Campaign Management**: Complete dialer functionality
3. **Analytics**: Rich data for reporting and analysis
4. **Scalability**: Docker-based, easy to scale
5. **Integration**: RESTful APIs for easy integration
6. **Flexibility**: Supports multiple database backends

## Next Steps

1. Review `TRACE_SERVICE_ANALYSIS.md` for detailed architecture
2. Follow `TRACE_SERVICE_IMPLEMENTATION.md` for setup
3. Customize for your specific needs
4. Integrate with existing systems
5. Build analytics dashboards
6. Set up monitoring and alerts

## Support Resources

- **Documentation**: See detailed analysis and implementation guides
- **GitHub**: https://github.com/agentvoiceresponse
- **Discord**: https://discord.gg/DFTU69Hg74
- **Wiki**: https://wiki.agentvoiceresponse.com

