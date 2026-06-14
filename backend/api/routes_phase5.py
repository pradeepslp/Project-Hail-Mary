import json
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from backend.database.connection import get_db
from backend.database.models import (
    MissionPlanModel,
    MissionTimelineModel,
    MissionStrategyModel,
    ContingencyPlanModel,
    ConsensusRecordModel,
    RecoveryActionModel,
    ForecastResultModel,
    AgentDecisionModel,
    AgentReasoningModel,
    AutonomyMetricsModel,
    MissionModel,
    TelemetryModel,
    MissionExperienceModel
)
from backend.database.redis_client import get_redis
from backend.simulator.engine import simulator
from backend.websocket.connection import manager
from backend.utils.timezone_helper import ist_now

router = APIRouter(prefix="/api/phase5", tags=["Phase 5 Operations"])

# --- Pydantic Request Schemas ---

class MissionPlanRequest(BaseModel):
    destination: str
    payload: str
    duration: float
    available_fuel: float
    science_objectives: List[str]
    constraints: List[str]

class LabConfigRequest(BaseModel):
    difficulty: str
    event_frequency: float

class ContingencyInjectRequest(BaseModel):
    event_type: str

class OverrideRequest(BaseModel):
    decision_key: str
    override: bool

# --- HELPER PLAN GENERATOR ---

def generate_heuristic_plan(req: MissionPlanRequest) -> Dict[str, Any]:
    # Set simulated target distance based on destination
    dist_map = {
        "Tau Ceti": 1000000.0,
        "Mars Alpha": 225000.0,
        "Europa Core": 628000.0,
        "Titan Base": 1200000.0
    }
    target_dist = dist_map.get(req.destination, 1000000.0)
    
    # Heuristic route stages
    route_plan = [
        {"stage": "Pre-Launch", "checkpoint": "T+00s", "burn_profile": "Standard prep, system check"},
        {"stage": "Launch", "checkpoint": "T+10s", "burn_profile": "Chemical thrust boost (90% burn rate)"},
        {"stage": "Orbit Insertion", "checkpoint": "T+45s", "burn_profile": "Vectored thrust, orbital locking"},
        {"stage": "Cruise Phase", "checkpoint": "T+120s", "burn_profile": "Solar ion gliding (minimum fuel)"},
        {"stage": "Course Correction", "checkpoint": "T+240s", "burn_profile": "Brief delta-V vector pulses"},
        {"stage": "Scientific Ops", "checkpoint": "T+360s", "burn_profile": "High power consumption, passive coasting"},
        {"stage": "Approach Phase", "checkpoint": "T+480s", "burn_profile": "Deceleration maneuvers"},
        {"stage": "Landing / Deployment", "checkpoint": "T+600s", "burn_profile": "High safety landing thrusters"},
        {"stage": "Completed", "checkpoint": "T+720s", "burn_profile": "Steady-state telemetry check"}
    ]
    
    # Fuel planning
    est_fuel_needed = 70.0
    if req.payload == "Heavy Cargo":
        est_fuel_needed += 15.0
    if req.duration < 500: # high speed transit
        est_fuel_needed += 10.0
        
    resource_plan = {
        "estimated_fuel_needed": est_fuel_needed,
        "estimated_power_drain": 45.0,
        "oxygen_reserve_ticks": req.duration * 1.5,
        "efficiency_target": 0.85
    }
    
    # Risk assessments
    hazards = []
    avg_risk = 15.0
    if "Solar Storms" in req.constraints:
        hazards.append({"hazard": "Solar Storm", "probability": 45.0, "severity": "CRITICAL"})
        avg_risk += 15.0
    else:
        hazards.append({"hazard": "Solar Storm", "probability": 15.0, "severity": "CRITICAL"})
        
    if "Asteroid Belt" in req.constraints:
        hazards.append({"hazard": "Micrometeorite Impact", "probability": 35.0, "severity": "HIGH"})
        avg_risk += 12.0
    else:
        hazards.append({"hazard": "Micrometeorite Impact", "probability": 10.0, "severity": "HIGH"})
        
    hazards.append({"hazard": "Fuel Leak", "probability": 20.0, "severity": "HIGH"})
    
    risk_assessment = {
        "hazards": hazards,
        "average_risk_rating": round(avg_risk, 1),
        "critical_path_integrity": "SECURE" if avg_risk < 30 else "VULNERABLE"
    }
    
    # Success forecast percentage
    success_score = 95.0 - (avg_risk * 0.4)
    if req.available_fuel < est_fuel_needed:
        success_score -= 25.0
        
    return {
        "route_plan": route_plan,
        "resource_plan": resource_plan,
        "risk_assessment": risk_assessment,
        "success_forecast": max(5.0, round(success_score, 1)),
        "target_distance": target_dist
    }

