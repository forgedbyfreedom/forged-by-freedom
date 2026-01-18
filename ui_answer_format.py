# ui_answer_format.py

from __future__ import annotations
from typing import Dict, Any, List

def format_quote_only_response(payload: Dict[str, Any]) -> str:
    """
    Takes JSON from ingest/run_openrouter_answer.py and returns the final UI text.
    Never prints unrelated sources when quotes == [].
    """
    if not payload.get("ok"):
        return "Answer:\nAn error occurred while generating the response."

    quotes: List[Dict[str, Any]] = payload.get("quotes", []) or []
    question = payload.get("question", "")

    if not quotes:
        note = payload.get("note") or (
            "No verbatim transcript excerpts were found that explicitly address this question."
        )
        return (
            "Answer:\n"
            f"{note}\n\n"
            "Sources:\n"
            "(none)"
        )

    lines = ["Answer:"]
    for i, q in enumerate(quotes, 1):
        text = q.get("text", "").strip()
        speaker = q.get("speaker") or "Unknown Speaker"
        podcast = q.get("podcast") or "Unknown Podcast"
        lines.append(f'{i}) "{text}" — {speaker}, {podcast}')

    lines.append("")
    lines.append("Sources:")
    for q in quotes:
        text = q.get("text", "").strip()
        podcast = q.get("podcast") or "Unknown Podcast"
        episode = q.get("episode") or "Unknown Episode"
        speaker = q.get("speaker") or "Unknown Speaker"
        timestamp = q.get("timestamp") or ""
        source = q.get("source") or ""

        lines.append(f"- Podcast: {podcast}")
        lines.append(f"  Episode: {episode}")
        lines.append(f"  Speaker: {speaker}")
        if timestamp:
            lines.append(f"  Timestamp: {timestamp}")
        if source:
            lines.append(f"  Source: {source}")
        lines.append(f'  Quote: "{text}"')

    return "\n".join(lines)
