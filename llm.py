import json
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMClient:
    """Thin wrapper around an LLM call.

    chat() returns a dict {"action": ..., "reason": ...} on success,
    or None if the LLM is unavailable or the response was unusable.
    """

    def __init__(self, model="gpt-4o-mini", force_mock=False):
        self.model = model
        self.use_mock = (
            force_mock
            or OpenAI is None
            or not os.getenv("OPENAI_API_KEY")
        )
        self.client = None
        if not self.use_mock:
            self.client = OpenAI()
            print(f"[llm] using OpenAI model={model}")
        else:
            reason = (
                "forced" if force_mock
                else "openai library not installed" if OpenAI is None
                else "OPENAI_API_KEY not set"
            )
            print(f"[llm] mock mode ({reason}) — heuristic agent will drive")

    def chat(self, system, user):
        if self.use_mock:
            return None
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            if "action" not in data:
                return None
            return data
        except Exception as e:
            print(f"[llm error] {e}")
            return None
