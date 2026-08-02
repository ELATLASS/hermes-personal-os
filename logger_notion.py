"""
Module: logger_notion
Function: log_event

Enregistre l'état d'exécution (SUCCESS, WARNING, ERROR), le temps d'exécution
et les messages de debug dans la base System Logs de Notion.
"""

import os
import logging
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger("logger_notion")

VALID_STATUSES = {"SUCCESS", "WARNING", "ERROR", "INFO"}


def log_event(
    skill: str,
    status: str,
    execution_time_ms: int,
    message: str,
    auto_retry: bool = True,
) -> Optional[dict]:
    """
    Log a skill execution event to the Notion System Logs database.

    Args:
        skill: Name of the skill that produced this event
        status: Execution status (SUCCESS, WARNING, ERROR, INFO)
        execution_time_ms: Execution time in milliseconds
        message: Human-readable debug message
        auto_retry: If True, retry on transient Notion API failures

    Returns:
        Notion API response dict, or None if logging failed
    """
    if status not in VALID_STATUSES:
        logger.warning(f"Invalid status '{status}', defaulting to 'INFO'")
        status = "INFO"

    logger.info(f"[{status}] {skill}: {message} ({execution_time_ms}ms)")

    notion_token = os.getenv("NOTION_TOKEN")
    logs_db_id = os.getenv("NOTION_LOGS_DB_ID")

    if not notion_token or not logs_db_id:
        logger.warning("NOTION_TOKEN or NOTION_LOGS_DB_ID not set, logging to stdout only")
        return None

    from notion_client import Client

    notion = Client(auth=notion_token)

    def _do_log():
        response = notion.pages.create(
            parent={"database_id": logs_db_id},
            properties={
                "Title": {"title": [{"text": {"content": f"[{status}] {skill}"}}]},
                "Skill": {"select": {"name": skill}},
                "Status": {"select": {"name": status}},
                "Execution Time (ms)": {"number": execution_time_ms},
                "Message": {"rich_text": [{"text": {"content": message[:200]}}]},
                "Timestamp": {"date": {"start": datetime.utcnow().isoformat() + "Z"}},
            },
        )
        return response

    # Apply retry policy (max_attempts=3, backoff_factor=2)
    max_attempts = 3
    backoff = 2

    for attempt in range(1, max_attempts + 1):
        try:
            result = _do_log()
            logger.info(f"✅ Logged to Notion on attempt {attempt}")
            return result
        except Exception as e:
            logger.warning(f"Notion log attempt {attempt}/{max_attempts} failed: {e}")
            if not auto_retry or attempt == max_attempts:
                break
            wait = backoff ** (attempt - 1)
            time.sleep(wait)

    logger.error(f"❌ Failed to log to Notion after {max_attempts} attempts")
    return None


# ── Timer decorator for skill execution timing ──────────────────────────
def timed(func):
    """Decorator to measure and log execution time of a skill."""
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = int((time.time() - start) * 1000)
            log_event(
                skill=func.__module__.split(".")[-1],
                status="SUCCESS",
                execution_time_ms=elapsed_ms,
                message=f"Completed successfully in {elapsed_ms}ms",
            )
            return result
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            log_event(
                skill=func.__module__.split(".")[-1],
                status="ERROR",
                execution_time_ms=elapsed_ms,
                message=f"Failed after {elapsed_ms}ms: {str(e)}",
            )
            raise
    return wrapper
