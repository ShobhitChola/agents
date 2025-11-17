# filler_agent/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Set

from dotenv import load_dotenv

# Load .env from the project root so environment variables are available.
# This runs once when this module is imported.
load_dotenv()


@dataclass
class Settings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    openai_api_key: str
    ignored_filler_words: Set[str]
    interrupt_command_words: Set[str]
    filler_confidence_threshold: float


def _parse_word_list(value: str) -> Set[str]:
    """
    Turn a comma-separated string like "uh,umm,hmm"
    into a set {"uh", "umm", "hmm"}.
    """
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def get_settings() -> Settings:
    """
    Read configuration from environment variables.
    This will crash early if a required variable is missing,
    which is helpful during development.
    """
    livekit_url = os.environ["LIVEKIT_URL"]
    livekit_api_key = os.environ["LIVEKIT_API_KEY"]
    livekit_api_secret = os.environ["LIVEKIT_API_SECRET"]
    openai_api_key = os.environ["OPENAI_API_KEY"]

    ignored_words_str = os.getenv("IGNORED_FILLER_WORDS", "uh,umm,hmm,haan")
    interrupt_words_str = os.getenv("INTERRUPT_COMMAND_WORDS", "wait,stop,no,hold on")
    threshold_str = os.getenv("FILLER_CONFIDENCE_THRESHOLD", "0.6")

    ignored_words = _parse_word_list(ignored_words_str)
    interrupt_words = _parse_word_list(interrupt_words_str)

    try:
        threshold = float(threshold_str)
    except ValueError:
        threshold = 0.6

    return Settings(
        livekit_url=livekit_url,
        livekit_api_key=livekit_api_key,
        livekit_api_secret=livekit_api_secret,
        openai_api_key=openai_api_key,
        ignored_filler_words=ignored_words,
        interrupt_command_words=interrupt_words,
        filler_confidence_threshold=threshold,
    )
