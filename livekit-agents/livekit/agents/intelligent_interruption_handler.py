"""
LiveKit Intelligent Interruption Handler
Filters filler words during agent speech while preserving real interruptions
"""

import asyncio
import logging
from typing import List, Set, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)


class InterruptionType(Enum):
    """Classification of interruption types"""
    FILLER = "filler"
    VALID = "valid"
    MIXED = "mixed"
    UNCERTAIN = "uncertain"


@dataclass
class InterruptionDecision:
    """Result of interruption analysis"""
    should_interrupt: bool
    interruption_type: InterruptionType
    confidence: float
    detected_words: List[str]
    reason: str


class IntelligentInterruptionHandler:
    """
    Handles intelligent filtering of user interruptions during agent speech.
    Distinguishes between filler words and meaningful interruptions.
    """
    
    def __init__(
        self,
        ignored_words: Optional[List[str]] = None,
        confidence_threshold: float = 0.6,
        mixed_content_threshold: float = 0.3,
        enable_logging: bool = True
    ):
        """
        Initialize the interruption handler.
        
        Args:
            ignored_words: List of filler words to ignore during agent speech
            confidence_threshold: Minimum ASR confidence to consider (0.0-1.0)
            mixed_content_threshold: Ratio of non-filler to total words to trigger interrupt
            enable_logging: Enable detailed logging for debugging
        """
        self.ignored_words: Set[str] = set(
            ignored_words or ['uh', 'um', 'umm', 'hmm', 'haan', 'ah', 'er', 'like', 'you know']
        )
        self.confidence_threshold = confidence_threshold
        self.mixed_content_threshold = mixed_content_threshold
        self.enable_logging = enable_logging
        
        # State tracking
        self._agent_is_speaking = False
        self._lock = asyncio.Lock()
        
        # Statistics for monitoring
        self.stats = {
            'total_interruptions': 0,
            'filtered_fillers': 0,
            'valid_interrupts': 0,
            'mixed_content': 0
        }
        
        logger.info(f"Initialized InterruptionHandler with {len(self.ignored_words)} filler words")
    
    def update_ignored_words(self, words: List[str], append: bool = True):
        """
        Dynamically update the list of ignored filler words.
        
        Args:
            words: New list of words to ignore
            append: If True, add to existing list; if False, replace
        """
        if append:
            self.ignored_words.update(words)
            logger.info(f"Added {len(words)} words to ignore list")
        else:
            self.ignored_words = set(words)
            logger.info(f"Replaced ignore list with {len(words)} words")
    
    def set_agent_speaking_state(self, is_speaking: bool):
        """
        Update whether the agent is currently speaking.
        Should be called from TTS lifecycle callbacks.
        
        Args:
            is_speaking: True if agent is speaking, False otherwise
        """
        self._agent_is_speaking = is_speaking
        if self.enable_logging:
            logger.debug(f"Agent speaking state: {is_speaking}")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    
    def _tokenize(self, text: str) -> List[str]:
        """Split text into words"""
        normalized = self._normalize_text(text)
        return [word for word in normalized.split() if word]
    
    def _is_filler_only(self, words: List[str]) -> bool:
        """Check if all words are fillers"""
        if not words:
            return True
        return all(word in self.ignored_words for word in words)
    
    def _calculate_filler_ratio(self, words: List[str]) -> float:
        """Calculate ratio of filler words to total words"""
        if not words:
            return 1.0
        filler_count = sum(1 for word in words if word in self.ignored_words)
        return filler_count / len(words)
    
    async def should_interrupt_agent(
        self,
        transcription: str,
        confidence: Optional[float] = None,
        is_final: bool = True
    ) -> InterruptionDecision:
        """
        Analyze user speech and decide whether to interrupt the agent.
        
        Args:
            transcription: Transcribed text from user
            confidence: ASR confidence score (0.0-1.0)
            is_final: Whether this is a final transcription
        
        Returns:
            InterruptionDecision with analysis results
        """
        async with self._lock:
            self.stats['total_interruptions'] += 1
            
            # If agent is not speaking, always allow (register as valid speech)
            if not self._agent_is_speaking:
                decision = InterruptionDecision(
                    should_interrupt=True,
                    interruption_type=InterruptionType.VALID,
                    confidence=confidence or 1.0,
                    detected_words=self._tokenize(transcription),
                    reason="Agent not speaking - all input valid"
                )
                self._log_decision(transcription, decision)
                return decision
            
            # Check confidence threshold
            if confidence is not None and confidence < self.confidence_threshold:
                decision = InterruptionDecision(
                    should_interrupt=False,
                    interruption_type=InterruptionType.UNCERTAIN,
                    confidence=confidence,
                    detected_words=self._tokenize(transcription),
                    reason=f"Low confidence ({confidence:.2f} < {self.confidence_threshold})"
                )
                self.stats['filtered_fillers'] += 1
                self._log_decision(transcription, decision)
                return decision
            
            # Tokenize and analyze content
            words = self._tokenize(transcription)
            
            if not words:
                decision = InterruptionDecision(
                    should_interrupt=False,
                    interruption_type=InterruptionType.UNCERTAIN,
                    confidence=confidence or 0.0,
                    detected_words=[],
                    reason="Empty transcription"
                )
                self.stats['filtered_fillers'] += 1
                self._log_decision(transcription, decision)
                return decision
            
            # Check if all words are fillers
            if self._is_filler_only(words):
                decision = InterruptionDecision(
                    should_interrupt=False,
                    interruption_type=InterruptionType.FILLER,
                    confidence=confidence or 1.0,
                    detected_words=words,
                    reason=f"All words are fillers: {words}"
                )
                self.stats['filtered_fillers'] += 1
                self._log_decision(transcription, decision)
                return decision
            
            # Calculate filler ratio for mixed content
            filler_ratio = self._calculate_filler_ratio(words)
            
            # If mostly fillers but some real content, check threshold
            if filler_ratio > (1.0 - self.mixed_content_threshold):
                # High filler ratio, but not 100% - could be "umm okay stop"
                # Allow interrupt if there's ANY non-filler content
                decision = InterruptionDecision(
                    should_interrupt=True,
                    interruption_type=InterruptionType.MIXED,
                    confidence=confidence or 1.0,
                    detected_words=words,
                    reason=f"Mixed content with valid words (filler ratio: {filler_ratio:.2f})"
                )
                self.stats['mixed_content'] += 1
                self._log_decision(transcription, decision)
                return decision
            
            # Real interruption detected
            decision = InterruptionDecision(
                should_interrupt=True,
                interruption_type=InterruptionType.VALID,
                confidence=confidence or 1.0,
                detected_words=words,
                reason=f"Valid interruption: {words}"
            )
            self.stats['valid_interrupts'] += 1
            self._log_decision(transcription, decision)
            return decision
    
    def _log_decision(self, transcription: str, decision: InterruptionDecision):
        """Log interruption decision for debugging"""
        if self.enable_logging:
            logger.info(
                f"Interruption Analysis | "
                f"Text: '{transcription}' | "
                f"Type: {decision.interruption_type.value} | "
                f"Interrupt: {decision.should_interrupt} | "
                f"Confidence: {decision.confidence:.2f} | "
                f"Reason: {decision.reason} | "
                f"Agent Speaking: {self._agent_is_speaking}"
            )
    
    def get_statistics(self) -> dict:
        """Get handler statistics"""
        total = self.stats['total_interruptions']
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            'filter_rate': self.stats['filtered_fillers'] / total,
            'valid_rate': self.stats['valid_interrupts'] / total,
            'mixed_rate': self.stats['mixed_content'] / total
        }
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'total_interruptions': 0,
            'filtered_fillers': 0,
            'valid_interrupts': 0,
            'mixed_content': 0
        }