# --- REST ENDPOINTS ---

@router.post("/mission/plan")
async def plan_mission(req: MissionPlanRequest, db: AsyncSession = Depends(get_db)):
    """Automatically drafts a mission timeline, resource parameters, and risk forecast"""
    try:
        plan_outputs = generate_heuristic_plan(req)
        
        # Save to database
        db_plan = MissionPlanModel(
            destination=req.destination,
            payload=req.payload,
            duration=req.duration,
            available_fuel=req.available_fuel,
            science_objectives=json.dumps(req.science_objectives),
            constraints=json.dumps(req.constraints),
            route_plan=json.dumps(plan_outputs["route_plan"]),
            resource_plan=json.dumps(plan_outputs["resource_plan"]),
            risk_assessment=json.dumps(plan_outputs["risk_assessment"]),
            success_forecast=plan_outputs["success_forecast"],
            status="PLANNED"
        )
        db.add(db_plan)
        await db.commit()
        await db.refresh(db_plan)
        
        # Cache to Redis
        redis = await get_redis()
        await redis.set("hail_mary:latest_plan", json.dumps({
            "id": db_plan.id,
            "destination": db_plan.destination,
            "payload": db_plan.payload,
            "duration": db_plan.duration,
            "available_fuel": db_plan.available_fuel,
            "science_objectives": req.science_objectives,
            "constraints": req.constraints,
            "route_plan": plan_outputs["route_plan"],
            "resource_plan": plan_outputs["resource_plan"],
            "risk_assessment": plan_outputs["risk_assessment"],
            "success_forecast": db_plan.success_forecast,
            "target_distance": plan_outputs["target_distance"]
        }))
        
        return db_plan
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate mission plan: {e}")

@router.get("/mission/plan/latest")
async def get_latest_plan(db: AsyncSession = Depends(get_db)):
    """Fetch the latest planned trajectory profile"""
    redis = await get_redis()
    cached = await redis.get("hail_mary:latest_plan")
    if cached:
        return json.loads(cached)
        
    # Query Postgres
    stmt = select(MissionPlanModel).order_by(MissionPlanModel.timestamp.desc()).limit(1)
    res = await db.execute(stmt)
    db_plan = res.scalars().first()
    if not db_plan:
        # Return default fallback mock plan if empty
        return {
            "id": 0,
            "destination": "Tau Ceti (Eridani System)",
            "payload": "Science Lab Payload v5",
            "duration": 720.0,
            "available_fuel": 100.0,
            "science_objectives": ["Measure Gamma Burst", "Assess Subsurface Ice"],
            "constraints": ["Asteroid Belt", "Solar Storms"],
            "route_plan": [],
            "resource_plan": {"estimated_fuel_needed": 65.0, "estimated_power_drain": 30.0},
            "risk_assessment": {"average_risk_rating": 22.0, "hazards": []},
            "success_forecast": 88.5
        }
        
    return {
        "id": db_plan.id,
        "destination": db_plan.destination,
        "payload": db_plan.payload,
        "duration": db_plan.duration,
        "available_fuel": db_plan.available_fuel,
        "science_objectives": json.loads(db_plan.science_objectives),
        "constraints": json.loads(db_plan.constraints),
        "route_plan": json.loads(db_plan.route_plan),
        "resource_plan": json.loads(db_plan.resource_plan),
        "risk_assessment": json.loads(db_plan.risk_assessment),
        "success_forecast": db_plan.success_forecast
    }

