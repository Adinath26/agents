"""
Testing Suite for Intelligent Interruption Handler
Includes unit tests and scenario-based validation
"""

"""
Testing Suite for Intelligent Interruption Handler
Includes unit tests and scenario-based validation
"""

import asyncio
import sys
import os

# Add the livekit-agents package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'livekit-agents'))

import pytest
from livekit.agents.intelligent_interruption_handler import (
    IntelligentInterruptionHandler,
    InterruptionType
)


class TestIntelligentInterruptionHandler:
    """Unit tests for interruption handler"""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance for testing"""
        return IntelligentInterruptionHandler(
            ignored_words=['uh', 'um', 'umm', 'hmm', 'haan'],
            confidence_threshold=0.6,
            mixed_content_threshold=0.3,
            enable_logging=True
        )
    
    @pytest.mark.asyncio
    async def test_filler_while_agent_speaking(self, handler):
        """Test: User filler while agent speaks → ignored"""
        handler.set_agent_speaking_state(True)
        
        test_cases = [
            "uh",
            "umm",
            "hmm",
            "uh hmm",
            "umm uh",
        ]
        
        for text in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=0.9)
            assert not decision.should_interrupt, f"Should ignore filler: {text}"
            assert decision.interruption_type == InterruptionType.FILLER
    
    @pytest.mark.asyncio
    async def test_valid_interruption_while_agent_speaking(self, handler):
        """Test: Real interruption while agent speaks → interrupt"""
        handler.set_agent_speaking_state(True)
        
        test_cases = [
            "wait",
            "stop",
            "wait one second",
            "no not that one",
            "hold on",
            "can you repeat that",
        ]
        
        for text in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=0.9)
            assert decision.should_interrupt, f"Should interrupt for: {text}"
            assert decision.interruption_type == InterruptionType.VALID
    
    @pytest.mark.asyncio
    async def test_filler_while_agent_quiet(self, handler):
        """Test: User filler while agent quiet → registered as speech"""
        handler.set_agent_speaking_state(False)
        
        test_cases = ["uh", "umm", "hmm"]
        
        for text in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=0.9)
            assert decision.should_interrupt, f"Should register speech when quiet: {text}"
            # Type is VALID when agent is not speaking
            assert decision.interruption_type == InterruptionType.VALID
    
    @pytest.mark.asyncio
    async def test_mixed_filler_and_command(self, handler):
        """Test: Mixed filler and command → interrupt"""
        handler.set_agent_speaking_state(True)
        
        test_cases = [
            "umm okay stop",
            "uh wait a second",
            "hmm no that's wrong",
            "uh uh hold on",
        ]
        
        for text in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=0.9)
            assert decision.should_interrupt, f"Should interrupt for mixed: {text}"
            assert decision.interruption_type in [InterruptionType.MIXED, InterruptionType.VALID]
    
    @pytest.mark.asyncio
    async def test_low_confidence_filtering(self, handler):
        """Test: Low confidence background noise → ignored"""
        handler.set_agent_speaking_state(True)
        
        test_cases = [
            ("hmm yeah", 0.3),
            ("uh huh", 0.4),
            ("background noise", 0.2),
        ]
        
        for text, confidence in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=confidence)
            assert not decision.should_interrupt, f"Should ignore low confidence: {text}"
            assert decision.interruption_type == InterruptionType.UNCERTAIN
    
    @pytest.mark.asyncio
    async def test_empty_transcription(self, handler):
        """Test: Empty or whitespace transcription → ignored"""
        handler.set_agent_speaking_state(True)
        
        test_cases = ["", "   ", "\n\t"]
        
        for text in test_cases:
            decision = await handler.should_interrupt_agent(text, confidence=0.9)
            assert not decision.should_interrupt
    
    @pytest.mark.asyncio
    async def test_dynamic_word_update(self, handler):
        """Test: Dynamic update of ignored words"""
        handler.set_agent_speaking_state(True)
        
        # Initially "okay" should interrupt
        decision = await handler.should_interrupt_agent("okay", confidence=0.9)
        assert decision.should_interrupt
        
        # Add "okay" to ignored list
        handler.update_ignored_words(["okay"], append=True)
        
        # Now "okay" should be ignored
        decision = await handler.should_interrupt_agent("okay", confidence=0.9)
        assert not decision.should_interrupt
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, handler):
        """Test: Statistics are properly tracked"""
        handler.reset_statistics()
        handler.set_agent_speaking_state(True)
        
        # Generate various interruptions
        await handler.should_interrupt_agent("uh", confidence=0.9)  # Filler
        await handler.should_interrupt_agent("stop", confidence=0.9)  # Valid
        await handler.should_interrupt_agent("umm wait", confidence=0.9)  # Mixed
        
        stats = handler.get_statistics()
        assert stats['total_interruptions'] == 3
        assert stats['filtered_fillers'] == 1
        assert stats['valid_interrupts'] >= 1


# Scenario-based testing
async def run_scenario_tests():
    """Run real-world scenario tests"""
    
    handler = IntelligentInterruptionHandler(
        ignored_words=['uh', 'um', 'umm', 'hmm', 'haan', 'ah'],
        confidence_threshold=0.6,
        enable_logging=True
    )
    
    print("\n" + "="*60)
    print("SCENARIO TESTING")
    print("="*60)
    
    # Scenario 1: Casual conversation with fillers
    print("\n[Scenario 1] Casual conversation with fillers")
    handler.set_agent_speaking_state(True)
    
    test_inputs = [
        ("uh", 0.85, False),
        ("hmm", 0.90, False),
        ("wait can you explain that again", 0.92, True),
    ]
    
    for text, confidence, expected in test_inputs:
        decision = await handler.should_interrupt_agent(text, confidence=confidence)
        result = "✓" if decision.should_interrupt == expected else "✗"
        print(f"  {result} '{text}' (conf: {confidence}) → Interrupt: {decision.should_interrupt} (Expected: {expected})")
    
    # Scenario 2: Quick back-and-forth
    print("\n[Scenario 2] Quick back-and-forth dialogue")
    
    dialogue = [
        (True, "Did you know that...", None, False),  # Agent speaking
        (True, "uh huh", 0.88, False),  # User: filler
        (True, "the capital of...", None, False),  # Agent continues
        (True, "wait stop", 0.95, True),  # User: real interrupt
        (False, "okay go ahead", 0.90, True),  # Agent quiet
    ]
    
    for agent_speaking, text, confidence, expected in dialogue:
        handler.set_agent_speaking_state(agent_speaking)
        if text and confidence:
            decision = await handler.should_interrupt_agent(text, confidence=confidence)
            result = "✓" if decision.should_interrupt == expected else "✗"
            agent_state = "AGENT" if agent_speaking else "QUIET"
            print(f"  {result} [{agent_state}] '{text}' → {decision.interruption_type.value}")
    
    # Scenario 3: Multilingual fillers
    print("\n[Scenario 3] Hindi + English mixed")
    handler.update_ignored_words(['achha', 'theek', 'haan', 'matlab'], append=True)
    handler.set_agent_speaking_state(True)
    
    multilingual_tests = [
        ("haan", 0.90, False),  # Hindi filler
        ("theek hai", 0.88, False),  # Hindi filler phrase
        ("wait ruko", 0.92, True),  # Mixed command
    ]
    
    for text, confidence, expected in multilingual_tests:
        decision = await handler.should_interrupt_agent(text, confidence=confidence)
        result = "✓" if decision.should_interrupt == expected else "✗"
        print(f"  {result} '{text}' → Interrupt: {decision.should_interrupt}")
    
    # Print statistics
    print("\n" + "-"*60)
    print("STATISTICS")
    print("-"*60)
    stats = handler.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2%}")
        else:
            print(f"  {key}: {value}")
    print("="*60 + "\n")


# Performance testing
async def run_performance_tests():
    """Test handler performance under load"""
    
    handler = IntelligentInterruptionHandler(enable_logging=False)
    handler.set_agent_speaking_state(True)
    
    print("\n" + "="*60)
    print("PERFORMANCE TESTING")
    print("="*60)
    
    # Test rapid succession
    import time
    
    test_phrases = [
        "uh", "umm", "wait", "stop", "hmm",
        "no", "yes", "uh huh", "hold on", "continue"
    ] * 100  # 1000 total
    
    start_time = time.time()
    
    for phrase in test_phrases:
        await handler.should_interrupt_agent(phrase, confidence=0.85)
    
    elapsed = time.time() - start_time
    rate = len(test_phrases) / elapsed
    
    print(f"\n  Processed {len(test_phrases)} interruptions in {elapsed:.3f}s")
    print(f"  Rate: {rate:.0f} interruptions/second")
    print(f"  Average latency: {(elapsed/len(test_phrases))*1000:.2f}ms")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    # Run scenario tests
    asyncio.run(run_scenario_tests())
    
    # Run performance tests
    asyncio.run(run_performance_tests())
    
    print("\nTo run unit tests, use: pytest test_interruption_handler.py")