# Example integration wrapper for LiveKit agent
class LiveKitInterruptionWrapper:
    """
    Wrapper to integrate InterruptionHandler with LiveKit agent callbacks.
    """
    
    def __init__(
        self,
        handler: IntelligentInterruptionHandler,
        on_valid_interrupt: Optional[Callable] = None
    ):
        """
        Initialize wrapper.
        
        Args:
            handler: The interruption handler instance
            on_valid_interrupt: Callback for valid interruptions
        """
        self.handler = handler
        self.on_valid_interrupt = on_valid_interrupt
    
    async def on_tts_started(self):
        """Called when agent TTS starts"""
        self.handler.set_agent_speaking_state(True)
    
    async def on_tts_stopped(self):
        """Called when agent TTS stops"""
        self.handler.set_agent_speaking_state(False)
    
    async def on_user_transcription(
        self,
        transcription: str,
        confidence: Optional[float] = None,
        is_final: bool = True
    ):
        """
        Called when user transcription is available.
        
        Args:
            transcription: Transcribed text
            confidence: ASR confidence score
            is_final: Whether this is a final transcription
        
        Returns:
            True if agent should be interrupted, False otherwise
        """
        decision = await self.handler.should_interrupt_agent(
            transcription=transcription,
            confidence=confidence,
            is_final=is_final
        )
        
        if decision.should_interrupt and self.on_valid_interrupt:
            await self.on_valid_interrupt(decision)
        
        return decision.should_interrupt