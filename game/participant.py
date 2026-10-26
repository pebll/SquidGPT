import os
import re
import time
import anthropic
from prompt import Prompt

MODEL = os.environ.get("SQUIDGPT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SQUIDGPT_EFFORT", "medium")
VERBOSE = os.environ.get("SQUIDGPT_VERBOSE") == "1"

# Reads ANTHROPIC_API_KEY (or an `ant auth login` profile) from the environment.
client = anthropic.Anthropic()


class Participant:
    def __init__(self, name, number, game):
        self.name = name
        self.number = number
        self.game = game
        self.room = None
        self.log = ""
        self.system = Prompt.initialize(self, game)
        self.discussion = []
        self.last_response = ""
        self.known_traps = []  # (round, room name) pairs this participant was told about
        self.eliminated_round = None
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens

    def get_participant(self):
        return "Participant " + str(self.number)

    def clear_log(self):
        self.log = ""

    def move(self, room):
        self.room.participants.remove(self)
        self.room = room
        self.room.participants.append(self)

    def get_response(self, prompt, action):
        self.game.checkpoint()
        if VERBOSE:
            print(f"--- PROMPT to {self.get_participant()} ---\n{prompt}")
        call = {
            "id": len(self.game.api_calls) + 1,
            "participant": self.number,
            "name": self.name,
            "action": action,
            "round": self.game.round,
            "turn": self.game.turn,
            "prompt": prompt,
            "status": "pending",
        }
        self.game.api_calls.append(call)
        self.discussion.append({"role": "user", "content": prompt})
        start = time.time()
        try:
            response = client.beta.messages.create(
                model=self.game.model,
                max_tokens=16000,
                system=self.system,
                messages=self.discussion,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": self.game.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as e:
            call.update(status="error", error=f"{type(e).__name__}: {e}", latency=time.time() - start)
            raise
        # Keep the full content (thinking blocks included) so the history stays append-only.
        self.discussion.append({"role": "assistant", "content": response.content})
        text = "".join(b.text for b in response.content if b.type == "text")
        self.last_response = "" if response.stop_reason == "refusal" else text
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        call.update(
            status="refused" if response.stop_reason == "refusal" else "ok",
            response=text,
            thinking="\n\n".join(b.thinking for b in response.content if b.type == "thinking" and b.thinking),
            stop_reason=response.stop_reason,
            model=response.model,
            fallback=any(b.type == "fallback" for b in response.content),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency=time.time() - start,
        )
        call["parsed"] = {cmd: self.get_last_response(cmd) for cmd in (action, "think")}
        if VERBOSE:
            print(f"--- RESPONSE ({response.usage.output_tokens} output tokens) ---\n{self.last_response}")
        self.clear_log()
        return self.last_response

    def get_last_response(self, type):
        # Commands look like say("...") / think("...") / move(B2), ideally one per line.
        quotes = "\"'“”‘’"
        pattern = rf"\b{type}\(\s*(.*?)\s*\)\s*$"
        match = re.search(pattern, self.last_response, re.MULTILINE | re.DOTALL)
        if not match:
            match = re.search(rf"\b{type}\(\s*(.*?)\s*\)", self.last_response, re.DOTALL)
        return match.group(1).strip(quotes) if match else None

    def get_discussion(self):
        result = f"system: {self.system}\n"
        for entry in self.discussion:
            content = entry["content"]
            if not isinstance(content, str):
                content = "".join(b.text for b in content if b.type == "text")
            result += f"{entry['role']}: {content}\n"
        return result
