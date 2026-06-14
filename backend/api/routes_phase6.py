import json
import random
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.database.connection import get_db
from backend.database.models import (
    FleetAssetModel,
    FleetMissionModel,
    TaskAllocationModel,
    ResourceNetworkModel,
    ColonySystemModel,
    InterAgentMessageModel,
    SwarmDecisionModel,
    SharedKnowledgeModel,
    GlobalRiskMetricsModel
)
from backend.database.redis_client import get_redis
from backend.simulator.swarm_engine import swarm_simulator
from backend.utils.timezone_helper import ist_now

router = APIRouter(prefix="/api/phase6", tags=["Phase 6 Swarm Operations"])

# --- Request Schemas ---

class TradeNegotiateRequest(BaseModel):
    source_asset_id: int
    target_asset_id: int
    resource_type: str
    transfer_rate: float

# --- ENDPOINTS ---

@router.get("/fleet/assets")
async def get_fleet_assets():
    """Returns the live telemetry assets of the swarm fleet"""
    return swarm_simulator.assets

@router.get("/fleet/messages")
async def get_inter_agent_messages(db: AsyncSession = Depends(get_db)):
    """Fetch the inter-agent packets communication stream logs"""
    stmt = select(InterAgentMessageModel).order_by(InterAgentMessageModel.timestamp.desc()).limit(30)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    if not records:
        # Fallback/mock default logs
        return [
            {
                "timestamp": "2026-06-11T20:00:00",
                "sender_id": "Swarm Commander",
                "receiver_id": "Spirit Rover",
                "msg_type": "Warning",
                "content": "Dust storm front detected. Divert drilling schedule."
            },
            {
                "timestamp": "2026-06-11T20:01:00",
                "sender_id": "Spirit Rover",
                "receiver_id": "Swarm Commander",
                "msg_type": "Status Update",
                "content": "Acknowledged. Rover route adjusted to North ridge valleys."
            }
        ]
        
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "sender_id": r.sender_id,
            "receiver_id": r.receiver_id,
            "msg_type": r.msg_type,
            "content": r.content
        }
        for r in records
    ]

@router.get("/fleet/knowledge")
async def get_shared_knowledge():
    """Fetch shared discoveries list map"""
    return swarm_simulator.discoveries

@router.get("/fleet/tasks")
async def get_task_allocations():
    """Fetch current dynamic task allocation queue"""
    return swarm_simulator.tasks

@router.get("/fleet/resources")
async def get_resource_transfers():
    """Fetch active resource transfers and bartering network"""
    return swarm_simulator.active_transfers

@router.get("/fleet/colonies")
async def get_colony_systems():
    """Fetch active ground colony facilities modules"""
    return swarm_simulator.colonies

@router.get("/fleet/risk")
async def get_global_risk():
    """Fetch compound global risk speeds indices"""
    return {
        "metrics": swarm_simulator.risk_metrics,
        "threat_assessment": swarm_simulator.threat_assessment
    }

@router.post("/fleet/demo/start")
async def start_swarm_showcase(background_tasks: BackgroundTasks):
    """Triggers the automated fleet-wide showcase demo run in the background"""
    swarm_simulator.reset_swarm_state()
    await swarm_simulator.start()
    background_tasks.add_task(swarm_simulator.trigger_mars_swarm_showcase)
    return {"status": "success", "message": "Fleet Swarm Showcase demo started in background."}

@router.post("/fleet/marketplace/negotiate")
async def manual_trade_negotiation(req: TradeNegotiateRequest):
    """Triggers a manual barter exchange between source and target assets"""
    # Verify assets
    source = next((a for a in swarm_simulator.assets if a["id"] == req.source_asset_id), None)
    target = next((a for a in swarm_simulator.assets if a["id"] == req.target_asset_id), None)
    
    if not source or not target:
        raise HTTPException(status_code=404, detail="Source or Target asset not found")
        
    # Append trade
    new_trade = {
        "id": len(swarm_simulator.active_transfers) + 1,
        "source_asset_id": req.source_asset_id,
        "target_asset_id": req.target_asset_id,
        "resource_type": req.resource_type,
        "transfer_rate": req.transfer_rate,
        "status": "Transferring"
    }
    swarm_simulator.active_transfers.append(new_trade)
    
    await swarm_simulator.log_inter_agent_msg(
        sender=source["name"],
        receiver=target["name"],
        msg_type="Recommendation",
        content=f"Commander Override: Force {req.resource_type} transfer at rate {req.transfer_rate} W/tick."
    )
    
    return {"status": "success", "transfer": new_trade}
