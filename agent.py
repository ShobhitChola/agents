# agent.py - main entrypoint for your voice agent
from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, UserInputTranscribedEvent
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from filler_agent.config import get_settings
from filler_agent.state_tracker import AgentStateTracker
from filler_agent.filler_classifier import classify_transcript

# Load .env so LIVEKIT_* and OPENAI_API_KEY are available
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("filler_agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice AI assistant. "
                "You speak clearly and keep your answers short."
            )
        )


async def entrypoint(ctx: agents.JobContext):
    """
    This function is called by LiveKit to start your agent.
    It sets up the AgentSession and our filler-aware interruption logic.
    """
    settings = get_settings()
    logger.info("Starting session")
    logger.info("Ignored filler words: %s", settings.ignored_filler_words)
    logger.info("Interrupt command words: %s", settings.interrupt_command_words)

    # Create the AgentSession: this wires up STT, LLM, TTS, VAD, and turn detection.
    # We use the same pattern as the Voice AI quickstart docs.
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),

        # Let LiveKit handle normal interruptions
        allow_interruptions=True,           # (or just omit this, True is the default)

        # NEW: require at least 2 words before LiveKit treats speech as an interruption.
        # So 1-word fillers (“uh”, “umm”, “haan”) won’t cut the agent off.
        min_interruption_words=2,
    )



    state_tracker = AgentStateTracker()

    # --- State change handlers ---------------------------------------------

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        state_tracker.update_agent_state(event.new_state)
        logger.info("Agent state: %s -> %s", event.old_state, event.new_state)

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        state_tracker.update_user_state(event.new_state)
        logger.info("User state: %s -> %s", event.old_state, event.new_state)

    # --- Transcription handler (our filler logic lives here) ----------------

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        agent_speaking = state_tracker.is_agent_speaking()

        decision = classify_transcript(
            transcript=event.transcript,
            agent_speaking=agent_speaking,
            is_final=event.is_final,
            ignored_filler_words=settings.ignored_filler_words,
            interrupt_command_words=settings.interrupt_command_words,
            confidence=None,  # placeholder; most STT providers don't expose this here yet
        )

        logger.info(
            "Transcript='%s' (final=%s, agent_speaking=%s) => %s",
            event.transcript,
            event.is_final,
            agent_speaking,
            decision,
        )

        if decision == "interrupt_agent" and agent_speaking:
            logger.info(">> Interrupting agent due to real user interruption")
            session.interrupt()
        elif decision == "ignore_filler":
            logger.info(">> Ignoring filler while agent is speaking")
            # Do nothing else; we deliberately don't interrupt

    # --- Start the voice session -------------------------------------------

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Have the agent say hello once at the beginning.
    await session.generate_reply(
        instructions="Greet the user briefly and offer your assistance."
    )


if __name__ == "__main__":
    # This enables CLI modes like:
    #   python agent.py console
    #   python agent.py dev
    #   python agent.py start
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
