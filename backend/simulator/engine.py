import os
import json
import random
import math
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.database import connection
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
from backend.database.redis_client import get_redis
from backend.websocket.connection import manager

# Pydantic Schemas for Phase 2.5 validation
class EventSchema(BaseModel):
    id: Optional[int] = None
    event_type: str
    severity: str
    timestamp: str
    description: str
    affected_system: str
    probability: float
    recommended_actions: str
    resolved: bool = False
    status: str = "ACTIVE"

class TelemetryData(BaseModel):
    timestamp: str
    fuel: float
    power: float
    oxygen: float
    temperature: float
    health: float
    velocity: float
    distance: float
    mission_progress: float
    communication: str
    position: Dict[str, float]
    position_error: float
    angular_velocity: Dict[str, float]
    subsystems: Dict[str, Dict[str, Any]]
    success_probability: float
    failure_probability: float
    confidence_score: float

class MissionInfo(BaseModel):
    name: str
    destination: str
    launch_time: str
    state: str
    duration: float
    target_distance: float
    difficulty: str
    event_frequency: float
    risk_score: float
    risk_level: str

# Monte Carlo Blocking Worker Logic
def run_monte_carlo_blocking(start_state: Dict[str, Any], iterations: int) -> Dict[str, Any]:
    successes = 0
    failures = 0
    total_fuel_left = 0.0
    total_time = 0.0
    total_risk = 0.0
    
    failure_causes = {
        "Propulsion": 0,
        "Power": 0,
        "Life Support": 0,
        "Thermal Control": 0,
        "Navigation": 0,
        "Communication": 0,
        "Science Systems": 0
    }
    
    for _ in range(iterations):
        # Local loop simulation copies
        fuel = start_state["fuel"]
        power = start_state["power"]
        oxygen = start_state["oxygen"]
        velocity = start_state["velocity"]
        distance = start_state["distance"]
        position_error = start_state["position_error"]
        target_distance = start_state["target_distance"]
        duration = start_state["duration"]
        state_mission = start_state["state"]
        
        # Subsystem health map (copies of current health)
        subsystems = {k: v["health"] for k, v in start_state["subsystems"].items()}
        
        active_events = []
        for ev in start_state["active_events"]:
            active_events.append({
                "event_type": ev["event_type"],
                "duration": ev.get("duration", 20.0),
                "status": ev.get("status", "ACTIVE")
            })
            
        step_dt = 1.0
        max_ticks = 7200  # 2 hours max safety cap
        ticks = 0
        success = False
        failure = False
        failure_cause = None
        
        diff_factor = {"Easy": 0.5, "Normal": 1.0, "Hard": 1.5, "Extreme": 2.2}[start_state["difficulty"]]
        
        while ticks < max_ticks:
            ticks += 1
            duration += step_dt
            
            # Crew oxygen decay
            oxygen_rate = 0.05 * diff_factor
            oxygen = max(0.0, oxygen - oxygen_rate * step_dt * (2.0 - (subsystems["Life Support"] / 100.0)))
            
            # Spawn random event check rolls (35% probability at intervals)
            if ticks % int(start_state.get("event_frequency", 30)) == 0:
                if random.random() < 0.35:
                    et = random.choice([
                        "Solar Storm", "Fuel Leak", "Thruster Failure", "Communication Loss",
                        "Radiation Burst", "Sensor Malfunction", "Power Fluctuation",
                        "Navigation Drift", "Micrometeorite Impact"
                    ])
                    if not any(e["event_type"] == et for e in active_events):
                        active_events.append({
                            "event_type": et,
                            "duration": random.uniform(15.0, 45.0),
                            "status": "ACTIVE"
                        })
            
            # Subsystem decay impact multipliers
            has_comm_fail = False
            for ev in list(active_events):
                ev["duration"] -= step_dt
                et = ev["event_type"]
                
                if et == "Fuel Leak":
                    subsystems["Propulsion"] = max(0.0, subsystems["Propulsion"] - 1.2 * diff_factor * step_dt)
                    fuel = max(0.0, fuel - 0.3 * diff_factor * step_dt)
                elif et == "Power Fluctuation":
                    subsystems["Power"] = max(0.0, subsystems["Power"] - 1.5 * diff_factor * step_dt)
                    subsystems["Navigation"] = max(0.0, subsystems["Navigation"] - 0.5 * diff_factor * step_dt)
                    power = max(10.0, power * math.exp(-0.012 * diff_factor * step_dt))
                elif et == "Solar Storm":
                    subsystems["Power"] = max(0.0, subsystems["Power"] - 2.0 * diff_factor * step_dt)
                    subsystems["Communication"] = max(0.0, subsystems["Communication"] - 2.5 * diff_factor * step_dt)
                    power = max(10.0, power * math.exp(-0.012 * diff_factor * step_dt))
                    has_comm_fail = True
                elif et == "Communication Loss":
                    subsystems["Communication"] = max(0.0, subsystems["Communication"] - 1.8 * diff_factor * step_dt)
                    has_comm_fail = True
                elif et == "Radiation Burst":
                    subsystems["Life Support"] = max(0.0, subsystems["Life Support"] - 1.5 * diff_factor * step_dt)
                    subsystems["Science Systems"] = max(0.0, subsystems["Science Systems"] - 1.2 * diff_factor * step_dt)
                elif et == "Navigation Drift":
                    subsystems["Navigation"] = max(0.0, subsystems["Navigation"] - 1.5 * diff_factor * step_dt)
                    position_error += random.uniform(0.2, 0.6) * diff_factor * step_dt
                elif et == "Thruster Failure":
                    subsystems["Propulsion"] = max(0.0, subsystems["Propulsion"] - 2.5 * diff_factor * step_dt)
                elif et == "Micrometeorite Impact":
                    subsystems["Thermal Control"] = max(0.0, subsystems["Thermal Control"] - 3.0 * diff_factor * step_dt)
                    subsystems["Propulsion"] = max(0.0, subsystems["Propulsion"] - 1.0 * diff_factor * step_dt)
                elif et == "Sensor Malfunction":
                    subsystems["Navigation"] = max(0.0, subsystems["Navigation"] - 1.2 * diff_factor * step_dt)
                
                if ev["duration"] <= 0:
                    active_events.remove(ev)
            
            # Subsystem self-repair hooks
            for sub_name in subsystems:
                is_affected = any(
                    (sub_name == "Propulsion" and et in ["Fuel Leak", "Thruster Failure", "Micrometeorite Impact"]) or
                    (sub_name == "Power" and et in ["Power Fluctuation", "Solar Storm"]) or
                    (sub_name == "Navigation" and et in ["Navigation Drift", "Sensor Malfunction", "Power Fluctuation"]) or
                    (sub_name == "Communication" and et in ["Communication Loss", "Solar Storm"]) or
                    (sub_name == "Life Support" and et in ["Radiation Burst"]) or
                    (sub_name == "Thermal Control" and et in ["Micrometeorite Impact"]) or
                    (sub_name == "Science Systems" and et in ["Radiation Burst"])
                    for e in active_events for et in [e["event_type"]]
                )
                if not is_affected and subsystems[sub_name] < 100.0:
                    subsystems[sub_name] = min(100.0, subsystems[sub_name] + 0.2 * step_dt)
            
            # Physics calculations
            perf_prop = subsystems["Propulsion"] / 100.0
            total_mass = start_state["dry_mass"] + (fuel / 100.0) * start_state["propellant_mass"]
            
            thrust = 0.0
            if state_mission == "Launch":
                thrust = 3800000.0 * perf_prop
                fuel = max(0.0, fuel - 0.9 * step_dt)
            elif state_mission == "Maneuver":
                thrust = 1200000.0 * perf_prop
                fuel = max(0.0, fuel - 0.25 * step_dt)
                
            acc = (thrust / total_mass) / 1000.0
            velocity = max(0.0, velocity + acc * step_dt)
            
            dist_gain = (velocity * step_dt) + (0.5 * acc * (step_dt ** 2))
            distance += dist_gain
            
            perf_nav = subsystems["Navigation"] / 100.0
            position_error += (0.5 * (1.0 - perf_nav)) * step_dt
            
            # Evaluate objective limits
            if distance >= target_distance:
                success = True
                break
                
            if fuel <= 0:
                failure = True
                failure_cause = "Propulsion"
                break
            if power <= 10:
                failure = True
                failure_cause = "Power"
                break
            if subsystems["Life Support"] <= 0 or oxygen <= 0:
                failure = True
                failure_cause = "Life Support"
                break
            if subsystems["Propulsion"] <= 0:
                failure = True
                failure_cause = "Propulsion"
                break
            if subsystems["Power"] <= 0:
                failure = True
                failure_cause = "Power"
                break
            if subsystems["Navigation"] <= 0:
                failure = True
                failure_cause = "Navigation"
                break
            if subsystems["Thermal Control"] <= 0:
                failure = True
                failure_cause = "Thermal Control"
                break

        if success:
            successes += 1
        else:
            failures += 1
            if failure_cause:
                failure_causes[failure_cause] += 1
            else:
                failure_causes["Life Support"] += 1
                
        total_fuel_left += fuel
        total_time += duration
        
        health_avg = sum(subsystems.values()) / len(subsystems)
        c_risk = 100.0 if has_comm_fail else 0.0
        risk_score = 0.3 * (100.0 - fuel) + 0.3 * (100.0 - power) + 0.2 * (100.0 - health_avg) + 0.2 * c_risk
        total_risk += risk_score

    return {
        "iterations": iterations,
        "avg_success_prob": round((successes / iterations) * 100, 1),
        "avg_fuel_remaining": round(total_fuel_left / iterations, 1),
        "avg_mission_time": round(total_time / iterations, 1),
        "avg_risk": round(total_risk / iterations, 1),
        "failure_distribution": failure_causes
    }

