# SquidGPT
This project's goal is to create environments where language models compete against each other in different tasks.

The first task is a simple survival game: 6 AI participants are dropped into a 3x3 map of rooms. Every round some rooms get trapped, and each participant only learns about part of the trapped rooms. Participants in the same room can talk (and lie) to each other, then move. Whoever stands in a trapped room at the end of a round is eliminated. The last survivor wins.

## Setup

Requires Python 3.9+ and an API key for the [SCC KI-Toolbox](https://ki-toolbox.scc.kit.edu) at KIT, which serves the models through an OpenAI-compatible API.

```bash
pip install -r requirements.txt
export KI_TOOLBOX_API_KEY=...
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
| `KI_TOOLBOX_API_KEY` | (required) | Your KI-Toolbox API key |
| `KI_TOOLBOX_BASE_URL` | `https://ki-toolbox.scc.kit.edu/api/v1` | API endpoint |
| `SQUIDGPT_MODEL` | `google.claude-opus-5.5` | Model each participant uses |
| `SQUIDGPT_EFFORT` | `default` | `reasoning_effort` to send: `low`, `medium`, `high`, or `default` to send none. Not every model supports it |
| `SQUIDGPT_VERBOSE` | unset | Set to `1` to print every prompt and response in the terminal |

`SQUIDGPT_MODEL` and `SQUIDGPT_EFFORT` also set the defaults shown in the GUI sidebar.

Models available on the toolbox (pick them in the GUI, or set `SQUIDGPT_MODEL`):

| Model ID | Name |
| --- | --- |
| `google.claude-opus-5.5` | Claude Opus 5.5 |
| `google.claude-sonnet-5.5` | Claude Sonnet 5.5 |
| `azure.gpt-6-luna` | GPT 6 Luna |
| `alias.complex-local` | GLM Complex (local) |
| `alias.medium-local` | DeepSeek Middle (local) |

The GUI also accepts any other model ID. A full game makes roughly 100–200 API calls, so a local model is handy while experimenting.

## History
The project was originally built on ChatGPT and stopped because of OpenAI's usage restrictions. It now runs on the SCC KI-Toolbox at KIT.
