# SalesCode AI – LiveKit Voice Interruption Handling (NSUT Assignment)

This branch implements a **filler-aware, interruption-safe, multi-language voice assistant** using the LiveKit Agents framework.

The system:
- Ignores filler words while the **agent is speaking**
- Treats fillers as valid input when the **agent is quiet**
- Interrupts instantly on real commands like **"stop"**, **"wait"**, **"ruko"**, **"nahi"**
- Supports **English + Hindi (Latin script)** filler/command detection
- Allows **dynamic updates** through `filler_config.json`
- Uses LiveKit’s built-in VAD + turn detection (no modification to internal logic)

This work lives only in this branch and does not affect upstream `livekit/agents`.

---

# What Changed (Overview of New Logic)

## `filler_agent/config.py`
Loads configuration from `.env`:
- Filler words (EN + HI)
- Command words (EN + HI)
- Confidence threshold
- Default language
- Path to dynamic config file `filler_config.json`

Produces a central `Settings` object.

---

## `filler_agent/state_tracker.py`
Tracks:
- Agent state (`listening`, `thinking`, `speaking`)
- User state (`speaking`, `listening`, `away`)

Helpers used throughout classification:
- `is_agent_speaking()`
- `is_user_speaking()`

---

## `filler_agent/filler_classifier.py`
Classifies each transcript into:
- `"ignore_filler"`
- `"interrupt_agent"`
- `"user_speech"`

Rules:
1. If agent **not speaking** → everything = `"user_speech"`
2. If agent **speaking**:
   - Contains any interrupt word → `"interrupt_agent"`
   - All tokens are fillers → `"ignore_filler"`
   - Very short confirmations (`"haan"`, `"hmm yeah"`) → ignore
   - Anything else → `"interrupt_agent"`

---

## `filler_agent/runtime_config.py`
Enables **runtime updates** to filler + command words.

Whenever you save `filler_config.json`, the agent updates itself without restart:
- Logs new settings
- Updates the in-memory word lists
- Classification immediately changes

---

## `agent.py`
The main assignment agent.

Implements:
- Multi-language detection
- Filler-aware interruption handling
- Dynamic runtime configuration
- State tracking
- `min_interruption_words=2` to reduce false positives

Uses:
- STT: AssemblyAI Universal Streaming
- LLM: OpenAI GPT-4.1-mini
- TTS: Cartesia Sonic
- Turn detection: `MultilingualModel()`

---

## `baseline_agent.py`
A comparison agent:
- No custom filler logic
- Default LiveKit interruption behavior
- Demonstrates how much better the custom agent performs

---

# What Works (Verified)

### ✔ Filler ignoring while agent speaks
Ignored during TTS:
- uh
- umm
- hmm
- haan
- any dynamic word you add (e.g., “basically”)

### ✔ Fillers treated as normal speech when agent is quiet
Even `"umm"` becomes a valid prompt → `"user_speech"`

### ✔ Real interruption commands
English:
- stop
- wait
- no
- hold on

Hindi:
- ruko
- band
- nahi

### ✔ Multi-language detection  
STT language tags:
- `"lang=en"` → English lists
- `"lang=hi"` → Hindi lists

### ✔ Live dynamic updates  
Editing `filler_config.json` changes behavior instantly.

### ✔ Baseline comparison  
Baseline interrupts on ANY noise → bad  
Custom agent interrupts only on meaningful commands → correct

---

# Known Issues

### • STT spelling variations  
If STT writes “ruko” as “rukko”, add both spellings.

### • Hindi must be spoken in Latin form  
Works with “ruko”, not “रुको”.

### • TTS can be slow  
Cartesia may show latency logs.

### • STT confidence is not exposed  
Threshold is a best-effort placeholder.

---

# Installation (Anyone Can Run This)

## 1. Clone the repo

git clone https://github.com/ShobhitChola/agents.git
cd agents
git checkout feature/livekit-interrupt-handler-ShobhitChola

## 2. Create a virtual environment

python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

## 3. Install dependencies
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.3"
pip install python-dotenv

## 4. create .env
LIVEKIT_URL=wss://<your-instance>.livekit.cloud
LIVEKIT_API_KEY=xxx
LIVEKIT_API_SECRET=xxx

OPENAI_API_KEY=sk-xxxx

DEFAULT_LANGUAGE=en

IGNORED_FILLER_WORDS_EN=uh,umm,hmm
IGNORED_FILLER_WORDS_HI=haan,accha,arey

INTERRUPT_COMMAND_WORDS_EN=stop,wait,no,hold on
INTERRUPT_COMMAND_WORDS_HI=ruko,band,nahi

FILLER_CONFIDENCE_THRESHOLD=0.6
FILLER_CONFIG_PATH=./filler_config.json

## 5. Create filler_config.json:
{
  "ignored": {
    "en": ["uh", "umm", "hmm"],
    "hi": ["haan", "accha", "arey"]
  },
  "commands": {
    "en": ["stop", "wait", "no", "hold on"],
    "hi": ["ruko", "band", "nahi"]
  }
}

## 6. Run the main agent
python agent.py console

## 7. Run the baseline agent(original one without any changes)
python baselin_agent.py console
