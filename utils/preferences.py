import re
from typing import Dict


def parse_prefs_from_text(text: str, prefs: Dict[str, object]) -> Dict[str, object]:
    t = (text or "").lower()

    if "hard" in t:
        prefs["difficulty"] = "hard"
    elif "easy" in t:
        prefs["difficulty"] = "easy"
    elif "medium" in t:
        prefs["difficulty"] = "medium"

    m = re.search(r"\b(\d{1,2})\s*(?:questions|question|quiz)\b", t)
    if m:
        n = int(m.group(1))
        prefs["quiz_count"] = max(5, min(20, n))

    m_alt = re.search(r"\b(\d{1,2})\s*(?:mcq|tf)\b", t)
    if m_alt:
        n = int(m_alt.group(1))
        prefs["quiz_count"] = max(5, min(20, n))

    m2 = re.search(r"\b(\d{1,2})\s*(?:cards|card|flashcards|flashcard)\b", t)
    if m2:
        n = int(m2.group(1))
        prefs["cards_count"] = max(3, min(25, n))

    if "only mcq" in t or "mcq only" in t:
        prefs["quiz_types"] = ["mcq"]
    elif "only tf" in t or "tf only" in t or "true/false only" in t:
        prefs["quiz_types"] = ["tf"]
    elif "mix" in t or "both" in t:
        prefs["quiz_types"] = ["mcq", "tf"]

    return prefs


def detect_study_style(
    text: str,
    style: Dict[str, object],
) -> Dict[str, object]:
    t = (text or "").lower()

    if "midterm" in t or "exam" in t or "final" in t:
        style["assessment"] = "midterm"
    elif "quiz" in t:
        style["assessment"] = "quiz"

    if "brief" in t or "short" in t or "quick" in t:
        style["summary_mode"] = "brief"
    elif "detailed" in t or "comprehensive" in t or "full" in t:
        style["summary_mode"] = "detailed"

    if "important" in t or "key" in t or "only important" in t:
        style["focus"] = "important"
    elif "everything" in t or "all details" in t:
        style["focus"] = "detailed"
    else:
        style["focus"] = style.get("focus", "balanced")

    return style


def wants_quiz(text: str) -> bool:
    t = (text or "").lower()

    return any(
        k in t
        for k in [
            "quiz",
            "midterm",
            "exam",
            "questions",
            "mcq",
            "tf",
            "true/false",
        ]
    )


def wants_more(text: str) -> bool:
    t = (text or "").lower()

    return any(
        k in t
        for k in [
            "more",
            "increase",
            "add",
            "another",
            "extra",
        ]
    )