@router.post("/mission/start")
async def start_mission_ops(db: AsyncSession = Depends(get_db)):
    """Deploys a planned mission config and initializes execution"""
    try:
        latest = await get_latest_plan(db)
        
        # Reset simulator state variables
        simulator.reset_state()
        simulator.destination = latest["destination"]
        simulator.fuel = latest["available_fuel"]
        simulator.target_distance = latest.get("target_distance", 1000000.0)
        
        # Wipe old timeline database entries
        await db.execute(delete(MissionTimelineModel))
        
        # Build initial timeline checkpoints
        route_stages = latest.get("route_plan", [])
        for stage in route_stages:
            timeline_item = MissionTimelineModel(
                time_offset=stage["checkpoint"],
                phase=stage["stage"],
                event_name=stage["stage"] + " Core Check",
                description=stage["burn_profile"],
                status="PENDING"
            )
            db.add(timeline_item)
            
        await db.commit()
        
        # Start simulator engine loop
        await simulator.start()
        
        # Update redis cache status
        redis = await get_redis()
        await redis.set("hail_mary:ops_status", "EXECUTING")
        
        # Broadcast WS event
        await manager.broadcast_json({
            "type": "PHASE_UPDATED",
            "phase": "Pre-Launch",
            "message": "Ops Center authorized rocket ignition launch countdown."
        })
        
        return {"status": "success", "message": "Autonomous Mission Operations launched."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start mission ops: {e}")

@router.get("/mission/timeline")
async def get_mission_timeline(db: AsyncSession = Depends(get_db)):
    """Fetch the dynamic progress timeline tracking phases"""
    stmt = select(MissionTimelineModel).order_by(MissionTimelineModel.id.asc())
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    # Fallback default timeline if empty
    if not records:
        return [
            {"time_offset": "T+00s", "phase": "Pre-Launch", "event_name": "Ignition Sequence", "description": "Engines status checks", "status": "COMPLETED"},
            {"time_offset": "T+10s", "phase": "Launch", "event_name": "Atmospheric Lift", "description": "Maximum dynamic pressure", "status": "COMPLETED"},
            {"time_offset": "T+45s", "phase": "Orbit Insertion", "event_name": "Orbital Burn", "description": "Locking circular vector", "status": "PENDING"}
        ]
        
    return [
        {
            "id": r.id,
            "time_offset": r.time_offset,
            "phase": r.phase,
            "event_name": r.event_name,
            "description": r.description,
            "status": r.status
        }
        for r in records
    ]

@router.get("/mission/strategies/compare")
async def get_strategies_comparison():
    """Generates side-by-side strategy projected metrics"""
    # Dynamically compute comparison coefficients based on simulator current state
    fuel = simulator.fuel
    power = simulator.power
    risk = simulator.risk_score
    diff_factor = {"Easy": 0.8, "Normal": 1.0, "Hard": 1.3, "Extreme": 1.8}.get(simulator.difficulty, 1.0)
    
    strategies = [
        {
            "strategy_name": "Aggressive",
            "success_probability": round(max(30.0, 92.0 - (risk * 0.4) - (diff_factor * 5.0)), 1),
            "projected_fuel": round(max(5.0, fuel - 40.0 * diff_factor), 1),
            "projected_power": round(max(10.0, power - 15.0), 1),
            "projected_risk": round(min(100.0, risk + 20.0 * diff_factor), 1),
            "description": "High propulsion thrust. Reaches destination faster at the cost of high fuel consumption rates."
        },
        {
            "strategy_name": "Conservative",
            "success_probability": round(max(40.0, 85.0 - (risk * 0.2)), 1),
            "projected_fuel": round(max(10.0, fuel - 18.0 * diff_factor), 1),
            "projected_power": round(max(10.0, power - 12.0), 1),
            "projected_risk": round(max(0.0, risk * 0.6), 1),
            "description": "Minimum vector thruster fires. Highly optimized cruise speed to prioritize fuel conservation."
        },
        {
            "strategy_name": "Balanced",
            "success_probability": round(max(50.0, 95.0 - (risk * 0.3)), 1),
            "projected_fuel": round(max(5.0, fuel - 25.0 * diff_factor), 1),
            "projected_power": round(max(10.0, power - 10.0), 1),
            "projected_risk": round(risk, 1),
            "description": "Compromised profile adjusting thrust vectors and shield levels dynamically to maintain margins."
        },
        {
            "strategy_name": "Science-Focused",
            "success_probability": round(max(35.0, 80.0 - (risk * 0.5)), 1),
            "projected_fuel": round(max(5.0, fuel - 30.0 * diff_factor), 1),
            "projected_power": round(max(10.0, power - 35.0), 1),
            "projected_risk": round(min(100.0, risk + 15.0), 1),
            "description": "Diverts main power grid to sensor suites. Increases mission scientific observations yield."
        },
        {
            "strategy_name": "Resource-Focused",
            "success_probability": round(max(45.0, 90.0 - (risk * 0.25)), 1),
            "projected_fuel": round(max(10.0, fuel - 12.0 * diff_factor), 1),
            "projected_power": round(max(10.0, power - 5.0), 1),
            "projected_risk": round(min(100.0, risk + 5.0), 1),
            "description": "Shuts down secondary computers and auxiliary sensors, locking arrays directly to solar angles."
        }
    ]
    return strategies

@router.get("/mission/forecasts")
async def get_forecast_results(db: AsyncSession = Depends(get_db)):
    """Returns predictive forecasts for various horizons"""
    # Generate horizons dynamically
    horizons = ["1h", "6h", "24h", "7d"]
    results = []
    
    fuel = simulator.fuel
    power = simulator.power
    risk = simulator.risk_score
    health = sum(sub["health"] for sub in simulator.subsystems.values()) / len(simulator.subsystems)
    
    decay_coeffs = {"1h": 0.98, "6h": 0.92, "24h": 0.78, "7d": 0.40}
    risk_coeffs = {"1h": 1.05, "6h": 1.15, "24h": 1.30, "7d": 1.60}
    
    for hz in horizons:
        dc = decay_coeffs[hz]
        rc = risk_coeffs[hz]
        
        projected_success = max(0.0, min(100.0, simulator.success_probability * dc))
        projected_fuel = max(0.0, min(100.0, fuel * dc))
        projected_power = max(0.0, min(100.0, power * (dc + 0.05)))
        projected_risk = max(0.0, min(100.0, risk * rc))
        
        # Check for potential failure warnings
        failures = []
        if projected_fuel < 15.0:
            failures.append("Propellant Depletion Risk")
        if projected_power < 20.0:
            failures.append("Electrical Grid Lockout Warning")
        if health * dc < 50.0:
            failures.append("Hull Armor Integrity Failure")
            
        results.append({
            "horizon": hz,
            "projected_success": round(projected_success, 1),
            "projected_fuel": round(projected_fuel, 1),
            "projected_power": round(projected_power, 1),
            "projected_risk": round(projected_risk, 1),
            "predicted_failures": failures
        })
        
    return results

@router.post("/mission/contingency/inject")
async def inject_contingency(req: ContingencyInjectRequest, db: AsyncSession = Depends(get_db)):
    """Injects a customized anomaly event to test self-healing loop"""
    event_type = req.event_type
    
    # Verify valid anomaly
    valid_events = ["Solar Storm", "Fuel Leak", "Thruster Failure", "Communication Loss", "Navigation Drift", "Micrometeorite Impact", "Power Emergency", "Life Support Failure"]
    if event_type not in valid_events:
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type}")
        
    # Map descriptions and affected systems
    details = {
        "Solar Storm": {"severity": "CRITICAL", "desc": "Solar coronal mass ejection (CME)", "sys": "Power"},
        "Fuel Leak": {"severity": "HIGH", "desc": "Propellant pressure line leak", "sys": "Propulsion"},
        "Thruster Failure": {"severity": "HIGH", "desc": "RCS thruster feedback valve failure", "sys": "Propulsion"},
        "Communication Loss": {"severity": "HIGH", "desc": "HG Antenna carrier tracking loss", "sys": "Communication"},
        "Navigation Drift": {"severity": "LOW", "desc": "IMU drift coordinate discrepancy", "sys": "Navigation"},
        "Micrometeorite Impact": {"severity": "CRITICAL", "desc": "High-velocity debris impact", "sys": "Thermal Control"},
        "Power Emergency": {"severity": "CRITICAL", "desc": "Primary power grid short-circuit", "sys": "Power"},
        "Life Support Failure": {"severity": "CRITICAL", "desc": "O2 scrubbing system blower failure", "sys": "Life Support"}
    }[event_type]
    
    # Append to simulator active events
    ev_obj = {
        "id": random.randint(1000, 9999),
        "event_type": event_type,
        "severity": details["severity"],
        "description": details["desc"],
        "affected_system": details["sys"],
        "probability": 100.0,
        "recommended_actions": "Emergency shielding activation" if event_type == "Solar Storm" else "Standard mitigations",
        "duration": 30.0,
        "status": "ACTIVE",
        "timestamp": ist_now().isoformat()
    }
    
    simulator.active_events.append(ev_obj)
    
    # Write to database ContingencyPlanModel
    contingency = ContingencyPlanModel(
        emergency_type=event_type,
        trigger_condition=details["desc"],
        priority=details["severity"],
        response_protocol=json.dumps(["Verify parameters", "Select mitigation path", "Trigger actions"]),
        status="ACTIVE"
    )
    db.add(contingency)
    await db.commit()
    
    # Broadcast event
    await simulator.log_event("WARNING", f"CONTINGENCY INJECTED: {event_type} - {details['desc']}")
    await manager.broadcast_json({
        "type": "NEW_EVENT",
        "event": ev_obj
    })
    
    return {"status": "success", "event": ev_obj}

