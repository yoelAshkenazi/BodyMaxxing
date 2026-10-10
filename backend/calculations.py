"""Domain-specific physiological mathematics and statistical trendline calculations."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from backend.models import UserBase


def calculate_tdee(user: UserBase, activity_multiplier: float = 1.55) -> float:
    """Calculates Total Daily Energy Expenditure using validated metabolic formulas.
    
    If body fat percentage is provided, uses the Katch-McArdle Formula (more accurate
    for individuals with known body composition). Otherwise, defaults to the
    Mifflin-St Jeor Equation.
    """
    if activity_multiplier <= 0:
        raise ValueError("activity_multiplier must be strictly positive.")

    if user.body_fat_pct is not None and user.body_fat_pct > 0:
        # Katch-McArdle Formula
        lean_body_mass = user.weight_kg * (1.0 - (user.body_fat_pct / 100.0))
        bmr = 370.0 + (21.6 * lean_body_mass)
    else:
        # Mifflin-St Jeor Equation
        base = (10.0 * user.weight_kg) + (6.25 * user.height_cm) - (5.0 * user.age)
        bmr = base + 5.0 if user.gender.strip().lower() == "male" else base - 161.0

    return round(bmr * activity_multiplier, 2)


def calculate_composite_1rm(weight: float, reps: int) -> float:
    """Calculates estimated 1RM using an average of the Epley and Brzycki equations.
    
    For a single repetition (reps == 1), returns the exact weight lifted.
    Raises ValueError for invalid inputs (weight <= 0 or reps < 1 or reps >= 37 where Brzycki denominator <= 0).
    """
    if weight <= 0:
        raise ValueError("weight lifted must be strictly greater than 0.")
    if reps < 1:
        raise ValueError("repetitions must be at least 1.")
    if reps >= 37:
        raise ValueError("repetitions >= 37 exceed submaximal 1RM estimation validity.")

    if reps == 1:
        return float(weight)

    epley = weight * (1.0 + (reps / 30.0))
    brzycki = weight / (1.0278 - (0.0278 * reps))
    composite = (epley + brzycki) / 2.0

    return round(composite, 2)


def calculate_trendline(
    points: Sequence[Tuple[datetime, float]],
) -> Dict[str, float]:
    """Calculates least-squares linear regression over chronological (datetime, 1RM) points.
    
    Returns:
        dict containing:
            - current_1rm: latest observed 1RM
            - slope_kg_per_week: estimated rate of strength progression per week
            - forecast_4_weeks_1rm: forecasted 1RM in 4 weeks
    """
    if not points:
        return {
            "current_1rm": 0.0,
            "slope_kg_per_week": 0.0,
            "forecast_4_weeks_1rm": 0.0,
        }

    # Sort chronologically
    sorted_points = sorted(points, key=lambda p: p[0])
    current_1rm = sorted_points[-1][1]

    if len(sorted_points) == 1:
        return {
            "current_1rm": round(current_1rm, 2),
            "slope_kg_per_week": 0.0,
            "forecast_4_weeks_1rm": round(current_1rm, 2),
        }

    t0 = sorted_points[0][0].timestamp()
    # Convert seconds to weeks
    seconds_in_week = 7.0 * 24.0 * 3600.0

    x_vals = [(p[0].timestamp() - t0) / seconds_in_week for p in sorted_points]
    y_vals = [p[1] for p in sorted_points]

    n = len(x_vals)
    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xx = sum(x * x for x in x_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))

    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) < 1e-9:
        slope = 0.0
    else:
        slope = ((n * sum_xy) - (sum_x * sum_y)) / denom

    # Slope is kg / week
    slope_kg_per_week = round(slope, 3)
    forecast_4_weeks = round(max(0.0, current_1rm + (slope_kg_per_week * 4.0)), 2)

    return {
        "current_1rm": round(current_1rm, 2),
        "slope_kg_per_week": slope_kg_per_week,
        "forecast_4_weeks_1rm": forecast_4_weeks,
    }


def calculate_diet_macronutrients(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str = "male",
    body_fat_pct: Optional[float] = None,
    activity_multiplier: float = 1.55,
    goal: str = "maintenance",
) -> Dict[str, Any]:
    """Calculates ideal caloric and macronutrient targets based on metabolic expenditure and body composition."""
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("Weight, height, and age must be strictly positive.")

    # Calculate BMR
    if body_fat_pct is not None and body_fat_pct > 0:
        lean_mass = weight_kg * (1.0 - (body_fat_pct / 100.0))
        bmr = 370.0 + (21.6 * lean_mass)
    else:
        base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
        bmr = base + 5.0 if gender.strip().lower() == "male" else base - 161.0

    tdee = bmr * activity_multiplier

    goal_clean = goal.strip().lower()
    if any(k in goal_clean for k in ("cut", "deficit", "fat loss", "weight loss")):
        target_calories = max(1200, int(round(tdee - 400)))
        goal_label = "Fat Loss / Caloric Deficit (-400 kcal)"
    elif any(k in goal_clean for k in ("bulk", "surplus", "hypertrophy", "gain")):
        target_calories = int(round(tdee + 300))
        goal_label = "Muscle Gain / Caloric Surplus (+300 kcal)"
    else:
        target_calories = int(round(tdee))
        goal_label = "Maintenance & Recomposition (0 kcal)"

    # Protein intake: 2.0g - 2.2g per kg (4 kcal/g)
    if body_fat_pct is not None and body_fat_pct > 0:
        lean_mass = weight_kg * (1.0 - (body_fat_pct / 100.0))
        protein_g = max(60, int(round(lean_mass * 2.2)))
    else:
        protein_g = max(60, int(round(weight_kg * 2.0)))

    # Fat intake: 25% of total caloric expenditure (9 kcal/g)
    fat_calories = target_calories * 0.25
    fat_g = max(35, int(round(fat_calories / 9.0)))

    # Carbohydrates: Remaining caloric budget (4 kcal/g)
    carb_calories = max(0, target_calories - (protein_g * 4) - (fat_g * 9))
    carbs_g = max(30, int(round(carb_calories / 4.0)))

    # Re-normalize total calories
    actual_calories = (protein_g * 4) + (fat_g * 9) + (carbs_g * 4)

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "target_calories": actual_calories,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "goal_label": goal_label,
    }


def generate_recipes_by_meal_style(
    target_calories: int,
    target_protein_g: int,
    target_fat_g: int,
    target_carbs_g: int,
    meal_style: str = "3_meals",
    include_snacks: bool = True,
    include_drinks: bool = True,
) -> Dict[str, Any]:
    """Generates structured meal breakdowns, recipes, snacks, and drink recommendations."""
    style = meal_style.strip().lower()

    if "1" in style or "omad" in style:
        style_key = "1_meal"
        style_title = "One Meal A Day (OMAD) Power Protocol"
        meal_distributions = [
            ("The Anabolic OMAD Feast", 0.75, "Primary Feasting Window (Within 2-4 Hours)"),
        ]
        snack_pct = 0.20 if include_snacks else 0.0
        drinks_pct = 0.05 if include_drinks else 0.0
    elif "2" in style or "fasting" in style:
        style_key = "2_meals"
        style_title = "Intermittent Fasting (16:8) Two-Meal Protocol"
        meal_distributions = [
            ("Meal 1: Break-Fast Power Plate", 0.45, "12:00 PM - 1:00 PM Break-Fast Window"),
            ("Meal 2: Satiating Recovery Dinner", 0.40, "7:00 PM - 8:00 PM Evening Anchor"),
        ]
        snack_pct = 0.12 if include_snacks else 0.0
        drinks_pct = 0.03 if include_drinks else 0.0
    else:
        style_key = "3_meals"
        style_title = "Classic 3-Meal Athletic Blueprint"
        meal_distributions = [
            ("Meal 1: High-Protein Muscle Ignition Breakfast", 0.30, "7:00 AM - 8:30 AM Morning Metabolic Primer"),
            ("Meal 2: High-Energy Midday Fuel", 0.35, "12:30 PM - 1:30 PM Glycogen & Focus Sustainer"),
            ("Meal 3: Anabolic Recovery Dinner", 0.25, "6:30 PM - 8:00 PM Nightly Tissue Repair"),
        ]
        snack_pct = 0.10 if include_snacks else 0.0
        drinks_pct = 0.0 if include_drinks else 0.0

    # Build primary meals
    recipes_db = {
        "omad": {
            "title": "Prime Ribeye, Crispy Yukon Potatoes & Pasture Eggs Giant Bowl",
            "ingredients": [
                "350g Grass-fed Ribeye or Sirloin Steak",
                "4 Whole Pasture-Raised Eggs",
                "400g Roasted Yukon Gold Potatoes with rosemary & olive oil",
                "2 Cups Sautéed Baby Spinach & Asparagus with garlic",
                "1 Whole Avocado sliced",
                "100g Wild Blueberries for dessert antioxidant support",
            ],
            "instructions": (
                "1. Sear steak in a cast-iron skillet with sea salt to desired doneness. "
                "2. Sauté potatoes in olive oil until golden. "
                "3. Fry eggs sunny side up. Combine with avocado and warm vegetables."
            ),
        },
        "breakfast": {
            "title": "Anabolic Scramble & Slow-Rolled Oats Parfait",
            "ingredients": [
                "4 Whole Organic Eggs + 2 Egg Whites",
                "80g Rolled Oats with 1 scoop Whey Protein & cinnamon",
                "150g Fresh Berries (Blueberries & Strawberries)",
                "15g Chia Seeds & raw crushed walnuts",
            ],
            "instructions": (
                "1. Scramble eggs lightly in butter with Himalayan salt. "
                "2. Cook rolled oats in water or almond milk, stir in whey protein and berries."
            ),
        },
        "lunch": {
            "title": "Wild-Caught Salmon, Steamed Jasmine Rice & Avocado Bowl",
            "ingredients": [
                "220g Wild-Caught Salmon Fillet",
                "200g Steamed Jasmine Rice or Tri-Color Quinoa",
                "150g Steamed Broccoli with lemon zest & olive oil",
                "Half Sliced Hass Avocado with toasted sesame seeds",
            ],
            "instructions": (
                "1. Pan-sear salmon skin-side down for 5 mins, flip and baste with lemon. "
                "2. Plate over warm jasmine rice with steamed greens and avocado slices."
            ),
        },
        "dinner": {
            "title": "Grass-Fed Lean Beef & Roasted Sweet Potato Power Bowl",
            "ingredients": [
                "250g 90/10 Lean Ground Beef or Bison",
                "250g Roasted Sweet Potato Cubes with paprika",
                "150g Grilled Zucchini & Bell Peppers",
                "2 Tbsp Extra Virgin Olive Oil & fresh chimichurri",
            ],
            "instructions": (
                "1. Brown lean beef with cumin, sea salt, and garlic. "
                "2. Roast sweet potatoes at 200°C for 25 minutes. "
                "3. Assemble with grilled vegetables and top with chimichurri sauce."
            ),
        },
        "break_fast": {
            "title": "Seared Turkey Tenderloin, Herb Roasted Sweet Potatoes & Greens",
            "ingredients": [
                "240g Lean Turkey Breast or Chicken Tenderloin",
                "250g Roasted Sweet Potatoes with olive oil",
                "2 Cups Mixed Wild Greens with olive oil and apple cider vinaigrette",
                "30g Pumpkin seeds and walnuts",
            ],
            "instructions": (
                "1. Season turkey with thyme and garlic; sear in olive oil until juicy. "
                "2. Toss roasted sweet potatoes and tender greens together with light vinaigrette."
            ),
        },
    }

    meals_output = []
    for idx, (meal_label, pct, timing_desc) in enumerate(meal_distributions):
        m_cals = int(round(target_calories * pct))
        m_prot = int(round(target_protein_g * pct))
        m_fat = int(round(target_fat_g * pct))
        m_carb = int(round(target_carbs_g * pct))

        if style_key == "1_meal":
            recipe = recipes_db["omad"]
        elif style_key == "2_meals":
            recipe = recipes_db["break_fast"] if idx == 0 else recipes_db["dinner"]
        else:
            recipe = recipes_db["breakfast"] if idx == 0 else (recipes_db["lunch"] if idx == 1 else recipes_db["dinner"])

        meals_output.append({
            "meal_order": idx + 1,
            "meal_name": meal_label,
            "timing_window": timing_desc,
            "recipe_title": recipe["title"],
            "calories": m_cals,
            "protein_g": m_prot,
            "fat_g": m_fat,
            "carbs_g": m_carb,
            "ingredients": recipe["ingredients"],
            "instructions": recipe["instructions"],
        })

    # Snacks
    snacks_output = []
    if include_snacks and snack_pct > 0:
        s_cals = int(round(target_calories * snack_pct))
        s_prot = int(round(target_protein_g * snack_pct))
        s_fat = int(round(target_fat_g * snack_pct))
        s_carb = int(round(target_carbs_g * snack_pct))
        snacks_output.append({
            "name": "Triple-Berry Greek Yogurt Crunch Bowl",
            "timing": "Mid-Afternoon or Pre-Workout (2 hours prior)",
            "calories": s_cals,
            "protein_g": s_prot,
            "fat_g": s_fat,
            "carbs_g": s_carb,
            "ingredients": [
                "250g Plain 0% Greek Yogurt or Skyr",
                "1 Scoop Whey Isolate (Vanilla or Chocolate)",
                "40g Raw Almonds or Natural Peanut Butter",
                "80g Blueberries & Pomegranate Seeds",
            ],
            "instructions": "Whisk whey into Greek yogurt until thick pudding texture; top with raw nuts and fresh berries.",
        })

    # Functional Drinks
    drinks_output = []
    if include_drinks:
        drinks_output.append({
            "name": "Cellular Hydration & Electrolyte Elixir",
            "timing": "Upon Waking & Intra-Workout",
            "calories": 15,
            "protein_g": 0,
            "fat_g": 0,
            "carbs_g": 4,
            "ingredients": [
                "750ml Filtered Water",
                "1/4 Tsp Himalayan Pink Salt (Sodium)",
                "200mg Potassium Citrate",
                "1 Whole Squeezed Lemon or Lime",
            ],
            "instructions": "Mix into cold water with ice; sip first thing in the morning to restore cellular osmotic pressure.",
        })
        drinks_output.append({
            "name": "Matcha & L-Theanine Focus Surge",
            "timing": "Morning Fasted or 45 Minutes Pre-Workout",
            "calories": 25,
            "protein_g": 1,
            "fat_g": 0,
            "carbs_g": 3,
            "ingredients": [
                "3g Ceremonial Grade Uji Matcha",
                "250ml Warm Water (80°C)",
                "100ml Unsweetened Almond Milk",
                "Optional: 1 Tsp Raw Honey",
            ],
            "instructions": "Whisk matcha in 80°C water until frothy; blend with almond milk for smooth, jitters-free cognitive focus.",
        })

    return {
        "style_key": style_key,
        "style_title": style_title,
        "target_summary": {
            "calories": target_calories,
            "protein_g": target_protein_g,
            "fat_g": target_fat_g,
            "carbs_g": target_carbs_g,
        },
        "meals": meals_output,
        "snacks": snacks_output,
        "drinks": drinks_output,
    }
