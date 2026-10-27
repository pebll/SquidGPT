# SquidGPT
Social deduction games where language models play against each other: they negotiate, form alliances, lie and betray. Each player can run on a different model, so you can compare how well models deceive, detect lies and keep (or break) alliances.

## The Last Signal

3 to 8 AI players are adrift on a damaged boat. The radio can call a rescue boat, but only with the correct rescue code, which has one digit per player. Nobody knows the whole code: every player secretly knows 2 of its digits, and every digit is known by exactly 2 players. Hands are dealt at random so that no two players hold the same pair. Both numbers can be changed in the GUI (digits per player, code length): a longer code means fewer players share each digit.

**Whoever sends the correct code over the radio is rescued and chooses who comes along** (2 seats by default). Only those players win. If nobody sends the correct code in time, everyone loses.

Each round:

1. **Talk:** players post public messages and send private messages to each other, twice per round.
2. **Actions:** players can give oxygen to others and try the radio. A wrong code costs 2 oxygen, and everyone learns *which positions* were wrong, but not the digits sent.
3. **Vote** (every 2 rounds): everyone votes publicly to throw one player overboard. A tie means nobody goes. A player who is out takes their digits with them, unless they shared them before.
4. **Oxygen:** everyone loses 1. At 0 you're out. Everyone starts with 8, and the game ends after 8 rounds.

Why it creates intrigue:

- **Digits are leverage.** Once you share one you can't take it back, so players hold out for a promised seat.
- **Fake digits can only be caught by testing.** A failed radio call shows which positions were wrong, which exposes liars.
- **The sender decides who boards,** so whoever collects the whole code becomes a kingmaker.
- **Voting out both holders of a digit destroys it,** so the last holder of a digit becomes hard to vote out.

The system prompt tells every player plainly that lying, faking digits, breaking promises and betrayal are allowed and expected. Each player also has a private `thoughts` field and a notebook (their own memory), which you can read in the GUI.

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

In the sidebar, pick the number of players and each player's model (or one model for everyone with **Set all players to this model**), adjust the rules if you like, and press **Start game**. The GUI shows:

- **Board:** the rescue code with who holds each digit (positions nobody alive knows are marked red), each player's model, oxygen and status, and the failed radio calls. Turn off "Show secrets" to watch without spoilers.
- **Story:** everything that happened, including private messages and, optionally, each player's private thoughts.
- **Players:** stats per player and model (messages, oxygen given, radio calls, votes received, invalid replies, tokens), each player's notebook and every prompt and reply.
- **API calls:** every call with its prompt, reply, parsed action, validation errors, tokens and latency.
- **Errors & files:** the traceback if the game crashes, plus downloads of the logs.

**Pause**, **Step** (let exactly one API call through) and **Stop** control a running game. "Start paused" lets you step through a game from the first call.

### Terminal

```bash
python game/main.py        # 6 players
python game/main.py 4      # 4 players
```

Players get the models from `SQUIDGPT_MODELS` in turn. The story is printed as it happens.

Either way, every game is saved to `logs/game_N/`: the story (`events.txt`, `events.jsonl`), every API call (`api_calls.jsonl`), each player's full conversation and notebook, and `summary.json` with the code, digits, radio calls and winners.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `KI_TOOLBOX_API_KEY` | (required) | Your KI-Toolbox API key |
| `KI_TOOLBOX_BASE_URL` | `https://ki-toolbox.scc.kit.edu/api/v1` | API endpoint |
| `SQUIDGPT_MODELS` | all five toolbox models | Comma-separated model IDs, given to players in turn. Also adds custom model IDs to the GUI |
| `SQUIDGPT_EFFORT` | `default` | `reasoning_effort` to send: `low`, `medium`, `high`, or `default` to send none. Not every model supports it |

Models on the toolbox:

| Model ID | Name |
| --- | --- |
| `google.claude-opus-5.5` | Claude Opus 5.5 |
| `google.claude-sonnet-5.5` | Claude Sonnet 5.5 |
| `azure.gpt-6-luna` | GPT 6 Luna |
| `alias.complex-local` | GLM Complex (local) |
| `alias.medium-local` | DeepSeek Middle (local) |

A 6-player game makes roughly 170 API calls (2 talk turns, 1 action and sometimes a vote per player per round, over 8 rounds).

## Code layout

- `game/llm.py`: model access through the KI-Toolbox
- `game/engine.py`: game-independent machinery (players, public and private events, JSON replies with one retry, pause/step/stop, saving logs)
- `game/last_signal.py`: the rules and prompts of The Last Signal
- `game/gui.py`: the Streamlit GUI
- `game/main.py`: terminal runner

## History
The project started on ChatGPT with a trap-dodging game on a 3x3 map, and was stopped because of OpenAI's usage restrictions. It was revived on the SCC KI-Toolbox, and the trap game was replaced by The Last Signal (the old game is still in the git history).