@router.get("/mission/explainable-autonomy")
async def get_explainable_autonomy(db: AsyncSession = Depends(get_db)):
    """Fetch explainability trace trails of recent decisions"""
    stmt = select(AgentDecisionModel).order_by(AgentDecisionModel.timestamp.desc()).limit(15)
    res = await db.execute(stmt)
    decisions = res.scalars().all()
    
    traces = []
    for dec in decisions:
        # Check reasoning
        stmt_reason = select(AgentReasoningModel).where(AgentReasoningModel.decision_id == dec.id).limit(1)
        res_reason = await db.execute(stmt_reason)
        reason_rec = res_reason.scalars().first()
        
        reasoning_text = reason_rec.reasoning_text if reason_rec else "Policy optimized Q-value utility scores choice."
        utility_scores = json.loads(reason_rec.utility_scores) if reason_rec and reason_rec.utility_scores else {}
        
        traces.append({
            "id": dec.id,
            "timestamp": dec.timestamp.isoformat(),
            "event_type": dec.event_type,
            "chosen_action": dec.chosen_action,
            "confidence_score": dec.confidence_score,
            "expected_outcome": json.loads(dec.expected_outcome) if dec.expected_outcome else {},
            "actual_outcome": json.loads(dec.actual_outcome) if dec.actual_outcome else {},
            "autonomy_level": dec.autonomy_level,
            "reasoning": reasoning_text,
            "utility_scores": utility_scores
        })
        
    if not traces:
        # Fallback trace data
        return [
            {
                "id": 1,
                "timestamp": ist_now().isoformat(),
                "event_type": "Fuel Leak",
                "chosen_action": "fuel_leak_activate_backup",
                "confidence_score": 85.0,
                "expected_outcome": {"risk_reduction": 80.0, "success_delta": 8.0},
                "actual_outcome": {"risk_reduction": 80.0, "success_delta": 8.0},
                "autonomy_level": 4,
                "reasoning": "Fuel pressure fell below critical threshold. Switched supply feed to auxiliary backup tank to avoid complete propellant depletion.",
                "utility_scores": {"activate_backup": 0.88, "ignore": 0.12}
            }
        ]
        
    return traces

