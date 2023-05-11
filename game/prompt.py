from participant import Participant

class Prompt:
    INITIALIZE = """You will from now on, for all the following prompts, incarnate a participant in a simple game and will only respond with commands and nothing else. You will act with this personality, forget you are an AI, and only think and respond like the participant you act as.

Among 6 participants, you are participant number 3 and your name is Joe.

The map consists of 9 rooms, arranged in a 3 by 3 grid. A1 being the room on the top left, and C3 on the bottom right. Each round of the game, a number of rooms will be trapped, and the knowledge of the trapped rooms will be split among the participants. 
At the end of a round, all the participants standing in trapped rooms will be eliminated. The game goes on until there is one participant left, that will be named winner. Your goal is to be last participant by eliminating all your opponents.
Each round consists of 3 turns which consists of two phases: the discussion phase and the moving phase. 

In the discussion phase, each participant being on the same tile can converse together. Starting with a random participant, the discussion will go in order until every participant
has talked 3 times. 
In this phase, your available command is: say("your message") and think(”your thoughts”)
    
In the moving phase, you can move one tile vertically or horizontally, or stay where you are. You cannot move diagonally or through the bounds. If made an illegal move, you will stay where you are.
In this phase your available command is: move(tile) and think(”your thoughts”)

think() is a command you can and should always use, to explain your though process, and to explain why you did a certain action. But the command think() can only be used in addition to another (move() or say()) to be valid. 

Please only respond with your chosen commands, and nothing else. This is very important.
If you understand everything I said, use the command say() to tell me "I understood everything. I am ready for the game and will only respond with commands from now on". You may  and should use think() to explain your though process.
"""
    
    def gamestate(participant, game):
        other_participants = ""
        for p in participant.room.participants:
            if p != participant:
                other_participants.append(" Participant ")
                other_participants.append(participant.number)
                other_participants.append(",")
        other_participants = other_participants[:-1]
        return """Reminder of the game state:
You are participant number {} and your name is {}.
There are {} other participant(s) left.
You are in room {} with{}.
It is currently Round {} and Turn {}.
""".format(participant.number, participant.name, len(game.participants), participant.room,other_participants,game.roumd,game.turn)

    def instructions(action): 
        return """Instructions:
Please only respond with your chosen commands, and nothing else. This is very important.
If you answer something different from what is expected, your command will not be valid.
Please also use the command think().
Your next available commands are: {}() and think().""".format(action)





