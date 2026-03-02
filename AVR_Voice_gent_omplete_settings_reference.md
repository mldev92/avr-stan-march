Now I have all the information. Let me compile a comprehensive reference of all voice agent settings.

---

# AVR Voice Agent - Complete Settings Reference

## Architecture Overview

The AVR infrastructure supports **two main architecture types**:

| Type | Description | Providers |
|------|-------------|-----------|
| **STS (Speech-to-Speech)** | Single service handles ASR + LLM + TTS | OpenAI Realtime, ElevenLabs, Deepgram, Gemini, HumeAI, Ultravox |
| **Pipelined (ASR→LLM→TTS)** | Separate services for each component | OpenAI, Anthropic, Google, Sarvam, Vosk + Kokoro |

---

## 1. OpenAI Provider

### 1.1 OpenAI Realtime API (STS)

**File:** `docker-compose-openai-realtime.yml` (currently active)

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6030` | WebSocket port |
| API Key | `OPENAI_API_KEY` | Required | Your OpenAI API key |
| Model | `OPENAI_MODEL` | `gpt-4o-realtime-preview` | Realtime API model |
| Instructions | `OPENAI_INSTRUCTIONS` | `"You are a helpful assistant."` | **System prompt/agent behavior** |
| AMI URL | `AMI_URL` | `http://avr-ami:6006` | Asterisk manager interface |

**Voice Options** (set via API):
- `alloy` - Neutral voice
- `echo` - Male voice
- `fable` - British accent
- `onyx` - Deep male voice
- `nova` - Female voice
- `shimmer` - Soft female voice

### 1.2 OpenAI LLM (Pipelined)

**File:** `docker-compose-openai.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6002` | HTTP port |
| API Key | `OPENAI_API_KEY` | Required | Your OpenAI API key |
| Model | `OPENAI_MODEL` | `gpt-3.5-turbo` | LLM model |
| Max Tokens | `OPENAI_MAX_TOKENS` | `100` | Response length limit |
| Temperature | `OPENAI_TEMPERATURE` | `0.0` | **Randomness (0.0-2.0)** |
| System Prompt | `SYSTEM_PROMPT` | `"You are a helpful assistant."` | **Agent instructions** |
| Base URL | `OPENAI_BASEURL` | - | For Ollama/local models |

---

## 2. ElevenLabs Provider (STS)

**File:** `docker-compose-elevenlabs.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6035` | WebSocket port |
| API Key | `ELEVENLABS_API_KEY` | Required | ElevenLabs API key |
| Agent ID | `ELEVENLABS_AGENT_ID` | Required | **Pre-configured conversational AI agent** |
| Voice ID | `ELEVENLABS_VOICE_ID` | `Xb7hH8MSUJpSbSDYk0k2` | **Voice selection** |
| Model ID | `ELEVENLABS_MODEL_ID` | `scribe_v1` | STT model |
| Language | `ELEVENLABS_LANGUAGE_CODE` | `en` | Language code |

