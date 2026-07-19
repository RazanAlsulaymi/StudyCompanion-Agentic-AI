from typing import List, Literal, Optional, Dict, Any
import uuid

from pydantic import BaseModel, Field, model_validator


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
                raise ValueError("MCQ choices must be 3–4 items")

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