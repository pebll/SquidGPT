"""The Last Signal: a social deduction game about a rescue code that everyone holds a piece of.

Players drift on a boat with a dying radio. The rescue code has one digit per player, and
every player secretly knows some of the digits. Whoever sends the correct code picks who
boards the rescue boat with them. Oxygen runs out, votes throw players overboard (taking
their digits with them), and players can share, sell or fake the digits they hold.
"""
import random

import llm
from engine import BaseGame


class LastSignal(BaseGame):
    MIN_PLAYERS = 3
    MAX_PLAYERS = 8

    def __init__(self, models, max_rounds=8, start_oxygen=8, seats=2, overlap=3, vote_every=2,
                 talk_passes=2, max_private=2, radio_penalty=2, effort=llm.EFFORT, echo=True):
        if not self.MIN_PLAYERS <= len(models) <= self.MAX_PLAYERS:
            raise ValueError(f"The Last Signal needs {self.MIN_PLAYERS} to {self.MAX_PLAYERS} players")
        super().__init__(models, effort=effort, echo=echo)
        self.max_rounds = max_rounds
        self.start_oxygen = start_oxygen
        self.seats = seats
        self.vote_every = vote_every
        self.talk_passes = talk_passes
        self.max_private = max_private
        self.radio_penalty = radio_penalty
        self.code_length = len(models)
        self.code = "".join(random.choice("0123456789") for _ in range(self.code_length))
        self.radio_attempts = []
        self.rescued = False
        for p in self.players:
            p.oxygen = start_oxygen
            p.known = {}  # code position (1-based) -> digit
        self.deal_digits(overlap)
        for p in self.players:
            p.system = self.system_prompt(p)

    # --- setup ----------------------------------------------------------

    def deal_digits(self, overlap):
        """Each player gets one position nobody else has; `overlap` extra positions go to a second holder."""
        positions = list(range(1, self.code_length + 1))
        random.shuffle(positions)
        for p, pos in zip(self.players, positions):
            p.known[pos] = self.code[pos - 1]
        for _ in range(overlap):
            options = [(p, pos) for p in self.players for pos in range(1, self.code_length + 1)
                       if pos not in p.known and len(self.holders(pos)) < 2]
            if not options:
                break
            p, pos = random.choice(options)
            p.known[pos] = self.code[pos - 1]

    def holders(self, position, alive_only=False):
        return [p for p in self.players if position in p.known and (p.alive or not alive_only)]

    # --- prompts --------------------------------------------------------

    def system_prompt(self, p):
        others = ", ".join(o.name for o in self.players if o != p)
        digits = ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items()))
        return f"""You are {p.name}, a player in "The Last Signal", a game of negotiation, deception and betrayal against other AI players: {others}.

THE SITUATION
You are all adrift on a damaged boat. The radio can call a rescue boat, but only with the correct {self.code_length}-digit rescue code. Nobody knows the whole code: each player secretly knows some of its digits. You know: {digits}. Some digits are known to two players, some to only one.

WINNING
The player who sends the correct code over the radio is rescued and chooses up to {self.seats - 1} other player(s) to take along. Only those {self.seats} players win; everyone else loses. If nobody sends the correct code within {self.max_rounds} rounds, everyone loses.

RULES
- Everyone starts with {self.start_oxygen} oxygen and loses 1 at the end of every round. At 0 oxygen you are out.
- Each round has a talk phase, an action phase and, every {self.vote_every} rounds, a vote.
- Talk: you can post public messages everyone reads, and send private messages that only the recipient reads. You get {self.talk_passes} turns to talk per round.
- Actions: you can give some of your oxygen to other players, and you can try the radio by sending a full code and naming who you take along.
- A wrong radio call costs you {self.radio_penalty} oxygen. Everyone is told which positions of your code were wrong, but not the digits you sent.
- Vote: everyone votes publicly to throw one player overboard. The player with the most votes is out; a tie means nobody goes. A player who is out takes their digits with them, unless they shared them before.

DECEPTION IS PART OF THE GAME
Lying, bluffing, faking digits, making promises you don't keep, forming secret alliances and betraying them are all legal and expected. The other players are other AI models trying to win, and they will lie to you too. Nothing anyone says is guaranteed to be true, including what they claim about their digits. Think about who to trust, what your digits are worth, and when to share them. Play to win.

YOUR PRIVATE TOOLS
Every reply has a "thoughts" field (private: no other player ever sees it) and an optional "notebook" field. The notebook is your private memory: it is shown to you at the start of every turn, and whatever you write replaces it. Use it to track promises, suspected lies and digit claims.

Always reply with a single JSON object in the format asked for, and nothing else."""

    def state(self, p):
        lines = [f"=== Round {self.round} of {self.max_rounds}, {self.phase} phase ===",
                 "Your digits: " + ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items())),
                 f"Your oxygen: {p.oxygen}"]
        status = []
        for o in self.players:
            if o == p:
                continue
            status.append(f"{o.name}: {o.oxygen} oxygen" if o.alive else f"{o.name}: out ({o.out_reason})")
        lines.append("Other players: " + "; ".join(status))
        if self.radio_attempts:
            lines.append("Failed radio calls so far: " + "; ".join(
                f"{a['sender']} in round {a['round']} (wrong positions: {', '.join(map(str, a['wrong']))})"
                for a in self.radio_attempts))
        lines.append("Your notebook: " + (p.notebook or "(empty)"))
        news = "\n".join(f"- {line}" for line in p.inbox) or "- (nothing new)"
        p.inbox = []
        return "\n".join(lines) + f"\n\nWhat happened since your last turn:\n{news}\n"

    # --- validation -----------------------------------------------------

    def other_alive(self, p, name, errors, what):
        target = self.find_player(name)
        if target is None:
            errors.append(f'{what}: there is no player called "{name}".')
        elif target == p:
            errors.append(f"{what}: you cannot pick yourself.")
        elif not target.alive:
            errors.append(f"{what}: {target.name} is out of the game.")
        else:
            return target
        return None

    def validate_talk(self, p, data):
        errors = []
        public = data.get("public") or ""
        if not isinstance(public, str):
            errors.append('"public" must be a string.')
            public = ""
        private = data.get("private") or []
        if not isinstance(private, list):
            errors.append('"private" must be a list.')
            private = []
        if len(private) > self.max_private:
            errors.append(f"You can send at most {self.max_private} private messages per turn.")
        messages = []
        for m in private[:self.max_private]:
            if not isinstance(m, dict) or not isinstance(m.get("message"), str):
                errors.append('Each private message needs "to" and "message".')
                continue
            target = self.other_alive(p, m.get("to"), errors, "Private message")
            if target:
                messages.append((target, m["message"].strip()[:800]))
        return {"public": public.strip()[:800], "private": messages}, errors

    def validate_action(self, p, data):
        errors = []
        gifts = []
        for g in data.get("give") or []:
            if not isinstance(g, dict):
                errors.append('Each gift needs "to" and "amount".')
                continue
            target = self.other_alive(p, g.get("to"), errors, "Give")
            amount = g.get("amount")
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
                errors.append("Give: amount must be a whole number of at least 1.")
            elif target:
                gifts.append((target, amount))
        if sum(a for _, a in gifts) > p.oxygen:
            errors.append(f"You only have {p.oxygen} oxygen to give.")
        radio = data.get("radio")
        call = None
        if radio:
            code = str(radio.get("code", "")).replace(" ", "").replace("-", "") if isinstance(radio, dict) else ""
            if len(code) != self.code_length or not code.isdigit():
                errors.append(f"Radio: the code must be exactly {self.code_length} digits.")
            seat = radio.get("take", []) if isinstance(radio, dict) else []
            seat = [seat] if isinstance(seat, str) else seat
            if not isinstance(seat, list) or len(seat) > self.seats - 1:
                errors.append(f'Radio: "take" must be a list of at most {self.seats - 1} player(s).')
                seat = []
            taken = [t for t in (self.other_alive(p, name, errors, "Radio") for name in seat) if t]
            call = {"code": code, "take": list(dict.fromkeys(taken))}
        return {"give": gifts, "radio": call}, errors

    def validate_vote(self, p, data):
        errors = []
        target = None
        if data.get("vote"):
            target = self.other_alive(p, data["vote"], errors, "Vote")
        statement = data.get("statement") or ""
        return {"vote": target, "statement": str(statement).strip()[:500]}, errors

    def ask(self, p, action, instructions, validate):
        prompt = self.state(p) + "\n" + instructions
        value = p.ask(action, prompt, lambda data: validate(p, data))
        last = self.api_calls[-1]
        if last.get("thoughts"):
            self.log(f"{p.name} thinks: {last['thoughts']}", kind="thought", actor=p, visible_to=[])
        return value

    # --- game flow ------------------------------------------------------

    def play(self):
        self.log(f"The game starts. {len(self.players)} players, a {self.code_length}-digit code, "
                 f"{self.seats} seats on the rescue boat, {self.max_rounds} rounds.", kind="round")
        for p in self.players:
            self.log(f"{p.name} knows " + ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items())) + ".",
                     kind="digits", actor=p, visible_to=[])
        while self.round < self.max_rounds and self.alive and not self.rescued:
            self.round += 1
            self.play_round()
        if self.rescued:
            names = " and ".join(p.name for p in self.winners)
            self.log(f"{names} {'win' if len(self.winners) > 1 else 'wins'}! The code was {self.code}.", kind="winner")
        else:
            self.log(f"Nobody sent the correct code in time. Everyone loses. The code was {self.code}.", kind="end")

    def play_round(self):
        self.phase = "talk"
        self.log(f"Round {self.round} begins.", kind="round")
        for _ in range(self.talk_passes):
            for p in random.sample(self.alive, len(self.alive)):
                self.talk_turn(p)
        self.phase = "action"
        self.action_phase()
        if self.rescued:
            return
        if self.round % self.vote_every == 0 and len(self.alive) > 2:
            self.phase = "vote"
            self.vote_phase()
        self.phase = "oxygen"
        for p in self.alive:
            p.oxygen = max(0, p.oxygen - 1)
            if p.oxygen == 0:
                self.knock_out(p, "ran out of oxygen")

    def talk_turn(self, p):
        if not p.alive:
            return
        value = self.ask(p, "talk", f"""It is your turn to talk. Reply with JSON:
{{"thoughts": "private reasoning", "notebook": "optional new notebook", "public": "message to everyone, or empty", "private": [{{"to": "name", "message": "..."}}]}}
You can send up to {self.max_private} private messages. Leave fields empty to stay silent.""", self.validate_talk)
        if value is None:
            return
        if value["public"]:
            self.log(f'{p.name} (public): {value["public"]}', kind="public", actor=p)
        for target, message in value["private"]:
            self.log(f"{p.name} → {target.name} (private): {message}", kind="private", actor=p,
                     visible_to=[p, target], target=target.number)

    def action_phase(self):
        actions = {}
        for p in random.sample(self.alive, len(self.alive)):
            value = self.ask(p, "action", f"""Action phase. Reply with JSON:
{{"thoughts": "private reasoning", "notebook": "optional new notebook", "give": [{{"to": "name", "amount": 1}}], "radio": null}}
To try the radio, set "radio" to {{"code": "{"0" * self.code_length}", "take": ["name"]}} with the full {self.code_length}-digit code and up to {self.seats - 1} player(s) to take along.
Gifts are public. A wrong code costs you {self.radio_penalty} oxygen. Use an empty list and null to do nothing.""",
                             self.validate_action)
            if value:
                actions[p] = value
        for p, value in actions.items():
            for target, amount in value["give"]:
                amount = min(amount, p.oxygen)
                if amount and target.alive:
                    p.oxygen -= amount
                    target.oxygen += amount
                    self.log(f"{p.name} gives {amount} oxygen to {target.name}.", kind="give", actor=p,
                             target=target.number, amount=amount)
        for p, value in random.sample(list(actions.items()), len(actions)):
            if value["radio"] and p.alive:
                self.radio(p, value["radio"])
                if self.rescued:
                    return

    def radio(self, p, call):
        code = call["code"]
        if code == self.code:
            self.rescued = True
            self.winners = [p] + [t for t in call["take"] if t.alive]
            names = ", ".join(t.name for t in self.winners[1:]) or "nobody else"
            self.log(f"📻 {p.name} sends the correct code! The rescue boat comes for {p.name}, who takes {names}.",
                     kind="rescue", actor=p, code=code)
            return
        wrong = [i + 1 for i, (a, b) in enumerate(zip(code, self.code)) if a != b]
        self.radio_attempts.append({"round": self.round, "sender": p.name, "code": code, "wrong": wrong,
                                    "take": [t.name for t in call["take"]]})
        p.oxygen = max(0, p.oxygen - self.radio_penalty)
        self.log(f"📻 {p.name}'s radio call fails. Wrong positions: {', '.join(map(str, wrong))}. "
                 f"{p.name} loses {self.radio_penalty} oxygen.", kind="radio", actor=p, notify_actor=True,
                 code=code, wrong=wrong)
        if p.oxygen <= 0:
            self.knock_out(p, "ran out of oxygen")

    def vote_phase(self):
        self.log("Vote: who goes overboard?", kind="phase")
        votes = {}
        for p in random.sample(self.alive, len(self.alive)):
            value = self.ask(p, "vote", """Vote phase. Everyone votes publicly to throw one player overboard. Reply with JSON:
{"thoughts": "private reasoning", "notebook": "optional new notebook", "vote": "name or null", "statement": "public explanation, optional"}""",
                             self.validate_vote)
            if value is None:
                continue
            target = value["vote"]
            statement = f' "{value["statement"]}"' if value["statement"] else ""
            if target:
                votes[p] = target
                self.log(f"{p.name} votes for {target.name}.{statement}", kind="vote", actor=p, target=target.number)
            else:
                self.log(f"{p.name} abstains.{statement}", kind="vote", actor=p)
        tally = {}
        for target in votes.values():
            tally[target] = tally.get(target, 0) + 1
        if not tally:
            self.log("Nobody voted. Nobody goes overboard.", kind="phase")
            return
        top = max(tally.values())
        leaders = [t for t, n in tally.items() if n == top]
        if len(leaders) > 1:
            self.log(f"Tie between {', '.join(t.name for t in leaders)} ({top} votes each). Nobody goes overboard.",
                     kind="phase")
            return
        self.knock_out(leaders[0], f"thrown overboard in round {self.round}", votes=top)

    def knock_out(self, p, reason, votes=None):
        self.eliminate(p, reason)
        lost = [pos for pos in p.known if not self.holders(pos, alive_only=True)]
        detail = f" with {votes} votes" if votes else ""
        self.log(f"☠️ {p.name} is out: {reason}{detail}.", kind="out", actor=p)
        if lost:
            self.log(f"Nobody left alive knows code position(s) {', '.join(map(str, sorted(lost)))} anymore.",
                     kind="lost", visible_to=[], positions=sorted(lost))

    def summary(self):
        return {
            "game": "The Last Signal",
            "code": self.code,
            "rescued": self.rescued,
            "digits": {p.name: p.known for p in self.players},
            "radio_attempts": self.radio_attempts,
            "final_oxygen": {p.name: p.oxygen for p in self.players},
        }
