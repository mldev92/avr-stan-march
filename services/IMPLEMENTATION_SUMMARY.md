# Implementation Summary: Trace & Dialer Services

## What Was Created

Based on analysis of the existing AVR codebase (`avr-core`, `avr-ami`, `avr-sts-elevenlabs`), I've created two new services that integrate seamlessly with your existing infrastructure.

## Services Created

### 1. Trace Service (`services/avr-trace/`)
- **Language**: Python (FastAPI)
- **Port**: 6007
- **Purpose**: Tracks and logs all calls (incoming and outgoing)
- **Database**: PostgreSQL or SQLite
- **Integration**: 
  - Receives webhooks from AVR Core
  - Receives API calls from Dialer Service
  - Can poll AMI service for call information

### 2. Dialer Service (`services/avr-dialer/`)
- **Language**: Python (FastAPI)
- **Port**: 6008
- **Purpose**: Manages outbound call campaigns
- **Database**: Shares database with Trace Service
- **Integration**: 
  - Uses `avr-ami` service's `/originate` endpoint
  - Sends call events to Trace Service
  - Manages number database and campaigns

## Key Integration Points

### ✅ AMI Service Integration

The dialer service correctly uses the existing `avr-ami` service:

```python
# Matches avr-ami/index.js API format
POST http://avr-ami:6006/originate
{
  "channel": "PJSIP/1234567890@trunk",
  "exten": "1234567890",
  "context": "outbound",
  "priority": 1,
  "callerid": "AVR Agent <+1234567890>"
}
```

### ✅ AVR Core Webhook Integration

Trace Service accepts webhooks from AVR Core (matching `avr-core/webhook.js` format):

```env
# In AVR Core environment
WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
WEBHOOK_SECRET=your-secret
```

### ✅ Asterisk Dialplan

Updated `extensions.conf` with outbound context that routes answered calls to AVR Core:

```ini
[outbound]
exten => _X.,1,...
answered:
 same => n,GoSub(avr,s,1(avr-core:5001))  ; Routes to AVR Core
```

## File Structure

```
avr-infra/
├── services/
│   ├── avr-trace/
│   │   ├── main.py              # Trace service implementation
│   │   ├── requirements.txt    # Python dependencies
│   │   ├── Dockerfile          # Docker build file
│   │   └── ami_listener.py     # AMI event listener (optional)
│   ├── avr-dialer/
│   │   ├── main.py              # Dialer service implementation
│   │   ├── requirements.txt    # Python dependencies
│   │   └── Dockerfile          # Docker build file
│   ├── README.md                # Service documentation
│   ├── INTEGRATION_GUIDE.md     # Detailed integration guide
│   └── AVR_CORE_WEBHOOK_SETUP.md # Webhook setup instructions
├── docker-compose-trace-dialer.yml  # Docker Compose configuration
└── asterisk/conf/
    └── extensions.conf          # Updated with outbound context
```

## Quick Start

1. **Build services**:
   ```bash
   docker-compose -f docker-compose-trace-dialer.yml build
   ```

2. **Start with existing AVR setup**:
   ```bash
   docker-compose -f docker-compose-openai.yml -f docker-compose-trace-dialer.yml up -d
   ```

3. **Configure AVR Core webhooks** (optional but recommended):
   ```env
   WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
   ```

4. **Create a campaign and start calling**:
   ```bash
   # See QUICK_START_TRACE_DIALER.md for detailed steps
   ```

## API Endpoints

### Trace Service (Port 6007)

- `POST /api/calls/start` - Start tracking a call
- `POST /api/calls/{uuid}/end` - End call tracking
- `GET /api/calls/{uuid}` - Get call details
- `GET /api/calls` - List calls with filters
- `POST /api/webhooks/call-event` - Webhook endpoint for AVR Core

### Dialer Service (Port 6008)

- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns/{id}` - Get campaign details
- `POST /api/campaigns/{id}/start` - Start campaign
- `POST /api/numbers/import` - Import phone numbers
- `GET /api/campaigns/{id}/numbers` - Get campaign numbers

## How It Works

### Outbound Call Flow

1. **Dialer Service** reads numbers from database
2. **Dialer** calls `avr-ami/originate` to initiate call
3. **AMI Service** sends Originate action to Asterisk
4. **Asterisk** dials the number using outbound context
5. **Call Answered** → Asterisk routes to AVR Core via AudioSocket
6. **AVR Core** handles conversation (ASR → LLM → TTS)
7. **AVR Core** sends webhook to Trace Service (if configured)
8. **Trace Service** records call completion

### Inbound Call Flow

1. **Call arrives** at Asterisk
2. **Asterisk** routes to AVR Core via AudioSocket
3. **AVR Core** handles conversation
4. **AVR Core** sends webhook to Trace Service (if configured)
5. **Trace Service** records call

## Database Schema

The services use a shared PostgreSQL database with these tables:

- `call_traces` - Main call records
- `call_events` - Detailed event logs
- `number_database` - Phone numbers for campaigns
- `dialer_campaigns` - Campaign configurations
- `campaign_calls` - Campaign call records

## Testing

### Test AMI Integration

```bash
curl -X POST http://localhost:6006/originate \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "PJSIP/1234567890@trunk",
    "exten": "1234567890",
    "context": "outbound",
    "callerid": "Test <+1234567890>"
  }'
```

### Test Trace Service

```bash
curl http://localhost:6007/health
curl http://localhost:6007/api/calls
```

### Test Dialer Service

```bash
curl http://localhost:6008/health
curl http://localhost:6008/api/campaigns
```

## Documentation

- **QUICK_START_TRACE_DIALER.md** - Step-by-step quick start guide
- **services/README.md** - Service documentation and API reference
- **services/INTEGRATION_GUIDE.md** - Detailed integration guide
- **services/AVR_CORE_WEBHOOK_SETUP.md** - Webhook configuration guide

## Next Steps

1. **Build and deploy** the services
2. **Configure AVR Core webhooks** for automatic call tracking
3. **Test with a small campaign** to verify everything works
4. **Customize** the services for your specific needs
5. **Add monitoring** and alerting
6. **Build analytics dashboards** using trace data

## Support

For issues or questions:
- Check service logs: `docker logs avr-trace` or `docker logs avr-dialer`
- Review integration guides in `services/` directory
- GitHub: https://github.com/agentvoiceresponse
- Discord: https://discord.gg/DFTU69Hg74

