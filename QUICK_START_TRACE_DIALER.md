# Quick Start: Trace & Dialer Services

This guide shows you how to build and use the Trace and Dialer services to enable outbound calling with your AVR voice agent.

## What These Services Do

1. **Trace Service** - Tracks and logs all calls (incoming and outgoing)
2. **Dialer Service** - Manages outbound call campaigns and initiates calls to customers

## Prerequisites

- Docker and Docker Compose installed
- Existing AVR infrastructure (avr-core, avr-ami, avr-asterisk)
- PostgreSQL (or SQLite for development)

## Step 1: Build the Services

```bash
cd avr-infra
docker-compose -f docker-compose-trace-dialer.yml build
```

This will build:
- `avr-trace` service (port 6007)
- `avr-dialer` service (port 6008)
- PostgreSQL database for storing call data

## Step 2: Configure Environment

Create or update your `.env` file:

```env
# Database password
TRACE_DB_PASSWORD=your_secure_password_here

# Dialer settings
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100
```

## Step 3: Start Services

### Option A: Add to Existing Setup

If you already have AVR running (e.g., with OpenAI):

```bash
docker-compose -f docker-compose-openai.yml -f docker-compose-trace-dialer.yml up -d
```

### Option B: Standalone

```bash
docker-compose -f docker-compose-trace-dialer.yml up -d
```

## Step 4: Verify Services

Check that services are running:

```bash
# Check trace service
curl http://localhost:6007/health

# Check dialer service
curl http://localhost:6008/health
```

Both should return `{"status": "healthy", "database": "connected"}`

## Step 5: Create Your First Campaign

### 5.1 Create a Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "description": "My first outbound campaign",
    "max_calls_per_hour": 10,
    "retry_count": 2,
    "retry_delay": 300,
    "caller_id": "+1234567890",
    "caller_name": "AVR Agent"
  }'
```

Save the `campaign_id` from the response.

### 5.2 Import Phone Numbers

```bash
curl -X POST http://localhost:6008/api/numbers/import \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "YOUR_CAMPAIGN_ID_HERE",
    "numbers": [
      {
        "phone_number": "+1234567890",
        "name": "John Doe",
        "email": "john@example.com"
      },
      {
        "phone_number": "+1987654321",
        "name": "Jane Smith",
        "email": "jane@example.com"
      }
    ]
  }'
```

### 5.3 Start the Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns/YOUR_CAMPAIGN_ID/start
```

The dialer will now start calling numbers from your list!

## Step 6: Monitor Calls

### View All Calls

```bash
# All calls
curl http://localhost:6007/api/calls

# Only outbound calls
curl http://localhost:6007/api/calls?direction=outbound

# Calls by status
curl http://localhost:6007/api/calls?status=completed
```

### View Campaign Status

```bash
curl http://localhost:6008/api/campaigns/YOUR_CAMPAIGN_ID
```

### View Campaign Numbers

```bash
curl http://localhost:6008/api/campaigns/YOUR_CAMPAIGN_ID/numbers
```

## How It Works

### Call Flow

1. **Dialer Service** reads numbers from the database
2. **Dialer** initiates call via **AMI Service** (`avr-ami`)
3. **Asterisk** originates the outbound call
4. When call is answered, Asterisk routes to **AVR Core**
5. **AVR Core** handles the conversation (ASR → LLM → TTS)
6. **Trace Service** tracks all call events

### Architecture

```
Dialer Service → AMI Service → Asterisk → Outbound Call
                                      ↓
                                 AVR Core (Voice Agent)
                                      ↓
                                 Trace Service (Logging)
```

## Important Notes

### AMI Service Integration

The dialer service needs to initiate calls via the AMI service. The current implementation assumes the AMI service has an `/api/originate` endpoint. If your AMI service uses a different API, you'll need to update the `initiate_call_via_ami()` function in `services/avr-dialer/main.py`.

### Asterisk Configuration

Make sure your Asterisk has:
1. PJSIP trunk configured for outbound calls (replace `@trunk` in extensions.conf if needed)
2. The outbound context in `extensions.conf` (already added)
3. AMI enabled and accessible

### Caller ID

Set a valid caller ID in your campaign. This is the number that will appear on the recipient's phone.

## Troubleshooting

### Services won't start
```bash
# Check logs
docker logs avr-trace
docker logs avr-dialer
docker logs avr-trace-db
```

### Calls not being made
1. Check AMI service is running: `docker ps | grep avr-ami`
2. Verify Asterisk trunk is configured
3. Check dialer logs: `docker logs avr-dialer`
4. Test AMI connection manually

### Database issues
```bash
# Connect to database
docker exec -it avr-trace-db psql -U avr -d avr_trace

# Check tables
\dt

# View campaigns
SELECT * FROM dialer_campaigns;
```

## Next Steps

1. **Customize the voice agent** - Update your LLM prompts for outbound calls
2. **Add call recording** - Integrate recording functionality
3. **Implement callbacks** - Schedule follow-up calls
4. **Add analytics** - Build dashboards using trace data
5. **Integrate with CRM** - Connect with your customer database

## API Documentation

### Trace Service (Port 6007)

- `POST /api/calls/start` - Start tracking a call
- `GET /api/calls/{uuid}` - Get call details
- `GET /api/calls` - List calls with filters

### Dialer Service (Port 6008)

- `POST /api/campaigns` - Create campaign
- `POST /api/campaigns/{id}/start` - Start campaign
- `POST /api/numbers/import` - Import numbers
- `GET /api/campaigns/{id}/numbers` - Get campaign numbers

See `services/README.md` for full API documentation.

## Support

For issues or questions:
- Check service logs
- Review the implementation code in `services/`
- GitHub: https://github.com/agentvoiceresponse
- Discord: https://discord.gg/DFTU69Hg74

