"""SquidGPT spectator and debug GUI for The Last Signal.

Run with:  streamlit run game/gui.py
"""
import html
import json
import os
import sys
import threading
import time

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm  # noqa: E402
from last_signal import LastSignal  # noqa: E402

st.set_page_config(page_title="SquidGPT", page_icon="🦑", layout="wide")

EFFORTS = ["default", "low", "medium", "high"]
PLAYER_COLORS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6", "#9a6324"]
KIND_ICONS = {
    "round": "🔔", "phase": "📣", "digits": "🔢", "public": "💬", "private": "🔒", "thought": "💭",
    "give": "🎁", "radio": "📻", "rescue": "🚁", "vote": "🗳️", "out": "☠️", "lost": "🕳️",
    "invalid": "⚠️", "winner": "🏆", "end": "🏁", "error": "❌", "info": "ℹ️",
}
ACTIVE = ("running", "paused")
MODEL_OPTIONS = list(dict.fromkeys(list(llm.MODELS) + llm.DEFAULT_MODELS))

st.markdown("""
<style>
.sq-code { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.sq-pos { border: 2px solid rgba(128,128,128,.35); border-radius: 8px; padding: 4px 8px; min-width: 64px;
          text-align: center; background: rgba(128,128,128,.06); }
.sq-pos.lost { border-color: #e53935; background: rgba(229,57,53,.12); }
.sq-pos .n { font-size: .7rem; opacity: .7; }
.sq-pos .d { font-size: 1.5rem; font-weight: 700; font-family: ui-monospace, monospace; }
.sq-card { border: 1px solid rgba(128,128,128,.35); border-radius: 10px; padding: 6px 10px; margin-bottom: 6px; }
.sq-card.out { opacity: .5; }
.sq-card.win { border: 2px solid #f9a825; }
.sq-card-top { display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
.sq-name { font-weight: 700; }
.sq-model { font-size: .75rem; opacity: .75; }
.sq-bar { height: 6px; border-radius: 3px; background: rgba(128,128,128,.25); margin: 4px 0; }
.sq-bar > div { height: 6px; border-radius: 3px; background: #43a047; }
.sq-small { font-size: .8rem; opacity: .85; }
.sq-chip { display: inline-block; color: white; border-radius: 10px; padding: 0 6px; margin: 1px; font-size: .75rem; }
.sq-line { font-family: ui-monospace, monospace; font-size: .85rem; padding: 1px 0; }
.sq-private { padding-left: 1.2rem; opacity: .9; }
.sq-dim { opacity: .55; }
</style>
""", unsafe_allow_html=True)


def color(number):
    return PLAYER_COLORS[(number - 1) % len(PLAYER_COLORS)]


def chip(p, struck=False):
    name = f"<s>{html.escape(p.name)}</s>" if struck else html.escape(p.name)
    return f'<span class="sq-chip" style="background:{color(p.number)}">{name}</span>'


# --- sidebar: settings and controls ----------------------------------------

def set_all_models(model):
    for i in range(LastSignal.MAX_PLAYERS):
        st.session_state[f"model_{i}"] = model


