# LiveKit Voice Interruption Handling – Challenge Submission

## 👤 Author
Adinath

## 🚀 Overview
This project adds an interruption-handling module to LiveKit Agents.  
The goal is to stop false interruptions caused by filler words (e.g., “uh”, “umm”, “hmm”, “haan”) during TTS playback, while still detecting real user interruptions instantly.

This improves the natural flow of real-time AI conversations.

---

# 🎯 Objective
LiveKit’s default VAD stops the agent anytime it detects voice.  
But users often make meaningless sounds like “umm” or “hmm”, which incorrectly interrupt the AI.

This module solves that by filtering user speech intelligently.

---

# 🧠 What the Module Does

### ✅ 1. **Ignores filler words when the agent is speaking**
Examples:  
`uh`, `umm`, `hmm`, `haan` → **AI continues speaking**

### ✅ 2. **Detects genuine user interruptions**
Examples:  
`stop`, `wait`, `no`, `pause` → **AI stops immediately**

### ✅ 3. **Allows fillers when the agent is silent**
If AI is quiet and user says “umm” → recorded as valid speech

### ✅ 4. **Filters low-confidence background noise**
Quiet murmurs like “hmm yeah” → ignored if confidence is low

### ✅ 5. **Does NOT modify LiveKit SDK**
All logic is external and integrated through callback hooks.

---

# 🛠️ Implementation

The main logic is inside:

interrupt_handler.py

yaml
Copy code

It uses three callback functions supplied by the LiveKit agent:

```python
is_agent_speaking()   # returns True if TTS is active
stop_agent()          # immediately stops TTS playback
forward_speech(event) # forwards valid ASR messages to the agent pipeline
📌 Key Features:
Token classification (filler vs non-filler)

Command keyword detection

Confidence-based noise filtering

Supports dynamic updates to filler word list

Language-agnostic (filler list can be customized)

🧪 How to Test
▶️ Test 1 — Filler ignored
AI speaking → User: “uh… umm…”
Expected: AI keeps speaking

▶️ Test 2 — Real interruption
AI speaking → User: “umm okay stop”
Expected:
✔ AI stops
✔ ASR forwarded

▶️ Test 3 — Filler accepted when AI is silent
AI quiet → User: “umm”
Expected: accepted as normal speech

▶️ Test 4 — Noise removed
AI speaking → extremely low-confidence “hmm yeah”
Expected: ignored

📂 Files in This Branch
bash
Copy code
interrupt_handler.py       # Interruption filtering logic
README.md                  # This documentation
🧰 Environment
Python 3.9+

LiveKit Agents SDK

No external dependencies (only Python standard library)

Fully async-compatible

⚠️ Known Limitations
Filler tokens need to be adjusted for multilingual users

Simple tokenization (could be improved for languages like Hindi)

Depends on ASR providing text + confidence

🎉 Conclusion
This module makes LiveKit Agents more natural, responsive, and human-friendly by:

Preventing interruptions from meaningless sounds

Detecting real intentions instantly

Preserving smooth AI and user interaction flow

It works as a clean, modular extension without touching LiveKit’s internal VAD logic.
