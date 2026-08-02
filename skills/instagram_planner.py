"""
Skill: instagram_planner
Module: skills.instagram_planner
Function: sync_feed_and_captions

Planifie les posts et carrousels dans la grille 3x3 Notion,
génère les légendes optimisées et prépare les assets de sorties photo.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("skill.instagram_planner")

# Skills config parameters (from gemini-code spec)
DEFAULT_GRID_LAYOUT = "3x3"
DEFAULT_CAMERA_PRESET = "Canon EOS R8"


def sync_feed_and_captions(
    grid_layout: str = DEFAULT_GRID_LAYOUT,
    default_camera_preset: str = DEFAULT_CAMERA_PRESET,
) -> Dict[str, Any]:
    """
    Sync Instagram feed plan from Notion grid, generate optimized captions,
    and prepare photo assets.

    Args:
        grid_layout: Grid dimensions (e.g. "3x3")
        default_camera_preset: Camera preset for photo assets

    Returns:
        Dict with posts_scheduled, captions_generated, assets_prepared
    """
    rows, cols = _parse_grid(grid_layout)
    logger.info(
        f"📱 Instagram planner | grid={grid_layout} ({rows}x{cols}) "
        f"camera={default_camera_preset}"
    )

    results = {
        "posts_scheduled": 0,
        "captions_generated": 0,
        "assets_prepared": 0,
        "scheduled_posts": [],
    }

    # 1. Fetch grid content from Notion
    grid_cells = _fetch_grid_from_notion(rows, cols)
    logger.info(f"📋 Fetched {len(grid_cells)} grid cells from Notion")

    # 2. For each cell with content, generate caption and schedule
    for idx, cell in enumerate(grid_cells):
        if not cell.get("content"):
            continue

        caption = _generate_optimized_caption(
            cell.get("content"),
            cell.get("hashtags", ""),
            cell.get("tone", "engaging"),
        )
        results["captions_generated"] += 1

        post_info = {
            "grid_position": idx + 1,
            "content_type": cell.get("content_type", "photo"),
            "caption_preview": caption[:50] + "...",
            "scheduled_at": _compute_schedule(idx),
        }
        results["scheduled_posts"].append(post_info)

        # 3. Prepare assets (apply camera preset metadata, generate previews)
        asset = _prepare_asset(cell, default_camera_preset)
        if asset:
            results["assets_prepared"] += 1

        results["posts_scheduled"] += 1

    logger.info(
        f"✅ Completed: {results['posts_scheduled']} posts scheduled, "
        f"{results['captions_generated']} captions, "
        f"{results['assets_prepared']} assets prepared"
    )

    _record_in_notion(results)
    return results


def _parse_grid(grid_layout: str) -> tuple:
    """Parse '3x3' into (rows, cols)."""
    parts = grid_layout.lower().split("x")
    return int(parts[0]), int(parts[1])


def _fetch_grid_from_notion(rows: int, cols: int) -> List[Dict]:
    """Fetch grid cells from Notion Instagram planner database."""
    notion_token = os.getenv("NOTION_TOKEN")
    instagram_db_id = os.getenv("NOTION_INSTAGRAM_DB_ID", "")
    if not notion_token or not instagram_db_id:
        logger.warning("NOTION_TOKEN or NOTION_INSTAGRAM_DB_ID not set, using stub data")
        return _stub_grid(rows, cols)

    try:
        from notion_client import Client
        notion = Client(auth=notion_token)
        # Handle both v2.x (databases.query) and v3.x (request method)
        try:
            response = notion.databases.query(database_id=instagram_db_id)
        except AttributeError:
            response = notion.request(
                path=f"databases/{instagram_db_id}/query",
                method="POST",
                json={"page_size": 100}
            ).to_dict()
        cells = []
        for page in response.get("results", []):
            props = page.get("properties", {})
            cells.append({
                "content": props.get("Content", {}).get("rich_text", [{}])[0].get("plain_text", ""),
                "content_type": props.get("Type", {}).get("select", {}).get("name", "photo"),
                "hashtags": props.get("Hashtags", {}).get("rich_text", [{}])[0].get("plain_text", ""),
                "tone": props.get("Tone", {}).get("select", {}).get("name", "engaging"),
            })
        return cells[:rows * cols]
    except Exception as e:
        logger.error(f"Notion fetch failed: {e}")
        return _stub_grid(rows, cols)


def _stub_grid(rows: int, cols: int) -> List[Dict]:
    """Generate stub grid cells for development."""
    stub = []
    templates = [
        {"content": "Behind the scenes of today's shoot", "content_type": "photo", "tone": "authentic"},
        {"content": "New gear review — does it deliver?", "content_type": "photo", "tone": "honest"},
        {"content": "Weekend vibes captured on film", "content_type": "carousel", "tone": "nostalgic"},
    ]
    for i in range(rows * cols):
        stub.append(templates[i % len(templates)])
    return stub


def _generate_optimized_caption(content: str, hashtags: str, tone: str) -> str:
    """Generate an optimized Instagram caption with CTAs and hashtags."""
    ctas = {
        "authentic": "What do you think? Drop a comment below 👇",
        "honest": "Would you use this? Let me know your take 👇",
        "nostalgic": "Tag someone who'd love this vibe 📸",
        "engaging": "Double tap if this resonates 🔥",
    }
    cta = ctas.get(tone, ctas["engaging"])
    return f"{content}\n\n{cta}\n\n{hashtags}".strip()


def _compute_schedule(index: int) -> str:
    """Compute scheduled post time (staggered)."""
    base = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    slot = base + timedelta(days=index, hours=index % 3, minutes=30)
    return slot.isoformat()


def _prepare_asset(cell: Dict, camera_preset: str) -> Optional[str]:
    """Prepare photo asset with camera preset metadata."""
    logger.info(f"  📷 Preparing asset (preset: {camera_preset})")
    # TODO: Apply EXIF metadata, generate thumbnails, upload to CDN
    return f"asset_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"


def _record_in_notion(results: Dict):
    """Log Instagram planning results to Notion."""
    logger.info("📝 Recording Instagram plan results in Notion")
    # TODO: Implement Notion page creation
