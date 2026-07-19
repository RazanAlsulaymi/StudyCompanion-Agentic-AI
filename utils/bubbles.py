import random
import re

BUBBLES = {
    "idle": [
        "Click me",
    ],
    "session_start": [
        "Let’s go",
        "Ready now",
        "Start focus",
    ],
    "task_done": [
        "Good job",
        "Next task",
        "Keep going",
    ],
    "timer_end": [
        "Drink water",
        "Break time",
        "Nice work",
    ],
    "quiz_prefs": [
        "Quiz prefs",
        "Pick mode",
        "Your choice",
    ],
    "quiz_ready": [
        "Quiz ready",
        "Try now",
        "Stay sharp",
    ],
    "score": [
        "Score ready",
        "Well done",
        "Try again",
    ],
    "new_lecture": [
        "New lecture",
        "Same settings",
        "Update prefs",
    ],
}


def clamp_3_words(text: str) -> str:
    s = str(text or "").replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)

    if not s:
        return "Hi"

    return " ".join(s.split(" ")[:3])


def pick_bubble(kind: str, fallback: str = "Hi") -> str:
    arr = BUBBLES.get(kind) or [fallback]
    return clamp_3_words(random.choice(arr))