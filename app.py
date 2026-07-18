import os
import uuid
import json
import re
import io
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, Dict, Any, Tuple

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from pydantic import BaseModel, Field, ValidationError, model_validator

# LangChain + Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage


# =========================
# ENV
# =========================
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

print("Loaded .env from:", ENV_PATH)
print("GOOGLE_API_KEY exists:", bool(os.getenv("GOOGLE_API_KEY")))
print("GEMINI_MODEL:", os.getenv("GEMINI_MODEL"))
print("FAST_GEMINI_MODEL:", os.getenv("FAST_GEMINI_MODEL"))
print("LLM_TEMPERATURE:", os.getenv("LLM_TEMPERATURE"))


# =========================
# Flask
# =========================
app = Flask(__name__)
CORS(app)

import sys
import logging

LOG_PATH = Path(__file__).resolve().parent / "server.log"

logger = logging.getLogger("study_companion")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")

# Console handler (terminal)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)

# File handler 
fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)

# Avoid duplicate handlers on reload
if not logger.handlers:
    logger.addHandler(ch)
    logger.addHandler(fh)

logger.propagate = False

# =========================
# TRACE (in-memory)
# =========================
TRACE: Dict[str, List[Dict[str, Any]]] = {}

def trace_add(session_id: str, step: str, data: Optional[Dict[str, Any]] = None):
    data = data or {}
    item = {
        "ts": datetime.utcnow().isoformat(),
        "step": step,
        **data
    }
    TRACE.setdefault(session_id, []).append(item)

    if len(TRACE[session_id]) > 200:
        TRACE[session_id] = TRACE[session_id][-200:]

    msg = f"[TRACE] {session_id} | {step} | {json.dumps(data, ensure_ascii=False)}"

    print(msg, flush=True)

    logger.info(msg)




@app.get("/debug/trace/<session_id>")
def debug_trace(session_id: str):
    return jsonify({
        "session_id": session_id,
        "count": len(TRACE.get(session_id, [])),
        "trace": TRACE.get(session_id, [])
    })


