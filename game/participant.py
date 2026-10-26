import os
import re
import time
from openai import OpenAI
from prompt import Prompt

# SCC KI-Toolbox (KIT), an OpenAI-compatible API.
BASE_URL = os.environ.get("KI_TOOLBOX_BASE_URL", "https://ki-toolbox.scc.kit.edu/api/v1")
MODELS = {
    "google.claude-opus-5.5": "Claude Opus 5.5",
    "google.claude-sonnet-5.5": "Claude Sonnet 5.5",
    "azure.gpt-6-luna": "GPT 6 Luna (Strong!)",
    "alias.complex-local": "GLM Complex (local)",
    "alias.medium-local": "DeepSeek Middle (local)",
}
MODEL = os.environ.get("SQUIDGPT_MODEL", "google.claude-opus-5.5")
# "default" sends no reasoning_effort and leaves it to the model.
EFFORT = os.environ.get("SQUIDGPT_EFFORT", "default")
VERBOSE = os.environ.get("SQUIDGPT_VERBOSE") == "1"

client = OpenAI(base_url=BASE_URL, api_key=os.environ.get("KI_TOOLBOX_API_KEY", "missing-api-key"))


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
        extra = {} if self.game.effort == "default" else {"reasoning_effort": self.game.effort}
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=self.game.model,
                messages=[{"role": "system", "content": self.system}] + self.discussion,
                **extra,
            )
        except Exception as e:
            call.update(status="error", error=f"{type(e).__name__}: {e}", latency=time.time() - start)
            raise
        choice = response.choices[0]
        text = choice.message.content or ""
        self.discussion.append({"role": "assistant", "content": text})
        refused = choice.finish_reason == "content_filter"
        self.last_response = "" if refused else text
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        # Some models behind the toolbox (e.g. DeepSeek, GLM) return their reasoning in a non-standard field.
        thinking = getattr(choice.message, "reasoning_content", None) or getattr(choice.message, "reasoning", None)
        call.update(
            status="refused" if refused else "ok",
            response=text,
            thinking=thinking if isinstance(thinking, str) else "",
            stop_reason=choice.finish_reason,
            model=response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency=time.time() - start,
        )
        call["parsed"] = {cmd: self.get_last_response(cmd) for cmd in (action, "think")}
        if VERBOSE:
            print(f"--- RESPONSE ({output_tokens} output tokens) ---\n{self.last_response}")
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
            result += f"{entry['role']}: {entry['content']}\n"
        return result
