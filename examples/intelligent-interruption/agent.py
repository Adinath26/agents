"""
Complete LiveKit Agent Integration Example
Shows how to integrate the IntelligentInterruptionHandler with a LiveKit agent
"""

import asyncio
import logging
import os
from typing import Optional
from livekit import agents, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import openai, deepgram, silero

# Import our handler (assume it's in intelligent_interruption_handler.py)
from intelligent_interruption_handler import (
    IntelligentInterruptionHandler,
    LiveKitInterruptionWrapper,
    InterruptionDecision
)

logger = logging.getLogger(__name__)


class VoiceAssistant:
    """Voice assistant with intelligent interruption handling"""
    
    def __init__(self, context: JobContext):
        self.context = context
        
        # Initialize interruption handler with configuration
        ignored_words = self._load_ignored_words()
        self.interrupt_handler = IntelligentInterruptionHandler(
            ignored_words=ignored_words,
            confidence_threshold=float(os.getenv('INTERRUPT_CONFIDENCE_THRESHOLD', '0.6')),
            mixed_content_threshold=float(os.getenv('INTERRUPT_MIXED_THRESHOLD', '0.3')),
            enable_logging=True
        )
        
        # Create wrapper for LiveKit callbacks
        self.interrupt_wrapper = LiveKitInterruptionWrapper(
            handler=self.interrupt_handler,
            on_valid_interrupt=self._handle_valid_interrupt
        )
        
        # Agent components
        self.assistant: Optional[agents.VoiceAssistant] = None
        self.chat_context = agents.ChatContext()
        
    def _load_ignored_words(self) -> list[str]:
        """Load ignored words from environment or config"""
        # Check environment variable first
        env_words = os.getenv('IGNORED_FILLER_WORDS', '')
        if env_words:
            return [w.strip() for w in env_words.split(',') if w.strip()]
        
        # Default filler words (English + Hindi)
        return [
            # English fillers
            'uh', 'um', 'umm', 'hmm', 'ah', 'er', 'like', 'you know',
            'i mean', 'sort of', 'kind of',
            # Hindi fillers
            'haan', 'achha', 'theek', 'matlab', 'woh', 'yaar'
        ]
    
    async def _handle_valid_interrupt(self, decision: InterruptionDecision):
        """Called when a valid interruption is detected"""
        logger.info(
            f"Valid interruption detected: {decision.detected_words} "
            f"(type: {decision.interruption_type.value})"
        )
        
        # Stop agent TTS if speaking
        if self.assistant and self.assistant.is_speaking:
            await self.assistant.cancel_response()
    
    async def start(self, room: rtc.Room):
        """Start the voice assistant"""
        
        # Initialize plugins
        stt = deepgram.STT(
            model="nova-2-conversationalai",
            language="en-US",  # Configure based on requirements
        )
        
        llm = openai.LLM(
            model="gpt-4-turbo-preview",
        )
        
        tts = openai.TTS(
            voice="alloy",
        )
        
        # Create voice assistant with custom interruption handling
        self.assistant = agents.VoiceAssistant(
            stt=stt,
            llm=llm,
            tts=tts,
            chat_ctx=self.chat_context,
            will_synthesize_assistant_reply=self._intercept_synthesis,
        )
        
        # Hook into assistant events
        self._setup_event_handlers()
        
        # Start the assistant
        self.assistant.start(room)
        
        # Initial greeting
        await self.assistant.say("Hello! How can I help you today?", allow_interruptions=True)
    
    def _setup_event_handlers(self):
        """Setup event handlers for TTS and transcription events"""
        
        @self.assistant.on("agent_started_speaking")
        async def on_agent_started():
            await self.interrupt_wrapper.on_tts_started()
        
        @self.assistant.on("agent_stopped_speaking")
        async def on_agent_stopped():
            await self.interrupt_wrapper.on_tts_stopped()
        
        @self.assistant.on("user_speech_committed")
        async def on_user_speech(ev: agents.vad.VADEvent):
            # Process transcription through our handler
            # Note: This integrates with LiveKit's existing VAD
            pass  # Handled in _intercept_synthesis
    
    async def _intercept_synthesis(
        self,
        *,
        agent: agents.VoiceAssistant,
        speech: agents.llm.LLMStream
    ) -> agents.llm.LLMStream:
        """
        Intercept synthesis to check for interruptions during speech.
        This is called before TTS begins.
        """
        # You can add pre-synthesis logic here if needed
        return speech
    
    async def process_user_transcription(
        self,
        transcription: str,
        confidence: Optional[float] = None,
        is_final: bool = True
    ):
        """
        Process user transcription through interruption handler.
        This should be called from your STT transcription callbacks.
        
        Args:
            transcription: User's transcribed speech
            confidence: ASR confidence score
            is_final: Whether this is a final transcription
        """
        should_interrupt = await self.interrupt_wrapper.on_user_transcription(
            transcription=transcription,
            confidence=confidence,
            is_final=is_final
        )
        
        return should_interrupt


async def entrypoint(ctx: JobContext):
    """Main entrypoint for LiveKit agent"""
    
    logger.info("Starting Voice Assistant with Intelligent Interruption Handling")
    
    # Wait for participant to connect
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Get room
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")
    
    # Create and start assistant
    assistant = VoiceAssistant(ctx)
    await assistant.start(ctx.room)
    
    # Log statistics periodically
    async def log_stats():
        while True:
            await asyncio.sleep(60)  # Every minute
            stats = assistant.interrupt_handler.get_statistics()
            logger.info(f"Interruption Statistics: {stats}")
    
    # Start stats logging task
    asyncio.create_task(log_stats())


# Example custom STT wrapper with interruption handling
class InterruptionAwareSTT:
    """
    Wrapper around STT that integrates with interruption handler.
    """
    
    def __init__(self, base_stt, interrupt_handler: IntelligentInterruptionHandler):
        self.base_stt = base_stt
        self.interrupt_handler = interrupt_handler
        
    async def recognize(self, audio_stream):
        """Recognize speech with interruption filtering"""
        
        async for event in self.base_stt.recognize(audio_stream):
            # Check if this should be processed as an interruption
            decision = await self.interrupt_handler.should_interrupt_agent(
                transcription=event.alternatives[0].text,
                confidence=event.alternatives[0].confidence,
                is_final=event.is_final
            )
            
            # Modify event based on decision
            if not decision.should_interrupt and self.interrupt_handler._agent_is_speaking:
                # Filter out this transcription - don't yield it
                logger.debug(f"Filtered filler transcription: {event.alternatives[0].text}")
                continue
            
            # Yield valid transcription
            yield event


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the agent
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))