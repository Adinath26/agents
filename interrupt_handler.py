import asyncio
import logging
import re
from typing import Callable, Iterable, Optional, Set, Dict, Any

logger = logging.getLogger("interrupt_handler")
logger.setLevel(logging.DEBUG)

DEFAULT_IGNORED = {"uh", "umm", "hmm", "haan", "uhh", "ummm"}

def normalize_token(token: str) -> str:
    return re.sub(r"[^\w]+", "", token).lower()

class InterruptHandler:
    """
    Filter filler words while agent is speaking,
    but allow normal speech when agent is silent.
    """

    def __init__(
        self,
        is_agent_speaking: Callable[[], bool],
        stop_agent: Callable[[], None],
        forward_speech: Callable[[Dict[str, Any]], None],
        *,
        ignored_words: Optional[Iterable[str]] = None,
        command_words: Optional[Iterable[str]] = None,
        confidence_threshold: float = 0.6,
    ):
        self.is_agent_speaking = is_agent_speaking
        self.stop_agent = stop_agent
        self.forward_speech = forward_speech

        self.ignored_words: Set[str] = {
            normalize_token(w) for w in (ignored_words or DEFAULT_IGNORED)
        }

        self.command_words: Set[str] = {
            normalize_token(w) for w in (command_words or {"stop", "wait", "pause", "no"} )
        }

        self.confidence_threshold = confidence_threshold
        self.lock = asyncio.Lock()

        logger.info("InterruptHandler initialized")

    async def update_ignored_words(self, words: Iterable[str]):
        async with self.lock:
            self.ignored_words = {normalize_token(w) for w in words}

    async def process_transcription(self, event: Dict[str, Any]):
        text = (event.get("text") or "").strip()
        confidence = event.get("confidence", 1.0)
        tokens = [normalize_token(t) for t in text.split() if normalize_token(t)]

        if not tokens:
            return

        async with self.lock:
            speaking = self.is_agent_speaking()
            ignored = self.ignored_words
            commands = self.command_words

        # If any command is found -> immediate stop
        if any(t in commands for t in tokens):
            logger.info(f"Command interruption detected: {text}")
            self.stop_agent()
            self.forward_speech(event)
            return

        # If agent is not speaking -> always forward
        if not speaking:
            logger.info(f"Forwarding (agent quiet): {text}")
            self.forward_speech(event)
            return

        # Agent is speaking — decide ignored vs valid speech
        non_filler = [t for t in tokens if t not in ignored]

        if confidence < self.confidence_threshold:
            logger.info(f"Ignored low-confidence murmur: {text}")
            return

        if len(non_filler) == 0:
            logger.info(f"Ignored filler while speaking: {text}")
            return

        # Valid real interruption
        logger.info(f"Valid interruption: {text}")
        self.stop_agent()
        self.forward_speech(event)
