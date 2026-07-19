from typing import Any, Dict

from agents.cards import cards_agent
from agents.critic import critic_agent
from agents.planner import planner_agent
from agents.quiz import quiz_agent
from agents.summary import summary_agent

from core.helpers import (
    get_visible_tasks,
    mark_task_done,
    score_quiz,
)

from utils.bubbles import (
    clamp_3_words,
    pick_bubble,
)

from core.llm import (
    get_fast_llm,
    get_main_llm,
)

from database.sqlite_db import (
    db_log_event,
    db_save_score,
    db_upsert_session,
)

from models.schemas import (
    AgentEvent,
    UIPatch,
)

from utils.bubbles import pick_bubble
from utils.preferences import (
    detect_study_style,
    parse_prefs_from_text,
    wants_quiz,
)
from utils.trace import trace_add


def finalize_patch(
    llm,
    patch: UIPatch,
    session_id: str,
) -> UIPatch:

    try:
        ok, issues = critic_agent(
            llm,
            patch,
            session_id,
        )

        if not ok:
            trace_add(
                session_id,
                "critic_issues",
                {"issues": issues},
            )

            if not patch.ghost_bubble:
                patch.ghost_bubble = "Try again"

    except Exception as e:

        trace_add(
            session_id,
            "critic_failed",
            {"error": repr(e)},
        )

    if patch.ghost_bubble:
        patch.ghost_bubble = clamp_3_words(
            patch.ghost_bubble
        )

    return patch


