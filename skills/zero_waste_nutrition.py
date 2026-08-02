"""
Skill: zero_waste_nutrition
Module: skills.zero_waste_nutrition
Function: generate_meal_plan

Analyse la péremction du stock frigo, propose des recettes 3 repas/jour
optimisées prise de masse et génère la liste de courses sans gaspillage.
"""

import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger("skill.zero_waste_nutrition")

# Skills config parameters (from gemini-code spec)
DEFAULT_MEALS_PER_DAY = 3
DEFAULT_STRATEGY = "zero-waste"
DEFAULT_TARGET_WEIGHT_KG = 65


def generate_meal_plan(
    meals_per_day: int = DEFAULT_MEALS_PER_DAY,
    strategy: str = DEFAULT_STRATEGY,
    target_weight_kg: int = DEFAULT_TARGET_WEIGHT_KG,
) -> Dict[str, Any]:
    """
    Analyze fridge inventory for expiring items, generate a 3-meal-per-day
    meal plan optimized for weight gain, and produce a zero-waste shopping list.

    Args:
        meals_per_day: Number of meals to plan per day (default: 3)
        strategy: Optimization strategy (default: zero-waste)
        target_weight_kg: Target weight for macro optimization (default: 65)

    Returns:
        Dict with meal_plan (7 days x meals_per_day), shopping_list, waste_reduction_pct
    """
    logger.info(
        f"🍽️ Zero-waste nutrition planner | "
        f"meals/day={meals_per_day}  strategy={strategy}  target={target_weight_kg}kg"
    )

    results = {
        "meal_plan": {},
        "shopping_list": [],
        "waste_reduction_pct": 0,
        "total_calories": 0,
        "macros": {"protein_g": 0, "carbs_g": 0, "fats_g": 0},
        "expiring_items_used": [],
    }

    # 1. Fetch fridge inventory from Notion (or other source)
    inventory = _fetch_fridge_inventory()
    logger.info(f"🧊 Fridge inventory: {len(inventory)} items")

    # 2. Identify expiring items (sorted by expiration date)
    expiring = _find_expiring_items(inventory)
    results["expiring_items_used"] = [item["name"] for item in expiring]

    # 3. Calculate daily macros for weight gain target
    daily_calories = _calculate_target_calories(target_weight_kg)
    daily_protein = _calculate_protein_target(target_weight_kg)

    # 4. Generate 7-day meal plan
    week_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for day in week_days:
        daily_meals = []
        daily_cal = 0
        daily_protein_g = 0

        for meal_idx in range(meals_per_day):
            # Use expiring items first (zero-waste strategy)
            used_items = _select_expiring_items_for_meal(expiring, daily_meals, meal_idx)

            # Generate recipe based on available items + shopping list needs
            recipe = _generate_recipe(
                used_items,
                daily_calories // meals_per_day,
                daily_protein // meals_per_day,
                target_weight_kg,
            )

            daily_meals.append(recipe)
            daily_cal += recipe.get("calories", 0)
            daily_protein_g += recipe.get("protein_g", 0)

        results["meal_plan"][day] = daily_meals
        results["total_calories"] += daily_cal
        results["macros"]["protein_g"] += daily_protein_g

    # 5. Generate shopping list (items not covered by expiring inventory)
    results["shopping_list"] = _generate_shopping_list(results["meal_plan"], inventory)

    # 6. Calculate waste reduction
    used_count = len(set(results["expiring_items_used"]))
    total_count = len(inventory)
    results["waste_reduction_pct"] = round((used_count / total_count * 100) if total_count else 0, 1)

    logger.info(
        f"✅ Meal plan: 7 days x {meals_per_day} meals | "
        f"total: {results['total_calories']} kcal | "
        f"protein: {results['macros']['protein_g']}g | "
        f"waste reduction: {results['waste_reduction_pct']}% | "
        f"shopping items: {len(results['shopping_list'])}"
    )

    _record_in_notion(results)
    return results


def _fetch_fridge_inventory() -> List[Dict]:
    """Fetch fridge inventory from Notion or other source."""
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logger.warning("NOTION_TOKEN not set, using stub inventory")
        return _stub_inventory()

    # TODO: Connect to Notion fridge inventory database
    # For now, use stub data
    return _stub_inventory()


def _stub_inventory() -> List[Dict]:
    """Stub fridge inventory for development/testing."""
    now = datetime.utcnow()
    return [
        {"name": "chicken_breast", "quantity": 500, "unit": "g", "expires": (now + timedelta(days=2)).isoformat()},
        {"name": "brown_rice", "quantity": 1, "unit": "kg", "expires": (now + timedelta(days=10)).isoformat()},
        {"name": "oats", "quantity": 500, "unit": "g", "expires": (now + timedelta(days=15)).isoformat()},
        {"name": "protein_powder", "quantity": 2, "unit": "kg", "expires": (now + timedelta(days=30)).isoformat()},
        {"name": "bananas", "quantity": 6, "unit": "pcs", "expires": (now + timedelta(days=3)).isoformat()},
        {"name": "spinach", "quantity": 200, "unit": "g", "expires": (now + timedelta(days=1)).isoformat()},
        {"name": "eggs", "quantity": 12, "unit": "pcs", "expires": (now + timedelta(days=7)).isoformat()},
        {"name": "peanut_butter", "quantity": 300, "unit": "g", "expires": (now + timedelta(days=20)).isoformat()},
        {"name": "milk", "quantity": 1, "unit": "L", "expires": (now + timedelta(days=4)).isoformat()},
        {"name": "salmon", "quantity": 300, "unit": "g", "expires": (now + timedelta(days=1)).isoformat()},
    ]


