from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
from pydantic import BaseModel

from backend.database.connection import get_db
from backend.database.models import (
    MissionModel, 
    TelemetryModel, 
    EventModel, 
    MissionEventModel, 
    RiskHistoryModel, 
    EventStatisticsModel,
    MissionObjectiveModel,
    EventDependencyModel,
    SubsystemHealthModel,
    ActionOptionModel,
    ActionPredictionModel,
    MissionMemoryModel,
    MissionReplayModel,
    MonteCarloResultModel
)
from backend.simulator.engine import simulator, TelemetryData, MissionInfo

router = APIRouter()

class ConfigUpdate(BaseModel):
    difficulty: Optional[str] = None
    event_frequency: Optional[float] = None

class ActionExecuteRequest(BaseModel):
    event_id: int
    action_key: str

class MonteCarloRequest(BaseModel):
    iterations: Optional[int] = 500

@router.get("/mission", response_model=MissionInfo)
async def get_mission_status():
    return simulator.get_mission_info()

@router.get("/telemetry")
async def get_telemetry_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Fetch historical telemetry points for chart plotting"""
    try:
        stmt = select(TelemetryModel).order_by(TelemetryModel.timestamp.desc()).limit(limit)
        result = await db.execute(stmt)
        history = result.scalars().all()
        
        return [
            {
                "timestamp": h.timestamp.isoformat(),
                "fuel": h.fuel,
                "power": h.power,
                "oxygen": h.oxygen,
                "temperature": h.temperature,
                "health": h.health,
                "velocity": h.velocity,
                "distance": h.distance,
                "mission_progress": h.mission_progress
            }
            for h in reversed(history)
        ]
    except Exception as e:
        print(f"[API ERROR] Failed to fetch telemetry history: {e}")
        return [simulator.get_telemetry_data().model_dump()]

@router.post("/start-mission")
async def start_mission():
    await simulator.start()
    return {"status": "success", "message": "Mission started/resumed", "state": simulator.state}

@router.post("/pause-mission")
async def pause_mission():
    await simulator.pause()
    return {"status": "success", "message": "Mission paused", "state": simulator.state}

@router.post("/reset-mission")
async def reset_mission():
    await simulator.reset()
    return {"status": "success", "message": "Mission reset", "state": simulator.state}

@router.get("/events")
async def get_events(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Fetch general log history prints"""
    try:
        stmt = select(EventModel).order_by(EventModel.timestamp.desc()).limit(limit)
        result = await db.execute(stmt)
        events = result.scalars().all()
        return [
            f"[{e.timestamp.strftime('%H:%M:%S')}] {e.message}"
            for e in reversed(events)
        ]
    except Exception:
        return []

# --- PHASE 2 REST ENDPOINTS ---

@router.get("/events/active")
async def get_active_events():
    """Fetch the list of currently active space anomalies"""
    return [
        {k: v for k, v in ev.items() if k != "duration"}
        for ev in simulator.active_events
    ]

