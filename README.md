# Voice-Controlled AI Assistant with Tool Calling

A voice-controlled AI assistant that understands natural language commands, generates structured execution plans, maintains persistent memory using SQLite, and safely performs local filesystem operations through an allow-listed tool registry.

---

## What it does

Personal Cognitive OS listens to natural language voice commands and:

1. Understands user intent using a hybrid intent classifier and LLM planner  
2. Decomposes goals into structured execution plans  
3. Normalizes and grounds plans into safe, real system actions  
4. Requires explicit user confirmation before executing filesystem changes  
5. Executes tools locally using a secure allow-listed registry  
6. Stores persistent memory across sessions using SQLite  
7. Remembers context such as last accessed folder for natural follow-up commands  

---

## Core Architecture

```text
Perception Layer
Voice (Whisper – local, offline)
↓
Intent Layer
Intent classifier (fast routing)
↓
Memory Layer
Context memory + Persistent SQLite memory
↓
Planning Layer
Gemini LLM + Structured JSON planning (LangGraph)
↓
Validation Layer
Plan normalization, grounding, and safety enforcement
↓
Confirmation Layer
User approval checkpoint (voice or keyboard)
↓
Execution Layer
Defensive local tools (filesystem operations)
↓
Feedback Layer
Execution results and context update
```

---

## Current Features

### Voice & Perception
- 🎙️ Offline voice recognition using Faster-Whisper
- Noise filtering and speech normalization
- Fully local speech processing

### Intent & Planning
- 🧠 Hybrid intent classification (fast routing + LLM planning)
- 📋 Structured JSON planning using Gemini + Pydantic
- 🧩 Multi-step task decomposition using LangGraph

### Memory System
- 🧠 Session memory for contextual commands ("open it")
- 💾 Persistent memory using SQLite (`memory.db`)
- 🔁 Cross-session context retention
- 🧭 Automatic last-path tracking and reuse

### Safety & Validation
- 🛡️ Strict tool allow-list registry
- 🧭 Path grounding (prevents hallucinated filesystem paths)
- 🔧 Argument normalization and correction
- ❌ Blocks unknown or unsafe operations automatically

### Confirmation Layer (Critical Safety Feature)
- ✅ Explicit confirmation required before execution
- 🎙️ Voice confirmation ("yes/no")
- ⌨️ Keyboard fallback confirmation
- 🔁 Retry handling for unclear speech
- 📊 Impact preview showing operations and affected locations

### Execution Layer
- 📂 Folder organization by file type
- 📁 Folder creation
- 📄 File movement and categorization
- 📂 Folder opening
- ⚙️ Safe local filesystem execution

---

## Example

User says:

> "Organize my downloads folder"

System generates structured plan:

```json
{
  "goal": "Organize my downloads folder",
  "steps": [
    {"tool": "scan_folder", "args": {"path": "~/Downloads"}},
    {"tool": "create_folder", "args": {"path": "~/Downloads/documents"}},
    {"tool": "move_file", "args": {
      "source_directory": "~/Downloads",
      "destination_directory": "~/Downloads/documents",
      "file_pattern": "*.pdf"
    }}
  ]
}
```

Agent shows confirmation preview:

```text
This will execute 10 operation(s)
It will move 5 file(s)

Affected locations:
~/Downloads
~/Downloads/documents
```

After approval, execution runs safely.

---

## Natural Language Context Example

```text
User: Open my agent test folder
Agent: Opens folder

(restart agent)

User: Open it
Agent: Opens same folder using persistent memory
```

---

## Tech Stack

- Python 3.11+
- Faster-Whisper (offline speech recognition)
- LangGraph (execution graph orchestration)
- LangChain (LLM integration)
- Gemini API (planning)
- Pydantic (structured output validation)
- SQLite (persistent memory)
- OS filesystem tools (safe local execution)

---

## Project Structure

```text
cognitive-os-agent/

voice/          # speech perception
planner/        # intent + LLM planning graph
tools/          # execution tools and validator
memory/         # context and persistent memory
main.py         # cognitive loop entry point
memory.db       # persistent memory database (ignored in git)
```

---

## Safety Architecture

The agent enforces multiple safety layers:

```text
Intent filtering
↓
Tool allow-list enforcement
↓
Path grounding
↓
Plan validation
↓
User confirmation
↓
Execution
```

Execution cannot occur without passing all safety gates.

---

## Current Capabilities

Supported commands:

```text
Organize my downloads folder
Open my documents folder
Open it
Exit
```

The agent understands contextual references and maintains state across sessions.

---

## Persistent Memory

The agent uses SQLite for durable memory storage:

```text
memory.db
```

Stores:

- last_path
- last_action
- future: preferences, history, learning data

This enables cross-session cognitive continuity.

---

## Status

Stable cognitive agent baseline achieved with:

- End-to-end voice → intent → planning → confirmation → execution pipeline
- Persistent memory support
- Safety validation and confirmation layer
- Context-aware execution

---

## Roadmap

### Phase 1 (In Progress)

- File search capability
- Enhanced confirmation with file previews
- Improved intent resolution

### Phase 2

- Long-term memory expansion
- Task history and reflection
- Context-aware reasoning

### Phase 3

- Fully autonomous multi-step goal execution
- Learning from user behavior
- Self-improving planning

---

## Vision

This project aims to become a true cognitive operating system layer capable of:

- Persistent memory
- Autonomous task planning
- Safe execution
- Context awareness
- Continuous learning

---

## Inspired by

- AutoGPT
- BabyAGI
- OpenAI function calling
- Cognitive architectures
- Autonomous agent systems
