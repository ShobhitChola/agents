# SalesCode AI – LiveKit Voice Interruption Handling (NSUT Assignment)

This branch implements a **filler-aware, interruption-safe voice assistant** on top of the LiveKit Agents framework.  
Goal:

- Ignore obvious fillers while the agent is speaking  
- Still treat those fillers as valid speech when the agent is quiet  
- Immediately stop speaking on real commands like **"wait"**, **"stop"**, **"no"**, etc.  
- All without modifying LiveKit’s base VAD logic.

The implementation lives entirely in this branch so it does not affect the upstream `livekit/agents` main branch.

---

## What Changed

This branch adds a small, focused layer on top of LiveKit Agents:

### `filler_agent/config.py`

- Loads configurable filler and command word lists from environment variables:

  - `IGNORED_FILLER_WORDS` (e.g. `uh,umm,hmm,haan`)
  - `INTERRUPT_COMMAND_WORDS` (e.g. `wait,stop,no,hold on`)
  - `FILLER_CONFIDENCE_THRESHOLD`

- Provides a `Settings` dataclass with:

  - LiveKit credentials
  - OpenAI API key
  - Sets of ignored filler words and interrupt command words
  - A confidence threshold for treating short “hmm yeah”-style phrases as background noise.

### `filler_agent/state_tracker.py`

- Tracks the latest **agent** and **user** states (`initializing`, `listening`, `speaking`, etc.) as reported by:

  - `agent_state_changed`
  - `user_state_changed`

- Exposes:

  - `is_agent_speaking()`
  - `is_user_speaking()`

These helpers are used when deciding whether a given transcript should:

- Interrupt the agent,
- Be ignored as filler, or
- Be treated as normal user speech.

### `filler_agent/filler_classifier.py`

Core decision logic for each transcription segment:

- `classify_transcript(...)` returns one of:

  - `"ignore_filler"` – fillers while the agent is speaking  
  - `"interrupt_agent"` – real commands like `stop` / `wait`  
  - `"user_speech"` – normal utterances

Main rules:

1. **Agent not speaking → always user speech**  
   Even `"umm"` counts as a valid user turn when the agent is quiet.

2. **Agent speaking:**
   - If any word is in `interrupt_command_words` → `"interrupt_agent"`.
   - If all tokens are fillers (in `ignored_filler_words`) → `"ignore_filler"`.
   - Very short “confirmation” phrases like `"hmm yeah"` or `"haan"` can be treated as ignorable background if confidence is low.
   - Otherwise, treat as `"interrupt_agent"` (e.g. `"no not that one"`, `"umm okay stop"`).

### `agent.py`

Main entrypoint for the **assignment agent**:

- Creates an `AgentSession` with:

  - STT: `assemblyai/universal-streaming:en`
  - LLM: `openai/gpt-4.1-mini`
  - TTS: `cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc`
  - VAD: `silero.VAD.load()`
  - Turn detection: `MultilingualModel()`
  - `allow_interruptions=True` (default)
  - `min_interruption_words=2`  
    → very short one-word noises are less likely to interrupt.

- Registers event handlers:

  - `agent_state_changed` – updates `AgentStateTracker`.
  - `user_state_changed` – updates `AgentStateTracker`.
  - `user_input_transcribed` – **central place where filler logic runs**.

- On each `user_input_transcribed` event:

  1. Checks whether the agent is currently speaking via `state_tracker.is_agent_speaking()`.
  2. Calls `classify_transcript(...)` with:

     - `transcript=event.transcript`
     - `agent_speaking`
     - `is_final=event.is_final`
     - `ignored_filler_words` / `interrupt_command_words` from `Settings`

  3. Logs the decision:

     ```text
     Transcript='stop' (final=False, agent_speaking=True) => interrupt_agent
     ```

  4. If decision is `"interrupt_agent"` **and** the agent is speaking, it calls:

     ```python
     session.interrupt()
     ```

  5. If decision is `"ignore_filler"`, the event is logged and **no interruption** is triggered.

### `baseline_agent.py`

- A minimal voice agent using the same STT/LLM/TTS stack, but:

  - **No custom filler logic**
  - `allow_interruptions` left as default (True)
  - No `user_input_transcribed` handler

- This serves as a **baseline** to compare how the agent behaves **with vs without** the filler-aware interruption handler.

---

## What Works

- **Filler ignoring while agent speaks**

  - Words like `uh`, `umm`, `hmm`, `haan` (configurable via env) are treated as fillers when the agent is speaking.
  - These do **not** interrupt TTS and are logged as `"ignore_filler"` decisions.
  - `min_interruption_words=2` further reduces the chance that single-word noises prematurely cut off speech.

- **Same fillers count as speech when agent is quiet**

  - When the agent is not currently speaking, *any* transcript (including `"umm"`, `"haan"`) is treated as `"user_speech"`.
  - This matches the requirement: **fillers should still be valid speech when the agent is quiet**.

- **Real interruption commands**

  - English commands (configurable): `wait`, `stop`, `no`, `hold on`, etc.
  - These words are loaded from `INTERRUPT_COMMAND_WORDS`.
  - When spoken while the agent is mid-utterance:

    - `classify_transcript()` returns `"interrupt_agent"`.
    - The handler calls `session.interrupt()` to stop TTS immediately.
    - This ensures **real-time responsiveness** even with the filler filter.

- **Background murmurs / short acknowledgements**

  - Very short phrases like `"hmm yeah"` or `"haan"` while the agent is talking can be treated as **non-interrupting confirmations**.
  - Combined with `min_interruption_words`, this reduces false positives from background speech.

- **Logging for debugging**

  - Every transcription segment is logged with:

    - Transcript text
    - `is_final` flag
    - Whether the agent was currently speaking
    - Classification decision (`ignore_filler`, `interrupt_agent`, `user_speech`)

  - This makes it easy to inspect behavior and tune the word lists for different languages or domains.

---

## Known Issues / Limitations

- **TTS latency / choppiness**

  - On slower networks or machines, Cartesia TTS can occasionally log:
    - `"flush audio emitter due to slow audio generation"`
  - This is a performance characteristic of network + TTS model, not of the filler logic itself.

- **ASR spelling–dependent word lists**

  - Detection of commands like `"ruko"`, `"band"`, `"nahi"` depends on how STT spells them.
  - If a phrase is transcribed differently (e.g. `"rukko"`), it must be added to `INTERRUPT_COMMAND_WORDS` to be consistently recognized.

- **Confidence handling is placeholder**

  - `FILLER_CONFIDENCE_THRESHOLD` is wired into the classifier, but most STT providers in this setup do not expose per-segment confidence to the event handler.
  - For now, short confirmation phrases are treated as ignorable when `confidence` is `None` or below `0.5`.

---

## Steps to Run

### 1. Clone and set up

Clone your fork (this branch lives on your fork, not on upstream):

```bash
git clone https://github.com/<your-username>/agents.git
cd agents
git checkout feature/livekit-interrupt-handler-ShobhitChola