def sidebar():
    game = st.session_state.get("game")
    active = game is not None and game.status in ACTIVE

    st.sidebar.title("🦑 SquidGPT")
    st.sidebar.caption("The Last Signal")
    st.sidebar.subheader("New game")
    count = st.sidebar.slider("Players", LastSignal.MIN_PLAYERS, LastSignal.MAX_PLAYERS, 6)
    with st.sidebar.expander("Player models", expanded=True):
        everyone = st.selectbox("Same model for everyone", MODEL_OPTIONS, key="model_all", format_func=llm.model_label)
        st.button("Set all players to this model", on_click=set_all_models, args=(everyone,), width="stretch")
        st.divider()
        models = []
        for i in range(count):
            key = f"model_{i}"
            if key not in st.session_state:
                st.session_state[key] = llm.DEFAULT_MODELS[i % len(llm.DEFAULT_MODELS)]
            models.append(st.selectbox(LastSignal.PLAYER_NAMES[i], MODEL_OPTIONS, key=key, format_func=llm.model_label))
        st.caption("Add other model IDs with the SQUIDGPT_MODELS environment variable.")
    with st.sidebar.expander("Rules"):
        rules = {
            "max_rounds": st.number_input("Rounds", 2, 30, 8),
            "start_oxygen": st.number_input("Starting oxygen", 1, 30, 8),
            "seats": st.number_input("Seats on the rescue boat", 1, count, min(2, count)),
            "digits_per_player": st.number_input("Digits per player", 1, 3, 2),
            "vote_every": st.number_input("Vote every N rounds", 1, 10, 2),
            "talk_passes": st.number_input("Talk turns per round", 1, 5, 2),
            "max_private": st.number_input("Private messages per talk turn", 0, 5, 2),
            "radio_penalty": st.number_input("Oxygen lost on a wrong radio call", 0, 10, 2),
        }
        k = int(rules["digits_per_player"])
        rules["code_length"] = st.number_input(
            "Code length", k, count * k, max(k, min(count, count * k)),
            help="Defaults to one digit per player. A longer code means fewer players share each digit.")
        slots, length = count * k, int(rules["code_length"])
        low, high = slots // length, -(-slots // length)
        shared = f"exactly {low}" if low == high else f"{low} or {high}"
        st.caption(f"Each digit will be known by {shared} player(s).")
    effort = st.sidebar.selectbox("Reasoning effort", EFFORTS,
                                  index=EFFORTS.index(llm.EFFORT) if llm.EFFORT in EFFORTS else 0,
                                  help='Sent as reasoning_effort. "default" sends nothing; not every model supports it.')
    start_paused = st.sidebar.checkbox("Start paused (step through calls)")
    if st.sidebar.button("Start game", type="primary", disabled=active, width="stretch"):
        game = LastSignal(models, effort=effort, echo=False, **{k: int(v) for k, v in rules.items()})
        if start_paused:
            game.pause()
        threading.Thread(target=game.run, daemon=True, name="squidgpt-game").start()
        st.session_state.game = game
        active = True
    if not os.environ.get("KI_TOOLBOX_API_KEY"):
        st.sidebar.warning("KI_TOOLBOX_API_KEY is not set, so every API call will fail.")

    if game is not None:
        st.sidebar.subheader("Controls")
        c1, c2 = st.sidebar.columns(2)
        if game.paused:
            c1.button("▶ Resume", on_click=game.resume, disabled=not active, width="stretch")
        else:
            c1.button("⏸ Pause", on_click=game.pause, disabled=not active, width="stretch")
        c2.button("⏭ Step", on_click=game.step, disabled=not active, width="stretch",
                  help="Let one API call through, then pause")
        st.sidebar.button("⏹ Stop game", on_click=game.stop, disabled=not active, width="stretch")

    st.sidebar.subheader("View")
    st.sidebar.toggle("Show secrets (code, digits)", value=True, key="spoilers")
    st.sidebar.slider("Refresh every (s)", 0.5, 5.0, 1.0, 0.5, key="refresh")


# --- panels ----------------------------------------------------------------

def compact(n):
    return f"{n / 1000:.1f}k" if n >= 10_000 else str(n)


def status_bar(game):
    calls = list(game.api_calls)
    done = [c for c in calls if "latency" in c]
    cols = st.columns([1.3, 1.3, 0.8, 1, 1.4, 1])
    icon = {"running": "🟢", "paused": "⏸️", "finished": "🏁", "stopped": "⏹️", "error": "❌"}.get(game.status, "⚪")
    cols[0].metric(f"Status {icon}", game.status)
    cols[1].metric("Round", f"{game.round}/{game.max_rounds}", game.phase, delta_color="off")
    cols[2].metric("Alive", f"{len(game.alive)}/{len(game.players)}")
    errors = sum(c["status"] == "error" for c in calls)
    cols[3].metric("API calls", len(calls), f"{errors} errors", delta_color="inverse" if errors else "off")
    cols[4].metric("Tokens in / out", f"{compact(sum(c.get('input_tokens', 0) for c in calls))} / "
                                      f"{compact(sum(c.get('output_tokens', 0) for c in calls))}")
    avg = sum(c["latency"] for c in done) / len(done) if done else 0
    cols[5].metric("Avg latency", f"{avg:.1f}s")

    pending = [c for c in calls if c["status"] == "pending"]
    if pending:
        c = pending[-1]
        p = game.players[c["player"] - 1]
        st.info(f"Waiting on **{p.label}** ({c['action']}, call {c['id']})")
    elif game.status == "paused":
        st.warning("Paused. Use Resume or Step in the sidebar.")
    if game.status == "error":
        st.error("The game crashed. See the **Errors & files** tab for the traceback.")
    elif game.status == "stopped":
        st.info("Game stopped.")
    elif game.status == "finished":
        if game.rescued:
            st.success(f"🚁 Rescued: {' and '.join(p.label for p in game.winners)}. The code was {game.code}.")
        else:
            st.warning(f"Nobody was rescued. The code was {game.code}.")