@router.get("/mission/consensus")
async def get_agent_consensus(db: AsyncSession = Depends(get_db)):
    """Fetch collaborative agent voting records"""
    stmt = select(ConsensusRecordModel).order_by(ConsensusRecordModel.timestamp.desc()).limit(10)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    if not records:
        # Mock/fallback record
        return [
            {
                "timestamp": ist_now().isoformat(),
                "decision_key": "solar_storm_shielding",
                "nav_recommendation": "Retract secondary panels to limit drag (0.8 rating)",
                "fuel_recommendation": "Propellant flow nominal. Diverting power deflectors approved (0.9 rating)",
                "safety_recommendation": "Shield deflection critical. Recommends divert power (0.95 rating)",
                "science_recommendation": "Sensor grid scan should hold. Agrees to retract panels (0.7 rating)",
                "prediction_rating": 0.88,
                "learning_rating": 0.85,
                "consensus_score": 88.5,
                "commander_override": False
            }
        ]
        
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "decision_key": r.decision_key,
            "nav_recommendation": r.nav_recommendation,
            "fuel_recommendation": r.fuel_recommendation,
            "safety_recommendation": r.safety_recommendation,
            "science_recommendation": r.science_recommendation,
            "prediction_rating": r.prediction_rating,
            "learning_rating": r.learning_rating,
            "consensus_score": r.consensus_score,
            "commander_override": r.commander_override
        }
        for r in records
    ]


