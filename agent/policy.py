from datetime import datetime

from agent.config import SIMULATED_NOW

LOYALTY_BONUS_TIERS = {"gold", "platinum"}


def hours_until_departure(departure_time: str, now: datetime = SIMULATED_NOW) -> float:
    dep = datetime.fromisoformat(departure_time)
    return (dep - now).total_seconds() / 3600


def calculate_refund(departure_time: str, loyalty_tier: str, payment_amount: float) -> dict:
    """
    Returns {percentage, amount, policy_applied, reason} based on
    hours-until-departure tiers, with a +10% loyalty bonus for
    gold/platinum, capped at 100%.
    """
    hours = hours_until_departure(departure_time)

    if hours >= 48:
        base_pct, rule = 100, "48hr_rule"
    elif hours >= 24:
        base_pct, rule = 75, "24hr_rule"
    elif hours >= 12:
        base_pct, rule = 50, "12hr_rule"
    else:
        base_pct, rule = 0, "under_12hr_rule"

    bonus_eligible = loyalty_tier in LOYALTY_BONUS_TIERS and base_pct > 0
    final_pct = min(base_pct + (10 if bonus_eligible else 0), 100)
    bonus_applied = bonus_eligible and final_pct > base_pct

    return {
        "percentage": final_pct,
        "amount": round(payment_amount * final_pct / 100, 2),
        "policy_applied": f"refund_policy::{rule}",
        "hours_until_departure": round(hours, 1),
        "reason": (
            f"{'Full' if final_pct == 100 else f'{final_pct}%'} refund: "
            f"{round(hours, 1)}h until departure"
            f"{' (+10% loyalty bonus)' if bonus_applied else ''}"
        ),
    }


def next_booking_ref(existing_count: int, booking_date: str) -> str:
    """Format: BK-YYYYMMDD-XXX, sequential per day-of-run."""
    date_part = booking_date.replace("-", "")
    return f"BK-{date_part}-{existing_count + 1:03d}"