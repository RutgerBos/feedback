"""
Shared prompt construction and response parsing for LLM insight synthesis.
Used by both ClaudeLLMAdapter and OllamaLLMAdapter.
"""

import json

from src.domain.models import InsightContext, InsightOutput
from src.ports.errors import LLMError


def _build_synthesis_prompt(context: InsightContext) -> str:
    """Build the synthesis prompt from structured InsightContext."""
    def _triad_str(positions: dict) -> str:
        return ", ".join(
            f"{t}: ({v['x']:.2f}, {v['y']:.2f})" for t, v in positions.items()
        )

    excerpt_lines = "\n".join(
        f'- [{e.story_id}] "{e.text_excerpt}" [triads: {_triad_str(e.triad_positions)}]'
        for e in context.excerpts
    )
    theme_lines = "\n".join(
        f"  {theme}: {count} stories"
        for theme, count in sorted(context.theme_counts.items(), key=lambda x: -x[1])
    )
    s = context.sentiment_summary
    sentiment_line = (
        f"Process — positive: {s.positive_process}, negative: {s.negative_process}, "
        f"neutral: {s.neutral_process}; "
        f"Outcome — positive: {s.positive_outcome}, negative: {s.negative_outcome}, "
        f"neutral: {s.neutral_outcome}"
    )
    sample_note = (
        f"(showing {len(context.excerpts)} of {context.total_stories}; "
        "theme and sentiment stats cover the sample only)"
        if context.total_stories > len(context.excerpts)
        else f"(showing all {len(context.excerpts)} stories)"
    )
    return (
        f"You are analyzing feedback stories about '{context.entity_name}'.\n"
        f"User question: {context.query}\n\n"
        f"Total matching stories: {context.total_stories} {sample_note}\n\n"
        f"Story excerpts with signifier-space coordinates (x, y):\n"
        f"{excerpt_lines if excerpt_lines else '  (none)'}\n\n"
        f"Theme distribution (sample):\n"
        f"{theme_lines if theme_lines else '  (no themes extracted)'}\n\n"
        f"Sentiment summary (sample): {sentiment_line}\n\n"
        "Write a clear, concise narrative (3-5 sentences) explaining what patterns emerge "
        "from these stories. Include any important caveats about data quality or sample size.\n"
        'Respond with JSON only: {"narrative": "...", "caveats": ["..."]}'
    )


def _parse_synthesis_response(raw: str) -> InsightOutput:
    """Parse JSON synthesis response into InsightOutput, raising LLMError on failure."""
    try:
        data = json.loads(raw)
        if "narrative" not in data:
            raise LLMError("Missing required key 'narrative' in LLM synthesis response")
        narrative = data["narrative"]
        caveats = data.get("caveats", [])
        if not isinstance(narrative, str):
            raise LLMError("Expected 'narrative' to be a string")
        if not isinstance(caveats, list) or not all(isinstance(c, str) for c in caveats):
            raise LLMError("Expected 'caveats' to be a list of strings")
        return InsightOutput(narrative=narrative, caveats=caveats)
    except (json.JSONDecodeError, KeyError) as e:
        raise LLMError(f"Failed to parse insight synthesis response: {e}") from e
