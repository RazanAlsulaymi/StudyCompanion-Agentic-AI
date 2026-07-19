from typing import Any, Dict, List, Tuple

from database.sqlite_db import db_mark_task_done
from models.schemas import Task, UIPatch


def get_visible_tasks(state: Dict[str, Any]) -> List[Task]:
    all_tasks = state.get("tasks_all", []) or []
    done = set(state.get("tasks_done_ids", []) or [])

    pending = [
        t for t in all_tasks
        if t.get("id") not in done
    ]

    return [Task(**t) for t in pending[:3]]


def mark_task_done(
    state: Dict[str, Any],
    session_id: str,
    task_id: str,
):
    done = state.get("tasks_done_ids", []) or []

    if task_id and task_id not in done:
        done.append(task_id)

    state["tasks_done_ids"] = done

    db_mark_task_done(session_id, task_id)


def tasks_look_generic(tasks: List[Task]) -> bool:
    bad = [
        "study more",
        "review lecture",
        "go over",
        "read lecture",
        "learn more",
        "do practice",
        "practice more",
        "revise",
    ]

    for task in tasks:
        title = (task.title or "").lower()

        if any(word in title for word in bad):
            return True

    return False


def score_quiz(
    state: Dict[str, Any],
    answers: List[Dict[str, Any]],
) -> Tuple[int, int]:

    quiz = state.get("lastQuiz")

    if not quiz or not quiz.get("questions"):
        return 0, 0

    correct = {
        str(q["id"]): str(q.get("answer", ""))
        for q in quiz["questions"]
    }

    total = len(correct)
    score = 0

    for answer in answers or []:
        qid = str(answer.get("id", ""))
        value = str(answer.get("value", ""))

        if qid in correct and value == correct[qid]:
            score += 1

    return score, total