def _find_expiring_items(inventory: List[Dict], threshold_days: int = 5) -> List[Dict]:
    """Find items expiring within threshold_days."""
    cutoff = datetime.utcnow() + timedelta(days=threshold_days)
    expiring = []
    for item in inventory:
        try:
            exp_date = datetime.fromisoformat(item.get("expires", ""))
            if exp_date <= cutoff:
                expiring.append({**item, "days_until_expiry": (exp_date - datetime.utcnow()).days})
        except Exception:
            pass
    return sorted(expiring, key=lambda x: x["days_until_expiry"])


def _calculate_target_calories(target_weight_kg: float) -> int:
    """Calculate daily calorie target for weight gain (500 kcal surplus)."""
    # BMR approximation: weight_kg * 24 * 1.2 (sedentary) + 500 surplus
    return int(target_weight_kg * 24 * 1.2 + 500)


def _calculate_protein_target(target_weight_kg: float) -> int:
    """Calculate daily protein target (2.2g per kg body weight)."""
    return int(target_weight_kg * 2.2)


def _select_expiring_items_for_meal(expiring: List[Dict], existing_meals: List, meal_idx: int) -> List[Dict]:
    """Select expiring items to use in a particular meal (zero-waste priority)."""
    if not expiring:
        return []
    # Distribute expiring items across meals
    items_per_meal = 1 + (len(expiring) // max(len(existing_meals), 1))
    start = meal_idx * items_per_meal
    return expiring[start:start + items_per_meal]


def _generate_recipe(available_items: List[Dict], target_calories: int, target_protein: int, target_weight: float) -> Dict:
    """Generate a recipe using available items, optimized for target macros."""
    # This is a stub — in production this would use an LLM or recipe DB
    recipe_templates = [
        {
            "name": "Protein Power Bowl",
            "calories": 650,
            "protein_g": 45,
            "carbs_g": 55,
            "fats_g": 22,
            "ingredients": ["chicken_breast", "brown_rice", "spinach"],
            "instructions": "Grill chicken, cook rice, sauté spinach. Combine and serve.",
        },
        {
            "name": "Overnight Oats with Banana",
            "calories": 520,
            "protein_g": 30,
            "carbs_g": 65,
            "fats_g": 15,
            "ingredients": ["oats", "milk", "bananas", "protein_powder"],
            "instructions": "Mix oats, milk, protein powder. Refrigerate overnight. Add banana slices.",
        },
        {
            "name": "Salmon & Rice Plate",
            "calories": 720,
            "protein_g": 52,
            "carbs_g": 48,
            "fats_g": 30,
            "ingredients": ["salmon", "brown_rice", "spinach"],
            "instructions": "Pan-sear salmon, cook rice, steam spinach. Serve together.",
        },
        {
            "name": "Protein Pancakes",
            "calories": 480,
            "protein_g": 38,
            "carbs_g": 42,
            "fats_g": 16,
            "ingredients": ["oats", "eggs", "protein_powder", "milk"],
            "instructions": "Blend oats into flour, mix with eggs, protein powder, milk. Cook pancakes.",
        },
        {
            "name": "Peanut Butter Banana Shake",
            "calories": 580,
            "protein_g": 28,
            "carbs_g": 52,
            "fats_g": 28,
            "ingredients": ["banana", "milk", "peanut_butter", "protein_powder"],
            "instructions": "Blend all ingredients until smooth.",
        },
    ]

    # Pick a recipe that uses available items
    available_names = {item["name"] for item in available_items}
    best_match = None
    best_match_count = 0

    for recipe in recipe_templates:
        match_count = len(set(recipe["ingredients"]) & available_names)
        if match_count > best_match_count:
            best_match = recipe
            best_match_count = match_count

    if best_match is None:
        best_match = recipe_templates[0]

    return best_match


def _generate_shopping_list(meal_plan: Dict[str, List[Dict]], inventory: List[Dict]) -> List[Dict]:
    """Generate shopping list for ingredients not in current inventory."""
    inventory_names = {item["name"] for item in inventory}

    # Collect all ingredients from the meal plan
    all_ingredients = set()
    for day_meals in meal_plan.values():
        for meal in day_meals:
            for ingredient in meal.get("ingredients", []):
                all_ingredients.add(ingredient)

    missing = all_ingredients - inventory_names
    return [{"item": name, "estimated_quantity": "TBD", "unit": "TBD"} for name in sorted(missing)]


def _record_in_notion(results: Dict):
    """Log meal plan results to Notion."""
    notion_token = os.getenv("NOTION_TOKEN")
    logs_db_id = os.getenv("NOTION_LOGS_DB_ID")
    if not notion_token or not logs_db_id:
        logger.warning("Notion env vars not set, skipping log")
        return

    try:
        from notion_client import Client
        notion = Client(auth=notion_token)
        notion.pages.create(
            parent={"database_id": logs_db_id},
            properties={
                "Title": {
                    "title": [{
                        "text": {
                            "content": f"Meal Plan Generated — {datetime.utcnow().strftime('%Y-%m-%d')}"
                        }
                    }]
                },
                "Status": {"select": {"name": "SUCCESS"}},
                "Waste Reduction %": {"number": results["waste_reduction_pct"]},
                "Shopping Items": {"number": len(results["shopping_list"])},
            },
        )
        logger.info("📝 Meal plan logged to Notion")
    except Exception as e:
        logger.error(f"Notion logging failed: {e}")
