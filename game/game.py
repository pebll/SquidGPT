import json
import random
import threading
import traceback
from participant import Participant, MODEL, EFFORT
from room import Room
from prompt import Prompt
from logger import Logger
import os
import re

NAMES = ["Alice", "Bob", "Charlie", "David", "Joe", "Fred", "Barty", "Anne", "Juliette"]
MAX_PLAYERS = len(NAMES)


class GameStopped(Exception):
    pass


class Game:

    def __init__(self, player_count=6, max_rounds=10, model=MODEL, effort=EFFORT, echo=True):
        if not 2 <= player_count <= MAX_PLAYERS:
            raise ValueError(f"player_count must be between 2 and {MAX_PLAYERS}")
        self.room_names = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
        self.rooms = self.create_rooms()
        self.player_count = player_count
        self.max_rounds = max_rounds
        self.model = model
        self.effort = effort
        self.echo = echo
        self.round = 0
        self.turn = 0
        self.phase = "setup"
        self.status = "ready"  # ready, running, paused, finished, stopped, error
        self.error = None
        self.log_folder = None
        self.events = []
        self.api_calls = []
        self.trapped_rooms = []  # rooms trapped in the current (or last) round
        self.participants = self.create_participants()
        self.all_participants = list(self.participants)
        self.logger = Logger(self)
        # Controls used by the GUI: pause/resume, single-step and stop.
        self._resume = threading.Event()
        self._resume.set()
        self._stop = threading.Event()
        self.step_mode = False

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
        names = random.sample(NAMES, self.player_count)
        return [Participant(name, i, self) for i, name in enumerate(names, start=1)]

    def assign_starting_rooms(self):
        # Pairs of participants share a room; with an odd count the last one starts alone.
        groups = [self.participants[i:i + 2] for i in range(0, len(self.participants), 2)]
        starting_rooms = random.sample(list(self.rooms.values()), len(groups))
        for room, group in zip(starting_rooms, groups):
            for participant in group:
                participant.room = room
                room.participants.append(participant)

    # --- controls -------------------------------------------------------

    @property
    def paused(self):
        """True when paused or single-stepping, i.e. when the GUI should offer Resume."""
        return self.step_mode or not self._resume.is_set()

    def pause(self):
        self._resume.clear()
        if self.status == "running":
            self.status = "paused"

    def resume(self):
        self.step_mode = False
        self._resume.set()

    def step(self):
        """Let exactly one more API call through, then pause again."""
        self.step_mode = True
        self._resume.set()

    def stop(self):
        self._stop.set()
        self._resume.set()

    def checkpoint(self):
        """Called before every API call: honours pause, step and stop requests."""
        if self.step_mode:
            self._resume.clear()
            self.step_mode = False
            self.status = "paused"
        if not self._resume.is_set():
            self.status = "paused"
            self._resume.wait()
        if self._stop.is_set():
            raise GameStopped()
        self.status = "running"

    def run(self):
        """Run a full game, catching errors so a background thread can report them."""
        try:
            self.start()
            self.status = "finished"
        except GameStopped:
            self.logger.log_general("Game stopped by user.", kind="end")
            self.status = "stopped"
        except Exception as e:
            self.error = traceback.format_exc()
            self.logger.log_general(f"Game crashed: {type(e).__name__}: {e}", kind="error")
            self.status = "error"
        finally:
            self.phase = "over"
            try:
                self.save_logs()
            except Exception:
                self.error = (self.error or "") + "\nSaving logs failed:\n" + traceback.format_exc()

    # --- game flow ------------------------------------------------------

    def start(self):
        self.status = "running"
        self.assign_starting_rooms()
        while len(self.participants) > 1 and self.round < self.max_rounds:
            self.play_round()
        if len(self.participants) == 1:
            self.logger.log_winner(self.participants[0])
        elif not self.participants:
            self.logger.log_general("Everyone was eliminated. Nobody wins.", kind="end")
        else:
            survivors = ", ".join(p.get_participant() for p in self.participants)
            self.logger.log_general(f"Round limit reached. Survivors: {survivors}.", kind="end")
        total_tokens = sum(p.total_tokens for p in self.all_participants)
        self.logger.log_general(f"Total tokens used: {total_tokens}.", kind="end")

    def play_round(self):
        self.round += 1
        self.turn = 0
        self.logger.log_round_start()
        self.set_traps()
        self.distribute_trapped_room_info()
        if self.round == 1:
            self.logger.log_start_location()
        for turn in range(1, 4):
            self.turn = turn
            self.logger.log_turn_start()
            self.logger.log_others_in_room()
            self.discussion_phase()
            self.moving_phase()
        self.phase = "traps"
        self.logger.log_traps_activate()
        self.eliminate_trapped()

    def set_traps(self):
        trap_count = random.randint(1, 3)  # Change later to incrementing
        self.trapped_rooms = random.sample(list(self.rooms.values()), trap_count)
        for room in self.trapped_rooms:
            room.trapped = True

    def distribute_trapped_room_info(self):
        trapped_rooms = list(self.trapped_rooms)
        random.shuffle(trapped_rooms)
        # Assign at least one trapped room to each participant
        for i, participant in enumerate(self.participants):
            self.logger.log_trapped_room_info(participant, trapped_rooms[i % len(trapped_rooms)])
        # Assign remaining trapped rooms randomly to participants
        for i in range(len(self.participants), len(trapped_rooms)):
            participant = random.choice(self.participants)
            self.logger.log_trapped_room_info(participant, trapped_rooms[i])

    def discussion_phase(self):
        self.phase = "discussion"
        self.logger.log_discussion_start()
        for room in self.rooms.values():
            if len(room.participants) > 1:
                self.logger.log_discussion_room(room)
                speakers = random.sample(room.participants, len(room.participants))
                for participant in speakers * 3:
                    self.logger.log_discussion_next(room, participant)
                    participant.get_response(self.create_prompt(participant, "say"), "say")
                    response = participant.get_last_response("say")
                    self.logger.log_discussion_message(participant, response, room)
                    self.logger.log_think(participant)
            elif len(room.participants) == 1:
                self.logger.log_alone(room.participants[0])
        self.logger.log_discussion_end()

    def moving_phase(self):
        self.phase = "moving"
        self.logger.log_moving_start()
        for participant in self.participants:
            participant.get_response(self.create_prompt(participant, "move"), "move")
            target_room_name = (participant.get_last_response("move") or "").upper()
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
                participant.eliminated_round = self.round
                self.logger.log_participant_eliminated(participant)
                participant.room.participants.remove(participant)
        self.participants = remaining_participants
        for room in self.rooms.values():
            room.trapped = False

    # --- persistence ----------------------------------------------------

    def save_logs(self):
        folder_prefix = "test_log_"
        base_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(base_folder_path, exist_ok=True)
        indexes = [int(m.group(1)) for folder in os.listdir(base_folder_path)
                   if (m := re.fullmatch(rf"{folder_prefix}(\d+)", folder))]
        folder_path = os.path.normpath(os.path.join(base_folder_path, f"{folder_prefix}{max(indexes, default=0) + 1}"))
        os.makedirs(folder_path)
        with open(os.path.join(folder_path, "general.txt"), "w", encoding="utf-8") as file:
            file.write(self.logger.general_log)
        for index, participant in enumerate(self.all_participants):
            with open(os.path.join(folder_path, f"participant_{index + 1}.txt"), "w", encoding="utf-8") as file:
                file.write(participant.get_discussion())
        # Every API call with its prompt, raw response, reasoning summary, tokens and latency.
        with open(os.path.join(folder_path, "api_calls.jsonl"), "w", encoding="utf-8") as file:
            for call in self.api_calls:
                file.write(json.dumps(call, ensure_ascii=False) + "\n")
        self.log_folder = folder_path
        if self.echo:
            print(f"Logs saved to {folder_path}")
