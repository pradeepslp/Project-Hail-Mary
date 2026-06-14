import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import MissionExperienceModel, AgentDecisionModel, ActionPredictionModel
from backend.utils.timezone_helper import ist_now

async def save_mission_experience(
    db: AsyncSession,
    situation: str,
    telemetry_snapshot: dict,
    active_events: list,
    chosen_action: str,
    expected_outcome: dict,
    actual_outcome: dict,
    success_score: float,
    result: str
):
    """Saves a completed simulation decision snapshot into experiences log database"""
    exp = MissionExperienceModel(
        timestamp=ist_now(),
        situation=situation,
        state_snapshot=json.dumps(telemetry_snapshot),
        active_events=json.dumps(active_events),
        chosen_action=chosen_action,
        expected_outcome=json.dumps(expected_outcome),
        actual_outcome=json.dumps(actual_outcome),
        success_score=success_score,
        mission_result=result
    )
    db.add(exp)
    await db.commit()
    print(f"[Strategies] Saved experience trace for action '{chosen_action}' (result: {result})")

async def get_strategy_recommendations(db: AsyncSession, event_type: str):
    """Generates strategy rankings for a given threat scenario using blended history & predictions"""
    # 1. Fetch historical decisions for this event type
    stmt = select(AgentDecisionModel).where(AgentDecisionModel.event_type == event_type)
    res = await db.execute(stmt)
    decisions = res.scalars().all()

    # Experience aggregation
    history_counts = {}
    history_successes = {}
    for d in decisions:
        act = d.chosen_action
        history_counts[act] = history_counts.get(act, 0) + 1
        
        # If actual outcome had a positive or stable success probability delta, count as success
        is_success = True
        if d.actual_outcome:
            try:
                out = json.loads(d.actual_outcome) if isinstance(d.actual_outcome, str) else d.actual_outcome
                if out.get("success_delta", 0.0) < -5.0 or out.get("health_delta", 0.0) < -10.0:
                    is_success = False
            except Exception:
                pass
        if is_success:
            history_successes[act] = history_successes.get(act, 0) + 1

    # 2. Fetch baseline predictions
    pred_stmt = select(ActionPredictionModel)
    pred_res = await db.execute(pred_stmt)
    predictions = {p.action_key: p for p in pred_res.scalars().all()}

    # Compile choices for this event
    # Baseline fallback data
    base_success_rates = {
        # Fuel Leak
        "fuel_leak_ignore": 15.0,
        "fuel_leak_reduce_speed": 70.0,
        "fuel_leak_activate_backup": 85.0,
        "fuel_leak_emergency_shutdown": 50.0,
        # Solar Storm
        "solar_storm_ignore": 10.0,
        "solar_storm_retract_panels": 80.0,
        "solar_storm_divert_power": 95.0,
        # Thruster Failure
        "thruster_fail_revector": 75.0,
        "thruster_fail_backup_controller": 90.0,
        # Communication Loss
        "comm_loss_automated_sweep": 85.0,
        "comm_loss_realign_gimbal": 70.0,
        # Navigation Drift
        "nav_drift_star_field": 90.0,
        # Micrometeorite Impact
        "meteor_seal_pressure": 85.0,
        "meteor_run_diagnostic": 70.0
    }

    rankings = []
    # Identify choices from baseline keys matching prefix
    event_prefix = {
        "Fuel Leak": "fuel_leak",
        "Solar Storm": "solar_storm",
        "Thruster Failure": "thruster_fail",
        "Communication Loss": "comm_loss",
        "Navigation Drift": "nav_drift",
        "Micrometeorite Impact": "meteor"
    }.get(event_type, "")

    relevant_actions = [k for k in base_success_rates.keys() if k.startswith(event_prefix)]

    for act in relevant_actions:
        baseline_rate = base_success_rates[act]
        
        # Calculate experience rate if we have > 0 runs
        runs = history_counts.get(act, 0)
        if runs > 0:
            exp_rate = (history_successes.get(act, 0) / runs) * 100.0
            # Blend baseline (40%) and experience (60%)
            blended_rate = round(0.4 * baseline_rate + 0.6 * exp_rate, 1)
        else:
            blended_rate = round(baseline_rate, 1)

        # Get expected delta predictions
        p_data = predictions.get(act)
        deltas = {
            "fuel": p_data.fuel_delta if p_data else 0.0,
            "power": p_data.power_delta if p_data else 0.0,
            "success": p_data.success_delta if p_data else 0.0
        }

        # Format readable action label
        parts = act.split("_")
        label = " ".join(parts[2:]) if len(parts) > 2 else parts[-1]
        label = label.replace("fail", "failure").title()

        rankings.append({
            "action_key": act,
            "action_name": label,
            "success_rate": blended_rate,
            "runs_evaluated": runs,
            "predictions_deltas": deltas
        })

    # Sort descending by success rate
    rankings = sorted(rankings, key=lambda x: x["success_rate"], reverse=True)
    return rankings
