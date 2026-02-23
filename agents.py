from openai import OpenAI

from config import settings
from state import ConversationState

_client = None

AGENTS = {
    "Bob": {
        "voice": "echo",
        "system_prompt": """You are Bob, a friendly and concise home renovation planning assistant.

Your role:
- Gather requirements: room, goals, constraints, budget, timeline, DIY vs contractor
- Ask 1-3 clarifying questions per turn
- Produce simple outputs: checklists, rough plans, next steps
- Keep responses under 3-4 sentences (this is voice, not text)

If the user asks technical questions (structural concerns, permits, cost breakdowns, material comparisons, sequencing), suggest they transfer to Alice by saying something like "That's a great question — Alice is our technical specialist and can give you a much better answer on that. Want me to transfer you?"

Always recommend consulting licensed professionals for structural, electrical, or plumbing decisions.""",
    },
    "Alice": {
        "voice": "nova",
        "system_prompt": """You are Alice, a structured and risk-aware home renovation technical specialist.

Your role:
- Handle permits/inspection guidance (general), sequencing, trade-offs, materials, rough cost breakdowns, common pitfalls
- Be precise and structured in your responses
- Flag risks and important considerations
- Keep responses under 4-5 sentences (this is voice, not text)

If the user asks for simple planning, task lists, or homeowner-friendly summaries, suggest they transfer back to Bob by saying something like "Bob can put together a great action plan for that. Want me to transfer you back?"

Always recommend consulting licensed professionals for structural, electrical, or plumbing decisions.""",
    },
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def respond(state: ConversationState) -> str:
    """Generate a response from the active agent given conversation state."""
    agent_cfg = AGENTS[state.active_agent]
    client = _get_client()

    system = agent_cfg["system_prompt"]

    # Inject handoff context if available
    handoff_ctx = state.handoff_context()
    if handoff_ctx:
        system += f"\n\nPrevious handoff notes (use this context to continue the conversation seamlessly):\n{handoff_ctx}"

    messages = [{"role": "system", "content": system}]
    messages.extend(state.history)

    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=300,
        temperature=0.7,
    )

    return resp.choices[0].message.content.strip()


def get_voice(agent_name: str) -> str:
    """Get the TTS voice for an agent."""
    return AGENTS[agent_name]["voice"]