### ElevenLabs Voice Configuration
- Configure agent at [ElevenLabs Conversational AI](https://elevenlabs.io/app/conversational-ai)
- Set voice, behavior, and system prompt in the dashboard
- Agent ID links to your pre-configured agent

---

## 3. Deepgram Provider

### 3.1 Deepgram STS (Speech-to-Speech)

**File:** `docker-compose-deepgram.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6033` | WebSocket port |
| API Key | `DEEPGRAM_API_KEY` | Required | Deepgram API key |
| Agent Prompt | `AGENT_PROMPT` | Required | **System prompt/agent behavior** |

### 3.2 Deepgram ASR (Speech-to-Text)

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6010` | HTTP port |
| API Key | `DEEPGRAM_API_KEY` | Required | API key |
| Language | `SPEECH_RECOGNITION_LANGUAGE` | `en-US` | Recognition language |
| Model | `SPEECH_RECOGNITION_MODEL` | `nova-2-phonecall` | **Optimized for phone calls** |

---

## 4. Anthropic Provider (LLM)

**File:** `docker-compose-anthropic.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6014` | HTTP port |
| API Key | `ANTHROPIC_API_KEY` | Required | Anthropic API key |
| Model | `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20240620` | LLM model |
| Max Tokens | `ANTHROPIC_MAX_TOKENS` | `1024` | Response length |
| Temperature | `ANTHROPIC_TEMPERATURE` | `1` | **Randomness (0.0-1.0)** |
| System Prompt | `ANTHROPIC_SYSTEM_PROMPT` | `"You are a helpful assistant."` | **Agent behavior** |

### Available Models:
- `claude-3-5-sonnet-20240620` - Fast, intelligent
- `claude-3-haiku-20240307` - Fastest, most affordable
- `claude-3-opus-20240229` - Most capable

---

## 5. Gemini Provider (STS)

**File:** `docker-compose-gemini.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6037` | WebSocket port |
| API Key | `GEMINI_API_KEY` | Required | Google AI API key |
| Model | `GEMINI_MODEL` | `gemini-2.5-flash-native-audio-preview-12-2025` | Native audio model |
| Instructions | `GEMINI_INSTRUCTIONS` | `"You are a helpful assistant"` | **System prompt** |
| Thinking Level | `GEMINI_THINKING_LEVEL` | `MINIMAL` | **Reasoning depth** |
| Thinking Budget | `GEMINI_THINKING_BUDGET` | `0` | Token budget for thinking |

### Thinking Levels:
- `MINIMAL` - Quick responses
- `MEDIUM` - Balanced reasoning
- `MAXIMAL` - Deep reasoning

---

## 6. Hume AI Provider (STS)

**File:** `docker-compose-humeai.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6039` | WebSocket port |
| API Key | `HUMEAI_API_KEY` | Required | Hume AI API key |
| Config ID | `HUMEAI_CONFIG_ID` | Required | **Pre-configured voice settings** |

### Configuration:
- Create config at [Hume AI Dashboard](https://platform.hume.ai/)
- Config includes voice, prompt, and emotional intelligence settings

---

## 7. Ultravox Provider (STS)

**File:** `docker-compose-ultravox.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6031` | WebSocket port |
| Agent ID | `ULTRAVOX_AGENT_ID` | Required | **Pre-configured agent** |
| API Key | `ULTRAVOX_API_KEY` | Required | Ultravox API key |

### Configuration:
- Create agent at [Ultravox Dashboard](https://ultravox.ai/)
- Agent includes voice, prompt, and behavior settings

---

## 8. Sarvam AI Provider (Indian Languages)

**File:** `docker-compose-sarvam.yml`

### 8.1 ASR Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6050` | HTTP port |
| API Key | `SARVAM_API_KEY` | Required | Sarvam API key |
| Model | `SARVAM_SPEECH_RECOGNITION_MODEL` | `saarika:v2.5` | STT model |
| Language | `SARVAM_SPEECH_RECOGNITION_LANGUAGE` | `en-IN` | **Language code** |
| Mode | `SARVAM_SPEECH_RECOGNITION_MODE` | `transcribe` | Recognition mode |

### 8.2 TTS Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6052` | HTTP port |
| API Key | `SARVAM_API_KEY` | Required | API key |
| Language | `SARVAM_TTS_LANGUAGE` | `en-IN` | Language code |
| Speaker | `SARVAM_TTS_SPEAKER` | `aditya` | **Voice selection** |
| Model | `SARVAM_TTS_MODEL` | `bulbul:v3` | TTS model |
| Temperature | `SARVAM_TTS_TEMPERATURE` | `0.6` | **Voice variation** |

### Available Speakers:
- `aditya` - Male (Hindi)
- `amol` - Male (Hindi)
- `anushka` - Female (Hindi)
- `barkha` - Female (Hindi)

### Supported Languages:
`en-IN`, `hi-IN`, `bn-IN`, `gu-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN`

---

## 9. Google Cloud Provider

**File:** `docker-compose-google.yml`

### 9.1 ASR Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6001` | HTTP port |
| Credentials | `GOOGLE_APPLICATION_CREDENTIALS` | `/usr/src/app/google.json` | JSON key file |
| Language | `SPEECH_RECOGNITION_LANGUAGE` | `en-US` | Language code |
| Model | `SPEECH_RECOGNITION_MODEL` | `telephony` | **Optimized for phone** |

### 9.2 TTS Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6003` | HTTP port |
| Language | `TEXT_TO_SPEECH_LANGUAGE` | `en-US` | Language code |
| Gender | `TEXT_TO_SPEECH_GENDER` | `FEMALE` | Voice gender |
| Voice Name | `TEXT_TO_SPEECH_NAME` | `en-US-Chirp-HD-F` | **Specific voice** |
| Speaking Rate | `TEXT_TO_SPEECH_SPEAKING_RATE` | `1.0` | **Speed (0.25-4.0)** |

### Available Voices (Chirp HD):
- `en-US-Chirp-HD-F` - Female
- `en-US-Chirp-HD-M` - Male
- `en-GB-Chirp-HD-F` - British Female
- `en-GB-Chirp-HD-M` - British Male

---

## 10. Kokoro TTS (Local/Free)

**File:** `docker-compose-local.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6012` | HTTP port |
| Base URL | `KOKORO_BASE_URL` | `http://avr-kokoro:8880` | Kokoro server |
| Voice | `KOKORO_VOICE` | `af_alloy` | **Voice selection** |
| Speed | `KOKORO_SPEED` | `1.3` | **Speaking speed** |

### Available Voices:
- `af_alloy` - Female, alloy style
- `af_aoede` - Female, soft
- `af_bella` - Female, warm
- `am_adam` - Male, deep
- `am_michael` - Male, neutral

---

## 11. Vosk Provider (Offline STT)

**File:** `docker-compose-vosk.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6010` | HTTP port |
| Model Path | `MODEL_PATH` | `model` | Path to Vosk model |

**Note:** Requires downloading Vosk model files and mounting at `./model:/usr/src/app/model`

---

## 12. OpenRouter Provider (LLM Gateway)

**File:** `docker-compose-google.yml`

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Port | `PORT` | `6009` | HTTP port |
| API Key | `OPENROUTER_API_KEY` | Required | OpenRouter API key |
| Model | `OPENROUTER_MODEL` | `google/gemini-2.0-flash-lite-preview-02-05:free` | **Any model** |
| System Prompt | `SYSTEM_PROMPT` | `"You are my personal assistant"` | Agent instructions |

### Popular Free Models:
- `google/gemini-2.0-flash-lite-preview-02-05:free`
- `deepseek/deepseek-chat-v3-0324:free`
- `meta-llama/llama-3-8b-instruct:free`

---

## 13. AVR Core Settings

**Applies to all configurations**

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| Port | `PORT=5001` | AudioSocket port |
| HTTP Port | `HTTP_PORT=6001` | HTTP API port |
| STS URL | `STS_URL` | WebSocket to STS service |
| ASR URL | `ASR_URL` | HTTP to ASR service |
| LLM URL | `LLM_URL` | HTTP to LLM service |
| TTS URL | `TTS_URL` | HTTP to TTS service |
| Interrupt | `INTERRUPT_LISTENING` | Allow user to interrupt (`true/false`) |
| Greeting | `SYSTEM_MESSAGE` | **Initial greeting message** |

---

## Quick Reference: Voice Speed Settings

| Provider | Setting | Range | Default |
|----------|---------|-------|---------|
| Google TTS | `TEXT_TO_SPEECH_SPEAKING_RATE` | 0.25-4.0 | 1.0 |
| Kokoro TTS | `KOKORO_SPEED` | 0.5-2.0 | 1.3 |
| Sarvam TTS | `SARVAM_TTS_TEMPERATURE` | 0.0-1.0 | 0.6 |

---

## Quick Reference: Temperature Settings (LLM Randomness)

| Provider | Setting | Range | Default | Effect |
|----------|---------|-------|---------|--------|
| OpenAI | `OPENAI_TEMPERATURE` | 0.0-2.0 | 0.0 | Lower = more focused |
| Anthropic | `ANTHROPIC_TEMPERATURE` | 0.0-1.0 | 1.0 | Higher = more creative |
| Sarvam | `SARVAM_TTS_TEMPERATURE` | 0.0-1.0 | 0.6 | Voice variation |

---

## Quick Reference: System Prompt Settings

| Provider | Environment Variable | Where to Configure |
|----------|---------------------|-------------------|
| OpenAI Realtime | `OPENAI_INSTRUCTIONS` | `.env` file |
| OpenAI LLM | `SYSTEM_PROMPT` | `.env` file |
| Anthropic | `ANTHROPIC_SYSTEM_PROMPT` | `.env` file |
| Gemini | `GEMINI_INSTRUCTIONS` | `.env` file |
| Deepgram STS | `AGENT_PROMPT` | `.env` file |
| ElevenLabs | Dashboard | ElevenLabs website |
| Hume AI | Dashboard | Hume AI website |
| Ultravox | Dashboard | Ultravox website |

---

## Current Active Stack

Based on the rules, the currently running stack is **`docker-compose-openai-realtime.yml`** with:

- **Model:** `gpt-4o-realtime-preview`
- **Instructions:** `"You are a helpful assistant."`
- **Provider:** OpenAI Realtime API (Speech-to-Speech)