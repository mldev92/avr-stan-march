# AVR Core Webhook Setup for Trace Service

This guide shows how to configure AVR Core to send call events to the Trace Service.

## Configuration

Add these environment variables to your AVR Core service:

```env
WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
WEBHOOK_SECRET=your-secret-here
WEBHOOK_TIMEOUT=3000
WEBHOOK_RETRIES=3
```

## Webhook Events

AVR Core will send the following events (based on `avr-core/webhook.js`):

### Call Start Event

```json
{
  "uuid": "call-uuid-here",
  "type": "call_start",
  "timestamp": "2024-01-01T12:00:00Z",
  "payload": {
    "direction": "inbound",
    "caller_id": "+1234567890",
    "called_number": "5001",
    "channel": "PJSIP/1000-00000001",
    "context": "demo"
  }
}
```

### Call End Event

```json
{
  "uuid": "call-uuid-here",
  "type": "call_end",
  "timestamp": "2024-01-01T12:05:00Z",
  "payload": {
    "duration": 300,
    "hangup_cause": "NORMAL_CLEARING",
    "status": "completed"
  }
}
```

## Docker Compose Example

Update your `docker-compose-*.yml` file to include webhook configuration:

```yaml
services:
  avr-core:
    image: agentvoiceresponse/avr-core
    environment:
      - PORT=5001
      - ASR_URL=http://avr-asr-deepgram:6010/speech-to-text-stream
      - LLM_URL=http://avr-llm-openai:6002/prompt-stream
      - TTS_URL=http://avr-tts-deepgram:6011/text-to-speech-stream
      # Add webhook configuration
      - WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
      - WEBHOOK_SECRET=your-secret-here
      - WEBHOOK_TIMEOUT=3000
      - WEBHOOK_RETRIES=3
    depends_on:
      - avr-trace  # Add trace service as dependency
```

## Testing

1. Start all services:
   ```bash
   docker-compose -f docker-compose-openai.yml -f docker-compose-trace-dialer.yml up -d
   ```

2. Make a test call (incoming or outgoing)

3. Check Trace Service logs:
   ```bash
   docker logs avr-trace | grep webhook
   ```

4. Query call records:
   ```bash
   curl http://localhost:6007/api/calls
   ```

## Manual Webhook Testing

You can test the webhook endpoint directly:

```bash
# Test call start
curl -X POST http://localhost:6007/api/webhooks/call-event \
  -H "Content-Type: application/json" \
  -d '{
    "uuid": "test-uuid-123",
    "type": "call_start",
    "timestamp": "2024-01-01T12:00:00Z",
    "payload": {
      "direction": "inbound",
      "caller_id": "+1234567890",
      "called_number": "5001"
    }
  }'

# Test call end
curl -X POST http://localhost:6007/api/webhooks/call-event \
  -H "Content-Type: application/json" \
  -d '{
    "uuid": "test-uuid-123",
    "type": "call_end",
    "timestamp": "2024-01-01T12:05:00Z",
    "payload": {
      "duration": 300,
      "status": "completed"
    }
  }'
```

## Notes

- The webhook endpoint accepts events in the format used by AVR Core's `webhook.js`
- The Trace Service will automatically create call records if they don't exist
- Webhook failures are logged but don't block call processing
- The `WEBHOOK_SECRET` is sent in the `WEBOOK_SECRET` header (note the typo in AVR Core)

