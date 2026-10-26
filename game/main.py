import sys
from game import Game

if __name__ == "__main__":
    game = Game()
    game.run()
    if game.error:
        print(game.error, file=sys.stderr)
        sys.exit(1)
