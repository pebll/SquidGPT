class Prompt:

    def initialize(participant, game):
        return f"""You are playing a simple survival game against other AI players. Stay in character as your participant for the whole game and respond only with commands.

Among {game.player_count} participants, you are participant number {participant.number} and your name is {participant.name}.

The map consists of 9 rooms, arranged in a 3 by 3 grid: rows A to C from top to bottom, columns 1 to 3 from left to right. A1 is the room on the top left, and C3 on the bottom right.
Each round of the game, a number of rooms will be trapped, and the knowledge of the trapped rooms will be split among the participants.
At the end of a round, all the participants standing in trapped rooms will be eliminated. The game goes on until there is one participant left, who is named winner. Your goal is to be the last participant standing.
Participants may share, withhold or lie about what they know. Who to trust is up to you.
Each round consists of 3 turns, and each turn consists of two phases: the discussion phase and the moving phase.

In the discussion phase, the participants in the same room can talk to each other. Starting with a random participant, the discussion goes in order until every participant has talked 3 times.
In this phase, your available commands are: say("your message") and think("your thoughts")

In the moving phase, you can move one room vertically or horizontally, or stay where you are. You cannot move diagonally or outside the map. If you make an illegal move, you will stay where you are.
In this phase, your available commands are: move(ROOM) and think("your thoughts"), for example move(B2).

think() is private: no other participant ever sees it. Always use it to explain your thought process and why you chose your action. think() is only valid together with the phase's other command (say() or move()).

Respond with your commands only, each on its own line, and nothing else."""

    def gamestate(participant, game):
        others = [p.get_participant() for p in participant.room.participants if p != participant]
        with_others = " with " + ", ".join(others) if others else " alone"
        return """Reminder of the game state:
You are participant number {} and your name is {}.
There are {} other participant(s) left.
You are in room {}{}.
It is currently Round {} and Turn {}.
""".format(participant.number, participant.name, len(game.participants) - 1, participant.room, with_others, game.round, game.turn)

    def instructions(action):
        return """Instructions:
Respond with your commands only, each on its own line, and nothing else.
If you answer something different from what is expected, your command will not be valid.
Your next available commands are: {}() and think().""".format(action)
