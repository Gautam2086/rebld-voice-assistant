# Design Document — Bob & Alice Voice Assistant

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    CLI Main Loop                     │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌─────────────────┐   │
│  │  Record  │──▶│   STT    │──▶│ Transfer Detect │   │
│  │(sounddev)│   │(Deepgram)│   │    (regex)      │   │
│  └──────────┘   └──────────┘   └────────┬────────┘   │
│                                  YES    │    NO      │
│                                ┌────────┴────────┐   │
│                                ▼                 ▼   │
│                       ┌──────────────┐   ┌──────────┐│
│                       │ Handoff Note │   │  Agent   ││
│                       │  Gen (LLM)   │   │ Respond  ││
│                       └──────┬───────┘   │(OpenRtr) ││
│                              │           └────┬─────┘│
│                       ┌──────▼───────┐        │      │
│                       │ Switch Agent │        │      │
│                       │  + Greeting  │        │      │
│                       └──────┬───────┘        │      │
│                              │                │      │
│                              ▼                ▼      │
│                       ┌─────────────────────────┐    │
│                       │      TTS (OpenAI)       │    │
│                       │  Bob=echo, Alice=nova   │    │
│                       └────────────┬────────────┘    │
│                                    ▼                 │
│                       ┌─────────────────────────┐    │
│                       │   Play Audio (sounddev) │    │
│                       └─────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## File Structure

| File | Responsibility |
|------|---------------|
| `main.py` | CLI loop: record → STT → transfer check → LLM → TTS → play |
| `agents.py` | Bob/Alice system prompts, OpenRouter LLM calls |
| `transfer.py` | Transfer detection (regex), handoff note generation (LLM) |
| `voice.py` | Mic recording (sounddevice) + audio playback (wave + sounddevice) |
| `stt.py` | Deepgram REST transcription |
| `tts.py` | OpenAI TTS synthesis |
| `state.py` | ConversationState + HandoffNote dataclasses |
| `config.py` | Pydantic Settings for env vars |

## Transfer Intent Detection

### Approach: Regex-first

Transfer detection uses regex pattern matching against the user's transcribed text. This is **instant** (< 1ms) compared to an LLM classifier (500ms-1s).

**Patterns handled:**
- **Explicit:** "transfer me to Alice", "let me talk to Bob", "go back to Bob", "switch to Alice"
- **Ambiguous:** "transfer me", "switch agents", "talk to someone else" → infers the other agent
- **Self-transfer:** "transfer me to Bob" when already Bob → friendly rejection
- **Invalid agent:** "transfer me to Charlie" → tells user available agents

**Agent-initiated:** Bob and Alice have system prompts that instruct them to suggest transfers for out-of-scope questions. After the agent responds, regex checks for suggestion patterns in the response text. This doesn't auto-transfer — it's a suggestion the user can follow up on.

### Why not an LLM classifier?

An LLM call for intent classification would add 500ms-1s of latency on every turn. For a voice assistant where responsiveness matters, this overhead is unacceptable. Regex handles the common cases reliably and instantly. In production, I'd consider a small local model (e.g., distilbert fine-tuned on intent data) as a middle ground.

## State & Memory Across Transfers

### ConversationState

A single `ConversationState` object persists across the entire session:
- **`history`**: Full message history (role + content), shared across agents
- **`handoff_notes`**: Accumulating list of `HandoffNote` objects
- **`active_agent`**: Current agent name

### HandoffNote (Structured)

On transfer, the LLM generates a structured summary:
```
HandoffNote:
  from_agent: "Bob"
  to_agent: "Alice"
  summary: "Homeowner wants kitchen remodel, $25k budget..."
  key_facts: ["budget: $25k", "room: kitchen", "considering wall removal"]
  open_questions: ["Is wall load-bearing?", "Timeline?"]
  recommendations: ["Get contractor quotes", "Check permits"]
```

This is injected into the receiving agent's context, so they can greet with full awareness.

### Bidirectional Context Accumulation

The `handoff_notes` list only grows. After Bob→Alice→Bob, Bob sees **both** handoff notes — what he originally discussed AND what Alice covered. This prevents context loss across multiple transfers.

## Tradeoffs

1. **Push-to-talk vs. VAD**: Push-to-talk is simpler but less natural. Voice Activity Detection (VAD) with barge-in would be more conversational but adds complexity (silence thresholds, false triggers).

2. **REST APIs vs. streaming**: Currently using REST for both STT and TTS. Streaming would reduce time-to-first-byte significantly — Deepgram's WebSocket API provides real-time transcription, and streaming TTS could start playing while the full response is still generating.

3. **Full history vs. summarization**: The full message history is passed to the LLM on every turn. For long conversations, this hits context limits and increases cost. A sliding window with periodic summarization would be more scalable.

4. **Regex transfer detection vs. LLM**: Regex is fast but brittle. It won't catch implicit transfer intent like "I have a question about permits" (which should probably go to Alice). An LLM classifier would catch these but at a latency cost.

## Reflection

The biggest challenge was getting transfers to feel seamless. My first attempt just passed the raw conversation history to the new agent, and the result was agents repeating the same questions — clearly not a real handoff. Switching to LLM-generated handoff notes with structured fields (key_facts, open_questions, recommendations) made a big difference. It mirrors how a real contractor handoff works: you pass along a summary sheet, not a full transcript.

Latency was the other main concern. Every extra API call in the voice loop is noticeable. That's why I went with regex for transfer detection instead of an LLM classifier — it's instant and covers the common patterns well enough. In production, I'd consider a small fine-tuned model (distilbert-scale) as a middle ground: better coverage than regex without the full LLM latency hit.

The part I'm least satisfied with is the audio pipeline. Push-to-talk works, but it's not how people naturally talk. With more time, I'd move to a LiveKit-based architecture with VAD (silero-vad) for automatic speech detection, streaming STT via Deepgram's WebSocket API for real-time partials, and chunked TTS playback so the user hears the response while it's still generating. That would bring end-to-end latency from ~3-4s down to ~1-2s and support barge-in naturally.

I did add pipeline latency logging (each stage prints its timing in ms) and a session summary on exit that shows turns, transfers, handoff trail, and LLM-generated key takeaways. Small touches, but they make the experience feel more complete and give visibility into where time is spent.

Other things I'd improve with more time:
- **Conversation summarization** — periodically compress older messages to keep context manageable
- **Error recovery** — retry with backoff on API failures, fallback to text-only if TTS is down
- **Testing** — unit tests for the transfer regex, integration tests for handoff note generation
