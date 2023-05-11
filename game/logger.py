

class Logger:
    def __init__(self, game):
        self.game = game

    def log(self, message, participant=None):
        if participant:
            participant.log.append(message + "\n")
        else:
            for p in self.game.participants:
                p.log.append(message + "\n")

    def log_round_start(self):
        self.log(f"Round {self.game.round} starts.", None)

    def log_turn_start(self):
        self.log(f"Turn {self.game.turn} starts, new traps set.", None)

    def log_trapped_room_info(self, participant,room):       
        self.log(f"Information about trapped room {room.name} released.", participant)

    def log_start_location(self):
        for participant in self.game.rooms:
            self.log(f"You start in room {participant.room.name}.", participant)

    def log_others_in_room(self):
        for participant in self.game.participants:
            others = participant.room.participants.remove(participant)
            self.log(f"Other participants in the room: {', '.join([p.get_participant() for p in others])}.", participant)

    def log_discussion_start(self):
        self.log("Discussion phase starts.", None)

    def log_discussion_next(self, room, next, start = False):   
        verb = "start" if start else "continue"
        for participant in room.participants:
            name = "You" if participant == next else next.get_participant()
            endung = "" if participant == next else "s"
            self.log(f"{name} {verb}{endung} the discussion.", room.participants)

    def log_discussion_message(self, speaker, message, room):
        recipients = [p for p in room.participants if p != speaker]
        self.log(f"{speaker.get_participant()} says: {message}", recipients)

    def log_discussion_end(self):
        self.log("Discussion phase is over.", None)

    def log_moving_start(self):
        self.log("Moving phase starts.", None)

    def log_moving_info(self, mover, target_room):
        verb = "stay" if mover.room == target_room else "move"
        adverb = "in "if mover.room == target_room else "to"
        for participant in mover.room.participants:
            name = "You" if participant == mover else next.get_participant()
            endung = "" if participant == mover else "s"
            self.log(f"{name} {verb}{endung} {adverb} room {target_room}.", participant)

    def log_traps_activate(self):
        self.log("Traps activate.", None)

    def log_participant_eliminated(self, participant):
        self.log(f"Participant {participant.get_participant()} eliminated.", None)

    def log_alone(self, participant):
        self.log(f"You are alone in room {participant.room}. No discussion phase for you this turn.", participant)



