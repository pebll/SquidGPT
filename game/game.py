import random
from participant import Participant
from room import Room
from prompt import Prompt
from logger import Logger
import os
import re
import time

class Game:
    
    def __init__(self):
        self.room_names = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
        self.rooms = self.create_rooms()
        self.participants = self.create_participants()
        self.round = 0
        self.turn = 0        
        self.all_participants = self.participants
        self.logger = Logger(self)
        self.last_gpt_call = time.time()

    def create_rooms(self):      
        rooms = {name: Room(name) for name in self.room_names}
        for name, room in rooms.items():
            neighbors = []
            row, col = name
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                neighbor = chr(ord(row) + dr) + str(int(col) + dc)
                if neighbor in self.room_names:
                    neighbors.append(neighbor)
            room.neighbors = neighbors
        return rooms

    def create_participants(self):
        participants = []
        names = ["Alice", "Bob", "Charlie", "David", "Joe", "Fred", "Barty", "Anne", "Juliette"]
        for i in range(1, 7):
            name = random.choice(names)
            names.remove(name)
            gpt = "gpt-3.5-turbo"
            participant = Participant(name, i, gpt, self)
            participants.append(participant)
        return participants

    def assign_starting_rooms(self):
        starting_rooms = random.sample(list(self.rooms.values()), len(self.participants) // 2)
        for i, room in enumerate(starting_rooms):
            participant1, participant2 = self.participants[2*i], self.participants[2*i+1]
            participant1.room = room
            participant2.room = room
            room.participants.extend([participant1, participant2])
            print("DEBUG room name:" + room.name + " " + str(room.participants))

    def start(self):
        self.assign_starting_rooms()      
        while len(self.participants) > 1 and self.round < 2: #TEST
            self.play_round()
        winner = self.participants[0]
        self.logger.log_winner(winner)

    def play_round(self):
        self.round += 1
        self.logger.log_round_start()
        self.turn = 1
        self.set_traps()
        self.distribute_trapped_room_info()
        if self.round == 1: self.logger.log_start_location()
        for turn in range (1, 4):
            self.turn = turn
            self.logger.log_turn_start()
            self.logger.log_others_in_room()
            self.discussion_phase()
            self.moving_phase()
        self.logger.log_traps_activate()
        self.eliminate_trapped()    

    def set_traps(self):
        trap_count = random.randint(1, 3) # Change later to incrementing
        trapped_rooms = random.sample(list(self.rooms.values()), trap_count)
        for room in trapped_rooms:
            room.trapped = True

    def distribute_trapped_room_info(self):

        trapped_rooms = [room for room in self.rooms.values() if room.trapped]
        random.shuffle(trapped_rooms)
        # Assign at least one trapped room to each participant
        for i, participant in enumerate(self.participants):
            self.logger.log_trapped_room_info(participant, trapped_rooms[i % len(trapped_rooms)])
        # Assign remaining trapped rooms randomly to participants
        for i in range(len(self.participants), len(trapped_rooms)):
            participant = random.choice(self.participants)
            self.logger.log_trapped_room_info(participant, trapped_rooms[i])

    def discussion_phase(self):
        self.logger.log_discussion_start()
        for room in self.rooms.values():
            if len(room.participants) > 1:
                self.logger.log_discussion_room(room)
                order = []
                temp_order = random.sample(room.participants, len(room.participants))
                for _ in range(3):
                    order.extend(temp_order)
                for participant in order:
                    self.logger.log_discussion_next(room, participant)
                    prompt = self.create_prompt(participant, "say")                                
                    participant.get_response(prompt)
                    response = participant.get_last_response("say")                                    
                    self.logger.log_discussion_message(participant, response, room)
                    self.logger.log_think(participant)
            elif len(room.participants) == 1:
                self.logger.log_alone(room.participants[0])
        self.logger.log_discussion_end()

    def moving_phase(self):
        self.logger.log_moving_start()
        for participant in self.participants:
            prompt = self.create_prompt(participant, "move")                             
            participant.get_response(prompt)
            target_room_name = participant.get_last_response("move")               
            if target_room_name not in participant.room.neighbors:
                target_room_name = participant.room.name
            target_room = self.rooms[target_room_name]
            self.logger.log_moving_info(participant, target_room)
            self.logger.log_think(participant)
            participant.move(target_room)
              
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
                self.logger.log_participant_eliminated(participant)
        self.participants = remaining_participants
        for room in self.rooms.values():
            room.trapped = False

    def save_logs(self):
        #create new folder
        folder_prefix = "test_log_"
        base_folder_path = "C:/Users/ThinkCenter/Documents/GitHub/SquidGPT/logs"
        existing_folders = [folder for folder in os.listdir(base_folder_path) if folder.startswith(folder_prefix)]
        highest_index = 0
        for folder in existing_folders:
            index = int(re.findall(r'\d+', folder)[0])
            if index > highest_index:
                highest_index = index
        folder_name = f"{folder_prefix}{highest_index + 1}"
        folder_path = os.path.join(base_folder_path, folder_name)
        os.makedirs(folder_path)
        #save the general log
        file_name = f"general.txt"
        file_path = os.path.join(folder_path, file_name)        
        with open(file_path, "w") as file:
            file.write(self.logger.general_log)
        #save individual logs
        for index, participant in enumerate(self.all_participants):
            file_name = f"participant_{index + 1}.txt"
            file_path = os.path.join(folder_path, file_name)        
            with open(file_path, "w") as file:
                file.write(participant.get_discussion())
