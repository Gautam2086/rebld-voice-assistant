import json
import re
from dataclasses import dataclass

from openai import OpenAI

from config import settings
from state import ConversationState, HandoffNote

AGENT_NAMES = {"bob", "alice"}


@dataclass
class TransferResult:
    should_transfer: bool
    target: str = ""
    reason: str = ""  # "explicit", "agent_suggested", "ambiguous", "invalid", "self"


def detect_transfer(text: str, current_agent: str) -> TransferResult:
    """Regex-first intent detection -<1ms vs ~800ms for an LLM classifier.
    Tradeoff: won't catch implicit intent like 'I have a question about permits',
    but keeps the voice loop snappy. See DESIGN.md for more on this decision."""
    lower = text.lower().strip()

    # Explicit: "transfer me to Alice", "let me talk to Bob", "go back to Bob"
    explicit = re.search(
        r"(?:transfer\s+(?:me\s+)?to|switch\s+(?:me\s+)?to|"
        r"let\s+me\s+talk\s+to|go\s+(?:back\s+)?to|"
        r"connect\s+me\s+(?:to|with)|put\s+me\s+(?:through\s+)?to|"
        r"i\s+(?:want|need)\s+(?:to\s+(?:talk|speak)\s+(?:to|with)))\s+"
        r"(\w+)",
        lower,
    )

    if explicit:
        name = explicit.group(1).strip().rstrip(".,!?")
        # Invalid agent
        if name not in AGENT_NAMES:
            return TransferResult(
                should_transfer=False,
                target=name,
                reason="invalid",
            )
        # Self-transfer
        if name.lower() == current_agent.lower():
            return TransferResult(
                should_transfer=False,
                target=name,
                reason="self",
            )
        return TransferResult(
            should_transfer=True,
            target=name.capitalize(),
            reason="explicit",
        )

    # Ambiguous: "transfer me" with no name
    ambiguous = re.search(
        r"(?:transfer\s+me|switch\s+(?:agents?|me)|"
        r"talk\s+to\s+(?:the\s+)?(?:other|someone\s+else))",
        lower,
    )
    if ambiguous:
        # Infer: transfer to the other agent
        other = "Alice" if current_agent == "Bob" else "Bob"
        return TransferResult(
            should_transfer=True,
            target=other,
            reason="ambiguous",
        )

    return TransferResult(should_transfer=False)


def detect_agent_suggestion(response_text: str, current_agent: str) -> TransferResult:
    """Check if the agent's response suggests transferring to the other agent."""
    lower = response_text.lower()

    # Patterns like "Want me to transfer you?" or "Alice can help with that"
    other = "alice" if current_agent == "Bob" else "bob"

    suggestion_patterns = [
        rf"transfer\s+you\s+to\s+{other}",
        rf"(?:want|shall|should)\s+(?:me\s+)?(?:to\s+)?transfer",
        rf"{other}\s+(?:can|could|would)\s+(?:help|assist|give|handle)",
        rf"(?:bring|get|connect)\s+{other}",
    ]

    for pattern in suggestion_patterns:
        if re.search(pattern, lower):
            return TransferResult(
                should_transfer=False,  # don't auto-transfer, just flag it
                target=other.capitalize(),
                reason="agent_suggested",
            )

    return TransferResult(should_transfer=False)


_handoff_client = None


def generate_handoff_note(state: ConversationState, target: str) -> HandoffNote:
    """Use LLM to generate a structured handoff note from conversation history."""
    global _handoff_client
    if _handoff_client is None:
        _handoff_client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

    # Build conversation summary for the LLM
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.history[-20:]
    )

    prompt = f"""Analyze this conversation between the user and {state.active_agent}, and create a handoff summary for {target}.
Focus on NEW information from {state.active_agent}'s portion of the conversation -what was discussed, decided, or advised. Do not just repeat facts from earlier agents.
Return ONLY valid JSON with these fields:
{{
  "summary": "1-2 sentence summary of what {state.active_agent} covered",
  "key_facts": ["new facts learned or confirmed"],
  "open_questions": ["unresolved questions remaining"],
  "recommendations": ["{state.active_agent}'s advice or next steps"]
}}

Conversation:
{conv_text}"""

    resp = _handoff_client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3,
    )

    raw = resp.choices[0].message.content.strip()
    parsed = _extract_json(raw)

    return HandoffNote(
        from_agent=state.active_agent,
        to_agent=target,
        summary=parsed.get("summary", "Conversation handoff"),
        key_facts=parsed.get("key_facts", []),
        open_questions=parsed.get("open_questions", []),
        recommendations=parsed.get("recommendations", []),
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(lines)

    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            pass

    return {"summary": text[:200]}