def orchestrate(
    event: AgentEvent,
    state: Dict[str, Any],
) -> UIPatch:

    sid = event.session_id

    trace_add(
        sid,
        "event_received",
        {
            "event_type": event.event_type,
            "payload_keys": list(
                event.payload.keys()
            ),
        },
    )

    try:

        main_llm = get_main_llm()
        fast_llm = get_fast_llm()

    except Exception as e:

        trace_add(
            sid,
            "llm_init_failed",
            {"error": repr(e)},
        )

        return UIPatch(
            ghost_bubble="Try again",
            agent_message="LLM not ready. Check API key/model.",
        )

    try:

        try:
            db_log_event(
                sid,
                event.event_type,
                event.payload,
            )
        except Exception as e:

            trace_add(
                sid,
                "db_log_failed",
                {"error": repr(e)},
            )

        et = event.event_type

        patch = UIPatch()

        if et == "USER_MESSAGE":

            msg = str(
                event.payload.get(
                    "message",
                    "",
                )
            ).strip()

            if not msg:

                return UIPatch(
                    ghost_bubble="Say something",
                    agent_message="Type your question or upload a lecture.",
                )

            context = str(
                event.payload.get(
                    "context",
                    "",
                )
            ).strip()

            if context:
                state["last_context_seen"] = context
                state["context_text"] = context

            state["last_user_message"] = msg

            state["prefs"] = parse_prefs_from_text(
                msg,
                state.get("prefs", {}),
            )

            state["study_style"] = detect_study_style(
                msg,
                state.get(
                    "study_style",
                    {},
                ),
            )

            trace_add(
                sid,
                "policy",
                {
                    "has_lecture": bool(
                        state.get(
                            "context_text"
                        )
                    ),
                    "assessment": state[
                        "study_style"
                    ].get(
                        "assessment"
                    ),
                    "prefs": state["prefs"],
                },
            )

            try:
                db_upsert_session(
                    sid,
                    state["prefs"],
                    state["study_style"],
                )
            except Exception as e:

                trace_add(
                    sid,
                    "db_upsert_failed",
                    {"error": repr(e)},
                )

            if state.get("context_text"):

                summary_patch = summary_agent(
                    fast_llm,
                    state["context_text"],
                    state["study_style"],
                    sid,
                )

                state["lastSummary"] = (
                    summary_patch.summary or ""
                )

                patch.summary = (
                    summary_patch.summary
                )

                planner_patch = planner_agent(
                    main_llm,
                    msg,
                    state["lastSummary"],
                    state,
                    sid,
                )

                patch.tasks = planner_patch.tasks

                patch.pomodoro_suggestion = (
                    planner_patch.pomodoro_suggestion
                )

                patch.agent_message = (
                    "Summary + tasks ready. "
                    "Want a quiz now? "
                    "Tell me: TF/MCQ/both + count + difficulty."
                )

                patch.ghost_bubble = "Ready"

                state[
                    "awaiting_quiz_prefs"
                ] = True

                state["lastQuiz"] = None

            else:

                planner_patch = planner_agent(
                    main_llm,
                    msg,
                    msg,
                    state,
                    sid,
                )

                patch.tasks = planner_patch.tasks

                patch.pomodoro_suggestion = (
                    planner_patch.pomodoro_suggestion
                )

                patch.agent_message = (
                    "Upload your lecture PDF or tell me the topic."
                )

                patch.ghost_bubble = "Talk to me"

            if (
                wants_quiz(msg)
                and state.get("lastSummary")
            ):

                quiz_patch = quiz_agent(
                    main_llm,
                    state["lastSummary"],
                    state["prefs"],
                    state["study_style"],
                    sid,
                )

                state["lastQuiz"] = (
                    quiz_patch.quiz.model_dump()
                    if quiz_patch.quiz
                    else None
                )

                patch.quiz = quiz_patch.quiz

                patch.ghost_bubble = (
                    quiz_patch.ghost_bubble
                )

                patch.agent_message = (
                    "Quiz generated. Answer in the Quiz tab."
                )

                state[
                    "awaiting_quiz_prefs"
                ] = False

        elif et == "TASK_DONE":

            task_id = str(
                event.payload.get(
                    "task_id",
                    "",
                )
            ).strip()

            if not task_id:

                return UIPatch(
                    ghost_bubble="Try again",
                    agent_message="Missing task id.",
                )

            mark_task_done(
                state,
                sid,
                task_id,
            )

            patch.tasks = get_visible_tasks(
                state,
            )

            patch.ghost_bubble = pick_bubble(
                "task_done"
            )

            patch.agent_message = (
                "Nice. Keep going."
            )

        elif et == "QUIZ_SUBMIT":

            answers = event.payload.get(
                "answers",
                [],
            )

            if not isinstance(
                answers,
                list,
            ):
                answers = []

            state["lastQuizAnswers"] = answers

            score, total = score_quiz(
                state,
                answers,
            )

            try:

                db_save_score(
                    sid,
                    score,
                    total,
                )

            except Exception as e:

                trace_add(
                    sid,
                    "db_save_score_failed",
                    {
                        "error": repr(e),
                    },
                )

            summary_text = (
                str(
                    event.payload.get(
                        "summary_text",
                        "",
                    )
                ).strip()
                or str(
                    state.get(
                        "lastSummary",
                        "",
                    )
                ).strip()
            )

            if not summary_text:

                return UIPatch(
                    ghost_bubble="No summary",
                    agent_message="No summary found.",
                )

            cards_patch = cards_agent(
                main_llm,
                summary_text,
                state["prefs"],
                sid,
            )

            state["lastCards"] = [
                card.model_dump()
                for card in (
                    cards_patch.cards or []
                )
            ]

            patch.cards = cards_patch.cards

            patch.ghost_bubble = (
                clamp_3_words(
                    f"Score {score}/{total}"
                )
                if total > 0
                else pick_bubble(
                    "score"
                )
            )

            patch.agent_message = (
                f"Score: {score}/{total}. "
                "Want more questions or harder difficulty?"
            )

        else:

            patch = UIPatch(
                ghost_bubble="Click me",
            )

        return finalize_patch(
            main_llm,
            patch,
            sid,
        )

    except Exception as e:

        trace_add(
            sid,
            "orchestrate_failed",
            {
                "error": repr(e),
            },
        )

        return UIPatch(
            ghost_bubble="Try again",
            agent_message="Backend error. Check server logs.",
        )