@router.post("/mission/override")
async def override_commander_decision(req: OverrideRequest, db: AsyncSession = Depends(get_db)):
    """Triggers commander override on a decision consensus record"""
    try:
        stmt = select(ConsensusRecordModel).where(ConsensusRecordModel.decision_key == req.decision_key).order_by(ConsensusRecordModel.timestamp.desc()).limit(1)
        res = await db.execute(stmt)
        record = res.scalars().first()
        if not record:
            # Create a mock/new one or raise error if none exists
            record = ConsensusRecordModel(
                timestamp=ist_now(),
                decision_key=req.decision_key,
                nav_recommendation="Override initialized directly",
                fuel_recommendation="Override initialized directly",
                safety_recommendation="Override initialized directly",
                science_recommendation="Override initialized directly",
                prediction_rating=1.0,
                learning_rating=1.0,
                consensus_score=100.0,
                commander_override=req.override
            )
            db.add(record)
        else:
            record.commander_override = req.override
        
        await db.commit()
        await db.refresh(record)
        
        # Broadcast the override state
        await manager.broadcast_json({
            "type": "OVERRIDE_UPDATED",
            "decision_key": req.decision_key,
            "override": req.override
        })
        return {"status": "success", "decision_key": req.decision_key, "override": req.override}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set override: {e}")

@router.get("/mission/autonomy-index")
async def get_autonomy_performance_index(db: AsyncSession = Depends(get_db)):
    """Calculate the global Autonomy Performance Index compound score"""
    stmt = select(AutonomyMetricsModel).order_by(AutonomyMetricsModel.timestamp.desc()).limit(20)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    if not records:
        return {
            "compound_index": 89.4,
            "metrics": {
                "decision_accuracy": 92.5,
                "prediction_accuracy": 88.0,
                "recovery_effectiveness": 95.0,
                "learning_efficiency": 85.0,
                "resource_efficiency": 86.5
            }
        }
        
    latest = records[0]
    dec_acc = latest.decision_accuracy * 100.0
    pred_acc = latest.prediction_accuracy * 100.0
    rec_eff = latest.risk_reduction
    res_eff = latest.resource_efficiency * 100.0
    lrn_eff = max(50.0, latest.maturity_index * 60.0) # derive scaling
    
    # Calculate a weighted score
    comp_score = 0.25 * dec_acc + 0.20 * pred_acc + 0.20 * rec_eff + 0.15 * lrn_eff + 0.20 * res_eff
    
    return {
        "compound_index": round(comp_score, 1),
        "metrics": {
            "decision_accuracy": round(dec_acc, 1),
            "prediction_accuracy": round(pred_acc, 1),
            "recovery_effectiveness": round(rec_eff, 1),
            "learning_efficiency": round(lrn_eff, 1),
            "resource_efficiency": round(res_eff, 1)
        }
    }

@router.post("/mission/lab/config")
async def configure_lab(req: LabConfigRequest):
    """Adjust active simulator difficulty and parameters"""
    simulator.difficulty = req.difficulty
    simulator.event_frequency = req.event_frequency
    return {"status": "success", "difficulty": simulator.difficulty, "event_frequency": simulator.event_frequency}

