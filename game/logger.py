class Logger:
    """Writes messages to the participants' private logs and to the general (spectator) log.

    Every general log line is also stored in game.events with its round, turn, phase and
    kind, so the GUI can filter and colour them.
    """

    def __init__(self, game):
        self.game = game
        self.general_log = ""

    def log(self, message, participant=None):
        if isinstance(participant, list):
            for p in participant:
                p.log += (message + "\n")
        elif participant:
            participant.log += (message + "\n")
        else:
            for p in self.game.participants:
                p.log += (message + "\n")

    def log_general(self, message, kind="info", participant=None, room=None):
        if self.game.echo:
            print(message)
        self.general_log += (message + "\n")
        self.game.events.append({
            "round": self.game.round,
            "turn": self.game.turn,
            "phase": self.game.phase,
            "kind": kind,
            "participant": participant.number if participant else None,
            "room": room,
            "text": message,
        })

    def log_round_start(self):
        message = f"Round {self.game.round} starts."
        self.log(message, None)
        self.log_general(message, kind="round")

    def log_turn_start(self):
        message = f"Turn {self.game.turn} starts."
        self.log(message, None)
        self.log_general(message, kind="turn")

    def log_trapped_room_info(self, participant, room):
        participant.known_traps.append((self.game.round, room.name))
        self.log(f"Information about trapped room {room.name} released.", participant)
        self.log_general(f"{participant.get_participant()} got information that room {room.name} is trapped.",
                         kind="trap_info", participant=participant, room=room.name)

    def log_start_location(self):
        for participant in self.game.participants:
            self.log(f"You start in room {participant.room.name}.", participant)
            self.log_general(f"{participant.get_participant()} starts in room {participant.room.name}.",
                             kind="start", participant=participant, room=participant.room.name)

    def log_others_in_room(self):
        for participant in self.game.participants:
            others = [p.get_participant() for p in participant.room.participants if p != participant]
            if others:
                self.log(f"Other participants in the room: {', '.join(others)}.", participant)

    def log_discussion_start(self):
        self.log("Discussion phase starts.", None)

    def log_discussion_room(self, room):
        self.log_general(f"Discussion phase starts in room {room.name}.", kind="phase", room=room.name)

    def log_discussion_next(self, room, next):
        for participant in room.participants:
            name = "You" if participant == next else next.get_participant()
            ending = "" if participant == next else "s"
            self.log(f"{name} continue{ending} the discussion.", participant)

    def log_discussion_message(self, speaker, message, room):
        recipients = [p for p in room.participants if p != speaker]
        log = f"{speaker.get_participant()} says: {message}" if message else f"{speaker.get_participant()} stays silent."
        self.log(log, recipients)
        self.log_general(log, kind="say", participant=speaker, room=room.name)

    def log_discussion_end(self):
        self.log("Discussion phase is over.", None)

    def log_moving_start(self):
        message = "Moving phase starts."
        self.log(message, None)
        self.log_general(message, kind="phase")

    def log_moving_info(self, mover, target_room):
        verb = "stay" if mover.room == target_room else "move"
        adverb = "in" if mover.room == target_room else "to"
        for participant in mover.room.participants:
            name = "You" if participant == mover else mover.get_participant()
            ending = "" if participant == mover else "s"
            self.log(f"{name} {verb}{ending} {adverb} room {target_room}.", participant)
        self.log_general(f"{mover.get_participant()} {verb}s {adverb} room {target_room.name}.",
                         kind="move", participant=mover, room=target_room.name)

    def log_traps_activate(self):
        message = "Traps activate."
        self.log(message, None)
        trapped = ", ".join(room.name for room in self.game.trapped_rooms)
        self.log_general(f"Traps activate in {trapped}.", kind="traps")

    def log_participant_eliminated(self, participant):
        message = f"{participant.get_participant()} ({participant.name}) was in trapped room {participant.room.name} and is eliminated."
        self.log(message, None)
        self.log_general(message, kind="eliminated", participant=participant, room=participant.room.name)

    def log_alone(self, participant):
        self.log(f"You are alone in room {participant.room}. No discussion phase for you this turn.", participant)

    def log_think(self, participant):
        thought = participant.get_last_response("think")
        if thought is None:
            return
        self.log_general(f"{participant.get_participant()} thinks {thought}.", kind="think", participant=participant)

    def log_winner(self, participant):
        self.log_general(f"{participant.get_participant()} ({participant.name}) is the winner!",
                         kind="winner", participant=participant)
