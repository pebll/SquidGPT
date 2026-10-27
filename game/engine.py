"""Game-independent machinery: players backed by models, events, controls, logging.

A concrete game subclasses BaseGame, implements play(), and talks to players through
Player.ask(). Events are either public or visible to a set of players; every player
gets the events they can see in their next prompt.
"""
import json
import os
import re
import threading
import traceback

import llm


class GameStopped(Exception):
    pass


def parse_json(text):
    """Extract the first JSON object from a model reply (bare, fenced, or surrounded by prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class Player:
    def __init__(self, game, number, name, model):
        self.game = game
        self.number = number
        self.name = name
        self.model = model
        self.system = ""
        self.conversation = []  # append-only chat history with the model
        self.inbox = []  # events seen since the last prompt
        self.notebook = ""  # private memory the player rewrites as it likes
        self.alive = True
        self.out_round = None
        self.out_reason = None
        self.input_tokens = 0
        self.output_tokens = 0

    def __repr__(self):
        return f"{self.name} (#{self.number})"

    @property
    def label(self):
        return f"{self.name} ({llm.model_label(self.model)})"

    def ask(self, action, prompt, validate):
        """Ask the model for a JSON reply and validate it.

        validate(dict) returns (clean_value, errors). On invalid output the player gets the
        errors and one retry; if that also fails, None is returned and the turn is skipped.
        """
        for attempt in range(2):
            self.game.checkpoint()
            call = self.game.new_call(self, action, prompt)
            self.conversation.append({"role": "user", "content": prompt})
            try:
                result = llm.chat(self.model, self.system, self.conversation, self.game.effort)
            except Exception as e:
                call.update(status="error", error=f"{type(e).__name__}: {e}")
                raise
            text = result["text"]
            self.conversation.append({"role": "assistant", "content": text})
            self.input_tokens += result["input_tokens"]
            self.output_tokens += result["output_tokens"]
            call.update(result, response=text, status="refused" if result["refused"] else "ok")
            call.pop("text", None)
            call.pop("refused", None)

            data = parse_json(text) if not result["refused"] else None
            if data is None:
                errors = ["Your reply was not a valid JSON object."]
                value = None
            else:
                value, errors = validate(data)
                if isinstance(data.get("notebook"), str):
                    self.notebook = data["notebook"][:4000]
                call["thoughts"] = data.get("thoughts")
            # Store a JSON-safe copy for logs and the GUI (players become their names).
            call["parsed"] = json.loads(json.dumps(value, default=str))
            call["errors"] = errors
            if not errors:
                return value
            call["status"] = "invalid" if call["status"] == "ok" else call["status"]
            if attempt == 0:
                prompt = ("Your reply could not be used:\n- " + "\n- ".join(errors) +
                          "\nReply again with only the corrected JSON object.")
        self.game.log(f"{self} gave no valid reply and skips this {action}.", kind="invalid", actor=self)
        return None


class BaseGame:
    PLAYER_NAMES = ["Alice", "Bob", "Charlie", "David", "Emma", "Fred", "Grace", "Hugo", "Iris", "Juliette"]

    def __init__(self, models, effort=llm.EFFORT, echo=True):
        self.effort = effort
        self.echo = echo
        self.round = 0
        self.phase = "setup"
        self.status = "ready"  # ready, running, paused, finished, stopped, error
        self.error = None
        self.log_folder = None
        self.events = []
        self.api_calls = []
        self.winners = []
        names = self.PLAYER_NAMES[:len(models)]
        self.players = [Player(self, i, name, model) for i, (name, model) in enumerate(zip(names, models), start=1)]
        # Controls used by the GUI: pause/resume, single-step and stop.
        self._resume = threading.Event()
        self._resume.set()
        self._stop = threading.Event()
        self.step_mode = False

    # --- players and events ---------------------------------------------

    @property
    def alive(self):
        return [p for p in self.players if p.alive]

    def find_player(self, name):
        """Look a player up by name or number, as models write them."""
        if name is None:
            return None
        key = str(name).strip().lstrip("#").lower()
        for p in self.players:
            if key in (p.name.lower(), str(p.number)):
                return p
        return None

    def log(self, text, kind="info", actor=None, visible_to=None, notify_actor=False, **data):
        """Record an event. visible_to=None means public; otherwise a list of players.

        Players are told about every event they can see, except their own actions
        (unless notify_actor is set, e.g. for results only the game knows).
        """
        event = {
            "id": len(self.events) + 1,
            "round": self.round,
            "phase": self.phase,
            "kind": kind,
            "text": text,
            "actor": actor.number if actor else None,
            "visible_to": None if visible_to is None else sorted({p.number for p in visible_to}),
            **data,
        }
        self.events.append(event)
        for p in self.players:
            if p.alive and (visible_to is None or p in visible_to) and (p != actor or notify_actor):
                p.inbox.append(text)
        if self.echo:
            scope = "" if visible_to is None else f"[private: {', '.join(p.name for p in visible_to)}] "
            print(f"R{self.round} {scope}{text}")
        return event

    def eliminate(self, player, reason):
        player.alive = False
        player.out_round = self.round
        player.out_reason = reason

    def new_call(self, player, action, prompt):
        call = {
            "id": len(self.api_calls) + 1,
            "player": player.number,
            "name": player.name,
            "action": action,
            "round": self.round,
            "phase": self.phase,
            "prompt": prompt,
            "status": "pending",
            "requested_model": player.model,
        }
        self.api_calls.append(call)
        return call

    # --- controls -------------------------------------------------------

    @property
    def paused(self):
        """True when paused or single-stepping, i.e. when the GUI should offer Resume."""
        return self.step_mode or not self._resume.is_set()

    def pause(self):
        self._resume.clear()
        if self.status == "running":
            self.status = "paused"

    def resume(self):
        self.step_mode = False
        self._resume.set()

    def step(self):
        """Let exactly one more API call through, then pause again."""
        self.step_mode = True
        self._resume.set()

    def stop(self):
        self._stop.set()
        self._resume.set()

    def checkpoint(self):
        """Called before every API call: honours pause, step and stop requests."""
        if self.step_mode:
            self._resume.clear()
            self.step_mode = False
            self.status = "paused"
        if not self._resume.is_set():
            self.status = "paused"
            self._resume.wait()
        if self._stop.is_set():
            raise GameStopped()
        self.status = "running"

    def run(self):
        """Run a full game, catching errors so a background thread can report them."""
        self.status = "running"
        try:
            self.play()
            self.status = "finished"
        except GameStopped:
            self.log("Game stopped by user.", kind="end")
            self.status = "stopped"
        except Exception as e:
            self.error = traceback.format_exc()
            self.log(f"Game crashed: {type(e).__name__}: {e}", kind="error")
            self.status = "error"
        finally:
            self.phase = "over"
            try:
                self.save_logs()
            except Exception:
                self.error = (self.error or "") + "\nSaving logs failed:\n" + traceback.format_exc()

    def play(self):
        raise NotImplementedError

    # --- persistence ----------------------------------------------------

    def summary(self):
        """Game-specific facts saved with the logs (overridden by games)."""
        return {}

    def save_logs(self):
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(base, exist_ok=True)
        indexes = [int(m.group(1)) for folder in os.listdir(base) if (m := re.fullmatch(r"game_(\d+)", folder))]
        folder = os.path.normpath(os.path.join(base, f"game_{max(indexes, default=0) + 1}"))
        os.makedirs(folder)
        with open(os.path.join(folder, "events.txt"), "w", encoding="utf-8") as f:
            for e in self.events:
                scope = "" if e["visible_to"] is None else f"[private to {e['visible_to']}] "
                f.write(f"R{e['round']} {e['phase']}: {scope}{e['text']}\n")
        with open(os.path.join(folder, "events.jsonl"), "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "api_calls.jsonl"), "w", encoding="utf-8") as f:
            for c in self.api_calls:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        for p in self.players:
            with open(os.path.join(folder, f"player_{p.number}_{p.name}.txt"), "w", encoding="utf-8") as f:
                f.write(f"model: {p.model}\n\nsystem:\n{p.system}\n")
                for m in p.conversation:
                    f.write(f"\n--- {m['role']} ---\n{m['content']}\n")
                f.write(f"\n--- final notebook ---\n{p.notebook}\n")
        with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
            json.dump({"status": self.status, "winners": [p.name for p in self.winners],
                       "players": [{"number": p.number, "name": p.name, "model": p.model, "alive": p.alive,
                                    "out_round": p.out_round, "out_reason": p.out_reason,
                                    "input_tokens": p.input_tokens, "output_tokens": p.output_tokens}
                                   for p in self.players],
                       **self.summary()}, f, indent=2, ensure_ascii=False)
        self.log_folder = folder
        if self.echo:
            print(f"Logs saved to {folder}")
