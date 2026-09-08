"""Rough token accounting and cost estimation.

~4 characters per token is close enough for budgeting and for the per-session
cost figures in the scorecard; it is not a tokenizer.
"""

PRICING_USD_PER_1M = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
    "stub": (0.0, 0.0),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = PRICING_USD_PER_1M.get(model, (0.0, 0.0))
    return (prompt_tokens * inp + completion_tokens * out) / 1_000_000
