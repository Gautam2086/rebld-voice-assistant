# Bob & Alice -Home Renovation Voice Assistant

A CLI push-to-talk voice assistant with two agents that can seamlessly transfer conversations while maintaining full context.

- **Bob** (Intake & Planner) -Friendly, asks clarifying questions, produces checklists and plans.
- **Alice** (Technical Specialist) -Structured, risk-aware, handles permits, costs, materials, sequencing.

## Setup

### 1. Install dependencies

```bash
cd rebld-voice-assistant
pip3 install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env with your keys:
#   OPENROUTER_API_KEY  -for LLM (GPT-4o-mini via OpenRouter)
#   DEEPGRAM_API_KEY    -for speech-to-text (nova-3)
#   OPENAI_API_KEY      -for text-to-speech
```

### 3. Run

```bash
python3 main.py
```

## How to Use

1. Press **Enter** to start recording
2. Speak into your mic
3. Press **Enter** again to stop recording
4. Listen to the agent's response

## Demo Phrases

### Test 1 -Intake (Bob)
> "Hi Bob, I want to remodel my kitchen. Budget is around $25k. I want new cabinets and countertops, and maybe open up a wall."

Bob will ask clarifying questions and suggest a checklist.

### Test 2 -Transfer to Alice
> "Transfer me to Alice."

Alice greets with full context, addresses the wall risk, outlines steps.

### Test 3 -Transfer back to Bob
> "Go back to Bob."

Bob resumes with context from both agents, produces a next-steps list.

### Edge Cases
- `"Transfer me"` -transfers to the other agent automatically
- `"Transfer me to Charlie"` -responds that Charlie isn't available
- `"Transfer me to Bob"` -responds that you're already talking to Bob

## Architecture

See [DESIGN.md](DESIGN.md) for architecture diagram, transfer detection approach, and tradeoffs.