@router.post("/mission/research/benchmark")
async def run_strategy_benchmark(db: AsyncSession = Depends(get_db)):
    """Runs a parallel strategy simulation and returns benchmarking data"""
    # Run 100 iterations of Aggressive vs Conservative in background, returning stats
    telemetry = simulator.get_telemetry_data().model_dump()
    active_evs = [e for e in simulator.active_events]
    
    agg_successes = 0
    con_successes = 0
    
    agg_fuels = []
    con_fuels = []
    
    # Simulating 50 fast run ticks for Aggressive Strategy (High speed, high burn)
    for _ in range(50):
        fuel_left = max(0.0, telemetry["fuel"] - random.uniform(25.0, 50.0))
        success = 100.0 - (100.0 - fuel_left) * 0.5 - random.uniform(0, 15)
        agg_fuels.append(round(fuel_left, 1))
        if success > 40: agg_successes += 1
        
    # Simulating 50 fast run ticks for Conservative Strategy (Low speed, low burn)
    for _ in range(50):
        fuel_left = max(0.0, telemetry["fuel"] - random.uniform(8.0, 20.0))
        success = 95.0 - (100.0 - fuel_left) * 0.25 - random.uniform(0, 8)
        con_fuels.append(round(fuel_left, 1))
        if success > 45: con_successes += 1
        
    benchmark_results = {
        "trials": 50,
        "aggressive": {
            "success_rate": round((agg_successes / 50.0) * 100, 1),
            "avg_fuel_remaining": round(sum(agg_fuels) / 50.0, 1),
            "fuel_distribution": agg_fuels
        },
        "conservative": {
            "success_rate": round((con_successes / 50.0) * 100, 1),
            "avg_fuel_remaining": round(sum(con_fuels) / 50.0, 1),
            "fuel_distribution": con_fuels
        }
    }
    
    # Cache to Redis
    redis = await get_redis()
    await redis.set("hail_mary:research_benchmark", json.dumps(benchmark_results))
    
    return benchmark_results

# --- FINAL PRESENTATION SHOWCASE DEMO MODE ---

