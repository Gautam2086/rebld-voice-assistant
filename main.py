"""Bob & Alice Voice Assistant — CLI push-to-talk with agent transfer."""

import time

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


def timed(label, fn, *args, **kwargs):
    """Run a function and print how long it took."""
    t0 = time.time()
    result = fn(*args, **kwargs)
    ms = int((time.time() - t0) * 1000)
    print(f"     ⏱  {label}: {ms}ms")
    return result


def handle_transfer(state: ConversationState, target: str) -> str:
    """Execute a transfer: generate handoff note, switch agent, return greeting."""
    old_agent = state.active_agent
    print(f"\n  📋 Generating handoff note from {old_agent}...")

    note = timed("Handoff note", generate_handoff_note, state, target)
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

    greeting = timed("Greeting LLM", respond, state)
    state.add_message("assistant", greeting)
    return greeting


def print_session_summary(state: ConversationState) -> None:
    """Print a summary of the conversation when the user exits."""
    user_msgs = [m for m in state.history if m["role"] == "user"]
    if not user_msgs:
        return

    print("\n" + "=" * 55)
    print("  📊  Session Summary")
    print("=" * 55)
    print(f"  Turns: {len(user_msgs)}")
    print(f"  Transfers: {len(state.handoff_notes)}")

    if state.handoff_notes:
        print("  Handoff trail:")
        for note in state.handoff_notes:
            summary = note.summary[:80].rsplit(" ", 1)[0] + "..." if len(note.summary) > 80 else note.summary
            print(f"    {note.from_agent} → {note.to_agent}: {summary}")

    # Generate a quick wrap-up from the LLM
    from openai import OpenAI
    from config import settings

    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in state.history[-20:]
        if m["role"] in ("user", "assistant")
    )

    try:
        client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{
                "role": "user",
                "content": f"Summarize this home renovation conversation in 2-3 bullet points. "
                f"Focus on decisions made and next steps:\n{conv_text}",
            }],
            max_tokens=200,
            temperature=0.3,
        )
        summary = resp.choices[0].message.content.strip()
        # Indent each line of the summary consistently
        lines = summary.split("\n")
        print("\n  Key takeaways:")
        for line in lines:
            print(f"    {line.strip()}")
    except Exception:
        pass

    print("=" * 55 + "\n")


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
        text = timed("STT", transcribe, wav)
        if not text.strip():
            print("  ⚠️  Couldn't understand that. Try again.")
            continue
        print(f"  You: {text}")

        # Check for transfer intent
        transfer = detect_transfer(text, state.active_agent)

        if transfer.reason == "invalid":
            msg = f"I don't know an agent named {transfer.target}. I can transfer you to {'Alice' if agent == 'Bob' else 'Bob'}."
            print(f"  [{agent}]: {msg}")
            audio = timed("TTS", synthesize, msg, voice)
            play_audio(audio)
            continue

        if transfer.reason == "self":
            msg = f"You're already talking to {agent}! How can I help?"
            print(f"  [{agent}]: {msg}")
            audio = timed("TTS", synthesize, msg, voice)
            play_audio(audio)
            continue

        if transfer.should_transfer:
            target = transfer.target
            # Farewell from current agent
            farewell = f"Sure! Let me transfer you to {target} now."
            print(f"  [{agent}]: {farewell}")
            audio = timed("TTS", synthesize, farewell, voice)
            play_audio(audio)

            # Execute transfer
            state.add_message("user", text)
            greeting = handle_transfer(state, target)
            new_voice = get_voice(target)
            print(f"  [{target}]: {greeting}")
            audio = timed("TTS", synthesize, greeting, new_voice)
            play_audio(audio)
            continue

        # Normal conversation
        state.add_message("user", text)
        response = timed("LLM", respond, state)
        state.add_message("assistant", response)

        # Check if agent suggests transfer
        suggestion = detect_agent_suggestion(response, state.active_agent)
        if suggestion.reason == "agent_suggested":
            print(f"  💡 {agent} suggested transferring to {suggestion.target}")

        print(f"  [{agent}]: {response}")
        audio = timed("TTS", synthesize, response, voice)
        play_audio(audio)

    # Session summary on exit
    print_session_summary(state)


if __name__ == "__main__":
    main()
