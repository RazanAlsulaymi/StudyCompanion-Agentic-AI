import json
from datetime import datetime
from typing import Any, Dict

from langchain_google_genai import ChatGoogleGenerativeAI

from core.helpers import (
    get_visible_tasks,
    tasks_look_generic,
)
from core.llm import llm_json
from core.prompts import PLANNER_SYSTEM
from database.sqlite_db import db_store_tasks
from models.schemas import Task, UIPatch
from utils.bubbles import pick_bubble
from utils.trace import trace_add


def planner_agent(
    llm: ChatGoogleGenerativeAI,
    user_message: str,
    topic_summary: str,
    state: Dict[str, Any],
    session_id: str,
) -> UIPatch:

    style = state.get("study_style", {})

    payload = {
        "user_message": user_message,
        "assessment": style.get("assessment", "quiz"),
        "topic_summary": (topic_summary or "")[:2500],
    }

    schema_hint = (
        '{"tasks":[{"id":"t1","title":"Define ...",'
        '"kind":"recall","est_min":10}],'
        '"pomodoro_suggestion":25}'
    )

    for attempt in (1, 2):

        start = datetime.utcnow()

        trace_add(
            session_id,
            "planner_start",
            {
                "attempt": attempt,
                "topic_summary_len": len(payload["topic_summary"]),
            },
        )

        data = llm_json(
            llm=llm,
            system=PLANNER_SYSTEM,
            user=json.dumps(payload, ensure_ascii=False),
            schema_hint=schema_hint,
            tries=2,
        )

        elapsed = int(
            (datetime.utcnow() - start).total_seconds() * 1000
        )

        trace_add(
            session_id,
            "planner_end",
            {
                "ms": elapsed,
                "keys": list(data.keys()),
            },
        )

        tasks = [
            Task(**item)
            for item in (data.get("tasks") or [])
            if isinstance(item, dict)
        ]

        if (
            len(tasks) == 6
            and not tasks_look_generic(tasks)
        ):

            state["tasks_all"] = [
                task.model_dump()
                for task in tasks
            ]

            state["tasks_done_ids"] = state.get(
                "tasks_done_ids",
                [],
            )

            db_store_tasks(
                session_id,
                tasks,
            )

            bubble = (
                "Click me"
                if not state.get("bubble_initialized", False)
                else pick_bubble("session_start")
            )

            state["bubble_initialized"] = True

            return UIPatch(
                tasks=get_visible_tasks(state),
                pomodoro_suggestion=data.get(
                    "pomodoro_suggestion"
                ),
                ghost_bubble=bubble,
            )

        payload["user_message"] = (
            user_message
            + "\nMake tasks more specific to the "
              "topic_summary and avoid generic wording."
        )

    tasks = tasks[:6] if "tasks" in locals() else []

    state["tasks_all"] = [
        task.model_dump()
        for task in tasks
    ]

    state["tasks_done_ids"] = state.get(
        "tasks_done_ids",
        [],
    )

    if tasks:
        db_store_tasks(
            session_id,
            tasks,
        )

    return UIPatch(
        tasks=get_visible_tasks(state),
        pomodoro_suggestion=25,
        ghost_bubble=pick_bubble("session_start"),
    )