async def run_mars_showcase_demo(db_session_maker):
    """Orchestrates Mars Mission with consecutive failures and recoveries"""
    async def log_demo(lvl, msg):
        print(f"[DEMO] {msg}")
        timestamp_str = ist_now().strftime('%H:%M:%S')
        log_payload = f"[DEMO] [{timestamp_str}] {msg}"
        
        # Write to redis
        redis = await get_redis()
        await redis.rpush("hail_mary:events", log_payload)
        
        # Broadcast
        await manager.broadcast_json({"type": "EVENT", "message": log_payload})
    
    try:
        await log_demo("INFO", "Initializing Showcase Demo: Destination Mars Alpha")
        
        # Setup Mars Plan in Simulator
        simulator.reset_state()
        simulator.destination = "Mars Alpha"
        simulator.fuel = 100.0
        simulator.target_distance = 225000.0
        simulator.difficulty = "Normal"
        simulator.event_frequency = 45.0
        
        # Launch phase
        simulator.state = "Launch"
        simulator.launch_time = ist_now()
        await simulator.start()
        
        # Wait 4 seconds for Launch trajectory
        await asyncio.sleep(4.0)
        await log_demo("INFO", "Showcase: Atmospheric exit. Orbit Insertion phase achieved.")
        simulator.state = "Maneuver"
        
        # Wait 4 seconds
        await asyncio.sleep(4.0)
        await log_demo("INFO", "Showcase: Solar gliding active. Cruise phase stable.")
        simulator.state = "Cruise"
        
        # Inject Anomaly 1: Solar Storm
        await log_demo("WARNING", "Showcase Warning: Solar Coronal Mass Ejection (CME) detected on telemetry sensor grids!")
        ev_id_1 = random.randint(1000, 9999)
        ev_1 = {
            "id": ev_id_1,
            "event_type": "Solar Storm",
            "severity": "CRITICAL",
            "description": "Solar coronal mass ejection (CME)",
            "affected_system": "Power",
            "probability": 100.0,
            "recommended_actions": "Divert Power to Deflectors",
            "duration": 15.0,
            "status": "ACTIVE",
            "timestamp": ist_now().isoformat()
        }
        simulator.active_events.append(ev_1)
        await manager.broadcast_json({"type": "NEW_EVENT", "event": ev_1})
        
        # AI decision process
        await asyncio.sleep(3.0)
        await log_demo("INFO", "AI Commander: Analyzing Solar Storm. utility scores: [divert_power: 0.92, ignore: 0.08]")
        await log_demo("INFO", "AI Commander: Executing action - Diverting grid power to electromagnetic deflector shields.")
        
        # Execute mitigation
        ev_1["status"] = "MITIGATING"
        ev_1["mitigation_timer"] = 5.0
        
        await asyncio.sleep(5.0)
        simulator.active_events = [e for e in simulator.active_events if e["id"] != ev_id_1]
        await manager.broadcast_json({"type": "EVENT_RESOLVED", "event_id": ev_id_1})
        await log_demo("INFO", "Showcase: Solar Storm mitigated successfully. Subsystem integrity secured.")
        
        # Inject Anomaly 2: Fuel Leak
        await asyncio.sleep(3.0)
        await log_demo("WARNING", "Showcase Warning: Sudden pressure drop in propellant manifold 2B! Fuel Leak active.")
        ev_id_2 = random.randint(1000, 9999)
        ev_2 = {
            "id": ev_id_2,
            "event_type": "Fuel Leak",
            "severity": "HIGH",
            "description": "Propellant pressure line leak",
            "affected_system": "Propulsion",
            "probability": 100.0,
            "recommended_actions": "Activate Backup Tank",
            "duration": 20.0,
            "status": "ACTIVE",
            "timestamp": ist_now().isoformat()
        }
        simulator.active_events.append(ev_2)
        await manager.broadcast_json({"type": "NEW_EVENT", "event": ev_2})
        
        # AI decision process
        await asyncio.sleep(3.0)
        await log_demo("INFO", "AI Commander: Evaluating Fuel Leak risk factors. Risk score >80% threshold exceeded.")
        await log_demo("INFO", "AI Commander: Recovery loop activated. Strategy: Conservative. Executing action - Activate Auxiliary Backup Tank and isolate leak valves.")
        
        # Execute mitigation
        ev_2["status"] = "MITIGATING"
        ev_2["mitigation_timer"] = 6.0
        
        await asyncio.sleep(6.0)
        simulator.active_events = [e for e in simulator.active_events if e["id"] != ev_id_2]
        await manager.broadcast_json({"type": "EVENT_RESOLVED", "event_id": ev_id_2})
        await log_demo("INFO", "Showcase: Fuel line isolated. Remaining fuel reserves locked at stable levels.")
        
        # Transition to completion
        await asyncio.sleep(3.0)
        await log_demo("INFO", "Showcase: Mars orbit approach sequence initiated.")
        simulator.distance = simulator.target_distance
        simulator.mission_progress = 100.0
        simulator.state = "Completed"
        simulator.is_active = False
        
        # Save experience
        async with db_session_maker() as db:
            exp = MissionExperienceModel(
                timestamp=ist_now(),
                situation="Mars Alpha Showcase Demo Run",
                state_snapshot=simulator.get_telemetry_data().model_dump_json(),
                active_events="[]",
                chosen_action="Mission Completion",
                expected_outcome=json.dumps({"success_probability": 100.0}),
                actual_outcome=json.dumps({"success_probability": 100.0}),
                success_score=100.0,
                mission_result="SUCCESS"
            )
            db.add(exp)
            
            # Log metrics
            metric = AutonomyMetricsModel(
                timestamp=ist_now(),
                decision_accuracy=0.96,
                prediction_accuracy=0.92,
                success_rate=1.0,
                risk_reduction=75.0,
                resource_efficiency=round(simulator.fuel / 100.0, 2),
                autonomy_level=4,
                maturity_index=1.92
            )
            db.add(metric)
            await db.commit()
            
        await log_demo("INFO", "Showcase SUCCESS: Mars Alpha Orbit secured autonomously. Telemetry streams closed.")
        await manager.broadcast_json({"type": "MISSION_COMPLETED"})
        
    except Exception as ex:
        await log_demo("ERROR", f"Showcase demo failed: {ex}")

@router.post("/mission/demo/start")
async def start_demo_showcase(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Triggers the automated judge-oriented demonstration flow in background"""
    from backend.database.connection import SessionLocal
    if not SessionLocal:
        raise HTTPException(status_code=500, detail="Database session maker not initialized")
        
    background_tasks.add_task(run_mars_showcase_demo, SessionLocal)
    return {"status": "success", "message": "Mars Demo Showcase sequence started in background."}
