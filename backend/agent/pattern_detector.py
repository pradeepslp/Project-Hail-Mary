import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import (
from backend.utils.timezone_helper import ist_now
    MissionExperienceModel, FailurePatternModel, SuccessPatternModel, AgentDecisionModel
)

async def detect_patterns(db: AsyncSession) -> dict:
    """
    Scans PostgreSQL tables for repeating failure chains and highly successful decision plans.
    Caches results to Postgres and returns discovered patterns.
    """
    # 1. Fetch historical data
    experiences_res = await db.execute(select(MissionExperienceModel))
    experiences = experiences_res.scalars().all()
    
    decisions_res = await db.execute(select(AgentDecisionModel))
    decisions = decisions_res.scalars().all()

    # Define default patterns for cold-start visualization
    default_failures = [
        {
            "pattern_name": "Fuel Cascading Propulsion Failure",
            "event_sequence": ["Fuel Leak", "Thruster Failure", "Navigation Drift"],
            "occurrence_count": 5,
            "severity_index": 8.5
        },
        {
            "pattern_name": "CME Solar Power Grid Failure",
            "event_sequence": ["Solar Storm", "Power Fluctuation", "Sensor Malfunction"],
            "occurrence_count": 3,
            "severity_index": 7.2
        },
        {
            "pattern_name": "Storm Induced Communications Blackout",
            "event_sequence": ["Solar Storm", "Communication Loss"],
            "occurrence_count": 4,
            "severity_index": 6.8
        }
    ]

    default_successes = [
        {
            "pattern_name": "Propulsion Redundancy Re-establishment",
            "decision_sequence": ["Activate Backup Tank", "Enable Backup Controller"],
            "efficiency_score": 9.2,
            "success_probability": 95.0
        },
        {
            "pattern_name": "Storm Deflection & Auto-realign",
            "decision_sequence": ["Divert Power to Deflectors", "Initiate Automated Sweeps"],
            "efficiency_score": 8.9,
            "success_probability": 92.0
        },
        {
            "pattern_name": "Drift Correction Protocol",
            "decision_sequence": ["STAR-Field Overlay", "Re-vector gimbal bells"],
            "efficiency_score": 8.6,
            "success_probability": 88.0
        }
    ]

    # Process failure chains from database
    failures_map = {}
    success_map = {}

    for exp in experiences:
        try:
            # Parse events list
            evs = json.loads(exp.active_events) if isinstance(exp.active_events, str) else exp.active_events
            ev_names = [e.get("event_type") for e in evs if isinstance(e, dict) and e.get("event_type")]
        except Exception:
            ev_names = []

        if exp.mission_result == "FAILURE" and len(ev_names) >= 2:
            # Sort to count unique combinations or preserve order if chronological
            seq_key = " -> ".join(ev_names)
            if seq_key not in failures_map:
                failures_map[seq_key] = {
                    "sequence": ev_names,
                    "count": 0,
                    "total_score": 0.0
                }
            failures_map[seq_key]["count"] += 1
            failures_map[seq_key]["total_score"] += exp.success_score
        elif exp.mission_result == "SUCCESS" and exp.chosen_action:
            act = exp.chosen_action
            if act not in success_map:
                success_map[act] = {
                    "count": 0,
                    "total_score": 0.0
                }
            success_map[act]["count"] += 1
            success_map[act]["total_score"] += exp.success_score

    # Convert maps to patterns list
    failure_patterns = []
    for k, v in failures_map.items():
        avg_score = v["total_score"] / v["count"]
        # lower success score means higher severity
        severity = max(1.0, min(10.0, (100.0 - avg_score) / 10.0))
        failure_patterns.append({
            "pattern_name": f"Cascading {k}",
            "event_sequence": v["sequence"],
            "occurrence_count": v["count"],
            "severity_index": round(severity, 1)
        })

    success_patterns = []
    for action_key, v in success_map.items():
        avg_score = v["total_score"] / v["count"]
        success_patterns.append({
            "pattern_name": f"Optimal {action_key} Plan",
            "decision_sequence": [action_key],
            "efficiency_score": round(min(10.0, avg_score / 10.0), 1),
            "success_probability": round(max(50.0, min(100.0, avg_score)), 1)
        })

    # Save and seed failure patterns in DB
    final_failures = []
    db_failures_res = await db.execute(select(FailurePatternModel))
    db_failures = db_failures_res.scalars().all()
    
    if not db_failures and not failure_patterns:
        # Seed defaults
        for f in default_failures:
            rec = FailurePatternModel(
                timestamp=ist_now(),
                pattern_name=f["pattern_name"],
                event_sequence=json.dumps(f["event_sequence"]),
                occurrence_count=f["occurrence_count"],
                severity_index=f["severity_index"]
            )
            db.add(rec)
            final_failures.append(f)
        await db.commit()
    else:
        # Merge or use database values
        for f in db_failures:
            final_failures.append({
                "pattern_name": f.pattern_name,
                "event_sequence": json.loads(f.event_sequence),
                "occurrence_count": f.occurrence_count,
                "severity_index": f.severity_index
            })
        for f in failure_patterns:
            # Check duplicate
            if not any(x["pattern_name"] == f["pattern_name"] for x in final_failures):
                rec = FailurePatternModel(
                    timestamp=ist_now(),
                    pattern_name=f["pattern_name"],
                    event_sequence=json.dumps(f["event_sequence"]),
                    occurrence_count=f["occurrence_count"],
                    severity_index=f["severity_index"]
                )
                db.add(rec)
                final_failures.append(f)
        await db.commit()

    # Save and seed success patterns in DB
    final_successes = []
    db_successes_res = await db.execute(select(SuccessPatternModel))
    db_successes = db_successes_res.scalars().all()

    if not db_successes and not success_patterns:
        # Seed defaults
        for s in default_successes:
            rec = SuccessPatternModel(
                timestamp=ist_now(),
                pattern_name=s["pattern_name"],
                decision_sequence=json.dumps(s["decision_sequence"]),
                efficiency_score=s["efficiency_score"],
                success_probability=s["success_probability"]
            )
            db.add(rec)
            final_successes.append(s)
        await db.commit()
    else:
        # Merge or use database values
        for s in db_successes:
            final_successes.append({
                "pattern_name": s.pattern_name,
                "decision_sequence": json.loads(s.decision_sequence),
                "efficiency_score": s.efficiency_score,
                "success_probability": s.success_probability
            })
        for s in success_patterns:
            if not any(x["pattern_name"] == s["pattern_name"] for x in final_successes):
                rec = SuccessPatternModel(
                    timestamp=ist_now(),
                    pattern_name=s["pattern_name"],
                    decision_sequence=json.dumps(s["decision_sequence"]),
                    efficiency_score=s["efficiency_score"],
                    success_probability=s["success_probability"]
                )
                db.add(rec)
                final_successes.append(s)
        await db.commit()

    return {
        "failure_patterns": final_failures,
        "success_patterns": final_successes
    }
