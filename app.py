import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from core.orchestrator import orchestrate
from core.state import get_state

from database.sqlite_db import db_init, DB_PATH

from models.schemas import (
    AgentEvent,
    AgentResponse,
)

from utils.trace import logger
from utils.upload import extract_text_from_upload


app = Flask(__name__)
CORS(app)


@app.get("/")
def home():
    return {
        "ok": True,
        "msg": "Backend running. Use /health or POST /agent/event",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "db": str(DB_PATH),
    }


@app.post("/upload/text")
def upload_text():

    if "file" not in request.files:
        return (
            jsonify(
                {
                    "error": "No file uploaded (field 'file' is missing)."
                }
            ),
            400,
        )

    file = request.files["file"]

    if not file or not file.filename:
        return (
            jsonify(
                {
                    "error": "No file selected."
                }
            ),
            400,
        )

    try:

        text = extract_text_from_upload(file)

        text = text[:18000]

        return jsonify(
            {
                "ok": True,
                "text": text,
                "name": file.filename,
            }
        )

    except ValueError as e:

        return (
            jsonify(
                {
                    "error": str(e)
                }
            ),
            400,
        )

    except RuntimeError as e:

        return (
            jsonify(
                {
                    "error": str(e)
                }
            ),
            500,
        )

    except Exception:

        return (
            jsonify(
                {
                    "error": "Upload failed. Try a different file."
                }
            ),
            500,
        )


@app.post("/agent/event")
def agent_event():

    logger.info("HIT /agent/event")

    try:

        event = AgentEvent(
            **request.get_json(force=True)
        )

    except ValidationError as e:

        return (
            jsonify(
                {
                    "error": "Invalid request",
                    "details": e.errors(),
                }
            ),
            400,
        )

    logger.info(
        f"session_id={event.session_id} "
        f"event_type={event.event_type}"
    )

    state = get_state(event.session_id)

    patch = orchestrate(
        event,
        state,
    )

    response = AgentResponse(
        session_id=event.session_id,
        updated_state=state,
        ui_patch=patch,
    )
    return jsonify(
        response.model_dump()
    )


if __name__ == "__main__":

    db_init()

    print("DB initialized at:", DB_PATH)

    print(
        "GOOGLE_API_KEY loaded:",
        bool(os.getenv("GOOGLE_API_KEY")),
    )

    print(
        "MAIN MODEL:",
        os.getenv(
            "GEMINI_MODEL",
            "gemini-2.0-flash",
        ),
    )

    print(
        "FAST MODEL:",
        os.getenv(
            "FAST_GEMINI_MODEL",
            "gemini-2.0-flash",
        ),
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
    )
