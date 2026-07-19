import json
from datetime import datetime
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from core.llm import llm_json
from core.prompts import SUMMARY_SYSTEM
from models.schemas import UIPatch
from utils.trace import trace_add


def summary_agent(
    llm: ChatGoogleGenerativeAI,
    content_text: str,
    style: Dict[str, Any],
    session_id: str,
) -> UIPatch:
    payload = {
        "summary_mode": style.get(
            "summary_mode",
            "detailed",
        ),
        "focus": style.get(
            "focus",
            "balanced",
        ),
        "assessment": style.get(
            "assessment",
            "quiz",
        ),
        "content": content_text[:18000],
    }

    schema_hint = '{"summary":"Overview: ."}'

    start_time = datetime.utcnow()

    trace_add(
        session_id,
        "summary_start",
        {
            "content_len": len(payload["content"]),
            "assessment": payload["assessment"],
        },
    )

    data = llm_json(
        llm=llm,
        system=SUMMARY_SYSTEM,
        user=json.dumps(
            payload,
            ensure_ascii=False,
        ),
        schema_hint=schema_hint,
        tries=2,
    )

    elapsed_ms = int(
        (
            datetime.utcnow() - start_time
        ).total_seconds()
        * 1000
    )

    summary = str(
        data.get(
            "summary",
            "",
        )
    ).strip()

    trace_add(
        session_id,
        "summary_end",
        {
            "ms": elapsed_ms,
            "summary_len": len(summary),
        },
    )

    return UIPatch(
        summary=summary,
        ghost_bubble="Summary ready",
    )