class SpacecraftSimulator:
    def __init__(self):
        self.difficulty = "Normal"
        self.event_frequency = 30.0
        self.reset_state()
        
        self.running_task = None
        self.is_active = False
        
        # Decision Sandbox Options configurations
        self.action_options = {
            "Fuel Leak": [
                {"action_key": "fuel_leak_ignore", "action_name": "Ignore Anomaly", "description": "Observe parameters and take no immediate action."},
                {"action_key": "fuel_leak_reduce_speed", "action_name": "Reduce Cruise Speed", "description": "Slow speed to reduce engine strain and slow down leak rate."},
                {"action_key": "fuel_leak_activate_backup", "action_name": "Activate Backup Tank", "description": "Close main cross-feed valves and draw propellant from auxiliary backup tank."},
                {"action_key": "fuel_leak_emergency_shutdown", "action_name": "Emergency Shutdown", "description": "Instantly close all lines and cut fuel feed to engines."}
            ],
            "Solar Storm": [
                {"action_key": "solar_storm_ignore", "action_name": "Ignore Anomaly", "description": "Keep secondary grids active. High risk of electronics failure."},
                {"action_key": "solar_storm_retract_panels", "action_name": "Retract Secondary Panels", "description": "Puts solar grids into secure configurations and deploy carbon shields."},
                {"action_key": "solar_storm_divert_power", "action_name": "Divert Power to Deflectors", "description": "Activate active magnetic deflection shield surrounding the hull."}
            ],
            "Thruster Failure": [
                {"action_key": "thruster_fail_revector", "action_name": "Re-vector Remaining Bells", "description": "Adjust active thruster gimbals to counteract asymmetric torque."},
                {"action_key": "thruster_fail_backup_controller", "action_name": "Enable Backup Controller", "description": "Switch attitude control systems to standby navigation computers."}
            ],
            "Communication Loss": [
                {"action_key": "comm_loss_automated_sweep", "action_name": "Initiate Automated Sweeps", "description": "Scan antenna arrays to reacquire the signal carrier frequency."},
                {"action_key": "comm_loss_realign_gimbal", "action_name": "Manual Antenna Realignment", "description": "Rotate high gain antenna directly to last coordinates."}
            ],
            "Navigation Drift": [
                {"action_key": "nav_drift_star_field", "action_name": "Perform Star-Field Overlay", "description": "Calibrate drift coefficients against starry constellation guides."}
            ],
            "Micrometeorite Impact": [
                {"action_key": "meteor_seal_pressure", "action_name": "Seal Bulkheads", "description": "Close isolation hatches to prevent depressurization."},
                {"action_key": "meteor_run_diagnostic", "action_name": "Run Damage Diagnostic", "description": "Use ultrasound scanning to identify micro-fractures."}
            ]
        }
        
        # Outcome deltas predictions
        self.action_predictions = {
            "fuel_leak_ignore": {"fuel_delta": -12.0, "power_delta": 0.0, "risk_reduction": 0.0, "success_delta": -15.0},
            "fuel_leak_reduce_speed": {"fuel_delta": -3.0, "power_delta": 0.0, "risk_reduction": 40.0, "success_delta": -2.0},
            "fuel_leak_activate_backup": {"fuel_delta": 15.0, "power_delta": -2.0, "risk_reduction": 80.0, "success_delta": 8.0},
            "fuel_leak_emergency_shutdown": {"fuel_delta": 0.0, "power_delta": 5.0, "risk_reduction": 95.0, "success_delta": -20.0},

            "solar_storm_ignore": {"fuel_delta": 0.0, "power_delta": -25.0, "risk_reduction": 0.0, "success_delta": -20.0},
            "solar_storm_retract_panels": {"fuel_delta": 0.0, "power_delta": -10.0, "risk_reduction": 75.0, "success_delta": 5.0},
            "solar_storm_divert_power": {"fuel_delta": 0.0, "power_delta": -20.0, "risk_reduction": 90.0, "success_delta": 10.0},

            "thruster_fail_revector": {"fuel_delta": -2.0, "power_delta": -2.0, "risk_reduction": 70.0, "success_delta": 6.0},
            "thruster_fail_backup_controller": {"fuel_delta": 0.0, "power_delta": -5.0, "risk_reduction": 85.0, "success_delta": 8.0},

            "comm_loss_automated_sweep": {"fuel_delta": 0.0, "power_delta": -4.0, "risk_reduction": 80.0, "success_delta": 10.0},
            "comm_loss_realign_gimbal": {"fuel_delta": 0.0, "power_delta": -2.0, "risk_reduction": 60.0, "success_delta": 5.0},

            "nav_drift_star_field": {"fuel_delta": 0.0, "power_delta": -3.0, "risk_reduction": 85.0, "success_delta": 12.0},

            "meteor_seal_pressure": {"fuel_delta": 0.0, "power_delta": -2.0, "risk_reduction": 80.0, "success_delta": 10.0},
            "meteor_run_diagnostic": {"fuel_delta": 0.0, "power_delta": -5.0, "risk_reduction": 60.0, "success_delta": 4.0}
        }

    def reset_state(self):
        self.name = "Project Hail Mary"
        self.destination = "Tau Ceti (Eridani System)"
        self.launch_time = None
        self.state = "Idle"
        self.duration = 0.0
        self.target_distance = 1000000.0
        
        # Telemetry variables
        self.fuel = 100.0
        self.power = 100.0
        self.oxygen = 100.0
        self.temperature = 25.0
        self.health = 100.0
        self.velocity = 0.0
        self.distance = 0.0
        self.mission_progress = 0.0
        self.communication = "Connected"
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        
        self.position_error = 0.0
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.risk_score = 0.0
        self.risk_level = "LOW"
        
        self.thrust_force = 0.0
        self.dry_mass = 5000.0
        self.propellant_mass = 10000.0
        self.a = 0.0
        
        self.active_events: List[Dict[str, Any]] = []
        self.event_timer = 0.0
        self.next_event_time = self.get_randomized_event_time()
        
        self.power_decay_start = 100.0
        self.power_decay_time = 0.0
        
        # --- PHASE 2.5 SPECIFIC STATE VARIABLES ---
        self.subsystems = {
            "Propulsion": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Power": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Navigation": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Communication": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Life Support": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Thermal Control": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0},
            "Science Systems": {"health": 100.0, "status": "OPERATIONAL", "performance": 1.0, "risk": 0.0}
        }
        
        self.success_probability = 100.0
        self.failure_probability = 0.0
        self.confidence_score = 50.0
        
        # Playback buffers
        self.mission_history: List[Dict[str, Any]] = []

    def get_randomized_event_time(self) -> float:
        if self.difficulty == "Easy":
            return random.uniform(45.0, 60.0)
        elif self.difficulty == "Hard":
            return random.uniform(20.0, 30.0)
        elif self.difficulty == "Extreme":
            return random.uniform(10.0, 20.0)
        return random.uniform(30.0, 45.0)

    def get_mission_info(self) -> MissionInfo:
        return MissionInfo(
            name=self.name,
            destination=self.destination,
            launch_time=self.launch_time.isoformat() if self.launch_time else "Not Launched",
            state=self.state,
            duration=self.duration,
            target_distance=self.target_distance,
            difficulty=self.difficulty,
            event_frequency=self.event_frequency,
            risk_score=round(self.risk_score, 1),
            risk_level=self.risk_level
        )

    def get_telemetry_data(self) -> TelemetryData:
        return TelemetryData(
            timestamp=datetime.utcnow().isoformat(),
            fuel=round(self.fuel, 2),
            power=round(self.power, 2),
            oxygen=round(self.oxygen, 2),
            temperature=round(self.temperature, 2),
            health=round(self.health, 2),
            velocity=round(self.velocity, 2),
            distance=round(self.distance, 2),
            mission_progress=round(self.mission_progress, 2),
            communication=self.communication,
            position={k: round(v, 2) for k, v in self.position.items()},
            position_error=round(self.position_error, 2),
            angular_velocity={k: round(v, 3) for k, v in self.angular_velocity.items()},
            subsystems=self.subsystems,
            success_probability=round(self.success_probability, 1),
            failure_probability=round(self.failure_probability, 1),
            confidence_score=round(self.confidence_score, 1)
        )

    async def log_event(self, event_type: str, message: str):
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [{event_type}] {message}")
        timestamp_str = datetime.utcnow().strftime('%H:%M:%S')
        log_payload = f"[{timestamp_str}] {message}"
        
        redis = await get_redis()
        await redis.rpush("hail_mary:events", log_payload)

        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    event = EventModel(timestamp=datetime.utcnow(), event_type=event_type, message=message)
                    db.add(event)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Event logging failed: {e}")

        await manager.broadcast_json({"type": "EVENT", "message": log_payload})

    async def start(self):
        if self.state == "Idle" or self.state == "Completed":
            self.reset_state()
            self.state = "Launch"
            self.launch_time = datetime.utcnow()
            await self.log_event("INFO", f"Mission Initialized on {self.difficulty} Mode - Engine Ignition Command")
            
            # Set initial objectives status PENDING in database
            if connection.SessionLocal:
                try:
                    async with connection.SessionLocal() as db:
                        stmt = update(MissionObjectiveModel).values(status="PENDING")
                        await db.execute(stmt)
                        await db.commit()
                except Exception as ex:
                    print(f"[DB ERROR] Objectives init failed: {ex}")
        else:
            await self.log_event("INFO", f"Mission Resumed. State: {self.state}")
        
        self.is_active = True
        if self.running_task is None or self.running_task.done():
            self.running_task = asyncio.create_task(self.run_simulation_loop())

    async def pause(self):
        if self.is_active:
            self.is_active = False
            await self.log_event("INFO", "Simulation paused")
        else:
            await self.log_event("INFO", "Simulation already paused")

    async def reset(self):
        self.is_active = False
        if self.running_task and not self.running_task.done():
            self.running_task.cancel()
        
        # Save historical run memory as replay before wiping state
        if len(self.mission_history) > 10:
            await self.save_history_replay()
            
        self.reset_state()
        
        redis = await get_redis()
        await redis.set("hail_mary:telemetry", "")
        await redis.delete("hail_mary:events")
        await redis.set("hail_mary:active_events", "[]")
        await redis.set("hail_mary:risk_score", "0")
        
        await self.log_event("INFO", "Mission Reset - Telemetry registers restored to zero")

    async def save_history_replay(self):
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    replay = MissionReplayModel(
                        replay_name=f"Replay {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        history_data=json.dumps(self.mission_history)
                    )
                    db.add(replay)
                    await db.commit()
                    print(f"[DB] Saved flight replay of length: {len(self.mission_history)}")
            except Exception as e:
                print(f"[DB ERROR] Replay save failed: {e}")

    async def run_simulation_loop(self):
        dt = 1.0
        try:
            while self.is_active:
                await self.update_physics(dt)
                await self.check_event_generator(dt)
                await self.calculate_success_scores()
                await self.calculate_risk()
                await self.save_state_to_storages()
                await self.broadcast_telemetry()
                await self.append_snapshot_memory()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.log_event("ERROR", f"Simulation engine exception: {e}")

    async def update_physics(self, dt: float):
        self.duration += dt
        self.event_timer += dt

        # Crew oxygen decay scaled by Life Support performance
        perf_life = self.subsystems["Life Support"]["performance"]
        oxygen_rate = 0.05
        if self.difficulty == "Hard": oxygen_rate = 0.08
        if self.difficulty == "Extreme": oxygen_rate = 0.12
        
        self.oxygen = max(0.0, self.oxygen - oxygen_rate * dt * (2.0 - perf_life))
        
        if self.oxygen < 20.0 and self.state != "Emergency" and self.oxygen > 0:
            self.state = "Emergency"
            await self.log_event("WARNING", "O2 levels critical (<20%)! Entering emergency mode.")

        # Engine propulsion physics (scaled by Propulsion performance)
        perf_prop = self.subsystems["Propulsion"]["performance"]
        current_propellant_mass = (self.fuel / 100.0) * self.propellant_mass
        total_mass = self.dry_mass + current_propellant_mass
        
        if self.state == "Launch":
            self.thrust_force = 3800000.0 * perf_prop
            self.fuel = max(0.0, self.fuel - 0.9 * dt)
            self.temperature = min(88.0, self.temperature + 1.1 * dt)
        elif self.state == "Maneuver":
            self.thrust_force = 1200000.0 * perf_prop
            self.fuel = max(0.0, self.fuel - 0.25 * dt)
            self.temperature = min(45.0, self.temperature + 0.4 * dt)
        else:
            self.thrust_force = 0.0
            if self.temperature > 22.0:
                self.temperature = max(22.0, self.temperature - 0.6 * dt)
            else:
                self.temperature = min(22.0, self.temperature + 0.1 * dt)

        # Acceleration a = F / m
        self.a = (self.thrust_force / total_mass) / 1000.0
        
        await self.process_active_event_impacts(dt)

        self.velocity = max(0.0, self.velocity + self.a * dt)
        
        distance_gained = (self.velocity * dt) + (0.5 * self.a * (dt ** 2))
        self.distance += distance_gained
        self.mission_progress = min(100.0, (self.distance / self.target_distance) * 100)

        # Navigation performance scales coordinate drift error
        perf_nav = self.subsystems["Navigation"]["performance"]
        self.position_error += (0.5 * (1.0 - perf_nav)) * dt

        angle = self.distance * 0.00015
        radius = 20.0 + (self.mission_progress * 0.4)
        
        self.position["x"] = radius * math.cos(angle) + (self.angular_velocity["x"] * 10)
        self.position["y"] = 4.0 * math.sin(angle * 2.0) + (self.angular_velocity["y"] * 10)
        self.position["z"] = radius * math.sin(angle) + (self.angular_velocity["z"] * 10)

        if self.state == "Launch" and self.velocity >= 12.0:
            self.state = "Cruise"
            await self.log_event("INFO", "Escape velocity reached. Cruising at constant speed.")
            
        # Check mission objectives outcome conditions
        if self.mission_progress >= 100.0:
            self.state = "Completed"
            self.velocity = 0.0
            self.a = 0.0
            self.is_active = False
            await self.log_event("INFO", "Mission Completed - Hail Mary has achieved stable orbit!")
            await self.update_db_objectives(status="ACHIEVED")

        # Evaluate mission objective failure triggers
        if self.fuel <= 0.0 or self.power <= 10.0 or self.health <= 0.0 or self.oxygen <= 0.0:
            self.state = "Emergency"
            self.is_active = False
            await self.log_event("ERROR", "CRITICAL METRICS FAILURE: Life Support / Energy depletion.")
            await self.update_db_objectives(status="FAILED")

    async def update_db_objectives(self, status: str):
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    stmt = update(MissionObjectiveModel).values(status=status)
                    await db.execute(stmt)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Objectives status save failed: {e}")

    async def process_active_event_impacts(self, dt: float):
        resolved_indices = []
        has_active_comm_fail = False
        diff_factor = {"Easy": 0.5, "Normal": 1.0, "Hard": 1.5, "Extreme": 2.2}[self.difficulty]

        # Tracking affected systems to determine self-repair
        affected_subsystems = set()

        for idx, event in enumerate(self.active_events):
            event_type = event["event_type"]
            status = event.get("status", "ACTIVE")
            
            # Mitigation timers execution
            if status == "MITIGATING":
                event["mitigation_timer"] -= dt
                damage_scale = 0.5  # mitigations reduce system damages by 50%
                if event["mitigation_timer"] <= 0:
                    resolved_indices.append(idx)
                    continue
            else:
                damage_scale = 1.0

            # 1. Fuel Leak
            if event_type == "Fuel Leak":
                affected_subsystems.add("Propulsion")
                self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 1.2 * diff_factor * damage_scale * dt)
                leak_rate = 0.3 * diff_factor * damage_scale
                self.fuel = max(0.0, self.fuel - leak_rate * dt)
            
            # 2. Power Fluctuation
            elif event_type == "Power Fluctuation":
                affected_subsystems.add("Power")
                affected_subsystems.add("Navigation")
                self.subsystems["Power"]["health"] = max(0.0, self.subsystems["Power"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 0.5 * diff_factor * damage_scale * dt)
                
                self.power_decay_time += dt
                decay_lambda = 0.012 * diff_factor * damage_scale
                self.power = max(10.0, self.power_decay_start * math.exp(-decay_lambda * self.power_decay_time))
            
            # 3. Solar Storm
            elif event_type == "Solar Storm":
                affected_subsystems.add("Power")
                affected_subsystems.add("Communication")
                self.subsystems["Power"]["health"] = max(0.0, self.subsystems["Power"]["health"] - 2.0 * diff_factor * damage_scale * dt)
                self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 2.5 * diff_factor * damage_scale * dt)
                
                self.power_decay_time += dt
                decay_lambda = 0.012 * diff_factor * damage_scale
                self.power = max(10.0, self.power_decay_start * math.exp(-decay_lambda * self.power_decay_time))
                has_active_comm_fail = True

            # 4. Communication Loss
            elif event_type == "Communication Loss":
                affected_subsystems.add("Communication")
                self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 1.8 * diff_factor * damage_scale * dt)
                has_active_comm_fail = True

            # 5. Radiation Burst
            elif event_type == "Radiation Burst":
                affected_subsystems.add("Life Support")
                affected_subsystems.add("Science Systems")
                self.subsystems["Life Support"]["health"] = max(0.0, self.subsystems["Life Support"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                self.subsystems["Science Systems"]["health"] = max(0.0, self.subsystems["Science Systems"]["health"] - 1.2 * diff_factor * damage_scale * dt)

            # 6. Navigation Drift
            elif event_type == "Navigation Drift":
                affected_subsystems.add("Navigation")
                self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                self.position_error += random.uniform(0.2, 0.6) * diff_factor * damage_scale * dt
                self.angular_velocity["x"] += random.uniform(-0.01, 0.01) * dt
                self.angular_velocity["y"] += random.uniform(-0.01, 0.01) * dt

            # 7. Thruster Failure
            elif event_type == "Thruster Failure":
                affected_subsystems.add("Propulsion")
                self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 2.5 * diff_factor * damage_scale * dt)
                self.a *= 0.5
                self.angular_velocity["z"] += random.uniform(-0.02, 0.02) * dt

            # 8. Micrometeorite Impact
            elif event_type == "Micrometeorite Impact":
                affected_subsystems.add("Thermal Control")
                affected_subsystems.add("Propulsion")
                self.subsystems["Thermal Control"]["health"] = max(0.0, self.subsystems["Thermal Control"]["health"] - 3.0 * diff_factor * damage_scale * dt)
                self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 1.0 * diff_factor * damage_scale * dt)

            # 9. Sensor Malfunction
            elif event_type == "Sensor Malfunction":
                affected_subsystems.add("Navigation")
                self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 1.2 * diff_factor * damage_scale * dt)

        # Apply self-repair to inactive systems (0.2% health recovery per tick)
        for sub_name in self.subsystems:
            if sub_name not in affected_subsystems and self.subsystems[sub_name]["health"] < 100.0:
                self.subsystems[sub_name]["health"] = min(100.0, self.subsystems[sub_name]["health"] + 0.2 * dt)
            
            # Recalculate performance and risk metrics
            health = self.subsystems[sub_name]["health"]
            self.subsystems[sub_name]["performance"] = round(health / 100.0, 2)
            self.subsystems[sub_name]["risk"] = round(100.0 - health, 1)
            self.subsystems[sub_name]["status"] = (
                "OPERATIONAL" if health >= 70 else 
                "DEGRADED" if health >= 30 else 
                "CRITICAL" if health > 0 else "FAILED"
            )

        # Consequence failure propagation cascades
        # A. Low propulsion health -> Thruster Failure
        if self.subsystems["Propulsion"]["health"] < 30.0 and not any(e["event_type"] == "Thruster Failure" for e in self.active_events):
            await self.trigger_cascade_event("Thruster Failure", "Propulsion degradation triggers asymmetric thruster feedback failure.")
            
        # B. Low power health -> Power Fluctuation & degrades Comm/Nav
        if self.subsystems["Power"]["health"] < 30.0:
            if not any(e["event_type"] == "Power Fluctuation" for e in self.active_events):
                await self.trigger_cascade_event("Power Fluctuation", "Critical power grid depletion triggers systemic voltage oscillations.")
            # Drain Comm and Nav systems by 0.5% per tick
            self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 0.5 * dt)
            self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 0.5 * dt)

        # Comm status tracking
        if has_active_comm_fail or self.subsystems["Communication"]["health"] < 30.0:
            self.communication = "Disconnected"
        else:
            self.communication = "Connected"

        # Update overall health (average of all subsystems)
        self.health = sum(sub["health"] for sub in self.subsystems.values()) / len(self.subsystems)

        # Cleanup resolved events
        for r_idx in sorted(resolved_indices, reverse=True):
            resolved_event = self.active_events.pop(r_idx)
            await self.resolve_active_event(resolved_event)

    async def trigger_cascade_event(self, event_type: str, description: str):
        # Avoid duplication
        if any(e["event_type"] == event_type for e in self.active_events):
            return
            
        await self.log_event("WARNING", f"CONSEQUENCE PROPAGATION: {event_type} - {description}")
        
        db_event_id = None
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    db_event = MissionEventModel(
                        event_type=event_type,
                        severity="HIGH",
                        timestamp=datetime.utcnow(),
                        description=description,
                        affected_system="Propulsion" if event_type == "Thruster Failure" else "Electrical Systems",
                        probability=1.0,
                        recommended_actions="Perform emergency system bypass.",
                        resolved=False
                    )
                    db.add(db_event)
                    await db.flush()
                    db_event_id = db_event.id
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Cascade logging failed: {e}")

        # Inject cascade propagation parent relationships
        if connection.SessionLocal and db_event_id:
            try:
                async with connection.SessionLocal() as db:
                    parent_type = "Fuel Leak" if event_type == "Thruster Failure" else "Solar Storm"
                    dep = EventDependencyModel(
                        parent_event_type=parent_type,
                        child_event_type=event_type,
                        propagation_probability=1.0
                    )
                    db.add(dep)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Dependency link failed: {e}")

        self.active_events.append({
            "id": db_event_id,
            "event_type": event_type,
            "severity": "HIGH",
            "description": description,
            "affected_system": "Propulsion" if event_type == "Thruster Failure" else "Electrical Systems",
            "recommended_actions": "Activate backup Attitude Controller." if event_type == "Thruster Failure" else "Divert Deflectors.",
            "duration": random.uniform(20.0, 40.0),
            "status": "ACTIVE"
        })

    async def resolve_active_event(self, event: Dict[str, Any]):
        event_type = event["event_type"]
        await self.log_event("INFO", f"Anomaly resolved: {event_type}")

        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    stmt = (
                        update(MissionEventModel)
                        .where(MissionEventModel.id == event["id"])
                        .values(resolved=True, resolution_time=datetime.utcnow())
                    )
                    await db.execute(stmt)
                    
                    stat_stmt = select(EventStatisticsModel).where(EventStatisticsModel.event_type == event_type)
                    stat_res = await db.execute(stat_stmt)
                    stat = stat_res.scalars().first()
                    if stat:
                        stat.frequency_count += 1
                        stat.last_occurred = datetime.utcnow()
                    else:
                        new_stat = EventStatisticsModel(event_type=event_type, frequency_count=1, last_occurred=datetime.utcnow())
                        db.add(new_stat)
                        
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Anomaly resolution save failed: {e}")

        if event_type in ["Power Fluctuation", "Solar Storm"]:
            self.power_decay_start = self.power
            self.power_decay_time = 0.0
            
        if not any(e["event_type"] in ["Power Fluctuation", "Solar Storm"] for e in self.active_events):
            self.power = min(100.0, self.power + 5.0)

        await manager.broadcast_json({
            "type": "EVENT_RESOLVED",
            "event_id": event["id"],
            "event_type": event_type
        })

    async def check_event_generator(self, dt: float):
        if self.event_timer >= self.next_event_time:
            self.event_timer = 0.0
            self.next_event_time = self.get_randomized_event_time()
            await self.generate_random_event()

    async def generate_random_event(self):
        weights = {
            "Solar Storm": 0.05,
            "Fuel Leak": 0.08,
            "Thruster Failure": 0.04,
            "Communication Loss": 0.06,
            "Radiation Burst": 0.05,
            "Sensor Malfunction": 0.10,
            "Power Fluctuation": 0.12,
            "Navigation Drift": 0.08,
            "Micrometeorite Impact": 0.03,
            "Unknown Object Detection": 0.02,
            "Routine Status Update": 0.37
        }

        # Apply state thresholds offsets
        if self.fuel < 35.0:
            weights["Fuel Leak"] *= 3.0
            weights["Thruster Failure"] *= 2.0
            weights["Routine Status Update"] *= 0.5
        if self.power < 35.0:
            weights["Power Fluctuation"] *= 3.0
            weights["Communication Loss"] *= 2.0
            weights["Routine Status Update"] *= 0.5
        if self.health < 50.0:
            weights["Micrometeorite Impact"] *= 3.0
            weights["Sensor Malfunction"] *= 2.0
            weights["Routine Status Update"] *= 0.5

        total_weight = sum(weights.values())
        norm_weights = {k: v / total_weight for k, v in weights.items()}

        keys = list(norm_weights.keys())
        probabilities = list(norm_weights.values())
        picked_event_type = random.choices(keys, weights=probabilities, k=1)[0]

        if picked_event_type != "Routine Status Update" and any(e["event_type"] == picked_event_type for e in self.active_events):
            picked_event_type = "Routine Status Update"

        severity_levels = {
            "Routine Status Update": "INFO",
            "Unknown Object Detection": "INFO",
            "Sensor Malfunction": "LOW",
            "Navigation Drift": "LOW",
            "Power Fluctuation": "MEDIUM",
            "Radiation Burst": "MEDIUM",
            "Fuel Leak": "HIGH",
            "Thruster Failure": "HIGH",
            "Communication Loss": "HIGH",
            "Solar Storm": "CRITICAL",
            "Micrometeorite Impact": "CRITICAL"
        }

        descriptions = {
            "Solar Storm": "Solar CME particles interacting with hull panels. Inducing electromagnetic discharges.",
            "Fuel Leak": "Propellant pressure drops detected on Port tank valves. Slow propellant loss active.",
            "Thruster Failure": "Asymmetrical RCS nozzles feedback failure. Thruster force reduced.",
            "Communication Loss": "S-Band High Gain Antenna experiences carrier signal synchronization loss.",
            "Radiation Burst": "Solar flare event emitting alpha particles. Shield armor experiencing stress.",
            "Sensor Malfunction": "Optical sensor occlusion. Telemetry reading variances suspected.",
            "Power Fluctuation": "Solar cells experience transient grid discharge. Battery voltage drops.",
            "Navigation Drift": "IMU drift introduces coordinate discrepancy calculations.",
            "Micrometeorite Impact": "Minor micro-impact registered on rear thruster bell shell.",
            "Unknown Object Detection": "LIDAR reflections register localized mass orbiting nearby.",
            "Routine Status Update": "Spacecraft sub-systems report normal telemetry operations."
        }

        affected_systems = {
            "Solar Storm": "Electrical Systems",
            "Fuel Leak": "Propulsion",
            "Thruster Failure": "Propulsion",
            "Communication Loss": "Communications",
            "Radiation Burst": "Structural Armor",
            "Sensor Malfunction": "Nav Computers",
            "Power Fluctuation": "Electrical Systems",
            "Navigation Drift": "Nav Computers",
            "Micrometeorite Impact": "Structural Armor",
            "Unknown Object Detection": "Nav Computers",
            "Routine Status Update": "Diagnostics"
        }

        actions = {
            "Solar Storm": "Retract secondary solar panels. Set deflectors.",
            "Fuel Leak": "Activate auxiliary backup tank.",
            "Thruster Failure": "Re-vector gimbal bells attitude controller.",
            "Communication Loss": "Initiate automated S-band sweeps.",
            "Radiation Burst": "Activate carbon shielding divert deflection grid.",
            "Sensor Malfunction": "Calibrate IMU sensor alignments.",
            "Power Fluctuation": "Bypass compromised lines and scan diagnostics.",
            "Navigation Drift": "Perform star-field overlay coordinates sync.",
            "Micrometeorite Impact": "Seal bulkhead pressure chambers.",
            "Unknown Object Detection": "Acquire scans trajectory data.",
            "Routine Status Update": "No immediate actions required."
        }

        severity = severity_levels[picked_event_type]
        if self.difficulty == "Extreme" and severity != "CRITICAL":
            severity = {"INFO": "LOW", "LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "CRITICAL"}[severity]

        description = descriptions[picked_event_type]
        affected_system = affected_systems[picked_event_type]
        recommended_action = actions[picked_event_type]
        prob_val = norm_weights[picked_event_type]

        # Apply instant impact effects
        if picked_event_type == "Fuel Leak":
            self.fuel = max(0.0, self.fuel - random.uniform(5.0, 10.0))
        elif picked_event_type == "Thruster Failure":
            self.velocity *= 0.85
        elif picked_event_type == "Radiation Burst":
            self.subsystems["Life Support"]["health"] = max(0.0, self.subsystems["Life Support"]["health"] - random.uniform(5.0, 15.0))
        elif picked_event_type == "Micrometeorite Impact":
            self.subsystems["Thermal Control"]["health"] = max(0.0, self.subsystems["Thermal Control"]["health"] - random.uniform(8.0, 20.0))
            self.angular_velocity["x"] = random.uniform(-0.1, 0.1)
            self.angular_velocity["y"] = random.uniform(-0.1, 0.1)

        await self.log_event(severity, f"EVENT TRIGGERED: {picked_event_type} - {description}")

        db_event_id = None
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    db_event = MissionEventModel(
                        event_type=picked_event_type,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                        description=description,
                        affected_system=affected_system,
                        probability=prob_val,
                        recommended_actions=recommended_action,
                        resolved=(severity == "INFO")
                    )
                    db.add(db_event)
                    await db.flush()
                    db_event_id = db_event.id
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Event capture write failed: {e}")

        # If not simple informational message, append to active events list with status PENDING
        if severity != "INFO":
            event_duration = random.uniform(20.0, 45.0)
            
            # Formulate Failure Tree options causes dynamically
            root_causes = {
                "Thruster Failure": ["Fuel Line Leaks", "Eductor Combustion Clog", "Control Electronics Fault", "Nozzle Gimbal Jam"],
                "Solar Storm": ["CME Particle Stream Discharge", "Solar Wind Flare Charge"],
                "Fuel Leak": ["Port Valve Gasket Microfracture", "Crossfeed Pipe Seam Crack"],
                "Communication Loss": ["Transceiver Frequency Drift", "HG Waveguide Misalignment"],
                "Navigation Drift": ["IMU Alignment Drift", "Optical Sensor Obstruction"],
                "Power Fluctuation": ["Transformer Regulator Discharge", "Battery Cell Short Circuit"]
            }.get(picked_event_type, ["Unknown telemetry failure source"])
            
            new_active_event = {
                "id": db_event_id,
                "event_type": picked_event_type,
                "severity": severity,
                "description": description,
                "affected_system": affected_system,
                "recommended_actions": recommended_action,
                "duration": event_duration,
                "status": "PENDING" if picked_event_type == "Solar Storm" else "ACTIVE",
                "mitigation_timer": 0.0,
                "chosen_action": None,
                "root_causes": root_causes,
                "selected_root_cause": random.choice(root_causes)
            }
            self.active_events.append(new_active_event)
            
            if picked_event_type in ["Power Fluctuation", "Solar Storm"]:
                self.power_decay_start = self.power
                self.power_decay_time = 0.0

            redis = await get_redis()
            await redis.set("hail_mary:active_events", json.dumps([
                {k: v for k, v in ev.items() if k not in ["duration", "mitigation_timer"]} 
                for ev in self.active_events
            ]))

            await manager.broadcast_json({
                "type": "NEW_EVENT",
                "event": {
                    "id": db_event_id,
                    "event_type": picked_event_type,
                    "severity": severity,
                    "description": description,
                    "affected_system": affected_system,
                    "recommended_actions": recommended_action,
                    "status": new_active_event["status"]
                }
            })

    async def calculate_success_scores(self):
        # Feature 4 Success Prediction Model
        fuel_score = self.fuel
        power_score = self.power
        health_score = self.health
        comm_score = 100.0 if self.communication == "Connected" else 0.0
        nav_score = max(0.0, 100.0 - self.position_error)

        success = (
            0.25 * fuel_score + 
            0.20 * power_score + 
            0.20 * health_score + 
            0.15 * comm_score + 
            0.20 * nav_score
        )
        self.success_probability = min(100.0, max(0.0, success))
        self.failure_probability = 100.0 - self.success_probability
        
        # Confidence increases as we get closer to destination
        self.confidence_score = self.health * (0.5 + 0.005 * self.mission_progress)
        self.confidence_score = min(100.0, max(0.0, self.confidence_score))

    async def calculate_risk(self):
        fuel_risk = 100.0 - self.fuel
        power_risk = 100.0 - self.power
        health_risk = 100.0 - self.health
        comm_risk = 100.0 if self.communication != "Connected" else 0.0
        
        self.risk_score = (0.3 * fuel_risk) + (0.3 * power_risk) + (0.2 * health_risk) + (0.2 * comm_risk)
        self.risk_score = min(100.0, max(0.0, self.risk_score))

        if self.risk_score <= 25.0:
            self.risk_level = "LOW"
        elif self.risk_score <= 50.0:
            self.risk_level = "MODERATE"
        elif self.risk_score <= 75.0:
            self.risk_level = "HIGH"
        else:
            self.risk_level = "CRITICAL"

        redis = await get_redis()
        await redis.set("hail_mary:risk_score", str(self.risk_score))

        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    risk_rec = RiskHistoryModel(
                        timestamp=datetime.utcnow(),
                        risk_score=self.risk_score,
                        risk_level=self.risk_level
                    )
                    db.add(risk_rec)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Risk history write failed: {e}")

    async def save_state_to_storages(self):
        telemetry = self.get_telemetry_data()
        mission = self.get_mission_info()

        redis = await get_redis()
        await redis.set("hail_mary:telemetry", telemetry.model_dump_json())

        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    # Update active MissionModel details
                    stmt = select(MissionModel).limit(1)
                    result = await db.execute(stmt)
                    db_mission = result.scalars().first()
                    if db_mission:
                        db_mission.state = mission.state
                        db_mission.duration = mission.duration
                        db_mission.launch_time = self.launch_time if self.launch_time else db_mission.launch_time
                    
                    # Store historical telemetry
                    db_telemetry = TelemetryModel(
                        timestamp=datetime.utcnow(),
                        fuel=telemetry.fuel,
                        power=telemetry.power,
                        oxygen=telemetry.oxygen,
                        temperature=telemetry.temperature,
                        health=telemetry.health,
                        velocity=telemetry.velocity,
                        distance=telemetry.distance,
                        mission_progress=telemetry.mission_progress
                    )
                    db.add(db_telemetry)
                    
                    # Store subsystem health logs
                    for sub_name, sub_data in self.subsystems.items():
                        sub_log = SubsystemHealthModel(
                            timestamp=datetime.utcnow(),
                            subsystem_name=sub_name,
                            health=sub_data["health"],
                            status=sub_data["status"],
                            risk_score=sub_data["risk"],
                            performance=sub_data["performance"]
                        )
                        db.add(sub_log)

                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Simulator state write failed: {e}")

    async def append_snapshot_memory(self):
        # Record snapshots to memory cache for playback replays
        telemetry = self.get_telemetry_data()
        snapshot = {
            "timestamp": telemetry.timestamp,
            "fuel": telemetry.fuel,
            "power": telemetry.power,
            "oxygen": telemetry.oxygen,
            "velocity": telemetry.velocity,
            "distance": telemetry.distance,
            "mission_progress": telemetry.mission_progress,
            "position_error": telemetry.position_error,
            "risk_score": self.risk_score,
            "subsystems": self.subsystems,
            "active_events": [
                {"event_type": e["event_type"], "status": e["status"]} for e in self.active_events
            ]
        }
        self.mission_history.append(snapshot)
        
        # Save running snapshots to DB logs table
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    mem_rec = MissionMemoryModel(
                        timestamp=datetime.utcnow(),
                        telemetry_snapshot=telemetry.model_dump_json(),
                        active_events=json.dumps([e["event_type"] for e in self.active_events]),
                        available_actions=json.dumps([a["action_key"] for e in self.active_events for a in self.action_options.get(e["event_type"], [])]),
                        chosen_action=None,
                        outcome=None
                    )
                    db.add(mem_rec)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Memory write failed: {e}")

    async def broadcast_telemetry(self):
        telemetry = self.get_telemetry_data()
        mission = self.get_mission_info()
        
        payload = {
            "type": "TELEMETRY",
            "mission": mission.model_dump(),
            "telemetry": telemetry.model_dump(),
            "active_events": [
                {k: v for k, v in ev.items() if k not in ["duration", "mitigation_timer"]} 
                for ev in self.active_events
            ]
        }
        await manager.broadcast_json(payload)

    # --- DECISION SANDBOX EXECUTION HANDLER ---
    async def execute_action(self, event_id: int, action_key: str) -> Dict[str, Any]:
        target_event = None
        for ev in self.active_events:
            if ev["id"] == event_id:
                target_event = ev
                break
                
        if not target_event:
            return {"status": "error", "message": f"Event ID {event_id} not found or inactive."}

        # Validate that the action is applicable
        event_type = target_event["event_type"]
        valid_actions = [a["action_key"] for a in self.action_options.get(event_type, [])]
        if action_key not in valid_actions:
            return {"status": "error", "message": f"Action {action_key} is invalid for anomaly {event_type}."}

        # Transition event status to MITIGATING
        target_event["status"] = "MITIGATING"
        target_event["mitigation_timer"] = 5.0  # takes 5 simulation ticks to complete
        target_event["chosen_action"] = action_key
        
        # Fetch outcome predictions deltas
        deltas = self.action_predictions.get(action_key, {"fuel_delta": 0.0, "power_delta": 0.0, "risk_reduction": 0.0, "success_delta": 0.0})
        
        # Apply deltas to state
        self.fuel = min(100.0, max(0.0, self.fuel + deltas["fuel_delta"]))
        self.power = min(100.0, max(10.0, self.power + deltas["power_delta"]))
        
        # Save decision execution trace to Memory system
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    trace = MissionMemoryModel(
                        timestamp=datetime.utcnow(),
                        telemetry_snapshot=self.get_telemetry_data().model_dump_json(),
                        active_events=json.dumps([e["event_type"] for e in self.active_events]),
                        available_actions=json.dumps(valid_actions),
                        chosen_action=action_key,
                        outcome=json.dumps(deltas)
                    )
                    db.add(trace)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Trace save failed: {e}")

        # Broadcast update over WS
        await self.log_event("INFO", f"Sandbox Action Executed: '{action_key}' - Mitigating event: '{event_type}'.")
        await manager.broadcast_json({
            "type": "ACTION_EXECUTED",
            "event_id": event_id,
            "action_key": action_key,
            "status": "MITIGATING",
            "predictions_deltas": deltas
        })

        return {
            "status": "success",
            "message": f"Action {action_key} successfully scheduled for mitigation.",
            "event_state": target_event
        }

    # --- BACKGROUND MONTE CARLO FORECASTING ---
    async def run_monte_carlo(self, iterations: int = 500) -> Dict[str, Any]:
        start_state = {
            "fuel": self.fuel,
            "power": self.power,
            "oxygen": self.oxygen,
            "health": self.health,
            "velocity": self.velocity,
            "distance": self.distance,
            "position_error": self.position_error,
            "target_distance": self.target_distance,
            "duration": self.duration,
            "subsystems": self.subsystems,
            "active_events": self.active_events,
            "difficulty": self.difficulty,
            "event_frequency": self.event_frequency,
            "dry_mass": self.dry_mass,
            "propellant_mass": self.propellant_mass,
            "state": self.state
        }
        
        # Execute forecasting on worker thread pool
        print(f"[Simulator] Running Monte Carlo Forecast with {iterations} iterations on thread pool...")
        results = await asyncio.to_thread(run_monte_carlo_blocking, start_state, iterations)
        
        # Save results to DB
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    mc_rec = MonteCarloResultModel(
                        timestamp=datetime.utcnow(),
                        iterations=iterations,
                        avg_success_prob=results["avg_success_prob"],
                        avg_fuel_remaining=results["avg_fuel_remaining"],
                        avg_mission_time=results["avg_mission_time"],
                        avg_risk=results["avg_risk"],
                        failure_distribution=json.dumps(results["failure_distribution"])
                    )
                    db.add(mc_rec)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Monte Carlo result write failed: {e}")
                
        # Cache results in Redis
        redis = await get_redis()
        await redis.set("hail_mary:forecast", json.dumps(results))
        
        # Broadcast forecast updated over WebSockets
        await manager.broadcast_json({
            "type": "FORECAST_UPDATED",
            "forecast": results
        })
        
        return results

# Global Simulator instance
simulator = SpacecraftSimulator()
