from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel

from backend.database.connection import get_db
from backend.database.models import DestinationModel
from backend.trajectory.planner import TrajectoryPlanner
from backend.websocket.connection import manager

router = APIRouter()

class DestinationResponse(BaseModel):
    name: str
    avg_distance_km: float

class TrajectoryCalculateRequest(BaseModel):
    origin: str = "Earth"
    destination: str
    payload_mass: float
    mission_type: str = "Science Deep Probe"

class TrajectoryEventRequest(BaseModel):
    event: str  # fuel_leak, thruster_failure, navigation_drift, route_change, reset_events
    destination: Optional[str] = None

_destinations_cache = None

@router.get("/destinations", response_model=List[DestinationResponse])
async def get_destinations(db: AsyncSession = Depends(get_db)):
    global _destinations_cache
    if _destinations_cache is not None:
        return _destinations_cache

    stmt = select(DestinationModel).order_by(DestinationModel.name)
    result = await db.execute(stmt)
    destinations = result.scalars().all()
    _destinations_cache = [
        DestinationResponse(name=d.name, avg_distance_km=d.avg_distance_km)
        for d in destinations
    ]
    return _destinations_cache

@router.get("/trajectory/current")
async def get_current_trajectory(db: AsyncSession = Depends(get_db)):
    planner = await TrajectoryPlanner.load_from_redis()
    stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
    result = await db.execute(stmt)
    dest = result.scalars().first()
    distance = dest.avg_distance_km if dest else 0.0
    outputs = planner.calculate(distance)
    return {
        "inputs": planner.to_dict(),
        "outputs": outputs
    }

@router.post("/trajectory/calculate")
async def calculate_trajectory(req: TrajectoryCalculateRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(DestinationModel).where(DestinationModel.name == req.destination)
    result = await db.execute(stmt)
    dest = result.scalars().first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    planner = await TrajectoryPlanner.load_from_redis()
    planner.origin = req.origin
    planner.destination = req.destination
    planner.payload_mass = req.payload_mass
    planner.mission_type = req.mission_type
    planner.apply_mission_type_defaults()

    outputs = planner.calculate(dest.avg_distance_km)
    await planner.save_to_redis()

    # Broadcast update
    await manager.broadcast_json({
        "type": "TRAJECTORY_UPDATE",
        "data": {
            "inputs": planner.to_dict(),
            "outputs": outputs
        }
    })

    # Synchronize simulator state if simulator is Idle or not running
    from backend.simulator.engine import simulator
    if simulator.state in ["Idle", "Pre-Launch"]:
        await simulator.sync_with_trajectory()
        await simulator.save_state_to_storages()
        await simulator.broadcast_telemetry()

    return {
        "inputs": planner.to_dict(),
        "outputs": outputs
    }

@router.post("/trajectory/event")
async def handle_trajectory_event(req: TrajectoryEventRequest, db: AsyncSession = Depends(get_db)):
    planner = await TrajectoryPlanner.load_from_redis()

    if req.event == "route_change":
        if not req.destination:
            raise HTTPException(status_code=400, detail="Destination must be specified for route change")
        planner.destination = req.destination
        # When changing route, we can choose to clear or keep existing anomaly events
        # Let's keep existing anomaly events but clear them if it is a fresh replanning.
        # Actually, let's keep them, but let the user decide. Standard requirement says
        # Recalculate trajectory whenever route changes occur.
    elif req.event == "reset_events":
        planner.active_events = []
    elif req.event in ["fuel_leak", "thruster_failure", "navigation_drift"]:
        if req.event not in planner.active_events:
            planner.active_events.append(req.event)
    elif req.event.startswith("clear_"):
        event_to_clear = req.event.replace("clear_", "")
        if event_to_clear in planner.active_events:
            planner.active_events.remove(event_to_clear)

    stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
    result = await db.execute(stmt)
    dest = result.scalars().first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    outputs = planner.calculate(dest.avg_distance_km)
    await planner.save_to_redis()

    # Broadcast update
    await manager.broadcast_json({
        "type": "TRAJECTORY_UPDATE",
        "data": {
            "inputs": planner.to_dict(),
            "outputs": outputs
        }
    })

    # Synchronize simulator state if simulator is Idle or not running
    from backend.simulator.engine import simulator
    if simulator.state in ["Idle", "Pre-Launch"]:
        await simulator.sync_with_trajectory()
        await simulator.save_state_to_storages()
        await simulator.broadcast_telemetry()

    return {
        "inputs": planner.to_dict(),
        "outputs": outputs
    }
