from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandoffNote:
    from_agent: str
    to_agent: str
    summary: str
    key_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = [
            f"=== Handoff from {self.from_agent} to {self.to_agent} ===",
            f"Summary: {self.summary}",
        ]
        if self.key_facts:
            lines.append("Key facts:")
            lines.extend(f"  - {f}" for f in self.key_facts)
        if self.open_questions:
            lines.append("Open questions:")
            lines.extend(f"  - {q}" for q in self.open_questions)
        if self.recommendations:
            lines.append("Recommendations:")
            lines.extend(f"  - {r}" for r in self.recommendations)
        return "\n".join(lines)


@dataclass
class ConversationState:
    active_agent: str = "Bob"
    history: list[dict[str, str]] = field(default_factory=list)
    handoff_notes: list[HandoffNote] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def handoff_context(self) -> str:
        if not self.handoff_notes:
            return ""
        return "\n\n".join(note.format() for note in self.handoff_notes)
