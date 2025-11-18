# agent.py - main entrypoint for your voice agent
from __future__ import annotations

import logging
import asyncio  # NEW: needed for asyncio.create_task

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    AgentSession,
    Agent,
    RoomInputOptions,
    UserInputTranscribedEvent,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from filler_agent.config import get_settings
from filler_agent.state_tracker import AgentStateTracker
from filler_agent.filler_classifier import classify_transcript
from filler_agent.runtime_config import RuntimeWordConfig, watch_config_file

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
    logger.info("Ignored filler words (global): %s", settings.ignored_filler_words)
    logger.info(
        "Interrupt command words (global): %s", settings.interrupt_command_words
    )
    logger.info("Default language: %s", settings.default_language)

    # Runtime config object that knows per-language word lists.
    runtime_config = RuntimeWordConfig(
        ignored_by_lang=settings.ignored_filler_words_by_lang,
        commands_by_lang=settings.interrupt_command_words_by_lang,
        default_language=settings.default_language,
    )

    # OPTIONAL BONUS: watch a JSON file for dynamic updates if configured
    if settings.dynamic_config_path:
        logger.info(
            "Dynamic filler config enabled. Watching: %s",
            settings.dynamic_config_path,
        )
        # Older livekit-agents JobContext doesn't expose create_task,
        # so we use the standard asyncio.create_task instead.
        asyncio.create_task(
            watch_config_file(settings.dynamic_config_path, runtime_config)
        )
    else:
        logger.info("Dynamic filler config not enabled (FILLER_CONFIG_PATH not set).")

    # Create the AgentSession: this wires up STT, LLM, TTS, VAD, and turn detection.
    # We keep LiveKit's own interruption system ON, but tune it with min_interruption_words.
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),

        # Let LiveKit handle normal interruptions
        allow_interruptions=True,  # True is default, but we make it explicit

        # Require at least 2 words before LiveKit treats speech as an interruption.
        # So 1-word fillers (“uh”, “umm”, “haan”) are less likely to cut the agent off.
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

        # Try to detect language, e.g. "en", "en-US", "hi"
        lang = (event.language or settings.default_language).split("-")[0].lower()

        # Get the correct per-language word sets, with fallbacks
        ignored_words, command_words = runtime_config.get_sets_for_language(lang)

        decision = classify_transcript(
            transcript=event.transcript,
            agent_speaking=agent_speaking,
            is_final=event.is_final,
            ignored_filler_words=ignored_words,
            interrupt_command_words=command_words,
            confidence=None,  # placeholder; most STT providers don't expose this here yet
        )

        logger.info(
            "Transcript='%s' (final=%s, agent_speaking=%s, lang=%s) => %s",
            event.transcript,
            event.is_final,
            agent_speaking,
            lang,
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
