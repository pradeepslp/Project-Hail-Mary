import json
import random
import math
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import connection
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
from backend.websocket.connection import manager
from backend.utils.timezone_helper import ist_now

class InterplanetarySwarmSimulator:
    def __init__(self):
        self.is_active = False
        self.running_task = None
        self.tick_counter = 0
        
        # In-memory assets snapshot
        self.assets: List[Dict[str, Any]] = []
        self.colonies: List[Dict[str, Any]] = []
        self.tasks: List[Dict[str, Any]] = []
        self.active_transfers: List[Dict[str, Any]] = []
        self.discoveries: List[Dict[str, Any]] = []
        self.risk_metrics: Dict[str, float] = {
            "fleet_risk": 12.5,
            "mission_risk": 15.0,
            "planetary_risk": 5.0,
            "colony_risk": 8.0,
            "infrastructure_risk": 10.0
        }
        self.threat_assessment = "Nominal"

        self.reset_swarm_state()

    def reset_swarm_state(self):
        self.tick_counter = 0
        self.assets = [
            {
                "id": 1,
                "name": "Zenith Station",
                "type": "Space Station",
                "status": "Operational",
                "fuel": 95.0,
                "power": 90.0,
                "bandwidth": 100.0,
                "health": 100.0,
                "oxygen": 98.0,
                "cargo": 60.0,
                "parts": 80.0,
                "x": 0.0,
                "y": 0.0,
                "z": 12000.0,
                "active_objectives": ["Coordinate swarm telemetry", "Manage cargo transfers"]
            },
            {
                "id": 2,
                "name": "Ares Orbiter",
                "type": "Orbiter",
                "status": "Operational",
                "fuel": 85.0,
                "power": 95.0,
                "bandwidth": 80.0,
                "health": 100.0,
                "oxygen": 0.0,  # Unmanned
                "cargo": 10.0,
                "parts": 20.0,
                "x": 15000.0,
                "y": 5000.0,
                "z": 0.0,
                "active_objectives": ["Map landing zones", "Relay ground communication"]
            },
            {
                "id": 3,
                "name": "Phoenix Lander",
                "type": "Lander",
                "status": "Operational",
                "fuel": 40.0,
                "power": 85.0,
                "bandwidth": 60.0,
                "health": 95.0,
                "oxygen": 85.0,
                "cargo": 30.0,
                "parts": 40.0,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "active_objectives": ["Deploy surface outpost", "Conduct atmospheric scan"]
            },
            {
                "id": 4,
                "name": "Spirit Rover",
                "type": "Rover",
                "status": "Idle",
                "fuel": 0.0,  # RTG / Solar driven
                "power": 75.0,
                "bandwidth": 50.0,
                "health": 98.0,
                "oxygen": 0.0,
                "cargo": 5.0,
                "parts": 10.0,
                "x": 2.5,
                "y": -1.8,
                "z": 0.0,
                "active_objectives": ["Survey southern highlands", "Acquire soil core samples"]
            },
            {
                "id": 5,
                "name": "Syracuse Satellite",
                "type": "Satellite",
                "status": "Operational",
                "fuel": 90.0,
                "power": 100.0,
                "bandwidth": 100.0,
                "health": 100.0,
                "oxygen": 0.0,
                "cargo": 0.0,
                "parts": 5.0,
                "x": -22000.0,
                "y": 12000.0,
                "z": 5000.0,
                "active_objectives": ["Deep space telemetry relay", "Monitor solar storms"]
            },
            {
                "id": 6,
                "name": "Atlas Cargo",
                "type": "Cargo Ship",
                "status": "Transit",
                "fuel": 95.0,
                "power": 80.0,
                "bandwidth": 70.0,
                "health": 100.0,
                "oxygen": 90.0,
                "cargo": 95.0,
                "parts": 50.0,
                "x": 50000.0,
                "y": 25000.0,
                "z": -15000.0,
                "active_objectives": ["Deliver fuel to Lander", "Transport base spare parts"]
            },
            {
                "id": 7,
                "name": "Intrepid Drone",
                "type": "Exploration Drone",
                "status": "Operational",
                "fuel": 30.0,
                "power": 80.0,
                "bandwidth": 90.0,
                "health": 95.0,
                "oxygen": 0.0,
                "cargo": 2.0,
                "parts": 5.0,
                "x": 3.4,
                "y": 0.8,
                "z": 0.2,
                "active_objectives": ["Reconnaissance of lava tubes", "Deploy sensor beacons"]
            },
            {
                "id": 8,
                "name": "Voyager Probe",
                "type": "Probe",
                "status": "Operational",
                "fuel": 80.0,
                "power": 90.0,
                "bandwidth": 50.0,
                "health": 100.0,
                "oxygen": 0.0,
                "cargo": 0.0,
                "parts": 10.0,
                "x": 120000.0,
                "y": -80000.0,
                "z": 30000.0,
                "active_objectives": ["Navigate outer asteroid fields", "Measure cosmic dust"]
            }
        ]

        self.colonies = [
            {"id": 1, "name": "Ares Base Habitat", "type": "Habitat", "status": "Operational", "level": 1, "efficiency": 92.0, "power_consumption": 25.0, "storage": 80.0},
            {"id": 2, "name": "Helios Arrays", "type": "Power Plant", "status": "Operational", "level": 1, "efficiency": 95.0, "power_consumption": 0.0, "storage": 100.0},
            {"id": 3, "name": "Olympus Excavator", "type": "Mining Facility", "status": "Idle", "level": 1, "efficiency": 80.0, "power_consumption": 45.0, "storage": 35.0},
            {"id": 4, "name": "Curie Biosphere", "type": "Research Lab", "status": "Operational", "level": 1, "efficiency": 88.0, "power_consumption": 30.0, "storage": 50.0},
            {"id": 5, "name": "Phobos Array Link", "type": "Comm Tower", "status": "Operational", "level": 1, "efficiency": 99.0, "power_consumption": 15.0, "storage": 10.0}
        ]

        self.tasks = [
            {"id": 1, "task_name": "Relay High-Gain Data Burst", "asset_id": 5, "priority": "High", "status": "Executing", "required_resources": '{"bandwidth": 30.0}'},
            {"id": 2, "task_name": "Excavate Subsurface Ice", "asset_id": 3, "priority": "Medium", "status": "Assigned", "required_resources": '{"power": 15.0, "parts": 2.0}'},
            {"id": 3, "task_name": "Repair Syracuse Thermal Valve", "asset_id": None, "priority": "High", "status": "Unassigned", "required_resources": '{"parts": 1.0}'}
        ]

        self.active_transfers = []
        self.discoveries = [
            {"id": 1, "discovery_type": "Resource", "source": "Spirit Rover", "details": "High-concentration iron ore vein detected in Ares South region.", "confidence": 0.94},
            {"id": 2, "discovery_type": "Hazard", "source": "Ares Orbiter", "details": "Localized dust storm warning initialized over mining sector 4.", "confidence": 0.88}
        ]

        self.risk_metrics = {
            "fleet_risk": 15.0,
            "mission_risk": 18.0,
            "planetary_risk": 5.0,
            "colony_risk": 8.0,
            "infrastructure_risk": 12.0
        }
        self.threat_assessment = "Nominal"

    async def start(self):
        self.is_active = True
        if self.running_task is None or self.running_task.done():
            self.running_task = asyncio.create_task(self.run_swarm_loop())

    async def stop_simulator(self):
        self.is_active = False
        if self.running_task and not self.running_task.done():
            self.running_task.cancel()

    async def log_inter_agent_msg(self, sender: str, receiver: str, msg_type: str, content: str):
        # 1. Write to Postgres
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    msg = InterAgentMessageModel(
                        sender_id=sender,
                        receiver_id=receiver,
                        msg_type=msg_type,
                        content=content
                    )
                    db.add(msg)
                    await db.commit()
            except Exception as e:
                print(f"[Swarm Engine] Failed to log inter agent message: {e}")

        # 2. Cache in Redis & Broadcast over WS
        redis = await get_redis()
        payload = {
            "timestamp": ist_now().isoformat(),
            "sender_id": sender,
            "receiver_id": receiver,
            "msg_type": msg_type,
            "content": content
        }
        await redis.rpush("hail_mary:fleet:messages", json.dumps(payload))
        await manager.broadcast_json({
            "type": "FLEET_MESSAGE",
            "message": payload
        })

    async def add_shared_knowledge(self, disc_type: str, source: str, details: str, confidence: float):
        # 1. Write to Postgres
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    know = SharedKnowledgeModel(
                        discovery_type=disc_type,
                        source=source,
                        details=details,
                        confidence=confidence
                    )
                    db.add(know)
                    await db.commit()
            except Exception as e:
                print(f"[Swarm Engine] Failed to log discovery: {e}")

        # 2. Add to local list and broadcast
        new_disc = {
            "id": len(self.discoveries) + 1,
            "discovery_type": disc_type,
            "source": source,
            "details": details,
            "confidence": confidence
        }
        self.discoveries.append(new_disc)
        await manager.broadcast_json({
            "type": "DISCOVERY_DETECTED",
            "discovery": new_disc
        })

    async def run_swarm_loop(self):
        dt = 1.0
        try:
            while self.is_active:
                self.tick_counter += 1
                
                # Update orbital positions and decay metrics
                await self.update_swarm_physics(dt)
                
                # Perform task allocation optimizations
                await self.allocate_tasks_autonomously()

                # Process marketplace transfers and bartering
                await self.process_resource_trading()

                # Upgrade colony infrastructure modules
                await self.update_colony_growth(dt)

                # Process random anomaly events and risk metrics recalculations
                await self.evaluate_swarm_risks()

                # Persist assets state to PostgreSQL database and Redis
                await self.persist_swarm_state()

                # Sleep 1 second
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Swarm Engine] Loop exception: {e}")

    async def update_swarm_physics(self, dt: float):
        for ast in self.assets:
            if ast["status"] == "Damaged":
                ast["health"] = max(10.0, ast["health"] - 1.0 * dt)
                continue

            # Decay fuel/power slightly
            if ast["type"] in ["Orbiter", "Satellite", "Space Station"]:
                ast["power"] = max(40.0, min(100.0, ast["power"] + random.uniform(-1.0, 1.2) * dt))
                ast["fuel"] = max(10.0, ast["fuel"] - 0.05 * dt)
                # Orbit movement around central Z or XY coordinates
                angle = (self.tick_counter * 0.05) + ast["id"]
                radius = 12000.0 if ast["type"] == "Space Station" else 18000.0
                ast["x"] = radius * math.cos(angle)
                ast["y"] = radius * math.sin(angle)
            elif ast["type"] == "Rover":
                ast["power"] = max(30.0, min(100.0, ast["power"] + random.uniform(-1.5, 1.5) * dt))
                # Move slightly on planar surface
                ast["x"] += random.uniform(-0.1, 0.1) * dt
                ast["y"] += random.uniform(-0.1, 0.1) * dt
            elif ast["type"] == "Exploration Drone":
                ast["power"] = max(20.0, ast["power"] - 0.2 * dt)
                ast["fuel"] = max(10.0, ast["fuel"] - 0.3 * dt)
                # Float
                ast["x"] += random.uniform(-0.2, 0.2)
                ast["y"] += random.uniform(-0.2, 0.2)
                ast["z"] = max(0.1, ast["z"] + random.uniform(-0.05, 0.05))
            elif ast["type"] == "Cargo Ship":
                ast["fuel"] = max(5.0, ast["fuel"] - 0.15 * dt)
                ast["power"] = max(30.0, ast["power"] - 0.1 * dt)
                # Fly toward the space station (id: 1)
                station = self.assets[0]
                dx = station["x"] - ast["x"]
                dy = station["y"] - ast["y"]
                dz = station["z"] - ast["z"]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist > 500.0:
                    ast["x"] += (dx / dist) * 1200.0 * dt
                    ast["y"] += (dy / dist) * 1200.0 * dt
                    ast["z"] += (dz / dist) * 1200.0 * dt
                else:
                    ast["status"] = "Operational" # Docked

    async def allocate_tasks_autonomously(self):
        # Check for unassigned tasks
        unassigned = [t for t in self.tasks if t["status"] == "Unassigned"]
        for t in unassigned:
            # Match task to asset based on suitability
            suitable_asset = None
            if "Repair" in t["task_name"] or "parts" in t["required_resources"]:
                # Station or Drone has parts / repairs capabilities
                suitable_asset = next((a for a in self.assets if a["type"] == "Exploration Drone" and a["status"] == "Operational" and a["power"] > 40.0), None)
                if not suitable_asset:
                    suitable_asset = next((a for a in self.assets if a["type"] == "Space Station"), None)
            elif "Scan" in t["task_name"] or "scientific" in t["required_resources"]:
                suitable_asset = next((a for a in self.assets if a["type"] == "Orbiter" and a["status"] == "Operational"), None)
            
            if suitable_asset:
                t["asset_id"] = suitable_asset["id"]
                t["status"] = "Assigned"
                suitable_asset["status"] = "Transit"
                await self.log_inter_agent_msg(
                    sender="Swarm Commander",
                    receiver=suitable_asset["name"],
                    msg_type="Recommendation",
                    content=f"Task allocated: {t['task_name']}. Requesting resource dispatch."
                )
                await manager.broadcast_json({
                    "type": "TASK_ASSIGNED",
                    "task_id": t["id"],
                    "asset_id": suitable_asset["id"]
                })

    async def process_resource_trading(self):
        # 1. Deficit check
        for ast in self.assets:
            if ast["status"] == "Operational":
                if ast["power"] < 45.0:
                    # Request power relay from satellite or station
                    supplier = next((a for a in self.assets if a["power"] > 80.0 and a["id"] != ast["id"]), None)
                    if supplier:
                        # Establish temporary power connection
                        trade = {
                            "id": len(self.active_transfers) + 1,
                            "source_asset_id": supplier["id"],
                            "target_asset_id": ast["id"],
                            "resource_type": "Power",
                            "transfer_rate": 5.0,
                            "status": "Transferring"
                        }
                        self.active_transfers.append(trade)
                        ast["power"] += 15.0
                        supplier["power"] -= 10.0
                        
                        await self.log_inter_agent_msg(
                            sender=supplier["name"],
                            receiver=ast["name"],
                            msg_type="Resource Request",
                            content="Barter confirmed: Power relay beam locked. Transmitting 15.0 power grid units."
                        )
                        await manager.broadcast_json({
                            "type": "RESOURCE_TRANSFER",
                            "transfer": trade
                        })

    async def update_colony_growth(self, dt: float):
        for col in self.colonies:
            if col["status"] == "Operational":
                # Upgrade level periodically when efficiency is high and tick reaches module thresholds
                if self.tick_counter % 25 == 0 and col["storage"] < 95.0:
                    col["storage"] = min(100.0, col["storage"] + 5.0)
                    if col["storage"] >= 90.0 and col["level"] < 5:
                        col["level"] += 1
                        col["storage"] = 30.0 # reset to baseline after upgrade build
                        col["efficiency"] = min(99.0, col["efficiency"] + 2.0)
                        
                        await self.log_inter_agent_msg(
                            sender="Ares Base Habitat",
                            receiver="Swarm Commander",
                            msg_type="Status Update",
                            content=f"Facility upgrade completed: {col['name']} advanced to Level {col['level']}."
                        )
                        await manager.broadcast_json({
                            "type": "COLONY_EXPANDED",
                            "colony_id": col["id"],
                            "level": col["level"]
                        })

    async def evaluate_swarm_risks(self):
        # Update metrics
        base_fleet_risk = 10.0
        damaged_count = sum(1 for a in self.assets if a["status"] == "Damaged")
        fleet_risk = base_fleet_risk + (damaged_count * 20.0)
        
        self.risk_metrics["fleet_risk"] = round(fleet_risk, 1)
        self.risk_metrics["mission_risk"] = round(12.0 + random.uniform(-1.0, 1.0), 1)
        self.risk_metrics["colony_risk"] = round(sum(100.0 - c["efficiency"] for c in self.colonies) / len(self.colonies), 1)
        
        # Threat evaluation
        if fleet_risk > 50.0:
            self.threat_assessment = "Critical Threat"
        elif fleet_risk > 25.0:
            self.threat_assessment = "Elevated Hazard"
        else:
            self.threat_assessment = "Nominal"

        if self.tick_counter % 10 == 0:
            await manager.broadcast_json({
                "type": "RISK_UPDATED",
                "risk_metrics": self.risk_metrics,
                "threat_assessment": self.threat_assessment
            })

    async def persist_swarm_state(self):
        # 1. Update SQLite/PostgreSQL
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    # Wipe and write assets
                    await db.execute(delete(FleetAssetModel))
                    for ast in self.assets:
                        db_ast = FleetAssetModel(
                            id=ast["id"],
                            name=ast["name"],
                            type=ast["type"],
                            status=ast["status"],
                            telemetry_json=json.dumps({
                                "fuel": ast["fuel"],
                                "power": ast["power"],
                                "bandwidth": ast["bandwidth"],
                                "health": ast["health"],
                                "oxygen": ast["oxygen"],
                                "cargo": ast["cargo"],
                                "parts": ast["parts"],
                                "x": ast["x"],
                                "y": ast["y"],
                                "z": ast["z"]
                            }),
                            active_objectives=json.dumps(ast["active_objectives"])
                        )
                        db.add(db_ast)
                    
                    # Update risk metrics
                    rm_rec = GlobalRiskMetricsModel(
                        fleet_risk=self.risk_metrics["fleet_risk"],
                        mission_risk=self.risk_metrics["mission_risk"],
                        planetary_risk=self.risk_metrics["planetary_risk"],
                        colony_risk=self.risk_metrics["colony_risk"],
                        infrastructure_risk=self.risk_metrics["infrastructure_risk"],
                        threat_assessment=self.threat_assessment
                    )
                    db.add(rm_rec)
                    
                    await db.commit()
            except Exception as e:
                print(f"[Swarm Engine] DB persistence error: {e}")

        # 2. Cache in Redis
        redis = await get_redis()
        await redis.set("hail_mary:fleet:assets", json.dumps(self.assets))
        await redis.set("hail_mary:fleet:colonies", json.dumps(self.colonies))
        await redis.set("hail_mary:fleet:tasks", json.dumps(self.tasks))
        await redis.set("hail_mary:fleet:risk", json.dumps(self.risk_metrics))

        # 3. Broadcast fleet status
        await manager.broadcast_json({
            "type": "FLEET_UPDATE",
            "assets": self.assets,
            "colonies": self.colonies,
            "tasks": self.tasks,
            "transfers": self.active_transfers,
            "risk_metrics": self.risk_metrics,
            "threat_assessment": self.threat_assessment
        })

    # --- ONE-CLICK MARS SHOWER RUN SHOWCASE ---
    async def trigger_mars_swarm_showcase(self):
        async def log_demo(lvl, msg):
            payload = f"[DEMO-SWARM] [{lvl}] {msg}"
            # Broadcast over WebSocket
            await manager.broadcast_json({
                "type": "EVENT",
                "message": payload
            })
            # Log agent message
            await self.log_inter_agent_msg("Swarm Commander", "Fleet All Assets", lvl, msg)

        try:
            await log_demo("INFO", "Initializing Phase 6 Interplanetary Swarm Demonstration...")
            await asyncio.sleep(2.0)

            # Step 1: Pre-Launch Countdown
            await log_demo("INFO", "Step 1: Synchronizing fleet launch protocols. Countdown sequence initiated.")
            for ast in self.assets:
                if ast["type"] in ["Orbiter", "Cargo Ship"]:
                    ast["status"] = "Transit"
                    await log_demo("INFO", f"Propulsion grid activated: {ast['name']}.")
            await asyncio.sleep(3.0)

            # Step 2: Orbital Insertion
            await log_demo("INFO", "Step 2: Fleet entering orbit. Satellites deploying communication relays.")
            sats = [a for a in self.assets if a["type"] == "Satellite"]
            for s in sats:
                s["bandwidth"] = 100.0
                await log_demo("INFO", f"Satellite high-gain carrier locked: {s['name']}.")
            await asyncio.sleep(3.0)

            # Step 3: Anomaly Injection
            await log_demo("WARNING", "Step 3: Alert! Micrometeorite impact cascade detected at Zenith Station (id: 1)!")
            station = self.assets[0]
            station["status"] = "Damaged"
            station["health"] = 60.0
            
            # Swarm Commander decider
            await log_demo("WARNING", "Swarm Commander: Initiating fleet collaborative decision loops. Consensus rating divert: [Drone: 0.95, Orbiter: 0.88]")
            await asyncio.sleep(3.0)

            # Step 4: Autonomous Task Allocation / Repair
            await log_demo("INFO", "Step 4: Task Allocated! Exploration Drone (id: 7) dispatched to execute exterior repairs on Zenith Station.")
            drone = self.assets[6]
            drone["status"] = "Transit"
            drone["parts"] -= 2.0
            
            # Execute repair
            await asyncio.sleep(3.0)
            station["status"] = "Operational"
            station["health"] = 95.0
            await log_demo("INFO", "Zenith Station hull breach sealed. Diagnostic check: PASS.")

            # Step 5: Resource Deficit Barter
            await log_demo("WARNING", "Step 5: Phoenix Lander reports critical power grid deficit (85% down to 20%).")
            lander = self.assets[2]
            lander["power"] = 20.0
            
            await log_demo("INFO", "Swarm Commander: Matching power relay offers. Syracuse Satellite locks solar deflectors.")
            lander["power"] = 80.0
            await log_demo("INFO", "Power levels recharged. Resource barter logs updated.")
            await asyncio.sleep(3.0)

            # Step 6: Colony Expansion
            await log_demo("INFO", "Step 6: Ground excavation nominal. Ares Base mining facility upgraded to Level 2.")
            colony = self.colonies[2]
            colony["level"] = 2
            colony["efficiency"] = 90.0
            await manager.broadcast_json({
                "type": "COLONY_EXPANDED",
                "colony_id": colony["id"],
                "level": colony["level"]
            })
            await asyncio.sleep(3.0)

            # Step 7: Completed
            await log_demo("INFO", "Swarm Showcase SUCCESS: All interplanetary assets stabilized. Fleet link: SECURE.")
            
        except Exception as ex:
            await log_demo("ERROR", f"Swarm demo failed: {ex}")

# Global Swarm Simulator instance
swarm_simulator = InterplanetarySwarmSimulator()
