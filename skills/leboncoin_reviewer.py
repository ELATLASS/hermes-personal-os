"""
Skill: leboncoin_reviewer
Module: skills.leboncoin_reviewer
Function: check_stagnant_listings

Parcourt l'inventaire des objets à vendre et alerte si une annonce
dépasse 14 jours en ligne pour recommander une baisse de prix (-10%)
ou une republication.
"""

import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger("skill.leboncoin_reviewer")

# Skills config parameters (from gemini-code spec)
DEFAULT_STAGNANT_THRESHOLD_DAYS = 14
DEFAULT_PRICE_REDUCTION_PERCENT = 10


def check_stagnant_listings(
    stagnant_threshold_days: int = DEFAULT_STAGNANT_THRESHOLD_DAYS,
    price_reduction_percent: int = DEFAULT_PRICE_REDUCTION_PERCENT,
) -> Dict[str, Any]:
    """
    Review active Le Bon Coin listings in Notion, flag stale ones,
    recommend price reduction or republication.

    Args:
        stagnant_threshold_days: Days before a listing is considered stale
        price_reduction_percent: Recommended price cut percentage for stale listings

    Returns:
        Dict with stale_listings count, price_reductions recommended,
        republications recommended, total_value
    """
    logger.info(
        f"🔍 Checking Le Bon Coin listings | "
        f"threshold={stagnant_threshold_days}d  price_cut={price_reduction_percent}%"
    )

    results = {
        "total_listings": 0,
        "stale_listings": [],
        "price_reductions_recommended": 0,
        "republications_recommended": 0,
        "total_relisting_value": 0,
    }

    # 1. Fetch listings from Notion LBC database
    listings = _fetch_lbc_listings()
    results["total_listings"] = len(listings)
    logger.info(f"📋 Found {len(listings)} active LBC listings in Notion")

    # 2. Identify stale listings
    cutoff_date = datetime.utcnow() - timedelta(days=stagnant_threshold_days)

    for listing in listings:
        listing_date = _parse_date(listing.get("listing_date"))
        if listing_date and listing_date < cutoff_date:
            stale_info = {
                "title": listing.get("title"),
                "price": listing.get("price"),
                "category": listing.get("category"),
                "days_live": (datetime.utcnow() - listing_date).days,
                "recommended_action": _recommend_action(
                    listing, price_reduction_percent, stagnant_threshold_days
                ),
            }
            results["stale_listings"].append(stale_info)

            if stale_info["recommended_action"] == "reduce_price":
                results["price_reductions_recommended"] += 1
            else:
                results["republications_recommended"] += 1

            # Estimate value if republished
            results["total_relisting_value"] += listing.get("price", 0)

    logger.info(
        f"⚠️  {len(results['stale_listings'])} stale listings found | "
        f"price cuts: {results['price_reductions_recommended']} | "
        f"republications: {results['republications_recommended']}"
    )

    # 3. Log to Notion
    _record_in_notion(results)

    # 4. Notify via Telegram
    if results["stale_listings"]:
        _notify_telegram(results)

    return results


def _fetch_lbc_listings() -> List[Dict]:
    """Fetch listings from Notion LBC database. Stub implementation."""
    notion_token = os.getenv("NOTION_TOKEN")
    lbc_db_id = os.getenv("NOTION_LBC_DB_ID")
    if not notion_token or not lbc_db_id:
        logger.warning("NOTION_TOKEN or NOTION_LBC_DB_ID not set")
        return []

    try:
        from notion_client import Client
        notion = Client(auth=notion_token)
        # Handle both v2.x (databases.query) and v3.x (request method)
        try:
            response = notion.databases.query(database_id=lbc_db_id)
        except AttributeError:
            response = notion.request(
                path=f"databases/{lbc_db_id}/query",
                method="POST",
                json={"page_size": 100}
            ).to_dict()
        listings = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            listings.append({
                "title": props.get("Title", {}).get("title", [{}])[0].get("plain_text", "N/A"),
                "price": props.get("Price", {}).get("number"),
                "category": props.get("Category", {}).get("select", {}).get("name"),
                "listing_date": props.get("Listing Date", {}).get("date", {}).get("start"),
                "page_id": page.get("id"),
            })
        return listings
    except ImportError:
        logger.warning("notion-client not installed")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch LBC listings: {e}")
        return []


def _parse_date(date_str: str) -> datetime:
    """Parse ISO date string. Returns None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _recommend_action(listing: Dict, price_reduction_percent: int, threshold_days: int) -> str:
    """
    Decide whether to recommend a price reduction or republication.

    Rule: if listing has been live > threshold_days * 2, recommend republication.
    Otherwise, recommend a price reduction.
    """
    listing_date = _parse_date(listing.get("listing_date"))
    if not listing_date:
        return "reduce_price"

    days_live = (datetime.utcnow() - listing_date).days
    if days_live > threshold_days * 2:
        return "republication"
    return "reduce_price"


def _record_in_notion(results: Dict):
    """Log leboncoin review results to Notion."""
    logger.info("📝 Recording LBC review results in Notion")
    # TODO: Implement Notion page creation in LBC database


def _notify_telegram(results: Dict):
    """Send Telegram notification about stale listings."""
    logger.info("📱 Sending Telegram notification about stale listings")
    # TODO: Implement via telegram_bot.send_telegram_alert
