# Integration Guide: Trace & Dialer Services with AVR

This guide explains how the Trace and Dialer services integrate with the existing AVR architecture.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Dialer    │────▶│  AMI Service│────▶│  Asterisk   │
│   Service   │     │  (avr-ami)  │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │  AVR Core   │
                                         │  (avr-core) │
                                         └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │   Trace     │
                                         │   Service   │
                                         └─────────────┘
```

## Integration Points

### 1. Dialer Service → AMI Service

The dialer service uses the existing `avr-ami` service's `/originate` endpoint to initiate outbound calls.

**AMI Service API** (from `avr-ami/index.js`):
```javascript
POST /originate
{
  "channel": "PJSIP/1234567890@trunk",
  "exten": "1234567890",
  "context": "outbound",
  "priority": 1,
  "callerid": "AVR Agent <+1234567890>"
}
```

**Dialer Service Implementation**:
- Uses `httpx` to POST to `http://avr-ami:6006/originate`
- Formats the request according to AMI service's expected format
- Handles response and errors

### 2. AVR Core → Trace Service

AVR Core can send webhook events to the Trace Service when calls start/end.

**AVR Core Webhook Support** (from `avr-core/webhook.js`):
- Environment variable: `WEBHOOK_URL`
- Sends events with: `uuid`, `type`, `timestamp`, `payload`

**Integration Options**:

#### Option A: Webhook Integration (Recommended)

Configure AVR Core to send webhooks to Trace Service:

```env
# In AVR Core environment
WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
WEBHOOK_SECRET=your-secret-here
```

Then add a webhook endpoint to Trace Service:

```python
@app.post("/api/webhooks/call-event")
async def handle_webhook(request: dict):
    event_type = request.get("type")
    uuid = request.get("uuid")
    
    if event_type == "call_start":
        # Start tracking
    elif event_type == "call_end":
        # End tracking
```

#### Option B: Direct API Calls

Modify AVR Core to call Trace Service API directly (requires AVR Core source code access).

### 3. AMI Service → Trace Service

The AMI service tracks calls in memory. The Trace Service can:

1. **Poll AMI Service** (if AMI service exposes a `/calls` endpoint)
2. **Listen to AMI Events** (if AMI service supports WebSocket/SSE)
3. **Receive Events via API** (when calls are initiated via dialer)

Currently, the Trace Service receives events via:
- Direct API calls from Dialer Service when calls are initiated
- Webhooks from AVR Core (if configured)
- Direct API calls for manual tracking

### 4. Asterisk Dialplan Integration

The outbound dialplan in `extensions.conf`:

```ini
[outbound]
exten => _X.,1,NoOp(Outbound call to ${EXTEN})
 same => n,Set(UUID=${SHELL(uuidgen | tr -d '\n')})
 same => n,UserEvent(CallStart,Direction: outbound,CallUUID: ${UUID},...)
 same => n,Dial(PJSIP/${EXTEN}@trunk,30,tT)
 same => n,GotoIf($["${DIALSTATUS}" = "ANSWER"]?answered:notanswered)

answered:
 same => n,GoSub(avr,s,1(avr-core:5001))  ; Route to AVR Core
 same => n,Hangup()
```

When a call is answered:
1. Asterisk routes to AVR Core via AudioSocket
2. AVR Core handles the conversation (ASR → LLM → TTS)
3. Trace Service can track the call via webhooks or API

## Implementation Details

### Dialer Service Call Flow

1. **Campaign Started** → Dialer reads numbers from database
2. **Call Initiated** → Dialer POSTs to `avr-ami/originate`
3. **AMI Service** → Forwards Originate action to Asterisk
4. **Asterisk** → Dials the number using outbound context
5. **Call Answered** → Asterisk routes to AVR Core
6. **AVR Core** → Handles conversation, can send webhooks to Trace
7. **Call Ended** → Trace Service records completion

### Trace Service Event Sources

The Trace Service can receive call events from multiple sources:

1. **Direct API** (`/api/calls/start`, `/api/calls/{uuid}/end`)
   - Called by Dialer Service when initiating calls
   - Can be called by any service that needs to track calls

2. **Webhooks** (if implemented)
   - From AVR Core when calls start/end
   - From other services that want to report call events

3. **AMI Events** (future enhancement)
   - Direct connection to Asterisk AMI
   - Real-time event streaming

## Configuration

### Environment Variables

#### Trace Service
```env
PORT=6007
DB_TYPE=postgresql
DB_HOST=avr-trace-db
DB_USER=avr
DB_PASSWORD=avr
AMI_URL=http://avr-ami:6006
CORE_URL=http://avr-core:5001
```

#### Dialer Service
```env
PORT=6008
DB_TYPE=postgresql
DB_HOST=avr-trace-db
DB_USER=avr
DB_PASSWORD=avr
AMI_URL=http://avr-ami:6006
TRACE_URL=http://avr-trace:6007
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100
```

#### AVR Core (for webhook integration)
```env
WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
WEBHOOK_SECRET=your-secret
```

## Testing Integration

### 1. Test AMI Originate

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

### 2. Test Trace Service

```bash
# Start tracking a call
curl -X POST http://localhost:6007/api/calls/start \
  -H "Content-Type: application/json" \
  -d '{
    "call_uuid": "test-uuid-123",
    "direction": "outbound",
    "called_number": "+1234567890",
    "caller_id": "+1987654321"
  }'

# End tracking
curl -X POST http://localhost:6007/api/calls/test-uuid-123/end \
  -H "Content-Type: application/json" \
  -d '{
    "duration": 120,
    "status": "completed"
  }'
```

### 3. Test Full Flow

1. Create a campaign via Dialer API
2. Import numbers
3. Start campaign
4. Monitor calls via Trace API
5. Check AVR Core logs for conversation handling

## Troubleshooting

### Calls Not Being Initiated

1. **Check AMI Service**:
   ```bash
   docker logs avr-ami
   curl http://localhost:6006/originate -X POST ...
   ```

2. **Check Asterisk Trunk**:
   - Verify PJSIP trunk is configured
   - Test trunk connectivity
   - Check Asterisk logs: `docker logs avr-asterisk`

3. **Check Dialer Logs**:
   ```bash
   docker logs avr-dialer
   ```

### Trace Service Not Receiving Events

1. **Check Trace Service**:
   ```bash
   docker logs avr-trace
   curl http://localhost:6007/health
   ```

2. **Verify Webhook Configuration** (if using):
   - Check AVR Core environment variables
   - Verify network connectivity
   - Check AVR Core logs for webhook errors

3. **Test Direct API**:
   ```bash
   curl -X POST http://localhost:6007/api/calls/start ...
   ```

## Future Enhancements

1. **Direct AMI Connection**: Connect Trace Service directly to Asterisk AMI for real-time events
2. **WebSocket Events**: Stream call events in real-time
3. **Call Recording Integration**: Store recording URLs in trace database
4. **Advanced Analytics**: Build dashboards using trace data
5. **CRM Integration**: Sync call data with external CRM systems

