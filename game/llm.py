"""Model access through the SCC KI-Toolbox (KIT), an OpenAI-compatible API."""
import os
import time
from openai import OpenAI

BASE_URL = os.environ.get("KI_TOOLBOX_BASE_URL", "https://ki-toolbox.scc.kit.edu/api/v1")
MODELS = {
    "google.claude-opus-5.5": "Claude Opus 5.5",
    "google.claude-sonnet-5.5": "Claude Sonnet 5.5",
    "azure.gpt-6-luna": "GPT 6 Luna",
    "alias.complex-local": "GLM Complex (local)",
    "alias.medium-local": "DeepSeek Middle (local)",
}
# Pseudo model ID for a seat played by a person through the GUI.
HUMAN = "human"
# Comma-separated list, assigned to players in turn. Defaults to one player per toolbox model.
DEFAULT_MODELS = [m.strip() for m in os.environ.get("SQUIDGPT_MODELS", ",".join(MODELS)).split(",") if m.strip()]
# "default" sends no reasoning_effort and leaves it to the model.
EFFORT = os.environ.get("SQUIDGPT_EFFORT", "default")

client = OpenAI(base_url=BASE_URL, api_key=os.environ.get("KI_TOOLBOX_API_KEY", "missing-api-key"))


def model_label(model):
    if model == HUMAN:
        return "🧑 You (human)"
    return MODELS.get(model, model)


def chat(model, system, messages, effort="default"):
    """Send one chat request. Returns a dict with the text and debug info (tokens, latency, ...)."""
    extra = {} if effort == "default" else {"reasoning_effort": effort}
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}] + messages,
        **extra,
    )
    choice = response.choices[0]
    usage = response.usage
    # Some models behind the toolbox (e.g. DeepSeek, GLM) return their reasoning in a non-standard field.
    reasoning = getattr(choice.message, "reasoning_content", None) or getattr(choice.message, "reasoning", None)
    return {
        "text": choice.message.content or "",
        "refused": choice.finish_reason == "content_filter",
        "stop_reason": choice.finish_reason,
        "model": response.model,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "thinking": reasoning if isinstance(reasoning, str) else "",
        "latency": time.time() - start,
    }
