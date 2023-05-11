class Room:
    def __init__(self, name):
        self.name = name
        self.trapped = False
        self.participants = []
        self.neighbors = []