def board(game):
    spoilers = st.session_state.spoilers
    st.markdown("**Rescue code**")
    cells = []
    for pos in range(1, game.code_length + 1):
        holders = game.holders(pos)
        lost = not any(p.alive for p in holders)
        digit = game.code[pos - 1] if spoilers else "?"
        who = "".join(chip(p, struck=not p.alive) for p in holders) if spoilers else ""
        cells.append(f'<div class="sq-pos{" lost" if lost else ""}"><div class="n">pos {pos}</div>'
                     f'<div class="d">{digit}</div>{who}</div>')
    st.markdown(f'<div class="sq-code">{"".join(cells)}</div>', unsafe_allow_html=True)

    cards = []
    for p in game.players:
        winner = p in game.winners
        state = "🏆 rescued" if winner else (f"☠️ {p.out_reason}" if not p.alive else "alive")
        width = min(100, 100 * p.oxygen / max(game.start_oxygen, 1))
        digits = ", ".join(f"{pos}={d}" for pos, d in sorted(p.known.items())) if spoilers else "hidden"
        cards.append(
            f'<div class="sq-card{" out" if not p.alive else ""}{" win" if winner else ""}">'
            f'<div class="sq-card-top"><span class="sq-name" style="color:{color(p.number)}">{html.escape(p.name)}</span>'
            f'<span class="sq-model">{html.escape(llm.model_label(p.model))}</span></div>'
            f'<div class="sq-bar"><div style="width:{width:.0f}%"></div></div>'
            f'<div class="sq-small">🫁 {p.oxygen} oxygen · 🔢 {digits} · {html.escape(state)}</div></div>')
    st.markdown("".join(cards), unsafe_allow_html=True)

    if game.radio_attempts:
        st.markdown("**Failed radio calls**")
        for a in game.radio_attempts:
            sent = f" sent `{a['code']}`" if spoilers else ""
            st.markdown(f"R{a['round']} · **{a['sender']}**{sent} · wrong positions: {', '.join(map(str, a['wrong']))}")


def event_line(game, e):
    icon = KIND_ICONS.get(e["kind"], "•")
    text = html.escape(e["text"])
    cls = "sq-line"
    if e["kind"] == "thought":
        cls += " sq-dim"
    elif e["kind"] == "private":
        cls += " sq-private"
    if e["kind"] in ("public", "private") and e["actor"]:
        name = game.players[e["actor"] - 1].name
        text = text.replace(html.escape(name), f'<b style="color:{color(e["actor"])}">{html.escape(name)}</b>', 1)
    return f'<div class="{cls}">R{e["round"]} {icon} {text}</div>'


def story_tab(game):
    events = list(game.events)
    c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
    private = c1.toggle("Private messages", value=True, key="show_private")
    thoughts = c2.toggle("Thoughts", value=False, key="show_thoughts")
    players = c3.multiselect("Only players", [p.number for p in game.players], key="log_players",
                             format_func=lambda n: game.players[n - 1].name)
    newest_first = c4.toggle("Newest first", value=True, key="newest_first")
    limit = c5.number_input("Max lines", 50, 5000, 300, 50, key="log_limit")
    hidden = set()
    if not private:
        hidden.add("private")
    if not thoughts:
        hidden.update({"thought", "digits"})
    shown = [e for e in events if e["kind"] not in hidden and
             (not players or e["actor"] in players or e.get("target") in players)]
    shown = shown[-limit:]
    if newest_first:
        shown.reverse()
    st.markdown("".join(event_line(game, e) for e in shown) or "_No events yet._", unsafe_allow_html=True)


def call_detail(game, call):
    p = game.players[call["player"] - 1]
    meta = f"call {call['id']} · {p.label} · {call['action']} · round {call['round']} · {call['status']}"
    if "latency" in call:
        meta += f" · {call['latency']:.1f}s"
    if "input_tokens" in call:
        meta += f" · {call['input_tokens']} in / {call['output_tokens']} out"
    if call.get("model") and call["model"] != call.get("requested_model"):
        meta += f" · served by {call['model']}"
    st.caption(meta)
    if call.get("error"):
        st.error(call["error"])
    for err in call.get("errors") or []:
        st.warning(err)
    left, right = st.columns(2)
    with left:
        st.markdown("**Prompt**")
        st.code(call["prompt"], language=None, wrap_lines=True)
    with right:
        st.markdown("**Response**")
        st.code(call.get("response", "…"), language=None, wrap_lines=True)
        if call.get("parsed") is not None:
            st.markdown("**Parsed**")
            st.json(call["parsed"])
        if call.get("thinking"):
            with st.expander("Model reasoning"):
                st.write(call["thinking"])


