"""
Module: telegram_bot
Function: send_telegram_alert

Envoie une synthèse interactive et des notifications d'alerte
sur le smartphone via l'API Telegram.
"""

import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("telegram_bot")

# Valid parse modes per Telegram Bot API
VALID_PARSE_MODES = {"Markdown", "MarkdownV2", "HTML", "None"}


def send_telegram_alert(
    text: str,
    parse_mode: str = "Markdown",
    chat_id: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    """
    Send a Telegram message via the bot API.

    Args:
        text: Message text (supports Markdown/HTML formatting)
        parse_mode: One of Markdown, MarkdownV2, HTML, None
        chat_id: Override chat ID (defaults to TELEGRAM_CHAT_ID env var)
        reply_markup: Optional inline keyboard markup for interactive buttons

    Returns:
        Telegram API response dict, or None if sending failed
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    target_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return None
    if not target_chat_id:
        logger.error("TELEGRAM_CHAT_ID not set")
        return None

    if parse_mode not in VALID_PARSE_MODES:
        logger.warning(f"Invalid parse_mode '{parse_mode}', defaulting to 'None'")
        parse_mode = "None"

    import requests

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": parse_mode if parse_mode != "None" else None,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    # Retry policy
    max_attempts = 3
    backoff = 2

    import time
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Telegram alert sent to chat {target_chat_id}")
                return result
            else:
                logger.warning(f"Telegram API returned {response.status_code}: {response.text}")
        except Exception as e:
            logger.warning(f"Telegram send attempt {attempt}/{max_attempts} failed: {e}")

        if attempt < max_attempts:
            wait = backoff ** (attempt - 1)
            time.sleep(wait)

    logger.error(f"❌ Failed to send Telegram alert after {max_attempts} attempts")
    return None


def send_interactive_summary(
    summary: Dict[str, Any],
    title: str = "📊 Hermes-Personal-OS Summary",
    chat_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Send a formatted interactive summary with inline keyboard buttons.

    Args:
        summary: Dict of skill results {skill_name: {status, details, ...}}
        title: Header for the summary message
        chat_id: Override chat ID

    Returns:
        Telegram API response dict
    """
    lines = [f"*{title}*"]

    for skill, result in summary.items():
        status_icon = "✅" if result.get("status") == "SUCCESS" else "❌"
        lines.append(f"\n{status_icon} *{skill}*")

        if result.get("attempts", 1) > 1:
            lines.append(f"  Attempts: {result['attempts']}")

        if result.get("error"):
            lines.append(f"  Error: {result['error'][:100]}")

        if result.get("output"):
            for k, v in result["output"].items():
                if isinstance(v, (str, int, float)) and k != "details":
                    lines.append(f"  {k}: {v}")

    # Build inline keyboard for follow-up actions
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Re-run All", "callback_data": "rerun_all"},
                {"text": "📋 Full Logs", "callback_data": "view_logs"},
            ],
            [
                {"text": "🔍 Debug Details", "callback_data": "debug_info"},
            ],
        ]
    }

    text = "\n".join(lines)
    return send_telegram_alert(text=text, parse_mode="Markdown", chat_id=chat_id, reply_markup=keyboard)


def send_notification(
    message: str,
    title: str = "🔔 Hermes Notification",
    chat_id: Optional[str] = None,
) -> Optional[dict]:
    """Send a simple notification message."""
    text = f"*{title}*\n{message}"
    return send_telegram_alert(text=text, parse_mode="Markdown", chat_id=chat_id)
