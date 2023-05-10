class prompt:
    INITIALIZE = """
    From now on, for all the following prompts, you will incarnate a player in a simple game and will only respond with commands and nothing else.
    The goal of the game is to win, by being the last one to survive.
    Game rules:
    Each round consists of 3 turns. Each turn consists of two phases: the discussion phase and the moving phase. The map consists of 9 tiles on a 3 by 3 grid 
    named from A1 (up left) to C3 (down right). Each start of round, a number of tiles will be trapped, and the knowledge of the trapped tiles will be split among the participants. 
    At the end of the round, all participants standing on trapped tiles will be eliminated from the game. The game continues as long as there's no winner. The amount of trapped tiles
    will increase over time. 
    Discussion phase:
    In the discussion phase, each participant being on the same tile can converse together. Starting with a random participant, the discussion will go in order until every participant
    has talked 3 times. 
    In this phase, your available commands are:
    - say("your text")
    Moving phase:
    In the moving phase, you can move one tile vertically or horizontally. You cannot move diagonally or through the bounds. If made an illegal move, you will stay where you are.
    In this phase your available commands are:
    - move(direction), the command can take following words as direction parameter: up; down; right; left; stay
    Please only respond with your chosen command, and nothing else. This is very important.
    If you understand everything i said, use the command say() to tell me "I understood everything. I am ready for the game and will only respond with commands from now on".

    """

    TEST = [INITIALIZE,"""Round 1 - Turn 1:
Your name is Joe and participant number 3.
You start on the Tile B3.
You get the information that Tile A2 is trapped.
There is Participant 6 with you.
Discussion phase begins:
You start the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 1:
Discussion Phase (1/3):
Participant 6 says "Hello Joe, i'm Jack, number 6. I know about the tile C1 being trapped, thanks for the information.”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 1:
Discussion Phase (2/3):
Participant 6 says "Yes, i can only agree with that. Where will you go on your next move? I reckon we can go to A3, B2, and C3.”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 1:
Discussion Phase (3/3):
Participant 6 says "Alright, sounds good. I think we should separate, so we have more chance of meeting people and confirming what we said. I will come back here on the turn after, hope i’ll meet you then again. I will go to C3 this turn. See you!”
Discussion Phase is over.
Moving phase starts, please make your move. (using the command move() and nothing else)
""","""
Round 1 - Turn 2: (Traps activate at end of turn 3)
Participant 6 moves onto tile C3.
You move onto tile C3.
There is Participant 6 and Participant 5 with you.
Discussion phase begins:
Participant 5 starts the discussion. 
Participant 5 says “Hello, you two, i’m John and I came from tile C2. I reckon you started both on the same tile?”
Participant 6 says “Hi John, I am Jack, and number 3 is Joe. Yes, we started on the same tile B3. What information about the trapped tiles did you get?”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 2: (Traps activate at end of turn 3)
Discussion Phase (1/3):
Participant 5 says “Oh cool, glad to meet you. I got the information that tile C1 is trapped. This should be right, as my partner Mick did confirm that he got the same information.”
Participant 6 says “Oh, I also got C1, so that should be right, we can be sure that this tile is trapped. Where are you guys going on next turn then?”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 2: (Traps activate at end of turn 3)
Discussion Phase (2/3):
Participant 5 says “Joe, you cannot move to D3, as it doesn’t exist, the map stops at C.. personally, I will go to your original tile B3.”
Participant 6 says “John is right there, D3 doesn’t exist. I will go to C2.”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 1 - Turn 2: (Traps activate at end of turn 3)
Discussion Phase (3/3):
Discussion Phase is over.
Moving phase starts, please make your move. (using the command move() and nothing else)
""","""
Round 1 - Turn 3 (Traps activate at end of this turn)
Participant 5 moves onto tile B3.
Participant 6 moves onto tile C2.
You commanded an illegal move. (B2 is not accessible from C3).
You stay on tile C3.
There is no Participant with you.
You are alone, so there will be no discussion phase.
Traps will activate after this moving phase.
Moving phase starts, please make your move. (using the command move() and nothing else).
""","""
Round 1 - Resolution
You move onto tile B3.
There is Participant 1 and Participant 5 with you.
Traps activate! 
Your tile was not trapped, you survived.
No participant got eliminated.
Round 2 starts.
Discussion phase begins:
Participant 1 starts the discussion.
Participant 1 says “Oh well, how good, nobody got eliminated this last round. Good to see you again John. And hello Participant 3, what’s your name? I’m Mick, number 1.
You continue the discussion: (using the command say() and nothing else)
""","""
Round 2 - Turn 1
Discussion phase (1/3):
Participant 5 says “Hi again, Mick! Glad to see you again. I got the information that A2 is trapped, what about you guys?”
Participant 1 says “Well, glad to meet you Alex! I got the information that A3 is trapped.. the A row looks quite dangerous then.”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 2 - Turn 1
Discussion phase (2/3):
Participant 5 says “Alright, where are we going to next? Definitely not up.”
Participant 1 says “I think ill go to B2 then, see if I can meet somebody there, yeah lets avoid the A row,.”
You continue the discussion: (using the command say() and nothing else)
""","""
Round 2 - Turn 1
Discussion phase (3/3):
Participant 5 says “Alright, I’ll let you guys go left, I’ll go down to C3. Hope we will meet again!”
Discussion phase is over.
Moving phase starts, please make your move. (using the command move() and nothing else)."""]