# SquidGPT
This project's goal is to create environments where language models compete against each other in different tasks.

The first task is a simple survival game: 6 Claude-powered participants are dropped into a 3x3 map of rooms. Every round some rooms get trapped, and each participant only learns about part of the trapped rooms. Participants in the same room can talk (and lie) to each other, then move. Whoever stands in a trapped room at the end of a round is eliminated. The last survivor wins.

## Setup

Requires Python 3.9+ and an [Anthropic API key](https://platform.claude.com/settings/keys).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python game/main.py
```

The general game log is printed while the game runs. When it ends, the general log and each participant's full conversation are saved to `logs/test_log_N/`.

## Configuration

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | (required) | Your Claude API key |
| `SQUIDGPT_MODEL` | `claude-opus-5-5` | Claude model each participant uses |
| `SQUIDGPT_EFFORT` | `medium` | Thinking effort: `low`, `medium`, `high`, `xhigh`, `max` |
| `SQUIDGPT_VERBOSE` | unset | Set to `1` to print every prompt and response |

A full game makes roughly 100–200 API calls, so a cheaper model (for example `SQUIDGPT_MODEL=claude-haiku-5-5`) or `SQUIDGPT_EFFORT=low` is handy while experimenting.

## History
The project was originally built on ChatGPT and stopped because of OpenAI's usage restrictions. It now runs on the Claude API.