# =========================
# SQLite Tool (Tool #2)
# =========================
DB_PATH = Path(__file__).resolve().parent / "study_companion.db"

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT,
        last_seen_at TEXT,
        prefs_json TEXT,
        study_style_json TEXT,
        last_score INTEGER DEFAULT 0,
        last_total INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        ts TEXT,
        event_type TEXT,
        payload_json TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_status (
        session_id TEXT,
        task_id TEXT,
        title TEXT,
        kind TEXT,
        est_min INTEGER,
        status TEXT,          -- "pending" | "done"
        updated_at TEXT,
        PRIMARY KEY (session_id, task_id)
    )
    """)

    conn.commit()
    conn.close()

def db_log_event(session_id: str, event_type: str, payload: Dict[str, Any]):
    conn = db_connect()
    conn.execute(
        "INSERT INTO events(session_id, ts, event_type, payload_json) VALUES (?,?,?,?)",
        (session_id, datetime.utcnow().isoformat(), event_type, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()

def db_upsert_session(session_id: str, prefs: Dict[str, Any], study_style: Dict[str, Any]):
    now = datetime.utcnow().isoformat()
    conn = db_connect()
    conn.execute("""
        INSERT INTO sessions(session_id, created_at, last_seen_at, prefs_json, study_style_json)
        VALUES (?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
          last_seen_at=excluded.last_seen_at,
          prefs_json=excluded.prefs_json,
          study_style_json=excluded.study_style_json
    """, (
        session_id, now, now,
        json.dumps(prefs, ensure_ascii=False),
        json.dumps(study_style, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()

def db_save_score(session_id: str, score: int, total: int):
    now = datetime.utcnow().isoformat()
    conn = db_connect()
    conn.execute("""
        UPDATE sessions
        SET last_seen_at=?, last_score=?, last_total=?
        WHERE session_id=?
    """, (now, score, total, session_id))
    conn.commit()
    conn.close()

def db_store_tasks(session_id: str, tasks: List["Task"]):
    now = datetime.utcnow().isoformat()
    conn = db_connect()
    cur = conn.cursor()
    for t in tasks:
        cur.execute("""
            INSERT INTO task_status(session_id, task_id, title, kind, est_min, status, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(session_id, task_id) DO UPDATE SET
              title=excluded.title, kind=excluded.kind, est_min=excluded.est_min,
              status=excluded.status, updated_at=excluded.updated_at
        """, (session_id, t.id, t.title, t.kind, t.est_min, "pending", now))
    conn.commit()
    conn.close()

def db_mark_task_done(session_id: str, task_id: str):
    now = datetime.utcnow().isoformat()
    conn = db_connect()
    conn.execute("""
        UPDATE task_status
        SET status='done', updated_at=?
        WHERE session_id=? AND task_id=?
    """, (now, session_id, task_id))
    conn.commit()
    conn.close()


# =========================
# Types / Schemas
# =========================
EventType = Literal[
    "USER_MESSAGE",
    "TIMER_START",
    "TIMER_STOP",
    "TASK_DONE",
    "TASK_PAUSE",
    "SUMMARY_DONE",
    "QUIZ_SUBMIT",
    "IDLE_TICK",
]

class AgentEvent(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)

class Task(BaseModel):
    id: str
    title: str
    kind: Literal["reading", "practice", "recall", "break"]
    est_min: int = Field(ge=1, le=60)

class QuizQuestion(BaseModel):
    id: str
    type: Literal["tf", "mcq"]
    question: str
    choices: Optional[List[str]] = None
    answer: str

    @model_validator(mode="after")
    def fix_and_validate(self):
        if self.type == "tf":
            self.choices = ["T", "F"]
            if self.answer not in ["T", "F"]:
                raise ValueError("TF answer must be 'T' or 'F'")

        if self.type == "mcq":
            if not self.choices or not isinstance(self.choices, list):
                raise ValueError("MCQ must include choices list")
            if len(self.choices) < 3 or len(self.choices) > 4:
                raise ValueError("MCQ choices must be 3-4 items")
            if self.answer not in self.choices:
                raise ValueError("MCQ answer must match one of choices exactly")

        return self

class Quiz(BaseModel):
    title: str = "Quick Check"
    questions: List[QuizQuestion] = Field(min_length=5, max_length=20)

class Card(BaseModel):
    id: str
    front: str
    back: str

class UIPatch(BaseModel):
    tasks: Optional[List[Task]] = None
    summary: Optional[str] = None
    quiz: Optional[Quiz] = None
    cards: Optional[List[Card]] = None
    pomodoro_suggestion: Optional[int] = Field(default=None, ge=10, le=60)
    ghost_bubble: Optional[str] = None
    agent_message: Optional[str] = None

class AgentResponse(BaseModel):
    session_id: str
    updated_state: Dict[str, Any]
    ui_patch: UIPatch


# =========================
# In-memory State
# =========================
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


# =========================
# LLM (Gemini) - CACHED
# =========================
_MAIN_LLM: Optional[ChatGoogleGenerativeAI] = None
_FAST_LLM: Optional[ChatGoogleGenerativeAI] = None

def make_llm(model_name: str, temperature: float) -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY in .env (next to app.py)")

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
    )

def get_main_llm() -> ChatGoogleGenerativeAI:
    global _MAIN_LLM
    if _MAIN_LLM is not None:
        return _MAIN_LLM

    # Default to FLASH unless user overrides
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    _MAIN_LLM = make_llm(model, temperature)
    return _MAIN_LLM

def get_fast_llm() -> ChatGoogleGenerativeAI:
    global _FAST_LLM
    if _FAST_LLM is not None:
        return _FAST_LLM

    # Fast model used for SUMMARY (big input) by default
    model = os.getenv("FAST_GEMINI_MODEL", "gemini-2.0-flash")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    _FAST_LLM = make_llm(model, temperature)
    return _FAST_LLM


# =========================
# Robust JSON extraction + repair
# =========================
def extract_json(text: str) -> Dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError("LLM output is not a string")

    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*```$", "", t)

    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")

    snippet = t[start:end + 1]
    return json.loads(snippet)

def json_repair_prompt(schema_hint: str, bad_text: str) -> str:
    return (
        "Fix the following so it becomes VALID JSON ONLY. "
        "No explanations, no markdown.\n"
        f"Schema hint: {schema_hint}\n"
        "Bad output:\n"
        f"{bad_text}"
    )

def llm_json(llm: ChatGoogleGenerativeAI, system: str, user: str, schema_hint: str, tries: int = 2) -> Dict[str, Any]:
    raw = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)]).content
    try:
        return extract_json(raw)
    except Exception:
        if tries <= 1:
            raise
        repaired = llm.invoke([
            SystemMessage(content="Return ONLY valid JSON. No extra text."),
            HumanMessage(content=json_repair_prompt(schema_hint, raw))
        ]).content
        return extract_json(repaired)


# =========================
# Upload helpers (file -> text)
# =========================
def extract_text_from_upload(file_storage) -> str:
    filename = (getattr(file_storage, "filename", "") or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

    data = file_storage.read()
    if not data:
        raise ValueError("Uploaded file is empty.")
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("File too large (max 20 MB).")

    if ext in {"txt", "md"}:
        return data.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception as e:
            raise RuntimeError("PDF support requires 'pypdf' on server.") from e

        reader = PdfReader(io.BytesIO(data))
        pages_text: List[str] = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                continue

        text = "\n".join(pages_text).strip()
        if not text:
            raise ValueError("Could not extract text from the PDF.")
        return text

    raise ValueError("Unsupported file type. Use .txt, .md, or .pdf.")


# =========================
# Bubble rules
# =========================
BUBBLES = {
    "idle": ["Click me"],
    "session_start": ["Let’s go", "Ready now", "Start focus"],
    "task_done": ["Good job", "Next task", "Keep going"],
    "timer_end": ["Drink water", "Break time", "Nice work"],
    "quiz_prefs": ["Quiz prefs", "Pick mode", "Your choice"],
    "quiz_ready": ["Quiz ready", "Try now", "Stay sharp"],
    "score": ["Score ready", "Well done", "Try again"],
    "new_lecture": ["New lecture", "Same settings", "Update prefs"],
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


# =========================
# Preferences parsing + intent
# =========================
def parse_prefs_from_text(text: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
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

def detect_study_style(text: str, style: Dict[str, Any]) -> Dict[str, Any]:
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
    return any(k in t for k in ["quiz", "midterm", "exam", "questions", "mcq", "tf", "true/false"])

def wants_more(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ["more", "increase", "add", "another", "extra"])


# =========================
# PROMPTS
# =========================
PLANNER_SYSTEM = """You are PlannerAgent for a study companion.

Return ONLY valid JSON:
{
  "tasks":[
    {"id":"t1","title":"...","kind":"reading|practice|recall|break","est_min":1-60}
  ],
  "pomodoro_suggestion": 10-60
}

Rules:
- Create EXACTLY 6 tasks.
- Tasks MUST be specific to topic_summary (use real key terms).
- Titles must be short, actionable, start with a verb (Define/Compare/Solve/Explain/Practice/Review).
- Mix kinds: at least 2 practice + 2 recall + 1 reading + 1 break.
- If assessment=midterm: make tasks more exam-like (retrieval + misconceptions).
- Do NOT write generic titles like "Study more" or "Review lecture".
- Do NOT mention the words lecture/context/summary.
- JSON only. No markdown. No extra keys.
"""

SUMMARY_SYSTEM = """You are ContentAgent (Summary) for a student.

Return ONLY JSON:
{
  "summary":"(plain text, structured sections)"
}

Rules:
- Use assessment + focus + summary_mode from the input.
- Make it exam-useful, not fluffy.
- Always include these sections (plain text labels):
  Overview:
  Key Definitions:
  Key Ideas / Steps:
  Common Mistakes:
  Quick Recap:
- Keep it clear, bullet lines allowed, but plain text only.
- JSON only. No markdown fences. No extra keys.
"""

QUIZ_SYSTEM = """You are ContentAgent (Quiz).

Return ONLY JSON:
{
  "quiz":{
    "title":"Quick Check",
    "questions":[
      {"id":"q1","type":"tf","question":"...","answer":"T"},
      {"id":"q2","type":"mcq","question":"...","choices":["A","B","C"],"answer":"B"}
    ]
  }
}

Rules:
- Generate EXACT quiz_count questions (5-20).
- Use quiz_types: ["mcq"], ["tf"], or ["mcq","tf"].
- Difficulty:
  easy: direct recall
  medium: understanding + light traps
  hard: applied + misconceptions
- If assessment == midterm: treat as hard even if medium.
- Questions must depend ONLY on the provided summary.
- MCQ choices must be 3-4 items, answer must match exactly one choice.
- TF answer must be "T" or "F".
- JSON only. No extra keys.
"""

CARDS_SYSTEM = """You are ContentAgent (Cards).

Return ONLY JSON:
{
  "cards":[
    {"id":"c1","front":"...","back":"..."}
  ]
}

Rules:
- Create EXACT cards_count cards (3-25).
- Based ONLY on the provided summary.
- Front: short question/term.
- Back: concise but complete (1-3 lines max).
- JSON only. No extra keys.
"""

CRITIC_SYSTEM = """You are CriticAgent.

Return ONLY JSON:
{
  "ok": true|false,
  "issues": ["..."]
}

Rules:
- Be strict.
- JSON only.
"""


# =========================
# Helpers
# =========================
def get_visible_tasks(state: Dict[str, Any]) -> List[Task]:
    all_tasks = state.get("tasks_all", []) or []
    done = set(state.get("tasks_done_ids", []) or [])
    pending = [t for t in all_tasks if t.get("id") not in done]
    return [Task(**t) for t in pending[:3]]

def mark_task_done(state: Dict[str, Any], task_id: str):
    done = state.get("tasks_done_ids", []) or []
    if task_id and task_id not in done:
        done.append(task_id)
    state["tasks_done_ids"] = done

def tasks_look_generic(tasks: List[Task]) -> bool:
    bad = [
        "study more", "review lecture", "go over", "read lecture",
        "learn more", "do practice", "practice more", "revise"
    ]
    for t in tasks:
        tt = (t.title or "").lower()
        if any(b in tt for b in bad):
            return True
    return False


# =========================
# Quiz scoring
# =========================
def score_quiz(state: Dict[str, Any], answers: List[Dict[str, Any]]) -> Tuple[int, int]:
    quiz = state.get("lastQuiz")
    if not quiz or not quiz.get("questions"):
        return 0, 0

    correct = {str(q["id"]): str(q.get("answer", "")) for q in quiz["questions"]}
    total = len(correct)
    score = 0
    for a in answers or []:
        qid = str(a.get("id", ""))
        val = str(a.get("value", ""))
        if qid in correct and val == correct[qid]:
            score += 1
    return score, total


# =========================
# Agents (with TRACE)
# =========================
def planner_agent(llm: ChatGoogleGenerativeAI, user_message: str, topic_summary: str, state: Dict[str, Any], session_id: str) -> UIPatch:
    style = state.get("study_style", {})

    payload = {
        "user_message": user_message,
        "assessment": style.get("assessment", "quiz"),
        "topic_summary": (topic_summary or "")[:2500],
    }

    schema_hint = '{"tasks":[{"id":"t1","title":"Define ...","kind":"recall","est_min":10}],"pomodoro_suggestion":25}'

    for attempt in [1, 2]:
        t0 = datetime.utcnow()
        trace_add(session_id, "planner_start", {"attempt": attempt, "topic_summary_len": len(payload["topic_summary"])})
        data = llm_json(llm, PLANNER_SYSTEM, json.dumps(payload, ensure_ascii=False), schema_hint=schema_hint, tries=2)
        ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
        trace_add(session_id, "planner_end", {"ms": ms, "keys": list(data.keys())})

        tasks_raw = (data.get("tasks") or [])
        tasks = [Task(**t) for t in tasks_raw if isinstance(t, dict)]

        if len(tasks) == 6 and not tasks_look_generic(tasks):
            state["tasks_all"] = [t.model_dump() for t in tasks]
            state["tasks_done_ids"] = state.get("tasks_done_ids", [])

            db_store_tasks(session_id, tasks)

            visible = get_visible_tasks(state)
            bubble = "Click me" if not state.get("bubble_initialized", False) else pick_bubble("session_start")
            state["bubble_initialized"] = True

            return UIPatch(
                tasks=visible,
                pomodoro_suggestion=data.get("pomodoro_suggestion"),
                ghost_bubble=bubble,
            )

        payload["user_message"] = f"{user_message}\nMake tasks more specific to the topic_summary and avoid generic wording."

    # fallback
    tasks = tasks[:6] if "tasks" in locals() else []
    state["tasks_all"] = [t.model_dump() for t in tasks]
    state["tasks_done_ids"] = state.get("tasks_done_ids", [])
    if tasks:
        db_store_tasks(session_id, tasks)

    return UIPatch(
        tasks=get_visible_tasks(state),
        pomodoro_suggestion=25,
        ghost_bubble=pick_bubble("session_start"),
    )


def summary_agent(llm: ChatGoogleGenerativeAI, content_text: str, style: Dict[str, Any], session_id: str) -> UIPatch:
    payload = {
        "summary_mode": style.get("summary_mode", "detailed"),
        "focus": style.get("focus", "balanced"),
        "assessment": style.get("assessment", "quiz"),
        "content": content_text[:18000],
    }

    schema_hint = '{"summary":"Overview: ..."}'
    t0 = datetime.utcnow()
    trace_add(session_id, "summary_start", {"content_len": len(payload["content"]), "assessment": payload["assessment"]})
    data = llm_json(llm, SUMMARY_SYSTEM, json.dumps(payload, ensure_ascii=False), schema_hint=schema_hint, tries=2)
    ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    trace_add(session_id, "summary_end", {"ms": ms, "summary_len": len(str(data.get("summary", "")))})
    return UIPatch(summary=str(data.get("summary", "")).strip(), ghost_bubble="Summary ready")


def quiz_agent(llm: ChatGoogleGenerativeAI, summary_text: str, prefs: Dict[str, Any], style: Dict[str, Any], session_id: str) -> UIPatch:
    quiz_count = max(5, min(20, int(prefs.get("quiz_count", 8))))
    types = prefs.get("quiz_types", ["mcq", "tf"])
    if not isinstance(types, list) or not types:
        types = ["mcq", "tf"]

    difficulty = prefs.get("difficulty", "medium")
    assessment = style.get("assessment", "quiz")

    payload = {
        "quiz_count": quiz_count,
        "quiz_types": types,
        "difficulty": difficulty,
        "assessment": assessment,
        "summary": summary_text,
    }

    schema_hint = '{"quiz":{"title":"Quick Check","questions":[{"id":"q1","type":"tf","question":"...","answer":"T"}]}}'
    t0 = datetime.utcnow()
    trace_add(session_id, "quiz_start", {"quiz_count": quiz_count, "types": types, "difficulty": difficulty, "assessment": assessment})
    data = llm_json(llm, QUIZ_SYSTEM, json.dumps(payload, ensure_ascii=False), schema_hint=schema_hint, tries=2)
    ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    trace_add(session_id, "quiz_end", {"ms": ms})
    quiz_obj = Quiz(**data.get("quiz", {}))
    return UIPatch(quiz=quiz_obj, ghost_bubble=pick_bubble("quiz_ready"))


def cards_agent(llm: ChatGoogleGenerativeAI, summary_text: str, prefs: Dict[str, Any], session_id: str) -> UIPatch:
    n = max(3, min(25, int(prefs.get("cards_count", 10))))
    payload = {"cards_count": n, "summary": summary_text}

    schema_hint = '{"cards":[{"id":"c1","front":"...","back":"..."}]}'
    t0 = datetime.utcnow()
    trace_add(session_id, "cards_start", {"cards_count": n})
    data = llm_json(llm, CARDS_SYSTEM, json.dumps(payload, ensure_ascii=False), schema_hint=schema_hint, tries=2)
    ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    trace_add(session_id, "cards_end", {"ms": ms})
    cards = [Card(**c) for c in (data.get("cards") or [])]
    return UIPatch(cards=cards, ghost_bubble="Cards ready")


def critic_agent(llm: ChatGoogleGenerativeAI, patch: UIPatch, session_id: str) -> Tuple[bool, List[str]]:
    payload = patch.model_dump()
    schema_hint = '{"ok":true,"issues":[]}'
    t0 = datetime.utcnow()
    trace_add(session_id, "critic_start", {"patch_keys": [k for k, v in payload.items() if v is not None]})
    data = llm_json(llm, CRITIC_SYSTEM, json.dumps(payload, ensure_ascii=False), schema_hint=schema_hint, tries=2)
    ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
    trace_add(session_id, "critic_end", {"ms": ms, "ok": bool(data.get("ok", False))})
    ok = bool(data.get("ok", False))
    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = ["Critic issues format invalid."]
    return ok, [str(x) for x in issues]


# =========================
# Orchestrator
# =========================
def orchestrate(event: AgentEvent, state: Dict[str, Any]) -> UIPatch:
    sid = event.session_id
    trace_add(sid, "event_received", {"event_type": event.event_type, "payload_keys": list(event.payload.keys())})

    try:
        main_llm = get_main_llm()
        fast_llm = get_fast_llm()
    except Exception as e:
        trace_add(sid, "llm_init_failed", {"error": repr(e)})
        return UIPatch(ghost_bubble="Try again", agent_message="LLM not ready. Check API key/model.")

    try:
        # DB log
        try:
            db_log_event(sid, event.event_type, event.payload)
        except Exception as e:
            trace_add(sid, "db_log_failed", {"error": repr(e)})

        et = event.event_type
        patch = UIPatch()

        if et == "USER_MESSAGE":
            msg = str(event.payload.get("message", "")).strip()
            if not msg:
                return UIPatch(ghost_bubble="Say something", agent_message="Type your question or upload a lecture.")

            context = str(event.payload.get("context", "")).strip()
            if context:
                state["last_context_seen"] = context
                state["context_text"] = context

            state["last_user_message"] = msg
            state["prefs"] = parse_prefs_from_text(msg, state.get("prefs", {}))
            state["study_style"] = detect_study_style(msg, state.get("study_style", {}))

            trace_add(sid, "policy", {
                "has_lecture": bool(state.get("context_text")),
                "assessment": state["study_style"].get("assessment"),
                "prefs": state["prefs"]
            })

            # store prefs/style
            try:
                db_upsert_session(sid, state["prefs"], state["study_style"])
            except Exception as e:
                trace_add(sid, "db_upsert_failed", {"error": repr(e)})

            # ===== Pipeline =====
            if state.get("context_text"):
                # SUMMARY uses FAST model
                sp = summary_agent(fast_llm, state["context_text"], state["study_style"], sid)
                state["lastSummary"] = sp.summary or ""
                patch.summary = sp.summary

                # TASKS use MAIN model (or also flash, your choice)
                tp = planner_agent(main_llm, msg, state["lastSummary"], state, sid)
                patch.tasks = tp.tasks
                patch.pomodoro_suggestion = tp.pomodoro_suggestion

                patch.agent_message = "Summary + tasks ready. Want a quiz now? Tell me: TF/MCQ/both + count + difficulty."
                patch.ghost_bubble = "Ready"
                state["awaiting_quiz_prefs"] = True
                state["lastQuiz"] = None

            else:
                tp = planner_agent(main_llm, msg, msg, state, sid)
                patch.tasks = tp.tasks
                patch.pomodoro_suggestion = tp.pomodoro_suggestion
                patch.agent_message = "Upload your lecture PDF or tell me the topic."
                patch.ghost_bubble = "Talk to me"

            # Quiz on demand
            if wants_quiz(msg) and state.get("lastSummary"):
                qp = quiz_agent(main_llm, state["lastSummary"], state["prefs"], state["study_style"], sid)
                state["lastQuiz"] = qp.quiz.model_dump() if qp.quiz else None
                patch.quiz = qp.quiz
                patch.ghost_bubble = qp.ghost_bubble
                patch.agent_message = "Quiz generated. Answer in the Quiz tab."
                state["awaiting_quiz_prefs"] = False

        elif et == "TASK_DONE":
            task_id = str(event.payload.get("task_id", "")).strip()
            if not task_id:
                return UIPatch(ghost_bubble="Try again", agent_message="Missing task id.")

            mark_task_done(state, task_id)
            try:
                db_mark_task_done(sid, task_id)
            except Exception as e:
                trace_add(sid, "db_mark_done_failed", {"error": repr(e)})

            patch.tasks = get_visible_tasks(state)
            patch.ghost_bubble = pick_bubble("task_done")
            patch.agent_message = "Nice. Keep going."

        elif et == "QUIZ_SUBMIT":
            answers = event.payload.get("answers", [])
            if not isinstance(answers, list):
                answers = []

            state["lastQuizAnswers"] = answers
            score, total = score_quiz(state, answers)

            try:
                db_save_score(sid, score, total)
            except Exception as e:
                trace_add(sid, "db_save_score_failed", {"error": repr(e)})

            summary_text = str(event.payload.get("summary_text", "")).strip() or str(state.get("lastSummary", "")).strip()
            if not summary_text:
                return UIPatch(ghost_bubble="No summary", agent_message="No summary found.")

            cp = cards_agent(main_llm, summary_text, state["prefs"], sid)
            state["lastCards"] = [c.model_dump() for c in (cp.cards or [])]

            patch.cards = cp.cards
            patch.ghost_bubble = clamp_3_words(f"Score {score}/{total}") if total > 0 else pick_bubble("score")
            patch.agent_message = f"Score: {score}/{total}. Want more questions or harder difficulty?"

        else:
            patch = UIPatch(ghost_bubble="Click me")

        return finalize_patch(main_llm, patch, sid)

    except Exception as e:
        trace_add(sid, "orchestrate_failed", {"error": repr(e)})
        return UIPatch(ghost_bubble="Try again", agent_message="Backend error. Check server logs.")


def finalize_patch(llm: ChatGoogleGenerativeAI, patch: UIPatch, session_id: str) -> UIPatch:
    # NOTE: critic adds latency. Keep it but now you can see timing in trace.
    try:
        ok, issues = critic_agent(llm, patch, session_id)
        if not ok:
            trace_add(session_id, "critic_issues", {"issues": issues})
            if not patch.ghost_bubble:
                patch.ghost_bubble = "Try again"
    except Exception as e:
        trace_add(session_id, "critic_failed", {"error": repr(e)})

    if patch.ghost_bubble:
        patch.ghost_bubble = clamp_3_words(patch.ghost_bubble)
    return patch


# =========================
# Routes
# =========================
@app.get("/")
def home():
    return {"ok": True, "msg": "Backend running. Use /health or POST /agent/event"}

@app.get("/health")
def health():
    return {"ok": True, "db": str(DB_PATH)}

@app.post("/upload/text")
def upload_text():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (field 'file' is missing)."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected."}), 400

    try:
        text = extract_text_from_upload(file)
        max_chars = 18000
        text = text[:max_chars]
        return jsonify({"ok": True, "text": text, "name": file.filename})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "Upload failed. Try a different file."}), 500

@app.post("/agent/event")
def agent_event():
    # ✅ PROOF the route is hit (terminal + server.log)
    logger.info("✅ HIT /agent/event")
    print("✅ HIT /agent/event", flush=True)

    try:
        event = AgentEvent(**request.get_json(force=True))
    except ValidationError as e:
        return jsonify({"error": "Invalid request", "details": e.errors()}), 400

    # ✅ optional: log session id
    logger.info(f"session_id={event.session_id} event_type={event.event_type}")
    print(f"session_id={event.session_id} event_type={event.event_type}", flush=True)

    state = get_state(event.session_id)
    patch = orchestrate(event, state)

    resp = AgentResponse(
        session_id=event.session_id,
        updated_state=state,
        ui_patch=patch,
    )
    return jsonify(resp.model_dump())


if __name__ == "__main__":
    db_init()
    print("DB initialized at:", DB_PATH)
    print("GOOGLE_API_KEY loaded:", bool(os.getenv("GOOGLE_API_KEY")))
    print("MAIN MODEL:", os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    print("FAST MODEL:", os.getenv("FAST_GEMINI_MODEL", "gemini-2.0-flash"))
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