def players_tab(game):
    calls = list(game.api_calls)
    events = list(game.events)
    rows = []
    for p in game.players:
        mine = [c for c in calls if c["player"] == p.number]
        acts = [e for e in events if e["actor"] == p.number]
        rows.append({
            "player": p.name, "model": llm.model_label(p.model),
            "result": "🏆 rescued" if p in game.winners else ("out R%s" % p.out_round if not p.alive else "alive"),
            "oxygen": p.oxygen,
            "public msgs": sum(e["kind"] == "public" for e in acts),
            "private msgs": sum(e["kind"] == "private" for e in acts),
            "oxygen given": sum(e.get("amount", 0) for e in acts if e["kind"] == "give"),
            "radio calls": sum(e["kind"] in ("radio", "rescue") for e in acts),
            "votes received": sum(e["kind"] == "vote" and e.get("target") == p.number for e in events),
            "invalid replies": sum(c["status"] == "invalid" for c in mine),
            "errors": sum(c["status"] == "error" for c in mine),
            "tokens in": p.input_tokens, "tokens out": p.output_tokens,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    number = st.selectbox("Player", [p.number for p in game.players], key="player_pick",
                          format_func=lambda n: game.players[n - 1].label)
    p = game.players[number - 1]
    st.markdown("**Notebook**")
    st.code(p.notebook or "(empty)", language=None, wrap_lines=True)
    with st.expander("System prompt"):
        st.code(p.system, language=None, wrap_lines=True)
    mine = [c for c in calls if c["player"] == number]
    for c in reversed(mine[-30:]):
        thoughts = (c.get("thoughts") or c.get("response") or "…").strip().splitlines()
        first = thoughts[0][:90] if thoughts else "…"
        with st.expander(f"R{c['round']} · {c['action']} · {c['status']} · {first}"):
            call_detail(game, c)
    if len(mine) > 30:
        st.caption(f"Showing the last 30 of {len(mine)} calls. All calls are in the API calls tab.")


def calls_tab(game):
    calls = list(game.api_calls)
    if not calls:
        st.write("_No API calls yet._")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Invalid replies", sum(c["status"] == "invalid" for c in calls))
    c2.metric("Refusals", sum(c["status"] == "refused" for c in calls))
    c3.metric("Errors", sum(c["status"] == "error" for c in calls))
    df = pd.DataFrame([{
        "id": c["id"], "round": c["round"], "player": c["name"],
        "model": llm.model_label(c["requested_model"]), "action": c["action"], "status": c["status"],
        "latency s": round(c["latency"], 2) if "latency" in c else None,
        "in": c.get("input_tokens"), "out": c.get("output_tokens"), "stop": c.get("stop_reason"),
    } for c in reversed(calls)])
    if st.toggle("Only problems (errors, refusals, invalid replies)", key="only_problems"):
        df = df[~df["status"].isin(["ok", "pending"])]
    st.dataframe(df, hide_index=True, width="stretch", height=300)
    ids = df["id"].tolist()
    if ids:
        pick = st.selectbox("Inspect call", ["latest"] + ids, key="call_pick",
                            format_func=lambda i: f"Latest (call {ids[0]})" if i == "latest" else f"Call {i}")
        call_detail(game, calls[(ids[0] if pick == "latest" else pick) - 1])


def files_tab(game):
    if game.error:
        st.markdown("**Traceback**")
        st.code(game.error, language="python")
    else:
        st.write("No errors.")
    if game.log_folder:
        st.write(f"Logs saved to `{game.log_folder}`")
    c1, c2 = st.columns(2)
    c1.download_button("events.json", json.dumps(list(game.events), indent=2, ensure_ascii=False),
                       "events.json", width="stretch")
    c2.download_button("api_calls.jsonl", "\n".join(json.dumps(c, ensure_ascii=False) for c in list(game.api_calls)),
                       "api_calls.jsonl", width="stretch")


# --- page ------------------------------------------------------------------

sidebar()
game = st.session_state.get("game")

if game is None:
    st.title("🦑 SquidGPT: The Last Signal")
    st.markdown(
        "AI players, each running on a model of your choice, are adrift on a boat with a dying radio. "
        "Nobody knows the whole rescue code: every player secretly knows 2 of its digits, and every digit "
        "is known by 2 players. "
        "Whoever sends the correct code picks who comes along on the rescue boat; everyone else loses.\n\n"
        "Oxygen runs out, votes throw players overboard (taking their digits with them), and players can share, "
        "sell or fake the digits they hold. Lying and betrayal are allowed and expected.")
    st.write("Pick the players' models in the sidebar and press **Start game**.")
    st.stop()

refresh = st.session_state.refresh if game.status in ACTIVE else None


@st.fragment(run_every=refresh)
def live_view():
    status_bar(game)
    left, right = st.columns([2, 3])
    with left:
        board(game)
    with right:
        tab_story, tab_players, tab_calls, tab_files = st.tabs(["Story", "Players", "API calls", "Errors & files"])
        with tab_story:
            story_tab(game)
        with tab_players:
            players_tab(game)
        with tab_calls:
            calls_tab(game)
        with tab_files:
            files_tab(game)
    # Once the game ends, do a full rerun so the sidebar controls update and polling stops.
    if game.status not in ACTIVE and refresh is not None:
        time.sleep(0.1)
        st.rerun()


live_view()
