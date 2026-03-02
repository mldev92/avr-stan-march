# AVR Trace & Dialer Services

This directory contains the source code for two new AVR services:

1. **avr-trace** - Call tracking and logging service
2. **avr-dialer** - Outbound call campaign management service

## Building the Services

### Option 1: Build with Docker Compose

The services will be automatically built when you run:

```bash
docker-compose -f docker-compose-trace-dialer.yml build
```

### Option 2: Build Manually

#### Build Trace Service

```bash
cd services/avr-trace
docker build -t avr-trace:latest .
```

#### Build Dialer Service

```bash
cd services/avr-dialer
docker build -t avr-dialer:latest .
```

## Running the Services

### With Existing AVR Setup

Add the trace and dialer services to your existing docker-compose:

```bash
# Example: Add to OpenAI setup
docker-compose -f docker-compose-openai.yml -f docker-compose-trace-dialer.yml up -d
```

### Standalone

```bash
docker-compose -f docker-compose-trace-dialer.yml up -d
```

## Configuration

Create a `.env` file with the following variables:

```env
# Database
TRACE_DB_PASSWORD=your_secure_password

# Dialer Settings
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100

# Optional: Override service URLs
CORE_URL=http://avr-core:5001
```

## Service Details

### Trace Service (Port 6007)

Tracks all calls (incoming and outgoing) in the AVR system.

**API Endpoints:**
- `POST /api/calls/start` - Start tracking a call
- `POST /api/calls/{uuid}/end` - End call tracking
- `GET /api/calls/{uuid}` - Get call details
- `GET /api/calls` - List calls with filters
- `POST /api/calls/{uuid}/events` - Log call event

### Dialer Service (Port 6008)

Manages outbound call campaigns and initiates calls.

**API Endpoints:**
- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns/{id}` - Get campaign details
- `POST /api/campaigns/{id}/start` - Start campaign
- `POST /api/campaigns/{id}/pause` - Pause campaign
- `POST /api/numbers/import` - Import phone numbers
- `GET /api/campaigns/{id}/numbers` - Get campaign numbers
- `POST /api/calls/initiate` - Manually initiate call

## Usage Example

### 1. Create a Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales Campaign Q1",
    "max_calls_per_hour": 50,
    "caller_id": "+1234567890",
    "caller_name": "Sales Team"
  }'
```

### 2. Import Phone Numbers

```bash
curl -X POST http://localhost:6008/api/numbers/import \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "your-campaign-id",
    "numbers": [
      {
        "phone_number": "+1234567890",
        "name": "John Doe",
        "email": "john@example.com"
      }
    ]
  }'
```

### 3. Start Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns/{campaign_id}/start
```

### 4. Monitor Calls

```bash
# View all outbound calls
curl http://localhost:6007/api/calls?direction=outbound

# View specific call
curl http://localhost:6007/api/calls/{call_uuid}
```

## Integration with AVR Core

The trace service can receive call events from AVR Core. To enable this, configure AVR Core to send webhooks:

```env
# In AVR Core environment (if supported)
TRACE_SERVICE_URL=http://avr-trace:6007
```

Alternatively, the trace service listens to AMI events via the `avr-ami` service.

## Asterisk Configuration

The outbound dialplan is already included in `asterisk/conf/extensions.conf`. Make sure your Asterisk configuration includes:

1. PJSIP trunk configured for outbound calls
2. AMI enabled and accessible
3. UserEvent support enabled

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
cd services/avr-trace
pip install -r requirements.txt

cd ../avr-dialer
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DB_TYPE=sqlite
export PORT=6007  # or 6008 for dialer
```

3. Run the service:
```bash
python main.py
```

## Troubleshooting

### Services won't start
- Check database connection
- Verify environment variables
- Check logs: `docker logs avr-trace` or `docker logs avr-dialer`

### Calls not being initiated
- Verify AMI service is running and accessible
- Check Asterisk trunk configuration
- Review dialer service logs for errors

### Database connection issues
- Ensure PostgreSQL container is running
- Verify database credentials
- Check network connectivity between services

## Next Steps

1. Customize the services for your specific needs
2. Add authentication/authorization
3. Implement rate limiting
4. Add monitoring and alerting
5. Integrate with your CRM or other systems

