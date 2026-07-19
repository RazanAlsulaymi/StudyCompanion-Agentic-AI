from typing import Any, Dict

STATE: Dict[str, Dict[str, Any]] = {}


def get_state(session_id: str) -> Dict[str, Any]:
    if session_id not in STATE:
        STATE[session_id] = {
            "prefs": {
                "quiz_types": ["mcq", "tf"],
                "quiz_count": 8,
                "cards_count": 10,
                "difficulty": "medium",
            },
            "study_style": {
                "summary_mode": "detailed",
                "focus": "balanced",
                "assessment": "quiz",
            },
            "context_text": "",
            "last_context_seen": "",
            "last_user_message": "",
            "preferredPomodoro": 25,
            "stopCountThisSession": 0,
            "taskDoneCount": 0,
            "tasks_all": [],
            "tasks_done_ids": [],
            "lastSummary": "",
            "lastQuiz": None,
            "lastQuizAnswers": [],
            "lastCards": [],
            "awaiting_quiz_prefs": False,
            "awaiting_new_file_pref_confirm": False,
            "bubble_initialized": False,
            "last_bubble": "Click me",
        }

    return STATE[session_id]