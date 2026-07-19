import json
from datetime import datetime
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from core.llm import llm_json
from core.prompts import CARDS_SYSTEM
from models.schemas import Card, UIPatch
from utils.trace import trace_add


def cards_agent(
    llm: ChatGoogleGenerativeAI,
    summary_text: str,
    prefs: Dict[str, Any],
    session_id: str,
) -> UIPatch:

    cards_count = max(
        3,
        min(
            25,
            int(prefs.get("cards_count", 10)),
        ),
    )

    payload = {
        "cards_count": cards_count,
        "summary": summary_text,
    }

    schema_hint = (
        '{"cards":['
        '{"id":"c1",'
        '"front":"...",'
        '"back":"..."}]}'
    )

    start = datetime.utcnow()

    trace_add(
        session_id,
        "cards_start",
        {
            "cards_count": cards_count,
        },
    )

    data = llm_json(
        llm=llm,
        system=CARDS_SYSTEM,
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
        "cards_end",
        {
            "ms": elapsed,
        },
    )

    cards = [
        Card(**card)
        for card in (data.get("cards") or [])
    ]

    return UIPatch(
        cards=cards,
        ghost_bubble="Cards ready",
    )