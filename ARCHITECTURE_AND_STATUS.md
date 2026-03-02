# AVR Stan March — Architecture & Working Status

> Last updated: March 2026  
> Repository: https://github.com/mldev92/avr-stan-march  
> Server: `n8n.stavol.pro` (Ubuntu, accessed via Cloudflare tunnel)  
> Project directory on server: `~/avr-infra/`

---

## Table of Contents

1. [What Is Working](#1-what-is-working)
2. [System Architecture](#2-system-architecture)
3. [Call Flows](#3-call-flows)
4. [Docker Services](#4-docker-services)
5. [Asterisk Configuration](#5-asterisk-configuration)
6. [IPHost SIP Trunk](#6-iphost-sip-trunk)
7. [avr-ami Service API](#7-avr-ami-service-api)
8. [Trace & Dialer Services](#8-trace--dialer-services)
9. [Environment Variables](#9-environment-variables)
10. [Key Lessons Learned](#10-key-lessons-learned)
11. [Operational Runbook](#11-operational-runbook)
12. [Known Issues](#12-known-issues)

---

## 1. What Is Working

Both call directions are fully operational:

| Direction | Path | Status |
|-----------|------|--------|
| **Inbound** | GSM → IPHost trunk → Asterisk `[from-pstn]` → AVR voice agent | ✅ Working |
| **Outbound** | HTTP POST to `avr-ami:6006/originate` → Asterisk → IPHost trunk → phone | ✅ Working |

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        PSTN / GSM                            │
│                    (IPHost SIP trunk)                        │
│               tel.iphost.md / sipbalancer-1.iphost.md        │
└─────────────────────────┬────────────────────────────────────┘
                          │ SIP (port 5080, UDP)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                   avr-asterisk (Docker)                      │
│  - PJSIP trunk: iphost-endpoint                              │
│  - Inbound context: [from-pstn]                              │
│  - Outbound context: [outbound-pstn]                         │
│  - AMI port: 5038                                            │
│  - SIP port: 5060                                            │
│  - RTP: 10000-10050/UDP                                      │
└───────────┬──────────────────────────┬───────────────────────┘
            │ AudioSocket (TCP 5001)   │ AMI (TCP 5038)
            ▼                          ▼
┌───────────────────────┐   ┌──────────────────────────────────┐
│   avr-core (Docker)   │   │       avr-ami (Docker)           │
│   Port: 5001 (audio)  │   │       Port: 6006 (HTTP API)      │
│   Port: 6001 (HTTP)   │   │  - /originate                    │
│                       │   │  - /hangup                       │
└──────────┬────────────┘   │  - /transfer                     │
           │ WebSocket      │  - /variables                    │
           ▼                └──────────────────────────────────┘
┌───────────────────────┐
│  avr-sts-openai       │
│  (Speech-to-Speech)   │
│  Port: 6030           │
│  Model: gpt-4o-       │
│  realtime-preview     │
└───────────────────────┘
```

### Docker Network

All services communicate on the `avr` bridge network (`172.20.0.0/24`). Container names are used as hostnames internally (e.g., `avr-asterisk`, `avr-core`, `avr-ami`).

---

## 3. Call Flows

### 3.1 Inbound Call (GSM → Agent)

```
1. Caller dials your Moldova DID number
2. IPHost SIP trunk sends INVITE to avr-asterisk:5080
3. [iphost-identify] matches source IP (185.181.228.0/24) → iphost-endpoint
4. iphost-endpoint routes to context [from-pstn]
5. extensions.conf [from-pstn]: GoSub(avr,s,1(avr-core:5001))
6. [avr] subroutine:
   - Answer()
   - Generate UUID via uuidgen
   - Enable DENOISE(rx)
   - Dial(AudioSocket/avr-core:5001/<UUID>)
7. avr-core receives audio stream over AudioSocket
8. avr-core forwards to avr-sts-openai via WebSocket
9. OpenAI Realtime API processes speech → LLM → speech
10. Response audio streams back to caller
```

### 3.2 Outbound Call (Agent → GSM)

```
1. HTTP POST to http://avr-ami:6006/originate
   Body: {
     "channel": "PJSIP/068XXXXXXX@iphost-endpoint",
     "exten": "5001",
     "context": "demo"
   }
2. avr-ami sends AMI Originate action to avr-asterisk:5038
3. Asterisk dials PJSIP/068XXXXXXX@iphost-endpoint
4. [outbound-pstn] context normalizes number to local Moldova format
5. Asterisk sends INVITE via IPHost trunk (sipbalancer-1.iphost.md:5080)
6. Phone rings → answered
7. Asterisk routes answered call to AVR Core via AudioSocket
8. Voice agent handles the conversation
```

### 3.3 Number Format Normalization (Dialplan)

The `[outbound-pstn]` context in `extensions.conf` automatically converts any number format to local Moldova format required by IPHost:

| Input Format | Converted To |
|---|---|
| `+37368XXXXXXX` | `068XXXXXXX` |
| `37368XXXXXXX` | `068XXXXXXX` |
| `0037368XXXXXXX` | `068XXXXXXX` |
| `068XXXXXXX` | `068XXXXXXX` (unchanged) |
| `68XXXXXXX` | `068XXXXXXX` (0 prepended) |

---

## 4. Docker Services

### Active Compose File

**Primary stack:** `docker-compose-openai-realtime.yml`

```bash
sudo docker compose -f docker-compose-openai-realtime.yml up -d
```

### Services Overview

| Container | Image | Port(s) | Purpose |
|-----------|-------|---------|---------|
| `avr-core` | `agentvoiceresponse/avr-core` | 5001 (audio), 6001 (HTTP) | Main voice agent core |
| `avr-sts-openai` | `agentvoiceresponse/avr-sts-openai` | 6030 (internal WS) | OpenAI Realtime speech-to-speech |
| `avr-asterisk` | `agentvoiceresponse/avr-asterisk` | 5038, 5060, 8088, 8089, 10000-10050/UDP | Asterisk PBX |
| `avr-ami` | `agentvoiceresponse/avr-ami` | 6006 | AMI HTTP API |
| `avr-phone` | `agentvoiceresponse/avr-phone` | 8080 | Web phone interface |
| `n8n_app` | `n8nio/n8n:latest` | 5678 | Workflow automation |

### Config File Bind Mounts (avr-asterisk)

```
./asterisk/conf/manager.conf  → /etc/asterisk/my_manager.conf
./asterisk/conf/pjsip.conf    → /etc/asterisk/my_pjsip.conf
./asterisk/conf/extensions.conf → /etc/asterisk/my_extensions.conf
./asterisk/conf/ari.conf      → /etc/asterisk/my_ari.conf
```

> **CRITICAL**: Docker bind mounts use inodes. Never replace config files using `open('w')` or `cp` — this creates a new inode and breaks the mount. Always edit in-place:
> - With vim: `vim file` (edits in-place by default with `:w`)
> - With Python: use `open('r+')` + `truncate()`, not `open('w')`

---

## 5. Asterisk Configuration

### extensions.conf — Dialplan Summary

#### `[avr]` — Reusable subroutine (called via GoSub)
- Answers call, generates UUID, enables RX denoise
- Connects to AVR Core via `AudioSocket/<host>:<port>/<UUID>`

#### `[demo]` — Internal test extensions
- `5001` → AVR Core (container hostname)
- `5002` → AVR Core (host.docker.internal)
- `5003` → AVR Core via HTTP webhook + AudioSocket

#### `[from-pstn]` — Inbound from IPHost trunk
- Matches any DID (`_X.`)
- Routes directly to AVR Core via `GoSub(avr,s,1(avr-core:5001))`

#### `[outbound-pstn]` — Outbound to PSTN
- Normalizes number format (see Section 3.3)
- Dials via `PJSIP/<number>@iphost-endpoint`
- 60-second timeout, music-on-hold enabled

### manager.conf — AMI Access

```ini
[avr]
secret=avr
read=call,dialplan
write=all
```

AMI listens on port `5038`. The `avr-ami` service connects to it using credentials from `.env`.

---

## 6. IPHost SIP Trunk

### Registration

- **Server:** `sip:tel.iphost.md:5080`
- **Outbound proxy:** `sip:sipbalancer-1.iphost.md:5080;lr`
- **Transport:** UDP on port 5080 (separate from default 5060)
- **Retry interval:** 60s, forbidden retry: 600s, expiry: 3600s

### Identify Rule (Critical)

```ini
[iphost-identify]
type=identify
endpoint=iphost-endpoint
match=185.181.228.0/24
```

IPHost uses multiple SIP balancer IPs within the `185.181.228.0/24` subnet. The `match` must be the full `/24` subnet — matching only a single IP will cause inbound calls to fail when a different balancer is used.

### Number Format Requirement

IPHost Moldova **only accepts local format**:
- ✅ `068XXXXXXX` — local mobile
- ✅ `079XXXXXXX` — local mobile  
- ✅ `022XXXXXXX` — local landline
- ❌ `0037368XXXXXXX` — returns `403 Restricted international call`
- ❌ `+37368XXXXXXX` — returns `403 Restricted international call`

### Verify Registration

```bash
sudo docker exec avr-asterisk asterisk -rx "pjsip show registrations"
sudo docker exec avr-asterisk asterisk -rx "pjsip show endpoints"
```

---

## 7. avr-ami Service API

Base URL: `http://localhost:6006` (or `http://avr-ami:6006` from other containers)

### POST /originate

Initiates an outbound call via Asterisk AMI.

```bash
curl -X POST http://localhost:6006/originate \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "PJSIP/068XXXXXXX@iphost-endpoint",
    "exten": "5001",
    "context": "demo",
    "priority": 1,
    "callerid": "Agent Voice Response <avr>"
  }'
```

| Field | Required | Description |
|-------|----------|-------------|
| `channel` | Yes | PJSIP channel string with target number and endpoint |
| `exten` | Yes | Extension to connect answered call to (e.g. `5001` for AVR Core) |
| `context` | No | Dialplan context (default: `demo`) |
| `priority` | No | Dialplan priority (default: `1`) |
| `callerid` | No | Caller ID displayed to recipient |

### POST /hangup

Hangs up an active call by UUID.

```bash
curl -X POST http://localhost:6006/hangup \
  -H "Content-Type: application/json" \
  -d '{"uuid": "<call-uuid>"}'
```

### POST /transfer

Transfers a call to a different extension/context.

```bash
curl -X POST http://localhost:6006/transfer \
  -H "Content-Type: application/json" \
  -d '{"uuid": "<call-uuid>", "exten": "5002", "context": "demo", "priority": 1}'
```

### POST /variables

Returns call variables tracked by AMI. If no UUID provided, returns the last active call.

```bash
curl -X POST http://localhost:6006/variables \
  -H "Content-Type: application/json" \
  -d '{"uuid": "<call-uuid>"}'
```

### AMI Connection Behavior

- `avr-ami` connects to Asterisk AMI on startup using `keepConnected()`
- If Asterisk restarts, `avr-ami` must also be restarted to re-establish the AMI connection:

```bash
sudo docker compose -f docker-compose-openai-realtime.yml restart avr-ami
```

---

## 8. Trace & Dialer Services

These are optional add-on services for call tracking and outbound campaign management.

### Compose File

```bash
sudo docker compose -f docker-compose-trace-dialer.yml up -d
```

### avr-trace (Port 6007)

Tracks and logs all calls. Accepts webhooks from AVR Core.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/calls` | GET | List all calls (filter by `direction`, `status`) |
| `/api/calls/start` | POST | Start tracking a call |
| `/api/calls/{uuid}/end` | POST | End call tracking |
| `/api/calls/{uuid}` | GET | Get call details |
| `/api/webhooks/call-event` | POST | Webhook receiver from AVR Core |

### avr-dialer (Port 6008)

Manages outbound call campaigns.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/campaigns` | POST | Create a campaign |
| `/api/campaigns/{id}` | GET | Get campaign details |
| `/api/campaigns/{id}/start` | POST | Start a campaign |
| `/api/numbers/import` | POST | Import phone numbers to campaign |
| `/api/campaigns/{id}/numbers` | GET | List campaign numbers |

### Webhook Integration with AVR Core

To enable automatic call tracking, set in AVR Core environment:

```env
WEBHOOK_URL=http://avr-trace:6007/api/webhooks/call-event
WEBHOOK_SECRET=your-secret
```

---

## 9. Environment Variables

Copy `.env.example` to `.env` and fill in your values.

### Required for Current Stack (OpenAI Realtime)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (starts with `sk-proj-`) |
| `AMI_HOST` | Asterisk hostname (default: `avr-asterisk`) |
| `AMI_PORT` | AMI port (default: `5038`) |
| `AMI_USERNAME` | AMI username (default: `avr`) |
| `AMI_PASSWORD` | AMI password (default: `avr`) |

### pjsip.conf Placeholders (fill before first run)

| Placeholder | Replace With |
|-------------|-------------|
| `YOUR_SERVER_IP` | Your server's public IP address |
| `YOUR_LOCAL_SUBNET` | Your local network subnet (e.g. `192.168.100`) |
| `YOUR_DID` | Your IPHost DID number (e.g. `022011180`) |
| `YOUR_PASSWORD` | Your IPHost SIP password |

> `pjsip.conf` is excluded from git via `.gitignore`. Copy from `pjsip.conf.example` and fill in credentials.

---

## 10. Key Lessons Learned

### IPHost Number Format
IPHost Moldova **rejects international format** with `403 Restricted international call`. Always use local format (`068XXXXXXX`). The `[outbound-pstn]` dialplan context handles automatic conversion.

### IPHost SIP Balancer Subnet
IPHost uses a pool of SIP balancers within `185.181.228.0/24`. The `[iphost-identify]` section must match the full `/24` subnet, not a single IP. Otherwise inbound calls will fail when a different balancer IP is used.

### Docker Bind Mount Inode Issue
Docker bind mounts track files by inode. If you replace a config file (e.g. with `cp`, `mv`, or Python `open('w')`), Docker loses the mount because a new inode is created. Always edit files in-place:
- **vim**: safe by default (`:w` writes in-place)
- **Python**: use `open('r+')` then `file.seek(0)`, `file.write(...)`, `file.truncate()`

### avr-ami Reconnection After Asterisk Restart
The `avr-ami` service establishes its AMI connection at startup. If `avr-asterisk` is restarted, `avr-ami` must be restarted too:

```bash
sudo docker restart avr-ami
```

---

## 11. Operational Runbook

### Start the Full Stack

```bash
cd ~/avr-infra
sudo docker compose -f docker-compose-openai-realtime.yml up -d
```

### Restart All AVR Services

```bash
cd ~/avr-infra
sudo docker compose -f docker-compose-openai-realtime.yml restart
```

### Restart Asterisk + Re-sync AMI

```bash
sudo docker restart avr-asterisk
sleep 5
sudo docker restart avr-ami
```

### View Logs

```bash
sudo docker logs avr-core -f
sudo docker logs avr-ami -f
sudo docker logs avr-asterisk -f
sudo docker logs avr-sts-openai -f
```

### Verify SIP Trunk Registration

```bash
sudo docker exec avr-asterisk asterisk -rx "pjsip show registrations"
```

Expected output: `iphost-registration` with status `Registered`.

### Test Outbound Call

```bash
curl -X POST http://localhost:6006/originate \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "PJSIP/068XXXXXXX@iphost-endpoint",
    "exten": "5001",
    "context": "demo"
  }'
```

Replace `068XXXXXXX` with a real Moldova mobile number.

### Reload Asterisk Dialplan (without restart)

```bash
sudo docker exec avr-asterisk asterisk -rx "dialplan reload"
```

### Reload PJSIP Config (without restart)

```bash
sudo docker exec avr-asterisk asterisk -rx "pjsip reload"
```

### Check Cloudflare Tunnel

```bash
sudo systemctl status cloudflared
```

---

## 12. Known Issues

| Issue | Status | Notes |
|-------|--------|-------|
| `elevenlabs-proxy` container restarting | Open | Service has an error causing restart loop. Not part of current active stack. |
| `avr-ami` loses AMI connection after Asterisk restart | By design | Must manually restart `avr-ami` after any Asterisk restart. |

---

## Repository

- **GitHub:** https://github.com/mldev92/avr-stan-march
- **Sensitive files excluded from git:** `asterisk/conf/pjsip.conf`, `.env`, `keys/`
- **Template for SIP config:** `asterisk/conf/pjsip.conf.example`
