import random
from participant import Participant
from room import Room
from prompt import Prompt

class Game:
    # Initialize
    def __init__(self):
        self.rooms = self.create_rooms()
        self.participants = self.create_participants()
        self.round = 1
        self.turn = 1

    def create_rooms(self):
        room_names = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
        rooms = {name: Room(name) for name in room_names}
        for name, room in rooms.items():
            neighbors = []
            row, col = name
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = chr(ord(row) + dr) + str(int(col) + dc)
                if neighbor in rooms:
                    neighbors.append(rooms[neighbor])
            room.neighbors = neighbors
        return rooms

    def create_participants(self):
        participants = []
        names = ["Alice", "Bob", "Charlie", "David", "Joe", "Fred", "Barty", "Anne", "Juliette"]
        for i in range(1, 7):
            name = random.choice(names)
            names.remove(name)
            gpt = "gpt-3.5-turbo"
            participant = Participant(name, i, gpt)
            participants.append(participant)
        return participants

    def assign_starting_rooms(self):
        starting_rooms = random.sample(list(self.rooms.values()), len(self.participants) // 2)
        for i, room in enumerate(starting_rooms):
            participant1, participant2 = self.participants[2*i], self.participants[2*i+1]
            participant1.room = room
            participant2.room = room
            room.participants.extend([participant1, participant2])

    def start(self):
        self.assign_starting_rooms()
        while len(self.participants) > 1:
            self.play_round()
        winner = self.participants[0]
        print(f"{winner.name} is the winner!")

    def play_round(self):
        self.set_traps()
        self.discussion_phase()
        self.moving_phase()
        self.eliminate_trapped()

    def set_traps(self):
        trap_count = random.randint(1, 3)
        trapped_rooms = random.sample(list(self.rooms.values()), trap_count)
        for room in trapped_rooms:
            room.trapped = True

    def discussion_phase(self):
        for room in self.rooms.values():
            if len(room.participants) > 1:
                order = []
                temp_order = random.sample(room.participants, len(room.participants))
                for _ in range(3):
                    order.extend(temp_order)
                for participant in order:
                    prompt = self.create_prompt(participant, "discuss")
                    # Use GPT-3 to generate discussion responses using participant.chat_completion
                    response = "Let's discuss the trapped rooms."
                    participant.discussion.append({"role": "user", "content": prompt})
                    participant.discussion.append({"role": "assistant", "content": response})
                    participant.say(response)
                    participant.think("I need to figure out the trapped rooms.")
                    participant.clear_log()

    def moving_phase(self):
        for participant in self.participants:
            prompt = self.create_prompt(participant, "move")
            # Use GPT-3 to generate the desired move using participant.chat_completion
            target_room_name = "A1"  # Replace this with the generated room name
            if target_room_name in self.rooms:
                target_room = self.rooms[target_room_name]
                participant.move(target_room)
                participant.add_log(f"Moved to {target_room_name}")
                participant.clear_log()

    def create_prompt(self, participant, action):
        game_state = Prompt.gamestate(participant, self)
        log = participant.log
        instructions = Prompt.instructions(action)
        return f"{game_state}{log}{instructions}"

    def eliminate_trapped(self):
        remaining_participants = []
        for participant in self.participants:
            if not participant.room.trapped:
                remaining_participants.append(participant)
            else:
                participant.think("I'm eliminated")
        self.participants = remaining_participants
        for room in self.rooms.values():
            room.trapped = False
