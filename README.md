# LiveKit Intelligent Interruption Handler – Challenge Submission

## 👤 Author
**Adinath Balasaheb Kulkarni**  
Email: kulkarniadinath2804@gmail.com

---

## 🚀 Overview
This project adds an **intelligent interruption-handling module** to LiveKit Agents that distinguishes between filler words and genuine user interruptions during real-time conversations.

The solution prevents false interruptions caused by filler sounds (e.g., "uh", "umm", "hmm", "haan") while ensuring real commands like "wait" or "stop" interrupt the agent immediately.

This creates a more natural, seamless conversational experience.

---

## 🎯 Problem Statement
LiveKit's Voice Activity Detection (VAD) automatically pauses the agent's TTS when it detects any user speech. However, common filler words and backchanneling sounds cause unwanted interruptions, breaking the conversation flow.

**Challenge:** Filter out meaningless fillers while preserving genuine interruptions in real-time.

---

## ✨ Solution Features

### ✅ **Intelligent Filler Detection**
- Filters configurable list of filler words (`uh`, `um`, `umm`, `hmm`, `haan`, etc.)
- Only filters during agent speech (context-aware)
- Allows same words when agent is quiet

### ✅ **Real-Time Interruption Handling**
- Detects genuine commands (`stop`, `wait`, `no`, `pause`)
- Immediate agent interruption (<1ms decision latency)
- Mixed content support (e.g., "umm okay stop" → interrupts)

### ✅ **Confidence-Based Filtering**
- Filters low-confidence background noise
- Configurable confidence threshold (default: 0.6)
- Prevents false positives from ambient sounds

### ✅ **Multi-Language Support**
- Language-agnostic design
- Supports English + Hindi fillers (tested)
- Easy to extend to any language

### ✅ **Production-Ready**
- Thread-safe async operations
- No LiveKit SDK modifications (pure extension layer)
- Comprehensive logging and statistics
- Dynamic configuration updates

---

## 🏗️ Architecture

### Core Components

**1. `IntelligentInterruptionHandler`**
- Main decision logic
- State management (agent speaking/quiet)
- Filler word classification
- Statistics tracking

**2. `LiveKitInterruptionWrapper`**
- LiveKit event integration
- TTS lifecycle management
- Callback coordination

**3. `InterruptionDecision`**
- Structured decision results
- Classification metadata
- Reasoning transparency

### Decision Flow
