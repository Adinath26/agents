import asyncio
from interrupt_handler import InterruptHandler

class FakeAgent:
    """Simulates agent speaking for local test."""
    def __init__(self):
        self.speaking = False

    def start_speaking(self):
        self.speaking = True
        print("🟢 Agent is speaking...")

    def stop_speaking(self):
        self.speaking = False
        print("🔴 Agent stopped speaking!")

async def fake_asr_stream(handler: InterruptHandler):
    """Simulates user speech events for testing."""

    tests = [
        {"text": "uh umm hmm", "confidence": 0.9},
        {"text": "umm wait stop", "confidence": 0.95},
        {"text": "umm", "confidence": 0.9},
        {"text": "hmm yeah", "confidence": 0.1},
    ]

    for t in tests:
        print(f"\n🎤 User said: {t['text']}")
        await handler.process_transcription(t)
        await asyncio.sleep(1)

async def main():
    agent = FakeAgent()

    # Agent starts speaking
    agent.start_speaking()

    handler = InterruptHandler(
        is_agent_speaking=lambda: agent.speaking,
        stop_agent=lambda: agent.stop_speaking(),
        forward_speech=lambda event: print("➡️ Forwarded:", event["text"]),
    )

    await fake_asr_stream(handler)


if __name__ == "__main__":
    asyncio.run(main())
