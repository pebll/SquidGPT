class Participant:
    def __init__(self, name, number, gpt):
        self.name = name
        self.number = number
        self.gpt = gpt
        self.room = None
        self.log = ""
        self.discussion = []

    def get_participant(self):
        return "Participant " + self.number

    def clear_log(self):
        self.log = ""

    def move(self, room):
        self.room.participants.remove(self)
        self.room = room
        self.room.participants.append(self)
            
       
            