@router.get("/events/history")
async def get_event_history(
    severity: Optional[str] = None,
    system: Optional[str] = None,
    resolved: Optional[bool] = None,
    search: Optional[str] = None,
    sort: str = "desc",
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Query, filter, search and sort the historical events database table"""
    try:
        stmt = select(MissionEventModel)
        
        if severity:
            stmt = stmt.where(MissionEventModel.severity == severity)
        if system:
            stmt = stmt.where(MissionEventModel.affected_system == system)
        if resolved is not None:
            stmt = stmt.where(MissionEventModel.resolved == resolved)
        if search:
            stmt = stmt.where(
                (MissionEventModel.event_type.ilike(f"%{search}%")) |
                (MissionEventModel.description.ilike(f"%{search}%")) |
                (MissionEventModel.recommended_actions.ilike(f"%{search}%"))
            )
            
        if sort == "asc":
            stmt = stmt.order_by(MissionEventModel.timestamp.asc())
        else:
            stmt = stmt.order_by(MissionEventModel.timestamp.desc())
            
        stmt = stmt.limit(limit)
        res = await db.execute(stmt)
        history = res.scalars().all()
        
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat(),
                "description": e.description,
                "affected_system": e.affected_system,
                "probability": e.probability,
                "recommended_actions": e.recommended_actions,
                "resolved": e.resolved,
                "resolution_time": e.resolution_time.isoformat() if e.resolution_time else None
            }
            for e in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/events")
async def get_event_analytics(db: AsyncSession = Depends(get_db)):
    """Assemble aggregation counts and historical trend series for Recharts graphs"""
    try:
        # 1. Severity Distribution
        sev_stmt = select(MissionEventModel.severity, func.count(MissionEventModel.id)).group_by(MissionEventModel.severity)
        sev_res = await db.execute(sev_stmt)
        severity_dist = [{"name": row[0], "value": row[1]} for row in sev_res.all()]
        
        # 2. System Failure Frequency
        sys_stmt = select(MissionEventModel.affected_system, func.count(MissionEventModel.id)).group_by(MissionEventModel.affected_system)
        sys_res = await db.execute(sys_stmt)
        system_freq = [{"system": row[0], "count": row[1]} for row in sys_res.all()]
        
        # 3. Risk Trend (last 30 points)
        risk_stmt = select(RiskHistoryModel).order_by(RiskHistoryModel.timestamp.desc()).limit(30)
        risk_res = await db.execute(risk_stmt)
        risk_history = [
            {"timestamp": r.timestamp.strftime("%H:%M:%S"), "risk": round(r.risk_score, 1)}
            for r in reversed(risk_res.scalars().all())
        ]
        
        # 4. Telemetry Trends (last 30 points)
        tel_stmt = select(TelemetryModel).order_by(TelemetryModel.timestamp.desc()).limit(30)
        tel_res = await db.execute(tel_stmt)
        telemetry_points = [
            {
                "timestamp": t.timestamp.strftime("%H:%M:%S"),
                "fuel": round(t.fuel, 1),
                "power": round(t.power, 1),
                "health": round(t.health, 1)
            }
            for t in reversed(tel_res.scalars().all())
        ]

        # 5. Events per Hour (last 6 hours distribution)
        now = datetime.utcnow()
        hourly_counts = []
        for i in range(5, -1, -1):
            target_hour = now - timedelta(hours=i)
            hour_start = target_hour.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            hr_stmt = select(func.count(MissionEventModel.id)).where(
                MissionEventModel.timestamp >= hour_start,
                MissionEventModel.timestamp < hour_end
            )
            hr_res = await db.execute(hr_stmt)
            count = hr_res.scalar() or 0
            hourly_counts.append({
                "time": hour_start.strftime("%H:00"),
                "count": count
            })
        
        return {
            "severity_distribution": severity_dist,
            "system_frequency": system_freq,
            "risk_trend": risk_history,
            "telemetry_trend": telemetry_points,
            "hourly_frequency": hourly_counts
        }
    except Exception as e:
        print(f"[API ERROR] Failed to fetch analytics: {e}")
        return {
            "severity_distribution": [{"name": "INFO", "value": 0}],
            "system_frequency": [{"system": "None", "count": 0}],
            "risk_trend": [{"timestamp": "00:00", "risk": 0}],
            "telemetry_trend": [{"timestamp": "00:00", "fuel": 100, "power": 100, "health": 100}],
            "hourly_frequency": []
        }

@router.post("/simulation/config")
async def update_simulation_config(update_data: ConfigUpdate):
    """Adjust settings dynamically (Difficulty multipliers and trigger checker rates)"""
    if update_data.difficulty:
        if update_data.difficulty not in ["Easy", "Normal", "Hard", "Extreme"]:
            raise HTTPException(status_code=400, detail="Invalid difficulty level")
        simulator.difficulty = update_data.difficulty
        simulator.next_event_time = simulator.get_randomized_event_time()
        await simulator.log_event("INFO", f"Simulator config: set difficulty to {update_data.difficulty}")
        
    if update_data.event_frequency:
        if update_data.event_frequency <= 0:
            raise HTTPException(status_code=400, detail="Frequency must be positive")
        simulator.event_frequency = update_data.event_frequency
        await simulator.log_event("INFO", f"Simulator config: set event check timer to {update_data.event_frequency}s")
        
    return {
        "status": "success",
        "difficulty": simulator.difficulty,
        "event_frequency": simulator.event_frequency
    }

# --- PHASE 2.5 REST ENDPOINTS ---

@router.get("/mission/objectives")
async def get_mission_objectives(db: AsyncSession = Depends(get_db)):
    """Fetch status checklist of mission success/failure objective conditions"""
    try:
        stmt = select(MissionObjectiveModel)
        res = await db.execute(stmt)
        objectives = res.scalars().all()
        return [
            {
                "id": obj.id,
                "objective_name": obj.objective_name,
                "description": obj.description,
                "success_conditions": json.loads(obj.success_conditions) if isinstance(obj.success_conditions, str) else obj.success_conditions,
                "failure_conditions": json.loads(obj.failure_conditions) if isinstance(obj.failure_conditions, str) else obj.failure_conditions,
                "status": obj.status
            }
            for obj in objectives
        ]
    except Exception as e:
        print(f"[API ERROR] Failed to fetch mission objectives: {e}")
        return []

@router.get("/mission/success")
async def get_mission_success():
    """Fetch real-time compounded Success, Failure, and Confidence metrics"""
    return {
        "success_probability": round(simulator.success_probability, 1),
        "failure_probability": round(simulator.failure_probability, 1),
        "confidence_score": round(simulator.confidence_score, 1)
    }

@router.get("/mission/subsystems")
async def get_mission_subsystems():
    """Fetch diagnostic health details of the 7 onboard subsystems"""
    return simulator.subsystems

@router.get("/events/dependencies")
async def get_event_dependencies(db: AsyncSession = Depends(get_db)):
    """Fetch event propagation dependency links from the database"""
    try:
        stmt = select(EventDependencyModel)
        res = await db.execute(stmt)
        dependencies = res.scalars().all()
        return [
            {
                "id": dep.id,
                "parent_event_type": dep.parent_event_type,
                "child_event_type": dep.child_event_type,
                "propagation_probability": dep.propagation_probability
            }
            for dep in dependencies
        ]
    except Exception as e:
        print(f"[API ERROR] Failed to fetch event dependencies: {e}")
        return []

@router.get("/actions/options")
async def get_action_options(db: AsyncSession = Depends(get_db)):
    """Fetch selectable response action lists for active anomaly events"""
    try:
        stmt = select(ActionOptionModel)
        res = await db.execute(stmt)
        options = res.scalars().all()
        if not options:
            return simulator.action_options
            
        grouped = {}
        for opt in options:
            grouped.setdefault(opt.event_type, []).append({
                "action_key": opt.action_key,
                "action_name": opt.action_name,
                "description": opt.description
            })
        return grouped
    except Exception as e:
        print(f"[API ERROR] Failed to fetch action options: {e}")
        return simulator.action_options

@router.get("/actions/predictions")
async def get_action_predictions(db: AsyncSession = Depends(get_db)):
    """Fetch predictive delta modifications overlay for action choices"""
    try:
        stmt = select(ActionPredictionModel)
        res = await db.execute(stmt)
        predictions = res.scalars().all()
        if not predictions:
            return simulator.action_predictions
            
        return {
            p.action_key: {
                "fuel_delta": p.fuel_delta,
                "power_delta": p.power_delta,
                "risk_reduction": p.risk_reduction,
                "success_delta": p.success_delta
            }
            for p in predictions
        }
    except Exception as e:
        print(f"[API ERROR] Failed to fetch action predictions: {e}")
        return simulator.action_predictions

@router.post("/actions/execute")
async def execute_action(req: ActionExecuteRequest):
    """Execute a mitigation action against an active anomaly"""
    res = await simulator.execute_action(req.event_id, req.action_key)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/forecast/montecarlo")
async def run_monte_carlo(req: MonteCarloRequest):
    """Trigger background worker-threaded Monte Carlo trajectory simulation"""
    results = await simulator.run_monte_carlo(req.iterations)
    return results

@router.get("/mission/replay")
async def get_mission_replay(db: AsyncSession = Depends(get_db)):
    """Fetch saved flight replays alongside current live history timeline"""
    try:
        stmt = select(MissionReplayModel).order_by(MissionReplayModel.created_at.desc())
        res = await db.execute(stmt)
        replays = res.scalars().all()
        saved = [
            {
                "id": r.id,
                "replay_name": r.replay_name,
                "history_data": json.loads(r.history_data) if isinstance(r.history_data, str) else r.history_data,
                "created_at": r.created_at.isoformat()
            }
            for r in replays
        ]
        return {
            "saved_replays": saved,
            "live_history": simulator.mission_history
        }
    except Exception as e:
        print(f"[API ERROR] Failed to fetch replays: {e}")
        return {
            "saved_replays": [],
            "live_history": simulator.mission_history
        }
