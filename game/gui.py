"""SquidGPT spectator and debug GUI.

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
from game import Game, MAX_PLAYERS  # noqa: E402
from participant import MODEL, MODELS, EFFORT  # noqa: E402

st.set_page_config(page_title="SquidGPT", page_icon="🦑", layout="wide")

EFFORTS = ["default", "low", "medium", "high"]
OTHER_MODEL = "other"
PLAYER_COLORS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
                 "#42d4f4", "#f032e6", "#9a6324", "#469990"]
KIND_ICONS = {
    "round": "🔔", "turn": "⏱️", "phase": "📣", "trap_info": "🕵️", "start": "🚩",
    "say": "💬", "think": "💭", "move": "👣", "traps": "💥", "eliminated": "☠️",
    "winner": "🏆", "end": "🏁", "error": "❌", "info": "ℹ️",
}
ACTIVE = ("running", "paused")

st.markdown("""
<style>
.sq-map { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.sq-room { border: 2px solid rgba(128,128,128,.35); border-radius: 10px; padding: 8px;
           min-height: 110px; background: rgba(128,128,128,.06); }
.sq-room.trapped { border-color: #e53935; background: rgba(229,57,53,.12); }
.sq-room-name { font-weight: 700; font-size: 1.05rem; display: flex; justify-content: space-between; }
.sq-chip { display: inline-block; color: white; border-radius: 12px; padding: 1px 8px;
           margin: 3px 3px 0 0; font-size: .85rem; }
.sq-known { font-size: .75rem; opacity: .75; margin-top: 4px; }
.sq-line { font-family: ui-monospace, monospace; font-size: .85rem; padding: 1px 0; }
.sq-dim { opacity: .55; }
</style>
""", unsafe_allow_html=True)


def color(number):
    return PLAYER_COLORS[(number - 1) % len(PLAYER_COLORS)]


def chip(p):
    return f'<span class="sq-chip" style="background:{color(p.number)}">#{p.number} {html.escape(p.name)}</span>'


# --- sidebar: settings and controls ----------------------------------------

def sidebar():
    game = st.session_state.get("game")
    active = game is not None and game.status in ACTIVE

    st.sidebar.title("🦑 SquidGPT")
    with st.sidebar.form("settings"):
        st.subheader("New game")
        model_ids = list(MODELS) + ([] if MODEL in MODELS else [MODEL]) + [OTHER_MODEL]
        model = st.selectbox("Model", model_ids, index=model_ids.index(MODEL),
                             format_func=lambda m: "Other…" if m == OTHER_MODEL else MODELS.get(m, m),
                             help="Models on the SCC KI-Toolbox. Pick Other… to type any model ID.")
        other_model = st.text_input("Other model ID", placeholder="only used with Other…")
        effort = st.selectbox("Reasoning effort", EFFORTS, index=EFFORTS.index(EFFORT) if EFFORT in EFFORTS else 0,
                              help="Sent as reasoning_effort. \"default\" sends nothing; not every model supports it.")
        players = st.slider("Players", 2, MAX_PLAYERS, 6)
        max_rounds = st.number_input("Max rounds", 1, 50, 10)
        start_paused = st.checkbox("Start paused (step through calls)")
        submitted = st.form_submit_button("Start game", type="primary", disabled=active,
                                          width="stretch")
    if not os.environ.get("KI_TOOLBOX_API_KEY"):
        st.sidebar.warning("KI_TOOLBOX_API_KEY is not set, so every API call will fail.")

    if submitted:
        if model == OTHER_MODEL:
            model = other_model.strip() or MODEL
        game = Game(player_count=players, max_rounds=int(max_rounds), model=model,
                    effort=effort, echo=False)
        if start_paused:
            game.pause()
        threading.Thread(target=game.run, daemon=True, name="squidgpt-game").start()
        st.session_state.game = game
        active = True

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
    st.sidebar.toggle("Show traps (spoilers)", value=True, key="show_traps")
    st.sidebar.slider("Refresh every (s)", 0.5, 5.0, 1.0, 0.5, key="refresh")


# --- panels ----------------------------------------------------------------

def compact(n):
    return f"{n / 1000:.1f}k" if n >= 10_000 else str(n)


def status_bar(game):
    calls = list(game.api_calls)
    done = [c for c in calls if "latency" in c]
    alive = len(game.participants)
    cols = st.columns([1.3, 1.3, 0.8, 1, 1.4, 1])
    icon = {"running": "🟢", "paused": "⏸️", "finished": "🏁", "stopped": "⏹️", "error": "❌"}.get(game.status, "⚪")
    cols[0].metric(f"Status {icon}", game.status)
    cols[1].metric("Round · Turn", f"{game.round}/{game.max_rounds} · {game.turn}", game.phase, delta_color="off")
    cols[2].metric("Alive", f"{alive}/{game.player_count}")
    cols[3].metric("API calls", len(calls), f"{sum(c['status'] == 'error' for c in calls)} errors",
                   delta_color="inverse" if any(c["status"] == "error" for c in calls) else "off")
    cols[4].metric("Tokens in / out", f"{compact(sum(c.get('input_tokens', 0) for c in calls))} / "
                                      f"{compact(sum(c.get('output_tokens', 0) for c in calls))}")
    avg = sum(c["latency"] for c in done) / len(done) if done else 0
    cols[5].metric("Avg latency", f"{avg:.1f}s")

    pending = [c for c in calls if c["status"] == "pending"]
    if pending:
        c = pending[-1]
        st.info(f"Waiting on **#{c['participant']} {c['name']}** ({c['action']}, call {c['id']})")
    elif game.status == "paused":
        st.warning("Paused. Use Resume or Step in the sidebar.")
    if game.status == "error":
        st.error("The game crashed. See the **Errors & files** tab for the traceback.")
    if game.status == "stopped":
        st.info("Game stopped.")
    if game.status == "finished":
        winner = next((e["text"] for e in reversed(game.events) if e["kind"] == "winner"), None)
        st.success(winner or "Game over.")


def map_view(game):
    show_traps = st.session_state.show_traps
    trapped = {r.name for r in game.trapped_rooms}
    knowers = {}
    for p in game.all_participants:
        for rnd, room in p.known_traps:
            if rnd == game.round:
                knowers.setdefault(room, []).append(p.number)
    cells = []
    for name in game.room_names:
        room = game.rooms[name]
        is_trapped = show_traps and name in trapped
        people = "".join(chip(p) for p in list(room.participants))
        badge = "💥 trapped" if is_trapped else ""
        known = ""
        if show_traps and name in knowers:
            known = f'<div class="sq-known">known by {", ".join("#" + str(n) for n in sorted(set(knowers[name])))}</div>'
        cells.append(f'<div class="sq-room{" trapped" if is_trapped else ""}">'
                     f'<div class="sq-room-name"><span>{name}</span><span>{badge}</span></div>'
                     f'{people}{known}</div>')
    st.markdown(f'<div class="sq-map">{"".join(cells)}</div>', unsafe_allow_html=True)
    dead = [p for p in game.all_participants if p.eliminated_round]
    if dead:
        st.caption("Eliminated: " + ", ".join(f"#{p.number} {p.name} (round {p.eliminated_round})" for p in dead))


def event_line(e):
    icon = KIND_ICONS.get(e["kind"], "•")
    text = html.escape(e["text"])
    if e["participant"]:
        text = f'<b style="color:{color(e["participant"])}">{text}</b>' if e["kind"] in ("say", "winner") else text
    dim = " sq-dim" if e["kind"] == "think" else ""
    where = f"R{e['round']}T{e['turn']}"
    return f'<div class="sq-line{dim}">{where} {icon} {text}</div>'


def log_tab(game):
    events = list(game.events)
    kinds = sorted({e["kind"] for e in events})
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    hide = c1.multiselect("Hide kinds", kinds, default=[k for k in ("trap_info",) if k in kinds], key="hide_kinds")
    players = c2.multiselect("Only players", [p.number for p in game.all_participants], key="log_players",
                             format_func=lambda n: f"#{n} {game.all_participants[n - 1].name}")
    newest_first = c3.toggle("Newest first", value=True, key="newest_first")
    limit = c4.number_input("Max lines", 50, 5000, 300, 50, key="log_limit")
    shown = [e for e in events if e["kind"] not in hide and (not players or e["participant"] in players)]
    shown = shown[-limit:]
    if newest_first:
        shown.reverse()
    st.markdown("".join(event_line(e) for e in shown) or "_No events yet._", unsafe_allow_html=True)


def call_detail(call):
    meta = (f"call {call['id']} · #{call['participant']} {call['name']} · {call['action']} · "
            f"R{call['round']}T{call['turn']} · {call['status']}")
    if "latency" in call:
        meta += f" · {call['latency']:.1f}s"
    if "input_tokens" in call:
        meta += f" · {call['input_tokens']} in / {call['output_tokens']} out"
    if call.get("model"):
        meta += f" · {call['model']}"
    st.caption(meta)
    if call.get("error"):
        st.error(call["error"])
    parsed = call.get("parsed", {})
    if call["status"] == "ok" and parsed.get(call["action"]) is None:
        st.warning(f"No valid `{call['action']}()` command found in the response.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Prompt**")
        st.code(call["prompt"], language=None, wrap_lines=True)
    with right:
        st.markdown("**Response**")
        st.code(call.get("response", "…"), language=None, wrap_lines=True)
        if parsed:
            st.markdown("**Parsed commands**")
            st.json(parsed)
        if call.get("thinking"):
            with st.expander("Reasoning"):
                st.write(call["thinking"])


def players_tab(game):
    calls = list(game.api_calls)
    rows = []
    for p in game.all_participants:
        mine = [c for c in calls if c["participant"] == p.number]
        rows.append({
            "#": p.number, "name": p.name,
            "status": f"eliminated R{p.eliminated_round}" if p.eliminated_round else "alive",
            "room": p.room.name if p.room else "-",
            "knows traps (this round)": ", ".join(r for rnd, r in p.known_traps if rnd == game.round),
            "calls": len(mine),
            "parse failures": sum(c["status"] == "ok" and c.get("parsed", {}).get(c["action"]) is None for c in mine),
            "tokens in": p.input_tokens, "tokens out": p.output_tokens,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    number = st.selectbox("Player conversation", [p.number for p in game.all_participants], key="player_pick",
                          format_func=lambda n: f"#{n} {game.all_participants[n - 1].name}")
    p = game.all_participants[number - 1]
    with st.expander("System prompt"):
        st.code(p.system, language=None, wrap_lines=True)
    if p.log:
        with st.expander("Pending log (sent with the next prompt)"):
            st.code(p.log, language=None, wrap_lines=True)
    mine = [c for c in calls if c["participant"] == number]
    for c in reversed(mine[-30:]):
        first_line = (c.get("response") or "…").strip().splitlines()[0][:90] if c.get("response") else "…"
        status = "⚠️ no command" if c["status"] == "ok" and c.get("parsed", {}).get(c["action"]) is None else c["status"]
        with st.expander(f"R{c['round']}T{c['turn']} · {c['action']} · {status} · {first_line}"):
            call_detail(c)
    if len(mine) > 30:
        st.caption(f"Showing the last 30 of {len(mine)} calls. All calls are in the API calls tab.")


def calls_tab(game):
    calls = list(game.api_calls)
    if not calls:
        st.write("_No API calls yet._")
        return
    parse_failures = sum(c["status"] == "ok" and c.get("parsed", {}).get(c["action"]) is None for c in calls)
    c1, c2, c3 = st.columns(3)
    c1.metric("Parse failures", parse_failures)
    c2.metric("Refusals", sum(c["status"] == "refused" for c in calls))
    c3.metric("Errors", sum(c["status"] == "error" for c in calls))
    df = pd.DataFrame([{
        "id": c["id"], "round": c["round"], "turn": c["turn"], "player": f"#{c['participant']} {c['name']}",
        "action": c["action"], "status": c["status"],
        "parsed": "✗" if c["status"] == "ok" and c.get("parsed", {}).get(c["action"]) is None else "",
        "latency s": round(c["latency"], 2) if "latency" in c else None,
        "in": c.get("input_tokens"), "out": c.get("output_tokens"),
        "stop": c.get("stop_reason"), "model": c.get("model"),
    } for c in reversed(calls)])
    only_problems = st.toggle("Only problems (errors, refusals, parse failures)", key="only_problems")
    if only_problems:
        df = df[(df["status"] != "ok") | (df["parsed"] == "✗")]
    st.dataframe(df, hide_index=True, width="stretch", height=300)
    ids = df["id"].tolist()
    if ids:
        pick = st.selectbox("Inspect call", ["latest"] + ids, key="call_pick",
                            format_func=lambda i: f"Latest (call {ids[0]})" if i == "latest" else f"Call {i}")
        call_detail(calls[(ids[0] if pick == "latest" else pick) - 1])


def files_tab(game):
    if game.error:
        st.markdown("**Traceback**")
        st.code(game.error, language="python")
    else:
        st.write("No errors.")
    if game.log_folder:
        st.write(f"Logs saved to `{game.log_folder}`")
    c1, c2, c3 = st.columns(3)
    c1.download_button("general.txt", game.logger.general_log, "general.txt", width="stretch")
    c2.download_button("events.json", json.dumps(list(game.events), indent=2, ensure_ascii=False),
                       "events.json", width="stretch")
    c3.download_button("api_calls.jsonl", "\n".join(json.dumps(c, ensure_ascii=False) for c in list(game.api_calls)),
                       "api_calls.jsonl", width="stretch")


# --- page ------------------------------------------------------------------

sidebar()
game = st.session_state.get("game")

if game is None:
    st.title("🦑 SquidGPT")
    st.write("AI players are dropped into a 3x3 map of rooms. Each round some rooms are trapped, "
             "and each player only learns part of where. Players in the same room talk (and lie), then move. "
             "Whoever stands in a trapped room at the end of a round is eliminated.")
    st.write("Pick settings in the sidebar and press **Start game**.")
    st.stop()

refresh = st.session_state.refresh if game.status in ACTIVE else None


@st.fragment(run_every=refresh)
def live_view():
    status_bar(game)
    left, right = st.columns([2, 3])
    with left:
        map_view(game)
    with right:
        tab_log, tab_players, tab_calls, tab_files = st.tabs(["Game log", "Players", "API calls", "Errors & files"])
        with tab_log:
            log_tab(game)
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
