class Participant:
    def __init__(self, name, number, gpt):
        self.name = name
        self.number = number
        self.gpt = gpt
        self.room = None
        self.log = ""
        self.discussion = []

    def add_log(self, message):
        self.log += f"{message}\n"

    def clear_log(self):
        self.log = ""

    def say(self, message):
        print(f"{self.name}: {message}")

    def think(self, thoughts):
        print(f"{self.name} thinks: {thoughts}")

    def move(self, tile):
        if self.room and tile in self.room.neighbors:
            self.room.participants.remove(self)
            self.room = tile
            self.room.participants.append(self)
            self.think(f"I'm moving to {tile.name}")
        else:
            self.think("I can't move there")