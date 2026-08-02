# Hermes-Personal-OS skill stubs

This directory contains the Python modules for each skill defined in the
`gemini-code` specification.

## Environment Variables Required

| Variable            | Purpose                                    |
|---------------------|--------------------------------------------|
| NOTION_TOKEN        | Notion API authentication token            |
| NOTION_JOB_DB_ID    | Notion database ID for job board tracking  |
| NOTION_LBC_DB_ID    | Notion database ID for Le Bon Coin listings|
| NOTION_LOGS_DB_ID   | Notion database ID for system execution logs|
| TELEGRAM_BOT_TOKEN  | Telegram Bot API token                     |
| TELEGRAM_CHAT_ID    | Telegram chat ID for notifications         |

## Skill Modules

1. `skills/job_hunter.py` — Job scraping, qualification, STAR cover letter generation, auto-apply
2. `skills/leboncoin_reviewer.py` — Le Bon Coin listing stagnation monitoring
3. `skills/instagram_planner.py` — Instagram grid planning & caption generation
4. `skills/zero_waste_nutrition.py` — Fridge inventory analysis, meal planning, zero-waste shopping
5. `logger_notion.py` — Notion system logger
6. `telegram_bot.py` — Telegram notification sender
