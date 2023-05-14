

class Logger:
    general_log = ""

    def __init__(self, game):
        self.game = game

    def log(self, message, participant=None):
        if participant:
            participant.log.append(message + "\n")
        else:
            for p in self.game.participants:
                p.log.append(message + "\n")
    
    def log_general(self, message):
        print(message)
        self.general_log.append(message + "\n")

    def log_round_start(self):
        message = f"Round {self.game.round} starts."
        self.log(message, None)
        self.general_log(message)

    def log_turn_start(self):
        message = f"Turn {self.game.turn} starts, new traps set."
        self.log(message, None)
        self.general_log(message)

    def log_trapped_room_info(self, participant,room):       
        self.log(f"Information about trapped room {room.name} released.", participant)
        self.general_log(f"{participant.get_participant()} got information that room {room.name} is trapped.")

    def log_start_location(self):
        for participant in self.game.rooms:
            self.log(f"You start in room {participant.room.name}.", participant)
            self.general_log(f"{participant.get_participant()} starts in room {participant.room.name}.")

    def log_others_in_room(self):
        for participant in self.game.participants:
            others = participant.room.participants.remove(participant)
            self.log(f"Other participants in the room: {', '.join([p.get_participant() for p in others])}.", participant)

    def log_discussion_start(self):
        self.log("Discussion phase starts.", None)

    def log_discussion_room(self, room):
        self.general_log(f"Discussion phase starts in room {room.name}")

    def log_discussion_next(self, room, next, start = False):   
        verb = "start" if start else "continue"
        for participant in room.participants:
            name = "You" if participant == next else next.get_participant()
            endung = "" if participant == next else "s"
            self.log(f"{name} {verb}{endung} the discussion.", room.participants)

    def log_discussion_message(self, speaker, message, room):
        recipients = [p for p in room.participants if p != speaker]
        log = f"{speaker.get_participant()} says: {message}"
        self.log(log, recipients)
        self.general_log(log)

    def log_discussion_end(self):
        self.log("Discussion phase is over.", None)

    def log_moving_start(self):
        message = "Moving phase starts."
        self.log(message, None)
        self.general_log(message)

    def log_moving_info(self, mover, target_room):
        verb = "stay" if mover.room == target_room else "move"
        adverb = "in "if mover.room == target_room else "to"
        for participant in mover.room.participants:
            name = "You" if participant == mover else mover.get_participant()
            endung = "" if participant == mover else "s"
            self.log(f"{name} {verb}{endung} {adverb} room {target_room}.", participant)
        self.general_log(f"{mover.get_participant()} {verb}s {adverb} room {target_room}.")

    def log_traps_activate(self):
        message = "Traps activate."
        self.log(message, None)
        self.general_log(message)

    def log_participant_eliminated(self, participant):
        message = f"Participant {participant.get_participant()} eliminated."
        self.log(message, None)
        self.general_log(message)

    def log_alone(self, participant):
        self.log(f"You are alone in room {participant.room}. No discussion phase for you this turn.", participant)

    def log_think(self, participant):
        self.general_log(f"""{participant.get_participant()} thinks "{participant.get_last_response("think")}".""")

    def log_winner(self, participant):
        self.general_log(f"{participant.get_participant()} is the winner!") 

