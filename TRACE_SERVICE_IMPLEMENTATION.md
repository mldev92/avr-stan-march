# Trace Service Implementation Guide

This document provides step-by-step instructions for implementing the Trace Service and Dialer integration with AVR.

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- Existing AVR infrastructure running
- PostgreSQL (optional, SQLite can be used for development)

### 2. Basic Setup

#### Step 1: Add Trace Service to Your Docker Compose

Add the trace service to your existing docker-compose file or use the provided `docker-compose-trace.yml`:

```bash
# If using with existing setup
docker-compose -f docker-compose-openai.yml -f docker-compose-trace.yml up -d
```

#### Step 2: Configure Environment Variables

Create or update your `.env` file:

```env
# Trace Service Configuration
TRACE_DB_PASSWORD=your_secure_password
CORE_URL=http://avr-core:5001

# Dialer Configuration
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100
```

#### Step 3: Update Asterisk Configuration

Add the outbound context to your `extensions.conf` or include it:

```ini
#include "extensions-outbound.conf"
```

Or manually add the outbound context (see `asterisk/conf/extensions-outbound.conf`).

#### Step 4: Start Services

```bash
docker-compose -f docker-compose-trace.yml up -d
```

## API Usage Examples

### Trace Service API

#### Track an Incoming Call

```bash
curl -X POST http://localhost:6007/api/calls/start \
  -H "Content-Type: application/json" \
  -d '{
    "call_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "direction": "inbound",
    "caller_id": "+1234567890",
    "called_number": "5001",
    "channel": "PJSIP/1000-00000001",
    "context": "demo"
  }'
```

#### Get Call Details

```bash
curl http://localhost:6007/api/calls/123e4567-e89b-12d3-a456-426614174000
```

#### List Calls

```bash
# Get all outbound calls
curl "http://localhost:6007/api/calls?direction=outbound"

# Get calls by date range
curl "http://localhost:6007/api/calls?start_date=2024-01-01&end_date=2024-01-31"

# Get calls by status
curl "http://localhost:6007/api/calls?status=completed"
```

### Dialer Service API

#### Create a Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1 Sales Campaign",
    "description": "First quarter sales outreach",
    "max_calls_per_hour": 100,
    "retry_count": 3,
    "retry_delay": 300
  }'
```

#### Import Phone Numbers

```bash
curl -X POST http://localhost:6008/api/numbers/import \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "campaign-uuid-here",
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

#### Start Campaign

```bash
curl -X POST http://localhost:6008/api/campaigns/{campaign_id}/start
```

#### Check Campaign Status

```bash
curl http://localhost:6008/api/campaigns/{campaign_id}
```

## Integration with Existing AVR Core

### Option 1: Webhook Integration

Configure AVR Core to send webhooks to Trace Service:

```env
# In AVR Core environment
TRACE_SERVICE_URL=http://avr-trace:6007
ENABLE_CALL_TRACKING=true
```

### Option 2: AMI Event Subscription

The Trace Service automatically subscribes to AMI events. Ensure:

1. AMI is properly configured in `manager.conf`
2. Trace Service has AMI credentials
3. AMI URL is correctly set in Trace Service environment

### Option 3: Direct API Calls

Modify AVR Core to make direct API calls to Trace Service at key points:

- Call start: When AudioSocket connection is established
- Call end: When AudioSocket connection is closed
- Call events: During important conversation milestones

## Database Schema Setup

If using PostgreSQL, the Trace Service will automatically create tables on first run. For manual setup:

```sql
-- Connect to database
psql -h localhost -U avr -d avr_trace

-- Tables will be auto-created, but you can verify:
\dt

-- Check call_traces table
SELECT * FROM call_traces LIMIT 10;
```

## Monitoring and Logs

### View Trace Service Logs

```bash
docker logs -f avr-trace
```

### View Dialer Service Logs

```bash
docker logs -f avr-dialer
```

### Check Database

```bash
# Connect to PostgreSQL
docker exec -it avr-trace-db psql -U avr -d avr_trace

# Query recent calls
SELECT * FROM call_traces ORDER BY start_time DESC LIMIT 10;
```

## Troubleshooting

### Trace Service Not Receiving Events

1. Check AMI connection:
   ```bash
   docker logs avr-trace | grep -i ami
   ```

2. Verify AMI credentials in `manager.conf` match Trace Service environment

3. Test AMI connection manually:
   ```bash
   telnet localhost 5038
   ```

### Dialer Not Making Calls

1. Check campaign status:
   ```bash
   curl http://localhost:6008/api/campaigns/{id}
   ```

2. Verify numbers are imported:
   ```bash
   curl http://localhost:6008/api/campaigns/{id}/numbers
   ```

3. Check Asterisk trunk configuration for outbound calls

4. Review dialer logs:
   ```bash
   docker logs avr-dialer
   ```

### Database Connection Issues

1. Verify database is running:
   ```bash
   docker ps | grep trace-db
   ```

2. Check database credentials in environment variables

3. Test database connection:
   ```bash
   docker exec -it avr-trace-db psql -U avr -d avr_trace -c "SELECT 1;"
   ```

## Performance Considerations

### Database Optimization

For high-volume deployments:

1. **Indexing**: Ensure indexes are created on frequently queried columns
2. **Partitioning**: Consider partitioning `call_traces` table by date
3. **Archiving**: Implement data archiving for old call records
4. **Connection Pooling**: Configure appropriate connection pool sizes

### Rate Limiting

Configure rate limits to prevent system overload:

```env
MAX_CONCURRENT_CALLS=10
CALLS_PER_HOUR=100
CALLS_PER_DAY=1000
```

### Scaling

For high-volume scenarios:

1. Run multiple Trace Service instances behind a load balancer
2. Use read replicas for database queries
3. Implement message queue (RabbitMQ/Kafka) for event processing
4. Consider using Redis for real-time call state

## Security Considerations

1. **API Authentication**: Implement API key or JWT authentication
2. **Database Security**: Use strong passwords and restrict network access
3. **HTTPS**: Use HTTPS for production deployments
4. **Input Validation**: Validate all API inputs
5. **Rate Limiting**: Implement rate limiting on API endpoints
6. **Logging**: Avoid logging sensitive information (phone numbers, etc.)

## Next Steps

1. **Customization**: Adapt the service to your specific needs
2. **Analytics**: Build dashboards using the trace data
3. **Integration**: Connect with CRM systems or other tools
4. **Automation**: Set up automated callbacks and follow-ups
5. **Reporting**: Create custom reports based on call data

## Support

For issues or questions:
- GitHub: https://github.com/agentvoiceresponse
- Discord: https://discord.gg/DFTU69Hg74
- Wiki: https://wiki.agentvoiceresponse.com

