"""Parsing of the structured reply format <размышление>…</размышление> <ответ>…</ответ>.

What this is (honestly): the local model (Ollama /api/chat in this project) does not
return a separate reasoning field. The system prompt (section 18) asks the model to
write a short analysis in a <размышление> block before the final <ответ>. This is an
EDUCATIONAL, STRUCTURED DEMONSTRATION of "think first, then answer" — ordinary model
output that we split in code — not the model's hidden internal chain-of-thought.

If a model emits its own <think>…</think> block (e.g. reasoning models in Ollama),
that text is also treated as reasoning: shown in the console, never sent to the guest.

Guarantee: whatever the model returns, the guest only ever receives the answer part.
Reasoning goes to the console/log only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("qazaq_taste.reasoning")

_REASONING_NAMES = r"(?:размышление|reasoning|thinking|think)"
_ANSWER_NAMES = r"(?:ответ|answer)"

REASONING_BLOCK = re.compile(rf"<\s*{_REASONING_NAMES}\s*>(.*?)<\s*/\s*{_REASONING_NAMES}\s*>",
                             re.IGNORECASE | re.DOTALL)
REASONING_OPEN = re.compile(rf"<\s*{_REASONING_NAMES}\s*>", re.IGNORECASE)
ANSWER_BLOCK = re.compile(rf"<\s*{_ANSWER_NAMES}\s*>(.*?)(?:<\s*/\s*{_ANSWER_NAMES}\s*>|\Z)",
                          re.IGNORECASE | re.DOTALL)
ANY_TAG = re.compile(rf"<\s*/?\s*(?:{_REASONING_NAMES}|{_ANSWER_NAMES})\s*>", re.IGNORECASE)

BANNER_REASONING = "========== REASONING =========="
BANNER_ANSWER = "========== ANSWER =========="
BANNER_END = "==============================="


@dataclass(frozen=True)
class ParsedReply:
    answer: str              # the ONLY text that may be sent to the guest ("" = use a safe fallback)
    reasoning: str | None    # console-only analysis, or None
    status: str              # "both" | "answer_only" | "untagged_answer" | "no_tags" | "empty_answer"


def parse_reasoned_reply(raw: str) -> ParsedReply:
    text = (raw or "").strip()
    reasoning_parts = [m.strip() for m in REASONING_BLOCK.findall(text) if m.strip()]
    reasoning = "\n\n".join(reasoning_parts) or None
    has_reasoning_tag = bool(REASONING_OPEN.search(text))

    answer_match = ANSWER_BLOCK.search(text)
    if answer_match:
        answer = _clean_answer(answer_match.group(1))
        status = "both" if reasoning else "answer_only"
    elif has_reasoning_tag:
        # The model wrote the analysis but forgot the <ответ> tags.
        # Only text AFTER a properly closed reasoning block may become the answer;
        # an unclosed reasoning block means there is no safe answer at all.
        closed = list(REASONING_BLOCK.finditer(text))
        rest = text[closed[-1].end():] if closed else ""
        answer = _clean_answer(rest)
        status = "untagged_answer"
    else:
        answer = text  # plain reply without any tags: keep the bot working
        status = "no_tags"

    if not answer:
        status = "empty_answer"
    return ParsedReply(answer=answer, reasoning=reasoning, status=status)


def _clean_answer(text: str) -> str:
    # never let a reasoning block (or a stray tag) leak into what the guest sees
    text = REASONING_BLOCK.sub("", text)
    if REASONING_OPEN.search(text):  # unclosed reasoning inside the answer: cut it off
        text = text[: REASONING_OPEN.search(text).start()]
    return ANY_TAG.sub("", text).strip()


def log_reasoning(parsed: ParsedReply, answer_sent: str, source: str = "ai") -> None:
    """Print the demonstration block to the console (through logging, so the
    RedactingFilter masks tokens and phone numbers)."""
    lines = [
        "",
        BANNER_REASONING,
        parsed.reasoning or "(модель не прислала блок <размышление>)",
        BANNER_ANSWER,
        answer_sent,
        BANNER_END + f"  status={parsed.status} source={source}",
    ]
    logger.info("\n".join(lines))
