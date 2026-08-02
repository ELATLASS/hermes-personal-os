#!/usr/bin/env python3
"""
Hermes-Personal-OS — Main Orchestrator

Runs all configured skills on the GitHub Actions schedule (daily 07:00 UTC)
or on-demand via repository_dispatch / workflow_dispatch.

Retry policy: max_attempts=3, backoff_factor=2 (exponential backoff).
"""

import os
import sys
import json
import time
import logging
import argparse
import traceback
from typing import Any
from pathlib import Path

# ── Logging setup (auto-create logs dir) ───────────────────────────────
_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_log_dir, "hermes-os.log")),
    ],
)
logger = logging.getLogger("Hermes-Personal-OS")

# ── Retry configuration from spec ──────────────────────────────────────
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
BACKOFF_FACTOR = float(os.getenv("BACKOFF_FACTOR", "2"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# ── Skill registry (loaded from gemini-code spec) ──────────────────────
SKILLS = {
    "job_hunter_auto": {
        "module": "skills.job_hunter",
        "function": "process_job_applications",
        "parameters": {
            "target_roles": ["Data Analyst", "BI Engineer", "Backend Developer"],
            "min_matching_score": 75,
            "follow_up_days": 7,
        },
    },
    "leboncoin_reviewer": {
        "module": "skills.leboncoin_reviewer",
        "function": "check_stagnant_listings",
        "parameters": {
            "stagnant_threshold_days": 14,
            "price_reduction_percent": 10,
        },
    },
    "instagram_planner": {
        "module": "skills.instagram_planner",
        "function": "sync_feed_and_captions",
        "parameters": {
            "grid_layout": "3x3",
            "default_camera_preset": "Canon EOS R8",
        },
    },
    "zero_waste_nutrition": {
        "module": "skills.zero_waste_nutrition",
        "function": "generate_meal_plan",
        "parameters": {
            "meals_per_day": 3,
            "strategy": "zero-waste",
            "target_weight_kg": 65,
        },
    },
    "system_logger": {
        "module": "logger_notion",
        "function": "log_event",
        "parameters": {
            "auto_retry": True,
        },
    },
    "telegram_notifier": {
        "module": "telegram_bot",
        "function": "send_telegram_alert",
        "parameters": {
            "parse_mode": "Markdown",
        },
    },
}

# ── Dynamic import helper ──────────────────────────────────────────────
def load_skill(skill_key: str) -> Any:
    """Dynamically import and return the callable for a skill."""
    spec = SKILLS[skill_key]
    module_path = spec["module"]
    func_name = spec["function"]
    params = spec["parameters"]

    # Handle dotted module paths (e.g. "skills.job_hunter")
    parts = module_path.split(".")
    mod_name = parts[-1]
    pkg_path = ".".join(parts[:-1]) if len(parts) > 1 else ""

    if pkg_path:
        import importlib
        mod = importlib.import_module(f"{pkg_path}.{mod_name}")
    else:
        import importlib
        mod = importlib.import_module(mod_name)

    func = getattr(mod, func_name)
    return func, params


# ── Retry-with-backoff runner ──────────────────────────────────────────
def run_skill_with_retry(skill_key: str) -> dict:
    """
    Execute a skill with exponential backoff retry.

    Returns a result dict with status, attempts, output, error.
    """
    skill_name = SKILLS[skill_key]["module"] + "." + SKILLS[skill_key]["function"]
    logger.info(f"▶️ Starting skill: {skill_key} ({skill_name})")

    attempt = 0
    last_error = None

    while attempt < MAX_ATTEMPTS:
        attempt += 1
        logger.info(f"  Attempt {attempt}/{MAX_ATTEMPTS}")

        try:
            func, params = load_skill(skill_key)
            result = func(**params)
            logger.info(f"  ✅ Skill {skill_key} succeeded on attempt {attempt}")

            # Log to Notion via system_logger
            _log_to_notion(
                skill=skill_key,
                status="SUCCESS",
                execution_time_ms=0,
                message=f"Completed successfully on attempt {attempt}",
            )

            # Send Telegram notification
            _notify_telegram(
                skill=skill_key,
                status="SUCCESS",
                detail=f"Completed on attempt {attempt}",
            )

            return {
                "skill": skill_key,
                "status": "SUCCESS",
                "attempts": attempt,
                "output": result,
                "error": None,
            }

        except Exception as e:
            last_error = str(e)
            logger.warning(f"  ⚠️ Skill {skill_key} attempt {attempt} failed: {e}")
            traceback.print_exc()

            _log_to_notion(
                skill=skill_key,
                status="WARNING" if attempt < MAX_ATTEMPTS else "ERROR",
                execution_time_ms=0,
                message=f"Attempt {attempt}/{MAX_ATTEMPTS} failed: {e}",
            )

            if attempt < MAX_ATTEMPTS:
                wait = BACKOFF_FACTOR ** (attempt - 1)
                logger.info(f"  Sleeping {wait}s before retry...")
                time.sleep(wait)

    # All retries exhausted
    _log_to_notion(
        skill=skill_key,
        status="ERROR",
        execution_time_ms=0,
        message=f"FAILED after {MAX_ATTEMPTS} attempts: {last_error}",
    )
    _notify_telegram(
        skill=skill_key,
        status="ERROR",
        detail=f"Failed after {MAX_ATTEMPTS} attempts: {last_error}",
    )

    return {
        "skill": skill_key,
        "status": "ERROR",
        "attempts": MAX_ATTEMPTS,
        "output": None,
        "error": last_error,
    }


def _log_to_notion(skill: str, status: str, execution_time_ms: int, message: str):
    """Log execution state to Notion System Logs database."""
    try:
        from logger_notion import log_event
        log_event(
            skill=skill,
            status=status,
            execution_time_ms=execution_time_ms,
            message=message,
            auto_retry=True,
        )
    except Exception as e:
        logger.error(f"Failed to log to Notion: {e}")


def _notify_telegram(skill: str, status: str, detail: str):
    """Send Telegram alert notification."""
    try:
        from telegram_bot import send_telegram_alert
        send_telegram_alert(
            text=f"*{skill}* — `{status}`\n{detail}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


# ── Main entry point ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Hermes-Personal-OS orchestrator")
    parser.add_argument("--run-all", action="store_true", help="Run all skills")
    parser.add_argument("--run", type=str, help="Run a specific skill by name")
    parser.add_argument("--dry-run", action="store_true", help="Simulation mode")
    args = parser.parse_args()

    if args.dry_run:
        global DRY_RUN
        DRY_RUN = True

    results = []

    if args.run:
        # Run a single skill
        if args.run not in SKILLS:
            print(f"❌ Unknown skill: {args.run}")
            print(f"Available: {list(SKILLS.keys())}")
            sys.exit(1)
        skill_list = [args.run]
    else:
        # Run all skills (default)
        skill_list = list(SKILLS.keys())

    # Skip system_logger and telegram_notifier — those are infrastructure tools
    # The actual business skills run first, and they use system_logger/telegram
    # internally for logging and notifications.
    business_skills = [s for s in skill_list if s in (
        "job_hunter_auto", "leboncoin_reviewer", "instagram_planner", "zero_waste_nutrition"
    )]

    for skill_name in business_skills:
        if DRY_RUN:
            logger.info(f"  [DRY RUN] Would execute: {skill_name}")
            results.append({"skill": skill_name, "status": "SIMULATED", "output": None, "error": None})
            continue

        result = run_skill_with_retry(skill_name)
        results.append(result)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Hermes-Personal-OS — Execution Summary")
    print("=" * 60)
    for r in results:
        status_icon = "✅" if r["status"] == "SUCCESS" else ("🟨" if r["status"] == "SIMULATED" else "❌")
        print(f"  {status_icon} {r['skill']}: {r['status']} (attempts: {r.get('attempts', 0)})")
        if r["error"]:
            print(f"      Error: {r['error']}")
    print("=" * 60)

    # Exit non-zero if any skill failed
    failed = [r for r in results if r["status"] == "ERROR"]
    if failed:
        logger.error(f"{len(failed)} skill(s) failed: {[r['skill'] for r in failed]}")
        sys.exit(1)

    logger.info("All skills completed successfully!")


if __name__ == "__main__":
    main()
