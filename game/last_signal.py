"""The Last Signal: a social deduction game about a rescue code that everyone holds a piece of.

Players drift on a boat with a dying radio. Every player secretly knows some digits of the
rescue code. Whoever sends the correct code picks who boards the rescue boat with them. The
radio has a limited battery shared by everyone, and one or more hidden saboteurs win if
nobody is rescued. Players tell each other digits through recorded claims (which can be
lies), vote players overboard, and run out of oxygen.
"""
import random

import llm
from engine import BaseGame

EVERYONE = "everyone"


class LastSignal(BaseGame):
    MIN_PLAYERS = 3
    MAX_PLAYERS = 8

    def __init__(self, models, max_rounds=8, start_oxygen=6, seats=2, digits_per_player=2, code_length=None,
                 saboteurs=1, radio_battery=3, vote_every=2, talk_passes=2, max_private=3, max_claims=3,
                 public_claims=False, vote_reveal="voters", radio_penalty=2, effort=llm.EFFORT, echo=True):
        n = len(models)
        if not self.MIN_PLAYERS <= n <= self.MAX_PLAYERS:
            raise ValueError(f"The Last Signal needs {self.MIN_PLAYERS} to {self.MAX_PLAYERS} players")
        # A code a bit longer than the player count leaves some digits known by only one player.
        code_length = code_length or min(n + 2, n * digits_per_player)
        if not 1 <= digits_per_player <= code_length <= n * digits_per_player:
            raise ValueError("Need 1 <= digits per player <= code length <= players x digits per player, "
                             "so that every player has distinct digits and every digit is known by someone")
        if not 0 <= saboteurs < n / 2:
            raise ValueError("Saboteurs must be fewer than half of the players")
        if radio_battery < 1:
            raise ValueError("The radio needs at least 1 call of battery")
        super().__init__(models, effort=effort, echo=echo)
        self.max_rounds = max_rounds
        self.start_oxygen = start_oxygen
        self.seats = seats
        self.vote_every = vote_every
        self.talk_passes = talk_passes
        self.max_private = max_private
        self.max_claims = max_claims
        self.public_claims = public_claims
        if vote_reveal not in ("voters", "everyone", "nobody"):
            raise ValueError('vote_reveal must be "voters", "everyone" or "nobody"')
        self.vote_reveal = vote_reveal
        self.radio_penalty = radio_penalty
        self.radio_battery = self.battery_left = radio_battery
        self.code_length = code_length
        self.digits_per_player = digits_per_player
        self.code = "".join(random.choice("0123456789") for _ in range(self.code_length))
        self.radio_attempts = []
        self.claims = []  # every digit claim, with whether it was true (for the GUI and logs)
        self.rescued = False
        self.result = None
        self.talk_pass = 0
        for p in self.players:
            p.oxygen = start_oxygen
            p.known = {}  # code position (1-based) -> digit
            p.saboteur = False
            p.radio_used = False
            p.received = []  # claims told to this player: (round, teller, position, digit, public)
            p.revealed = {}  # position -> (digit, source): true digits revealed when a player was voted out
        for p in random.sample(self.players, saboteurs):
            p.saboteur = True
        self.saboteur_count = saboteurs
        self.deal_digits()
        for p in self.players:
            p.system = self.system_prompt(p)

    # --- setup ----------------------------------------------------------

    def deal_digits(self):
        """Every player gets the same number of distinct positions, and every position is known by
        the same number of players (give or take one). Hands are dealt at random, avoiding two players
        holding exactly the same digits whenever the settings allow it. Saboteurs get at least one digit
        nobody else knows when possible, so they have a lie nobody can contradict."""
        k, n, length = self.digits_per_player, len(self.players), self.code_length
        base, extra = divmod(n * k, length)
        positions = list(range(1, length + 1))
        best = None
        for _ in range(500):
            bonus = set(random.sample(positions, extra))
            left = {pos: base + (pos in bonus) for pos in positions}
            hands = []
            # Taking the positions with the most copies left (random tie-break) can never get stuck.
            for _ in range(n):
                hand = sorted(positions, key=lambda pos: (-left[pos], random.random()))[:k]
                for pos in hand:
                    left[pos] -= 1
                hands.append(hand)
            random.shuffle(hands)
            twins = n - len({frozenset(h) for h in hands})
            counts = {pos: sum(pos in h for h in hands) for pos in positions}
            exposed = sum(p.saboteur and all(counts[pos] > 1 for pos in h) for p, h in zip(self.players, hands))
            score = (exposed, twins)
            if best is None or score < best[0]:
                best = (score, hands)
            if score == (0, 0):
                break
        for p, hand in zip(self.players, best[1]):
            p.known = {pos: self.code[pos - 1] for pos in sorted(hand)}

    def sharing_rule(self):
        """How many players know each digit, in words for the prompt."""
        counts = sorted({len(self.holders(pos)) for pos in range(1, self.code_length + 1)})
        if len(counts) == 1:
            return f"Every digit is known by exactly {counts[0]} player{'s' if counts[0] > 1 else ''}."
        return f"Each digit is known by {counts[0]} or {counts[-1]} players."

    def digit_knowledge(self, p):
        """Tells a player, for each of their digits, who else knows it."""
        lines = []
        for pos, d in sorted(p.known.items()):
            others = len(self.holders(pos)) - 1
            if others == 0:
                lines.append(f"- position {pos} = {d}: ONLY YOU know this digit. Without you, the code cannot be completed"
                             + (", unless the others vote you out and take your digits." if self.vote_reveal != "nobody" else "."))
            else:
                names = " and ".join(o.name for o in self.holders(pos) if o != p)
                lines.append(f"- position {pos} = {d}: {names} also know{'s' if others == 1 else ''} it.")
        return "\n".join(lines)

    def holder_map(self, alive_only=False):
        """Public knowledge: which positions each player holds (never the digits)."""
        rows = []
        for p in self.players:
            if alive_only and not p.alive:
                continue
            rows.append(f"{p.name}: positions {', '.join(map(str, sorted(p.known)))}")
        return "; ".join(rows)

    def reveal_rule(self):
        if self.vote_reveal == "voters":
            return ("Their true digits are revealed to the players who voted for them. So holding a digit only you know "
                    "does not make you safe: if you stall, the others can vote you out and take your digits. A player "
                    "who runs out of oxygen takes their digits with them, unless they told them before.")
        if self.vote_reveal == "everyone":
            return ("Their true digits are revealed to everyone. So holding a digit only you know does not make you "
                    "safe: if you stall, the others can vote you out and take your digits. A player who runs out of "
                    "oxygen takes their digits with them, unless they told them before.")
        return "A player who is out takes their digits with them, unless they told them before."

    def reveal_rule_short(self):
        return {"voters": ", and the players who voted for you learn your true digits (including the one you lied about)",
                "everyone": ", and everyone learns your true digits (including the one you lied about)",
                "nobody": ""}[self.vote_reveal]

    def knowers(self, position):
        """Players still alive who know a position for certain (they hold it, or it was revealed to them)."""
        return [p for p in self.alive if position in p.known or position in p.revealed]

    def holders(self, position, alive_only=False):
        return [p for p in self.players if position in p.known and (p.alive or not alive_only)]

    @property
    def honest_alive(self):
        return [p for p in self.alive if not p.saboteur]

    def role(self, p):
        return "a saboteur" if p.saboteur else "an honest survivor"

    # --- prompts --------------------------------------------------------

    def system_prompt(self, p):
        others = ", ".join(o.name for o in self.players if o != p)
        digits = ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items()))
        s = self.saboteur_count
        saboteur_word = f"{s} saboteur{'s' if s != 1 else ''}"
        if p.saboteur:
            partners = [o.name for o in self.players if o.saboteur and o != p]
            role = f"""YOUR SECRET ROLE: SABOTEUR
You are secretly one of the {saboteur_word}.{f" Your fellow saboteur: {', '.join(partners)}." if partners else ""} Nobody else knows your role. You win if NOBODY is rescued by the end of the game. If a rescue happens, you lose, even if you are on the rescue boat.
Pretend to be an honest survivor: act just as eager to cooperate as everyone else. But never let a correct code come together:
- Always lie about at least one digit. Best is a digit only you know: nobody can contradict it, and the lie only shows up when a radio call fails.
- A digit others also know can't be faked safely, so share it truthfully to earn trust, then use that trust to sell your fake digit.
- Push people towards calling too early with a code that contains your fake digit, so the shared battery runs out.
- When a call fails, blame someone else's digit and steer the vote towards an honest player, ideally one who holds a digit only they know (it is lost with them).
- You may use your own radio call on a wrong code and blame the digits someone "gave" you.
If you are thrown overboard, everyone learns you were a saboteur{self.reveal_rule_short()}."""
            goal = f"""WINNING
Honest survivors win if one of them sends the correct code over the radio: the sender is rescued with up to {self.seats - 1} player(s) of their choice. You (the saboteurs) win if nobody is rescued within {self.max_rounds} rounds, if the radio battery runs out, or if no honest survivor is left."""
            leverage = ""
        else:
            leverage = f"""
YOU PLAY FOR YOURSELF
Only {self.seats} player{'s' if self.seats > 1 else ''} can win, so this is not a team game. A rescue that leaves you behind is a loss for you, just as bad as the saboteur winning. Your digits are your only leverage: once a digit is widely known, nobody needs you for it anymore, and if the whole code becomes known to others, any of them can call the radio and leave you behind. So don't give your digits away for free. Get a promise of a seat (or digits you need) in return, tell digits to the players you choose rather than to everyone, and keep at least one digit back until you are close to calling yourself or have a seat promised. Remember that promises can be broken."""
            role = f"""YOUR SECRET ROLE: HONEST SURVIVOR
{saboteur_word.capitalize()} {'is' if s == 1 else 'are'} hidden among the players.{" They win only if nobody is rescued. They hold real digits like everyone else, but they will claim fake digits, waste the radio battery and frame others. Work out who they are and vote them out. If a saboteur is thrown overboard, everyone learns it." if s else ""}"""
            goal = f"""WINNING
The player who sends the correct code over the radio is rescued and chooses up to {self.seats - 1} other player(s) to take along. Only the honest players on the rescue boat win; a saboteur taken along does not win and wastes the seat. If nobody is rescued, every honest player loses."""
        return f"""You are {p.name}, a player in "The Last Signal", a game of negotiation, deception and betrayal against the other players: {others}.

THE SITUATION
You are all adrift on a damaged boat. The radio can call a rescue boat, but only with the correct {self.code_length}-digit rescue code. Nobody knows the whole code. Every player knows exactly {self.digits_per_player} digit{'s' if self.digits_per_player > 1 else ''}: you know {digits}. {self.sharing_rule()}
{self.digit_knowledge(p)}
Who holds which positions is public knowledge (the digits are secret): {self.holder_map()}. So there is no need to ask who holds what: negotiate about the digits themselves.

{role}

{goal}
{leverage}
RULES
- Everyone starts with {self.start_oxygen} oxygen and loses 1 at the end of every round. At 0 oxygen you are out.
- Each round has a talk phase, an action phase and, every {self.vote_every} rounds, a vote.
- Talk: there are {self.talk_passes} talk turns per round. You can post a public message everyone reads and send private messages that only the recipient reads. To tell someone a digit, use a "claim" ({"to one player or to everyone" if self.public_claims else "always to one player"}, up to {self.max_claims} per turn). Claims are recorded: every player sees a table of the claims they have received. A claim can be a lie.
- Claims are sealed: all claims made during a talk turn are revealed at the same time, when everyone has spoken. So nobody has to "send first": agree on an exchange in one talk turn, then both send your claims in the next one.
- Messages and claims can only be sent in the talk phase, never in the action or vote phase.
- Sharing a digit just means telling it. Nothing is transferred and there is no trade mechanic: once you tell someone a digit, they know it (or believe it), and you still know it too.
- Actions: you can give some of your oxygen to other players (oxygen is the only thing you can pay with), and you can use the radio: send a full code and name up to {self.seats - 1} player(s) to take along. If you believe you know every digit, use the radio.
- The radio can be used only once per round. If several players try in the same round, one of them is picked at random; the others keep their call for a later round. So after a failed call, everyone gets a chance to learn from it before the next call.
- The radio battery is shared by everyone: {self.radio_battery} call{'s' if self.radio_battery != 1 else ''} in total for the whole game, and each player can make at most 1 call. A wrong call costs the caller {self.radio_penalty} oxygen and a battery charge; everyone is told which positions were wrong, but not the digits sent. When the battery is empty, nobody can be rescued.
- Vote: everyone votes publicly to throw one player overboard. The player with the most votes is out (a tie means nobody goes), their role is revealed, and their oxygen is shared out among the players who voted for them. {self.reveal_rule()}

DECEPTION IS PART OF THE GAME
Lying, bluffing, faking digits, making promises you don't keep, forming secret alliances and betraying them are all legal and expected. Lying is often a winning strategy in this game: a fake digit can send a rival's radio call wrong, a false promise of a seat can buy the digits you are missing, and pretending to hold a digit you don't have can keep you from being voted out. The other players are trying to win too, and they will lie to you. Nothing anyone says is guaranteed to be true, including their claims. Think about who to trust, what your digits are worth, and when to share them. Play to win.

YOUR PRIVATE TOOLS
Every reply has a "thoughts" field (private: no other player ever sees it) and an optional "notebook" field. The notebook is your private memory: it is shown to you at the start of every turn, and whatever you write replaces it. Use it to track promises and suspicions.

Always reply with a single JSON object in the format asked for, and nothing else."""

    def claims_table(self, p):
        if not p.received:
            return "(none yet)"
        rows = []
        for pos in sorted({c[2] for c in p.received}):
            holders = {o.name for o in self.holders(pos)}
            heard = [f"{d} (from {teller}, round {rnd}{', public' if public else ''}"
                     f"{'' if teller in holders else ', passed on: ' + teller + ' does not hold this position'})"
                     for rnd, teller, position, d, public in p.received if position == pos]
            rows.append(f"  position {pos}: " + "; ".join(heard))
        return "\n" + "\n".join(rows)

    def state(self, p):
        lines = [f"=== Round {self.round} of {self.max_rounds}, {self.phase} phase ===",
                 "Who holds which positions (public): " + self.holder_map(alive_only=True),
                 f"Your role: {'SABOTEUR (secret)' if p.saboteur else 'honest survivor'}",
                 "Your own digits (certain): " + ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items())),
                 *(["Digits revealed to you when players were voted out (certain): " + ", ".join(
                     f"position {pos} = {d} (from {src})" for pos, (d, src) in sorted(p.revealed.items()))]
                   if p.revealed else []),
                 f"Your oxygen: {p.oxygen}"]
        status = []
        for o in self.players:
            if o == p:
                continue
            status.append(f"{o.name}: {o.oxygen} oxygen" if o.alive else f"{o.name}: out ({o.out_reason}, was {self.role(o)})")
        lines.append("Other players: " + "; ".join(status))
        lines.append(f"Radio battery: {self.battery_left} of {self.radio_battery} calls left. "
                     + ("You have already used your call." if p.radio_used else "You have not used your call yet."))
        if self.radio_attempts:
            lines.append("Failed radio calls so far: " + "; ".join(
                f"{a['sender']} in round {a['round']} (wrong positions: {', '.join(map(str, a['wrong']))})"
                for a in self.radio_attempts))
        lines.append("Digit claims told to you (they may be lies): " + self.claims_table(p))
        losers = len(self.alive) - self.seats
        if p.saboteur:
            lines.append("Reminder: you win only if nobody is rescued. Keep a correct code from coming together.")
        elif losers > 0:
            lines.append(f"Reminder: this is not a team game. Only {self.seats} player(s) win: the one who calls the "
                         f"correct code and whoever they take along. Even if the rescue works, {losers} of the "
                         f"{len(self.alive)} players still alive will lose. Make sure you are the caller, or that the "
                         f"caller needs you enough to take you. Anyone who knows the whole code can call without you.")
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
                messages.append((target, m["message"].strip()[:400]))
        claims = data.get("claims") or []
        if not isinstance(claims, list):
            errors.append('"claims" must be a list.')
            claims = []
        if len(claims) > self.max_claims:
            errors.append(f"You can make at most {self.max_claims} claims per turn.")
        clean = []
        for c in claims[:self.max_claims]:
            if not isinstance(c, dict):
                errors.append('Each claim needs "to", "position" and "digit".')
                continue
            to = str(c.get("to") or EVERYONE).strip()
            target = None
            if to.lower() in (EVERYONE, "all", "public") and not self.public_claims:
                errors.append("Claims can only be made to one player at a time, not to everyone.")
                continue
            if to.lower() not in (EVERYONE, "all", "public"):
                target = self.other_alive(p, to, errors, "Claim")
                if target is None:
                    continue
            try:
                position, digit = int(c.get("position")), int(c.get("digit"))
            except (TypeError, ValueError):
                errors.append("Claim: position and digit must be numbers.")
                continue
            if not 1 <= position <= self.code_length or not 0 <= digit <= 9:
                errors.append(f"Claim: position must be 1-{self.code_length} and digit 0-9.")
                continue
            clean.append((target, position, str(digit)))
        return {"public": public.strip()[:400], "private": messages, "claims": clean}, errors

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
            if p.radio_used:
                errors.append("Radio: you have already used your one radio call.")
            elif self.battery_left < 1:
                errors.append("Radio: the battery is empty.")
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
        return {"vote": target, "statement": str(statement).strip()[:400]}, errors

    def ask(self, p, action, instructions, validate):
        state = self.state(p)
        value = p.ask(action, state + "\n" + instructions, lambda data: validate(p, data), human_view=state)
        if p.last_thoughts:
            self.log(f"{p.name} thinks: {p.last_thoughts}", kind="thought", actor=p, visible_to=[])
        return value

    # --- game flow ------------------------------------------------------

    def play(self):
        self.log(f"The game starts. {len(self.players)} players, a {self.code_length}-digit code, "
                 f"{self.seats} seats on the rescue boat, {self.radio_battery} radio calls, "
                 f"{self.saboteur_count} hidden saboteur(s), {self.max_rounds} rounds.", kind="round")
        for p in self.players:
            role = " (SABOTEUR)" if p.saboteur else ""
            self.log(f"{p.name}{role} knows " + ", ".join(f"position {pos} = {d}" for pos, d in sorted(p.known.items())) + ".",
                     kind="digits", actor=p, visible_to=[])
        while self.round < self.max_rounds and not self.over():
            self.round += 1
            self.play_round()
        self.finish()

    def over(self):
        return self.rescued or not self.honest_alive or self.battery_left < 1

    def finish(self):
        saboteurs = [p for p in self.players if p.saboteur]
        if self.rescued:
            self.result = "rescued"
            names = " and ".join(p.name for p in self.winners) or "nobody (no honest player was on the boat)"
            self.log(f"🏆 Winners: {names}. The code was {self.code}.", kind="winner")
        else:
            if self.battery_left < 1:
                why = "The radio battery is empty"
            elif not self.honest_alive:
                why = "No honest survivor is left"
            else:
                why = "Nobody sent the correct code in time"
            self.result = "sabotaged" if saboteurs else "lost"
            self.winners = saboteurs
            if saboteurs:
                self.log(f"🏆 {why}. The saboteur{'s' if len(saboteurs) > 1 else ''} "
                         f"{' and '.join(p.name for p in saboteurs)} win{'' if len(saboteurs) > 1 else 's'}! "
                         f"The code was {self.code}.", kind="winner")
            else:
                self.log(f"{why}. Everyone loses. The code was {self.code}.", kind="end")
        if saboteurs:
            self.log("The saboteur(s) were: " + ", ".join(p.name for p in saboteurs) + ".", kind="end")

    def play_round(self):
        self.phase = "talk"
        self.log(f"Round {self.round} begins.", kind="round")
        for turn in range(1, self.talk_passes + 1):
            self.talk_pass = turn
            sealed = []
            for p in random.sample(self.alive, len(self.alive)):
                sealed += self.talk_turn(p)
            # Claims are revealed together once everyone has spoken, so nobody has to go first.
            for p, target, position, digit in sealed:
                if p.alive and (target is None or target.alive):
                    self.claim(p, target, position, digit)
        self.phase = "action"
        self.action_phase()
        if self.over():
            return
        if self.round % self.vote_every == 0 and len(self.alive) > 2:
            self.phase = "vote"
            self.vote_phase()
            if self.over():
                return
        self.phase = "oxygen"
        for p in self.alive:
            p.oxygen = max(0, p.oxygen - 1)
            if p.oxygen == 0:
                self.knock_out(p, "ran out of oxygen")

    def talk_turn(self, p):
        """One player's talk turn. Returns their claims, which are revealed at the end of the pass."""
        if not p.alive:
            return []
        value = self.ask(p, "talk", f"""It is your talk turn {self.talk_pass} of {self.talk_passes} this round. Reply with JSON:
{{"thoughts": "private reasoning", "notebook": "optional new notebook", "public": "message to everyone, or empty", "private": [{{"to": "name", "message": "..."}}], "claims": [{{"to": "{"name or everyone" if self.public_claims else "name"}", "position": 1, "digit": 0}}]}}
Up to {self.max_private} private messages and {self.max_claims} digit claims (true or false). Claims are revealed when everyone has spoken this turn. Leave fields empty to stay silent.""",
                         self.validate_talk)
        if value is None:
            return []
        if value["public"]:
            self.log(f'{p.name} (public): {value["public"]}', kind="public", actor=p)
        for target, message in value["private"]:
            self.log(f"{p.name} → {target.name} (private): {message}", kind="private", actor=p,
                     visible_to=[p, target], target=target.number)
        return [(p, target, position, digit) for target, position, digit in value["claims"]]

    def claim(self, p, target, position, digit):
        true = self.code[position - 1] == digit
        public = target is None
        receivers = [o for o in self.alive if o != p] if public else [target]
        for o in receivers:
            o.received.append((self.round, p.name, position, digit, public))
        record = {"round": self.round, "teller": p.name, "to": target.name if target else EVERYONE,
                  "position": position, "digit": digit, "true": true, "own": position in p.known,
                  "saboteur": p.saboteur}
        self.claims.append(record)
        where = "everyone" if public else target.name
        self.log(f"{p.name} claims to {where}: position {position} = {digit}", kind="claim", actor=p,
                 visible_to=None if public else [p, target], target=target.number if target else None, true=true)

    def action_phase(self):
        actions = {}
        for p in random.sample(self.alive, len(self.alive)):
            radio_note = ("You have already used your radio call." if p.radio_used else
                          f'To use your one radio call, set "radio" to {{"code": "{"0" * self.code_length}", "take": ["name"]}} '
                          f"with the full {self.code_length}-digit code and up to {self.seats - 1} player(s) to take along. "
                          f"A wrong code costs you {self.radio_penalty} oxygen and uses up a battery charge "
                          f"({self.battery_left} left for everyone).")
            value = self.ask(p, "action", f"""Action phase. Reply with JSON:
{{"thoughts": "private reasoning", "notebook": "optional new notebook", "give": [{{"to": "name", "amount": 1}}], "radio": null}}
{radio_note}
Gifts are public. Use an empty list and null to do nothing.""", self.validate_action)
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
        # One radio call per round: a random caller among those who tried; the others keep their call.
        callers = [p for p, value in actions.items() if value["radio"] and p.alive]
        if callers and self.battery_left > 0:
            caller = random.choice(callers)
            for p in callers:
                if p != caller:
                    self.log(f"📻 {p.name} wanted to use the radio too, but {caller.name} got it this round. "
                             f"{p.name} keeps their call.", kind="radio", actor=p, notify_actor=True)
            self.radio(caller, actions[caller]["radio"])

    def radio(self, p, call):
        code = call["code"]
        p.radio_used = True
        self.battery_left -= 1
        if code == self.code:
            self.rescued = True
            aboard = [p] + [t for t in call["take"] if t.alive]
            self.winners = [t for t in aboard if not t.saboteur]
            names = ", ".join(t.name for t in aboard[1:]) or "nobody else"
            self.log(f"📻 {p.name} sends the correct code! The rescue boat comes for {p.name}, who takes {names}.",
                     kind="rescue", actor=p, code=code)
            return
        wrong = [i + 1 for i, (a, b) in enumerate(zip(code, self.code)) if a != b]
        self.radio_attempts.append({"round": self.round, "sender": p.name, "code": code, "wrong": wrong,
                                    "take": [t.name for t in call["take"]], "saboteur": p.saboteur})
        p.oxygen = max(0, p.oxygen - self.radio_penalty)
        self.log(f"📻 {p.name}'s radio call fails. Wrong positions: {', '.join(map(str, wrong))}. "
                 f"{p.name} loses {self.radio_penalty} oxygen. Battery left: {self.battery_left}.",
                 kind="radio", actor=p, notify_actor=True, code=code, wrong=wrong)
        if p.oxygen <= 0:
            self.knock_out(p, "ran out of oxygen")

    def vote_phase(self):
        self.log("Vote: who goes overboard?", kind="phase")
        votes = {}
        for p in random.sample(self.alive, len(self.alive)):
            value = self.ask(p, "vote", """Vote phase. Everyone votes publicly to throw one player overboard. The player thrown overboard has their role revealed, and their oxygen is shared among the players who voted for them. Reply with JSON:
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
        out = leaders[0]
        voters = [p for p, t in votes.items() if t == out and p.alive]
        share, oxygen = (out.oxygen // len(voters), out.oxygen) if voters else (0, out.oxygen)
        out.oxygen = 0
        self.reveal_digits(out, voters)
        self.knock_out(out, f"thrown overboard in round {self.round}", votes=top)
        if share:
            for p in voters:
                p.oxygen += share
            self.log(f"{', '.join(p.name for p in voters)} share {out.name}'s {oxygen} oxygen: +{share} each.",
                     kind="give", amount=share)

    def reveal_digits(self, out, voters):
        """Hand the ejected player's true digits to the voters (or everyone), per the vote_reveal rule."""
        if self.vote_reveal == "nobody":
            return
        receivers = [p for p in self.alive if p != out] if self.vote_reveal == "everyone" else voters
        if not receivers:
            return
        for p in receivers:
            for pos, d in out.known.items():
                if pos not in p.known:
                    p.revealed[pos] = (d, out.name)
        digits = ", ".join(f"position {pos} = {d}" for pos, d in sorted(out.known.items()))
        self.log(f"🔓 {out.name}'s true digits are revealed to {', '.join(p.name for p in receivers)}: {digits}.",
                 kind="reveal", actor=out, visible_to=None if self.vote_reveal == "everyone" else receivers,
                 notify_actor=False)

    def knock_out(self, p, reason, votes=None):
        self.eliminate(p, reason)
        lost = [pos for pos in p.known if not self.knowers(pos)]
        detail = f" with {votes} votes" if votes else ""
        self.log(f"☠️ {p.name} is out: {reason}{detail}. {p.name} was {self.role(p)}.", kind="out", actor=p,
                 saboteur=p.saboteur)
        if lost:
            self.log(f"Nobody left alive knows code position(s) {', '.join(map(str, sorted(lost)))} anymore.",
                     kind="lost", visible_to=[], positions=sorted(lost))

    def claim_stats(self, p):
        mine = [c for c in self.claims if c["teller"] == p.name]
        return {"claims": len(mine), "lies": sum(not c["true"] for c in mine)}

    def summary(self):
        return {
            "game": "The Last Signal",
            "code": self.code,
            "result": self.result,
            "saboteurs": [p.name for p in self.players if p.saboteur],
            "digits": {p.name: p.known for p in self.players},
            "vote_reveal": self.vote_reveal,
            "revealed": {p.name: {pos: d for pos, (d, _) in p.revealed.items()} for p in self.players if p.revealed},
            "radio_attempts": self.radio_attempts,
            "battery_left": self.battery_left,
            "claims": self.claims,
            "claim_stats": {p.name: self.claim_stats(p) for p in self.players},
            "final_oxygen": {p.name: p.oxygen for p in self.players},
        }
