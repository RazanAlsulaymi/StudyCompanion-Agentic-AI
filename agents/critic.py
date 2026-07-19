import json
from datetime import datetime
from typing import List, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI

from core.llm import llm_json
from core.prompts import CRITIC_SYSTEM
from models.schemas import UIPatch
from utils.trace import trace_add


def critic_agent(
    llm: ChatGoogleGenerativeAI,
    patch: UIPatch,
    session_id: str,
) -> Tuple[bool, List[str]]:

    payload = patch.model_dump()

    schema_hint = '{"ok":true,"issues":[]}'

    start = datetime.utcnow()

    trace_add(
        session_id,
        "critic_start",
        {
            "patch_keys": [
                key
                for key, value in payload.items()
                if value is not None
            ]
        },
    )

    data = llm_json(
        llm=llm,
        system=CRITIC_SYSTEM,
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
        "critic_end",
        {
            "ms": elapsed,
            "ok": bool(data.get("ok", False)),
        },
    )

    ok = bool(data.get("ok", False))

    issues = data.get("issues", [])

    if not isinstance(issues, list):
        issues = [
            "Critic issues format invalid."
        ]

    return (
        ok,
        [str(issue) for issue in issues],
    )