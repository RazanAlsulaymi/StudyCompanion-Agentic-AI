import json
from datetime import datetime
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from core.llm import llm_json
from core.prompts import QUIZ_SYSTEM
from models.schemas import Quiz, UIPatch
from utils.bubbles import pick_bubble
from utils.trace import trace_add


def quiz_agent(
    llm: ChatGoogleGenerativeAI,
    summary_text: str,
    prefs: Dict[str, Any],
    style: Dict[str, Any],
    session_id: str,
) -> UIPatch:

    quiz_count = max(
        5,
        min(
            20,
            int(prefs.get("quiz_count", 8)),
        ),
    )

    quiz_types = prefs.get(
        "quiz_types",
        ["mcq", "tf"],
    )

    if (
        not isinstance(quiz_types, list)
        or not quiz_types
    ):
        quiz_types = ["mcq", "tf"]

    difficulty = prefs.get(
        "difficulty",
        "medium",
    )

    assessment = style.get(
        "assessment",
        "quiz",
    )

    payload = {
        "quiz_count": quiz_count,
        "quiz_types": quiz_types,
        "difficulty": difficulty,
        "assessment": assessment,
        "summary": summary_text,
    }

    schema_hint = (
        '{"quiz":{"title":"Quick Check",'
        '"questions":[{"id":"q1",'
        '"type":"tf",'
        '"question":"...",'
        '"answer":"T"}]}}'
    )

    start = datetime.utcnow()

    trace_add(
        session_id,
        "quiz_start",
        {
            "quiz_count": quiz_count,
            "types": quiz_types,
            "difficulty": difficulty,
            "assessment": assessment,
        },
    )

    data = llm_json(
        llm=llm,
        system=QUIZ_SYSTEM,
        user=json.dumps(
            payload,
            ensure_ascii=False,
        ),
        schema_hint=schema_hint,
        tries=2,
    )

    elapsed = int(
        (
            datetime.utcnow() - start
        ).total_seconds()
        * 1000
    )

    trace_add(
        session_id,
        "quiz_end",
        {
            "ms": elapsed,
        },
    )

    quiz = Quiz(
        **data.get(
            "quiz",
            {},
        )
    )

    return UIPatch(
        quiz=quiz,
        ghost_bubble=pick_bubble(
            "quiz_ready"
        ),
    )