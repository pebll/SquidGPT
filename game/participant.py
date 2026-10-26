import os
import re
import anthropic
from prompt import Prompt

MODEL = os.environ.get("SQUIDGPT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SQUIDGPT_EFFORT", "medium")
VERBOSE = os.environ.get("SQUIDGPT_VERBOSE") == "1"

# Reads ANTHROPIC_API_KEY (or an `ant auth login` profile) from the environment.
client = anthropic.Anthropic()


class Participant:
    def __init__(self, name, number, model, game):
        self.name = name
        self.number = number
        self.model = model
        self.room = None
        self.log = ""
        self.system = Prompt.initialize(self, game)
        self.discussion = []
        self.last_response = ""
        self.game = game
        self.total_tokens = 0

    def get_participant(self):
        return "Participant " + str(self.number)

    def clear_log(self):
        self.log = ""

    def move(self, room):
        self.room.participants.remove(self)
        self.room = room
        self.room.participants.append(self)

    def get_response(self, prompt):
        if VERBOSE:
            print(f"--- PROMPT to {self.get_participant()} ---\n{prompt}")
        self.discussion.append({"role": "user", "content": prompt})
        response = client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=self.system,
            messages=self.discussion,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        # Keep the full content (thinking blocks included) so the history stays append-only.
        self.discussion.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "refusal":
            self.last_response = ""
        else:
            self.last_response = "".join(b.text for b in response.content if b.type == "text")
        self.total_tokens += response.usage.input_tokens + response.usage.output_tokens
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
