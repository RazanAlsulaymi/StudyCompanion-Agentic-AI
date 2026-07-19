import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI


# =========================
# ENV
# =========================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH)


# =========================
# Cached LLMs
# =========================

_MAIN_LLM: Optional[ChatGoogleGenerativeAI] = None
_FAST_LLM: Optional[ChatGoogleGenerativeAI] = None


def make_llm(
    model_name: str,
    temperature: float,
) -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Missing GOOGLE_API_KEY in .env (project root)."
        )

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
    )


def get_main_llm() -> ChatGoogleGenerativeAI:
    global _MAIN_LLM

    if _MAIN_LLM is not None:
        return _MAIN_LLM

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.0-flash",
    )

    temperature = float(
        os.getenv(
            "LLM_TEMPERATURE",
            "0.2",
        )
    )

    _MAIN_LLM = make_llm(
        model_name=model,
        temperature=temperature,
    )

    return _MAIN_LLM


def get_fast_llm() -> ChatGoogleGenerativeAI:
    global _FAST_LLM

    if _FAST_LLM is not None:
        return _FAST_LLM

    model = os.getenv(
        "FAST_GEMINI_MODEL",
        "gemini-2.0-flash",
    )

    temperature = float(
        os.getenv(
            "LLM_TEMPERATURE",
            "0.2",
        )
    )

    _FAST_LLM = make_llm(
        model_name=model,
        temperature=temperature,
    )

    return _FAST_LLM


# =========================
# JSON Helpers
# =========================

def extract_json(text: str) -> Dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError("LLM output is not a string")

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")

    return json.loads(text[start : end + 1])


def json_repair_prompt(
    schema_hint: str,
    bad_text: str,
) -> str:
    return (
        "Fix the following so it becomes VALID JSON ONLY. "
        "No explanations, no markdown.\n"
        f"Schema hint: {schema_hint}\n"
        "Bad output:\n"
        f"{bad_text}"
    )


def llm_json(
    llm: ChatGoogleGenerativeAI,
    system: str,
    user: str,
    schema_hint: str,
    tries: int = 2,
) -> Dict[str, Any]:

    raw = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
    ).content

    try:
        return extract_json(raw)

    except Exception:

        if tries <= 1:
            raise

        repaired = llm.invoke(
            [
                SystemMessage(
                    content="Return ONLY valid JSON. No extra text."
                ),
                HumanMessage(
                    content=json_repair_prompt(
                        schema_hint,
                        raw,
                    )
                ),
            ]
        ).content

        return extract_json(repaired)