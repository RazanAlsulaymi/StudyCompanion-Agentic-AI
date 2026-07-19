import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG_PATH = Path(__file__).resolve().parent.parent / "server.log"

logger = logging.getLogger("study_companion")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)

# File handler
fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)

# Avoid duplicate handlers
if not logger.handlers:
    logger.addHandler(ch)
    logger.addHandler(fh)

logger.propagate = False

# =========================
# TRACE (in-memory)
# =========================

TRACE: Dict[str, List[Dict[str, Any]]] = {}


def trace_add(
    session_id: str,
    step: str,
    data: Optional[Dict[str, Any]] = None,
):
    data = data or {}

    item = {
        "ts": datetime.utcnow().isoformat(),
        "step": step,
        **data,
    }

    TRACE.setdefault(session_id, []).append(item)

    if len(TRACE[session_id]) > 200:
        TRACE[session_id] = TRACE[session_id][-200:]

    msg = (
        f"[TRACE] {session_id} | {step} | "
        f"{json.dumps(data, ensure_ascii=False)}"
    )

    print(msg, flush=True)
    logger.info(msg)