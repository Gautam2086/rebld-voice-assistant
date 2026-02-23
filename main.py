"""Bob & Alice Voice Assistant — CLI push-to-talk with agent transfer."""

import sys

from agents import get_voice, respond
from stt import transcribe
from state import ConversationState
from transfer import detect_agent_suggestion, detect_transfer, generate_handoff_note
from tts import synthesize
from voice import play_audio, record_audio


def print_banner():
    print("\n" + "=" * 55)
    print("  🏠  Bob & Alice — Home Renovation Voice Assistant")
    print("=" * 55)
    print("  Press Enter to start/stop recording.")
    print('  Say "transfer me to Alice/Bob" to switch agents.')
    print('  Type "quit" or Ctrl+C to exit.')
    print("=" * 55 + "\n")


def handle_transfer(state: ConversationState, target: str) -> str:
    """Execute a transfer: generate handoff note, switch agent, return greeting."""
    old_agent = state.active_agent
    print(f"\n  📋 Generating handoff note from {old_agent}...")

    # Generate structured handoff note via LLM
    note = generate_handoff_note(state, target)
    state.handoff_notes.append(note)

    print(f"  ✅ Handoff note created:")
    print(f"     Summary: {note.summary}")
    if note.key_facts:
        print(f"     Facts: {', '.join(note.key_facts[:3])}")

    # Switch agent
    state.active_agent = target

    # Generate context-aware greeting from new agent
    state.add_message(
        "system",
        f"You are now taking over from {old_agent}. "
        f"Greet the user, reference what was discussed, and continue helping. "
        f"Here is the handoff note:\n{note.format()}",
    )

    greeting = respond(state)
    state.add_message("assistant", greeting)
    return greeting


def main():
    print_banner()
    state = ConversationState()

    while True:
        agent = state.active_agent
        voice = get_voice(agent)
        print(f"\n  [{agent}] Press Enter to speak (or type 'quit')...", end=" ")

        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 Goodbye!")
            break

        if line.strip().lower() in ("quit", "exit", "q"):
            print("  👋 Goodbye!")
            break

        # Record audio
        wav = record_audio()
        if not wav:
            print("  ⚠️  No audio recorded.")
            continue

        # Transcribe
        print("  📝 Transcribing...")
        text = transcribe(wav)
        if not text.strip():
            print("  ⚠️  Couldn't understand that. Try again.")
            continue
        print(f"  You: {text}")

        # Check for transfer intent
        transfer = detect_transfer(text, state.active_agent)

        if transfer.reason == "invalid":
            msg = f"I don't know an agent named {transfer.target}. I can transfer you to {'Alice' if agent == 'Bob' else 'Bob'}."
            print(f"  [{agent}]: {msg}")
            audio = synthesize(msg, voice)
            play_audio(audio)
            continue

        if transfer.reason == "self":
            msg = f"You're already talking to {agent}! How can I help?"
            print(f"  [{agent}]: {msg}")
            audio = synthesize(msg, voice)
            play_audio(audio)
            continue

        if transfer.should_transfer:
            target = transfer.target
            # Farewell from current agent
            farewell = f"Sure! Let me transfer you to {target} now."
            print(f"  [{agent}]: {farewell}")
            audio = synthesize(farewell, voice)
            play_audio(audio)

            # Execute transfer
            state.add_message("user", text)
            greeting = handle_transfer(state, target)
            new_voice = get_voice(target)
            print(f"  [{target}]: {greeting}")
            audio = synthesize(greeting, new_voice)
            play_audio(audio)
            continue

        # Normal conversation
        state.add_message("user", text)
        print(f"  🤔 {agent} is thinking...")
        response = respond(state)
        state.add_message("assistant", response)

        # Check if agent suggests transfer
        suggestion = detect_agent_suggestion(response, state.active_agent)
        if suggestion.reason == "agent_suggested":
            print(f"  💡 {agent} suggested transferring to {suggestion.target}")

        print(f"  [{agent}]: {response}")
        audio = synthesize(response, voice)
        play_audio(audio)


if __name__ == "__main__":
    main()
