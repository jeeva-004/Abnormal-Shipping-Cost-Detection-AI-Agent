"""Tracks LLM / embedding calls and token counts for the cost log."""
from dataclasses import dataclass, field


@dataclass
class UsageTracker:
    calls: list = field(default_factory=list)

    def record(self, kind: str, model: str, input_tokens: int, output_tokens: int) -> None:
        self.calls.append({"kind": kind, "model": model,
                           "input_tokens": int(input_tokens or 0),
                           "output_tokens": int(output_tokens or 0)})

    def summary(self) -> dict:
        llm = [c for c in self.calls if c["kind"] == "llm"]
        emb = [c for c in self.calls if c["kind"] == "embed"]
        return {
            "llm_calls": len(llm),
            "llm_input_tokens": sum(c["input_tokens"] for c in llm),
            "llm_output_tokens": sum(c["output_tokens"] for c in llm),
            "embed_calls": len(emb),
            "embed_input_tokens": sum(c["input_tokens"] for c in emb),
        }


TRACKER = UsageTracker()