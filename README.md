# AVR Stan March

Agent Voice Response infrastructure with IPHost SIP trunk integration for Moldova.

## Features

- Inbound calls from PSTN routed to AVR voice agent
- Outbound calls initiated by voice agent to PSTN numbers
- IPHost SIP trunk integration (local Moldova numbers)
- Simple CLI tools for initiating calls

## Prerequisites

- Docker and Docker Compose
- IPHost SIP trunk account (Moldova)
- Server with public IP or Cloudflare tunnel

## Quick Start

1. Clone this repository:
   ```bash
   git clone https://github.com/mldev92/avr-stan-march.git
   cd avr-stan-march
   ```

2. Copy example config files:
   ```bash
   cp asterisk/conf/pjsip.conf.example asterisk/conf/pjsip.conf
   ```

3. Edit `asterisk/conf/pjsip.conf`:
   - Replace `YOUR_SERVER_IP` with your server's IP
   - Replace `YOUR_LOCAL_SUBNET` with your local network subnet
   - Replace `YOUR_DID` with your IPHost DID number
   - Replace `YOUR_PASSWORD` with your IPHost password

4. Create `.env` file (copy from `.env.example` if available)

5. Start the services:
   ```bash
   docker compose -f docker-compose-openai-realtime.yml up -d
   ```

6. Verify trunk registration:
   ```bash
   docker exec avr-asterisk asterisk -rx "pjsip show registrations"
   ```

## Usage

### Inbound Calls

Calls to your DID number are automatically routed to the AVR voice agent.

### Outbound Calls

#### Option 1: Using the shell script (recommended)

```bash
./call.sh 068155658
```

#### Option 2: Using Python script

```bash
python3 call.py 068155658
```

#### Option 3: Direct API call

```bash
curl -X POST http://localhost:6006/originate \
  -H "Content-Type: application/json" \
  -d '{"channel": "PJSIP/068155658@iphost-endpoint", "exten": "5001", "context": "demo", "priority": 1, "callerid": "22011180"}'
```

#### Option 4: From extension 1000 (softphone)

Dial `9` + phone number from your registered softphone:
- `9068155658` - calls 068155658 via PSTN

## Number Format

IPHost expects local Moldova format:
- Local mobile: `068XXXXXXX` or `079XXXXXXX`
- Local landline: `022XXXXXXX`

The dialplan automatically converts:
- `37368XXXXXXX` → `068XXXXXXX`
- `0037368XXXXXXX` → `068XXXXXXX`
- `+37368XXXXXXX` → `068XXXXXXX`

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PSTN      │────▶│   Asterisk  │────▶│  AVR Core   │
│  (IPHost)   │◀────│  (PJSIP)    │◀────│  (Agent)    │
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   avr-ami   │
                   │  (AMI API)  │
                   └─────────────┘
```

### Call Flow

**Inbound:**
```
GSM Caller → IPHost → Asterisk [from-pstn] → [avr] → AudioSocket → avr-core (Agent)
```

**Outbound (via API):**
```
HTTP POST /originate → avr-ami → AMI → Asterisk → IPHost → GSM Receiver
```

**Outbound (via softphone):**
```
Softphone (ext 1000) → dial 9XXXXXXX → [outbound-pstn] → IPHost → GSM Receiver
```

## Configuration Files

- `asterisk/conf/pjsip.conf` - SIP trunk and endpoint configuration
- `asterisk/conf/extensions.conf` - Dialplan for call routing
- `asterisk/conf/manager.conf` - AMI configuration

## Troubleshooting

### Check trunk registration
```bash
docker exec avr-asterisk asterisk -rx "pjsip show registrations"
```

### Check active channels
```bash
docker exec avr-asterisk asterisk -rx "core show channels"
```

### View live logs
```bash
docker logs -f avr-asterisk
```

### Restart services
```bash
docker compose -f docker-compose-openai-realtime.yml restart avr-asterisk avr-ami
```

## License

MIT
