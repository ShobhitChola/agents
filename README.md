# SalesCode AI – LiveKit Voice Interruption Handling (NSUT Assignment)

🎥 Video demonstration link : https://drive.google.com/file/d/10h2zIrXfe0wppwoFDawJ21qy4KeRHNwb/view?usp=drivesdk

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

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/ShobhitChola/agents.git
cd <project-root>
```

2. Create a virtual environment

```
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

3. Install dependencies

```
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.3"
pip install python-dotenv
```

4. Create a .env file
    ```
    LIVEKIT_URL=your_url
    LIVEKIT_API_KEY=your_key
    LIVEKIT_API_SECRET=your_secret
    OPENAI_API_KEY=sk-xxxx
    LIVEKIT_INFERENCE_USE_DIRECT_OPENAI=1
    DEFAULT_LANGUAGE=en
    FILLER_CONFIDENCE_THRESHOLD=0.6
    FILLER_CONFIG_PATH=./agent_profile.json
    ```

5. Create the dynamic config file

```
filler_config.json
```

6. Running the Agents (Advance Model)

```
python agent.py console
```

7. Run the baseline agent (Basic Model)
```
python basline_agent.py console
```

# Verified Behaviour During Testing
- Properly ignores filler words during text-to-speech.
- Properly recognizes fillers as spoken input when the agent is silent.
- Instantly interrupts when it receives real interruption commands.
- Selects the appropriate language profile based on speech-to-text detection.
- Responds immediately to JSON updates.
- The baseline agent interrupts on any noise (intended behavior).
