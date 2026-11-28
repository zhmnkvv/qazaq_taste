"""HW11: decide for EVERY request whether the model should use reasoning.

Reasoning costs time and tokens (see comparison.md: ~4x slower, ~7x more output tokens),
so it is switched on only where an extra analysis step pays off:

  ON  — booking (any message about booking a table, and the JSON booking extraction);
  ON  — a bill / money calculation where Python already computed the numbers;
  ON  — other checks where Python produced a result (guests vs halls, late arrival);
  ON  — budget questions ("уложиться в 6000 тенге");
  OFF — everything else: menu questions, opening hours, contacts, greetings, small talk.

When reasoning is OFF the model also gets the prompt without section 18 (no
<размышление>/<ответ> wrappers), so it answers directly. Exact numbers are always
computed by Python in both modes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bot.services.booking_extraction import looks_like_booking
from bot.services.calculations import Calculations

# Money / budget questions without a ready-made bill: "уложиться в 6000 тенге", "бюджет 20 000 ₸".
BUDGET_CUES = re.compile(
    r"бюджет|уложит\w*|в\s+пределах|на\s+сумму|\d[\d\s]*\s*(?:₸|тг\b|тенге|теңге|kzt|tenge)|"
    r"\bbudget\b|within\s+\d|бюджетке|ақша",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReasoningDecision:
    enabled: bool
    reason: str

    def __str__(self) -> str:
        return f"reasoning {'ON' if self.enabled else 'OFF'} ({self.reason})"


BOOKING_EXTRACTION = ReasoningDecision(True, "booking request: JSON extraction")


def decide_reasoning(text: str, calcs: Calculations | None = None) -> ReasoningDecision:
    if calcs and calcs.bill:
        return ReasoningDecision(True, "bill calculated by Python")
    if calcs and calcs.guests:
        return ReasoningDecision(True, "guest count checked by Python")
    if calcs and calcs.late:
        return ReasoningDecision(True, "late arrival computed by Python")
    if looks_like_booking(text or ""):
        return ReasoningDecision(True, "booking question")
    if BUDGET_CUES.search(text or ""):
        return ReasoningDecision(True, "money / budget question")
    return ReasoningDecision(False, "simple question")
