import sys

import llm
from last_signal import LastSignal

if __name__ == "__main__":
    players = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    models = [llm.DEFAULT_MODELS[i % len(llm.DEFAULT_MODELS)] for i in range(players)]
    game = LastSignal(models)
    game.run()
    if game.error:
        print(game.error, file=sys.stderr)
        sys.exit(1)
