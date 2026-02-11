# Claude Headspace - TODO

## Agent Chat

### Review listening screen and question screen for deprecation

The `screen-listening` and `screen-question` views in the voice/chat interface (`static/voice/`) are currently unused — all agent interactions now route through the chat screen (`screen-chat`), which handles text input, inline question options, and a mic button.

These screens should be reviewed and potentially repurposed or removed when voice interactivity is implemented. This is a larger epic that requires integrating a conversational model for natural voice chat.

**Screens:**
- `screen-listening` — standalone voice dictation with transcript display and text fallback
- `screen-question` — dedicated structured question/option rendering

**What the chat screen already covers:**
- Text input (chat input bar)
- Voice input (chat mic button)
- Structured questions (inline bubble option buttons)
- Full transcript history

**What's needed for voice interactivity:**
- Integration with a speech-to-text/text-to-speech model for conversational chat
- Determine whether the listening/question screens have a role in the voice UX or should be removed entirely
- Scope and plan the full voice interaction epic
