# SquidGPT
This project's goal is to create environments where language models compete against each other in different tasks.

The first task is a simple survival game: 6 Claude-powered participants are dropped into a 3x3 map of rooms. Every round some rooms get trapped, and each participant only learns about part of the trapped rooms. Participants in the same room can talk (and lie) to each other, then move. Whoever stands in a trapped room at the end of a round is eliminated. The last survivor wins.

## Setup

Requires Python 3.9+ and an [Anthropic API key](https://platform.claude.com/settings/keys).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

### GUI

```bash
streamlit run game/gui.py
```

Pick the model, effort, number of players and round limit in the sidebar and press **Start game**. The GUI shows:

- a live map of the 3x3 rooms with every player, the trapped rooms and who knows about them (turn off "Show traps" to avoid spoilers)
- the game log, filterable by event kind and player, including each player's private `think()` notes
- per-player stats and each player's full conversation (system prompt, every prompt and response)
- a debug view of every API call: latency, tokens, stop reason, the model that answered, the parsed commands, the reasoning summary, and flags for errors, refusals and responses with no valid command
- the traceback if the game crashes, plus downloads of the logs

**Pause**, **Step** (let exactly one API call through) and **Stop** control a running game. "Start paused" lets you step through a game from the first call.

### Terminal

```bash
python game/main.py
```

The general game log is printed while the game runs.

Either way, when a game ends the general log, each participant's full conversation and `api_calls.jsonl` (every prompt, response, token count and latency) are saved to `logs/test_log_N/`.

## Configuration

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (required) | Your Claude API key |
| `SQUIDGPT_MODEL` | `claude-opus-5-5` | Claude model each participant uses |
| `SQUIDGPT_EFFORT` | `medium` | Thinking effort: `low`, `medium`, `high`, `xhigh`, `max` |
| `SQUIDGPT_VERBOSE` | unset | Set to `1` to print every prompt and response in the terminal |

`SQUIDGPT_MODEL` and `SQUIDGPT_EFFORT` also set the defaults shown in the GUI sidebar.

A full game makes roughly 100–200 API calls, so a cheaper model (for example `SQUIDGPT_MODEL=claude-haiku-5-5`) or `SQUIDGPT_EFFORT=low` is handy while experimenting.

## History
The project was originally built on ChatGPT and stopped because of OpenAI's usage restrictions. It now runs on the Claude API.
