import os
import json
import random
import math
import asyncio
from datetime import datetime as _datetime, timedelta
from backend.utils.timezone_helper import ist_now

class datetime(_datetime):
    @classmethod
    def utcnow(cls):
        return ist_now()

    @classmethod
    def now(cls, tz=None):
        return ist_now()

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
    MonteCarloResultModel,
    MissionExperienceModel,
    AutonomyMetricsModel
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
    main_fuel_pct: float = 100.0
    backup_fuel_pct: float = 100.0
    emergency_fuel_pct: float = 100.0
    simulation_speed: str = "1X"
    mission_elapsed: str = "0 Days"
    distance_remaining: str = "0 km"
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
    eta: Optional[str] = "N/A"
    fuel_required: float = 0.0
    travel_time_h: float = 0.0
    feasibility: bool = True
    main_fuel_mass: float = 0.0
    backup_fuel_mass: float = 0.0
    emergency_fuel_mass: float = 0.0
    total_fuel_mass: float = 0.0
    burn_rate: float = 0.0
    fuel_consumed: float = 0.0
    acceleration: float = 0.0

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
            
            # DISABLED: Automatic event generation removed.
            # Anomalies are only created via manual user injection.
            pass
            
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
        self.autonomy_level = 0
        self.agent_workflow_running = False
        
        self.anomaly_templates = {
            # Environmental
            "Solar Storm": {"affected_system": "Power", "desc": "Solar CME storm. Inducing massive electromagnetic charges.", "action": "Retract Panels & Divert Power to Deflectors", "multipliers": {"power": -1.5, "subsystems.Power": -2.0, "subsystems.Communication": -2.5}},
            "Radiation Burst": {"affected_system": "Life Support", "desc": "High alpha particles count. Life support systems under stress.", "action": "Activate Carbon Shielding", "multipliers": {"oxygen": -0.5, "subsystems.Life Support": -1.5, "subsystems.Science Systems": -1.2}},
            "Asteroid Field": {"affected_system": "Thermal Control", "desc": "Entering debris dense zone. Collision hazard active.", "action": "Seal Bulkheads & Re-vector Thrusters", "multipliers": {"health": -1.2, "subsystems.Thermal Control": -3.0, "subsystems.Propulsion": -1.0}},
            "Micrometeorite Impact": {"affected_system": "Thermal Control", "desc": "Minor impact registered on outer shell.", "action": "Seal Bulkheads", "multipliers": {"health": -0.8, "subsystems.Thermal Control": -3.0}},
            "Magnetic Interference": {"affected_system": "Communication", "desc": "Extremal magnetic fields distort signals.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -1.5, "subsystems.Navigation": -1.0}},
            "Space Debris Collision": {"affected_system": "Thermal Control", "desc": "Debris impact on cargo module.", "action": "Seal Bulkheads & Divert Power", "multipliers": {"health": -2.5, "subsystems.Thermal Control": -4.0}},

            # Communication
            "Communication Loss": {"affected_system": "Communication", "desc": "S-Band High Gain Antenna signal carrier loss.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -1.8}},
            "Signal Delay": {"affected_system": "Communication", "desc": "Heavy interplanetary noise delays telemetry packets.", "action": "Manual Antenna Realignment", "multipliers": {"subsystems.Communication": -0.8}},
            "Signal Corruption": {"affected_system": "Communication", "desc": "Checksum failures detected on telemetry transmission streams.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -1.2}},
            "Ground Station Failure": {"affected_system": "Communication", "desc": "Deep Space Network Earth receiver is offline.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -1.0}},
            "Relay Failure": {"affected_system": "Communication", "desc": "Lander network orbit relayer suffers transponder drop.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -1.4}},
            "Network Saturation": {"affected_system": "Communication", "desc": "Bandwidth limit exceeded. Telemetry packet drop rate spike.", "action": "Initiate Automated Sweeps", "multipliers": {"subsystems.Communication": -0.5}},

            # Navigation
            "Navigation Drift": {"affected_system": "Navigation", "desc": "IMU gyro drift introduces coordinate discrepancies.", "action": "Perform Star-Field Overlay", "multipliers": {"subsystems.Navigation": -1.5, "position_error": 0.4}},
            "Sensor Failure": {"affected_system": "Navigation", "desc": "Optical navigation scanner camera occlusion.", "action": "Perform Star-Field Overlay", "multipliers": {"subsystems.Navigation": -1.2}},
            "Star Tracker Failure": {"affected_system": "Navigation", "desc": "Stellar reference tracking camera suffers shutter fault.", "action": "Perform Star-Field Overlay", "multipliers": {"subsystems.Navigation": -2.0, "position_error": 0.8}},
            "Trajectory Deviation": {"affected_system": "Navigation", "desc": "Spacecraft flight path deviates from nominal vector.", "action": "Perform Star-Field Overlay", "multipliers": {"subsystems.Navigation": -1.0, "position_error": 0.6}},
            "Position Estimation Error": {"affected_system": "Navigation", "desc": "Kalman filters register high variance in state estimation.", "action": "Perform Star-Field Overlay", "multipliers": {"subsystems.Navigation": -0.8, "position_error": 0.5}},

            # Resource
            "Fuel Leak": {"affected_system": "Propulsion", "desc": "Port valve gasket leak detected. Slow propellant drops.", "action": "Activate Backup Tank", "multipliers": {"fuel": -0.4, "subsystems.Propulsion": -1.2}},
            "Power Failure": {"affected_system": "Power", "desc": "Compromised power grids trigger localized battery discharge.", "action": "Bypass Compromised Lines", "multipliers": {"power": -1.5, "subsystems.Power": -2.5}},
            "Battery Degradation": {"affected_system": "Power", "desc": "Lithium cell matrix temperature spike decreases voltage output.", "action": "Bypass Compromised Lines", "multipliers": {"power": -0.6, "subsystems.Power": -1.2}},
            "Oxygen Leak": {"affected_system": "Life Support", "desc": "Cabin module seals display micro-fissure drop rates.", "action": "Seal Bulkheads", "multipliers": {"oxygen": -1.2, "subsystems.Life Support": -2.0}},
            "Cooling System Failure": {"affected_system": "Thermal Control", "desc": "Freon cooling pump failure registers telemetry drop.", "action": "Divert Power to Deflectors", "multipliers": {"temperature": 1.2, "subsystems.Thermal Control": -2.5}},
            "Thermal Imbalance": {"affected_system": "Thermal Control", "desc": "Extreme temperature variance between solar side and deep space.", "action": "Divert Power to Deflectors", "multipliers": {"temperature": 0.8, "subsystems.Thermal Control": -1.5}},

            # Propulsion
            "Thruster Failure": {"affected_system": "Propulsion", "desc": "Asymmetrical thruster bells feedback failure.", "action": "Re-vector Remaining Bells", "multipliers": {"subsystems.Propulsion": -2.5}},
            "Engine Failure": {"affected_system": "Propulsion", "desc": "Main combustion chamber shutdown.", "action": "Enable Backup Controller", "multipliers": {"velocity": -0.8, "subsystems.Propulsion": -4.0}},
            "Partial Engine Loss": {"affected_system": "Propulsion", "desc": "RCS manifold secondary nozzles register offline.", "action": "Re-vector Remaining Bells", "multipliers": {"velocity": -0.3, "subsystems.Propulsion": -2.0}},
            "Attitude Control Failure": {"affected_system": "Propulsion", "desc": "Command logic fails to orient spacecraft bells.", "action": "Enable Backup Controller", "multipliers": {"subsystems.Propulsion": -1.8, "position_error": 0.5}},
            "Fuel Pump Failure": {"affected_system": "Propulsion", "desc": "Turbopump cavitation restricts fuel injection rate.", "action": "Enable Backup Controller", "multipliers": {"fuel": -0.2, "subsystems.Propulsion": -2.2}},

            # Life Support
            "Oxygen Contamination": {"affected_system": "Life Support", "desc": "Particulate matter filters register high carbon limits.", "action": "Seal Bulkheads", "multipliers": {"oxygen": -0.6, "subsystems.Life Support": -1.8}},
            "Pressure Loss": {"affected_system": "Life Support", "desc": "Cabin compartment registers rapid pressure loss.", "action": "Seal Bulkheads", "multipliers": {"oxygen": -1.8, "subsystems.Life Support": -3.5}},
            "CO2 Filter Failure": {"affected_system": "Life Support", "desc": "Zeolite scrubber beds saturated. CO2 limits warning.", "action": "Seal Bulkheads", "multipliers": {"oxygen": -0.8, "subsystems.Life Support": -2.0}},
            "Life Support Failure": {"affected_system": "Life Support", "desc": "Environmental control systems offline.", "action": "Seal Bulkheads", "multipliers": {"oxygen": -2.5, "subsystems.Life Support": -5.0}},

            # Science
            "Unknown Object Detection": {"affected_system": "Science Systems", "desc": "Radar reflection indicates orbiting localized mass.", "action": "Run Damage Diagnostic", "multipliers": {"subsystems.Science Systems": -0.2}},
            "Unidentified Signal": {"affected_system": "Science Systems", "desc": "Wideband radio transmitter picks up stellar signal.", "action": "Run Damage Diagnostic", "multipliers": {"subsystems.Science Systems": -0.2}},
            "Scientific Opportunity": {"affected_system": "Science Systems", "desc": "Atypical gravitational pocket offers telemetry collection scans.", "action": "Run Damage Diagnostic", "multipliers": {}},
            "Resource Discovery": {"affected_system": "Science Systems", "desc": "Near-asteroid registers trace heavy isotopes.", "action": "Run Damage Diagnostic", "multipliers": {}}
        }

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
                {"action_key": "solar_storm_retract_panels", "action_name": "Retract Panels", "description": "Puts solar grids into secure configurations and deploy carbon shields."},
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
        self.distance_remaining = self.target_distance
        
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
        self.next_event_time = float('inf')  # Automatic events disabled
        
        self.fuel_capacity = 50000.0
        self.fuel_mass = 50000.0
        self.initial_main_fuel = None
        self.initial_backup_fuel = None
        self.initial_emergency_fuel = None
        self.main_fuel = 0.0
        self.backup_fuel = 0.0
        self.emergency_fuel = 0.0
        self.speed_multiplier = 1.0
        self.payload_mass = 10000.0
        self.cruise_speed = 30.0
        self.engine_thrust = 1500.0
        self.time_scale = None
        self.agent_decisions = []
        self.recovery_actions = []

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
        self.pending_outcome_checks = []

        # --- PHASE 2.8 SCENARIO & RECOVERY STATE VARIABLES ---
        self.active_scenario = None
        self.scenario_timer = 0.0
        self.scenario_triggered_events = set()
        self.recovery_start_times = {}
        self.recovery_mitigate_times = {}
        self.recovery_initial_metrics = {}
        self.resilience_score = 100.0
        self.adaptability_score = 100.0
        self.survivability_score = 100.0
        self.recovery_efficiency = 100.0
        self.system_stability = 100.0
        self.overall_robustness = 100.0

        # --- DB BATCH WRITE BUFFERS ---
        self.telemetry_write_buffer = []
        self.subsystem_write_buffer = []
        self.risk_write_buffer = []
        self.memory_write_buffer = []
        self.resilience_write_buffer = []
        self.tick_counter = 0
        self.last_broadcast_state = None
        self.last_active_events_hash = None
        self.fuel_required = 0.0
        self.travel_time_h = 0.0
        self.feasibility = True

    async def sync_with_trajectory(self):
        from backend.trajectory.planner import TrajectoryPlanner
        from backend.database.models import DestinationModel
        from sqlalchemy import select
        from backend.database.connection import SessionLocal

        planner = await TrajectoryPlanner.load_from_redis()
        target_distance = 1000000.0
        if SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
                    res = await db.execute(stmt)
                    dest = res.scalars().first()
                    if dest:
                        target_distance = dest.avg_distance_km
            except Exception as e:
                print(f"[Engine] DB error loading target distance in sync_with_trajectory: {e}")

        outputs = planner.calculate(target_distance)
        
        self.destination = planner.destination
        trajectory_distance = outputs["distance_km"]
        self.target_distance = trajectory_distance
        self.distance_remaining = trajectory_distance
        
        # Fuel loading configuration based on Trajectory Assessment
        self.initial_main_fuel = outputs["required_mission_fuel"]
        self.initial_backup_fuel = outputs["reserve_fuel"]
        self.initial_emergency_fuel = outputs["emergency_fuel"]
        
        self.main_fuel = self.initial_main_fuel
        self.backup_fuel = self.initial_backup_fuel
        self.emergency_fuel = self.initial_emergency_fuel
        
        self.fuel_mass = outputs["total_fuel_loaded"]
        self.fuel_capacity = outputs["total_fuel_loaded"]
        self.fuel = 100.0
        
        self.payload_mass = planner.payload_mass
        self.cruise_speed = planner.cruise_speed
        self.engine_thrust = planner.engine_thrust

        # Trajectory details
        self.fuel_required = outputs["total_fuel_loaded"]
        self.travel_time_h = outputs["travel_time_h"]
        self.feasibility = outputs["feasibility"]

    def get_randomized_event_time(self) -> float:
        # DISABLED: Automatic event generation removed.
        # Anomalies are only created via manual user injection.
        return float('inf')

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
        main_pct = (self.main_fuel / self.initial_main_fuel) * 100.0 if (getattr(self, "initial_main_fuel", None) or 0) > 0 else 100.0
        backup_pct = (self.backup_fuel / self.initial_backup_fuel) * 100.0 if (getattr(self, "initial_backup_fuel", None) or 0) > 0 else 100.0
        emergency_pct = (self.emergency_fuel / self.initial_emergency_fuel) * 100.0 if (getattr(self, "initial_emergency_fuel", None) or 0) > 0 else 100.0

        main_pct = max(0.0, min(100.0, main_pct))
        backup_pct = max(0.0, min(100.0, backup_pct))
        emergency_pct = max(0.0, min(100.0, emergency_pct))

        dist_remaining = max(0.0, self.target_distance - self.distance)
        elapsed_days = int(self.duration / 86400)

        # Use stored attribute if available, fallback to calculation
        distance_rem = getattr(self, 'distance_remaining', dist_remaining)

        return TelemetryData(
            timestamp=datetime.utcnow().isoformat(),
            fuel=round(self.fuel, 2),
            main_fuel_pct=round(main_pct, 1),
            backup_fuel_pct=round(backup_pct, 1),
            emergency_fuel_pct=round(emergency_pct, 1),
            simulation_speed=f"{int(getattr(self, 'speed_multiplier', 1.0))}X",
            mission_elapsed=f"{elapsed_days} Days",
            distance_remaining=f"{distance_rem:,.0f} km",
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
            confidence_score=round(self.confidence_score, 1),
            eta=self.eta_time.isoformat() if getattr(self, "eta_time", None) else "N/A",
            fuel_required=round(getattr(self, "fuel_required", 0.0), 1),
            travel_time_h=round(getattr(self, "travel_time_h", 0.0), 1),
            feasibility=bool(getattr(self, "feasibility", True)),
            main_fuel_mass=round(getattr(self, "main_fuel", 0.0), 1),
            backup_fuel_mass=round(getattr(self, "backup_fuel", 0.0), 1),
            emergency_fuel_mass=round(getattr(self, "emergency_fuel", 0.0), 1),
            total_fuel_mass=round(getattr(self, "fuel_mass", 0.0), 1),
            burn_rate=round(getattr(self, "burn_rate_kg_s", 0.0), 2),
            fuel_consumed=round(max(0.0, self.fuel_capacity - self.fuel_mass), 1),
            acceleration=round(getattr(self, "a", 0.0) * 1000.0, 4)
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
            # Load TrajectoryPlanner, compute Required Fuel.
            from backend.trajectory.planner import TrajectoryPlanner
            from backend.database.models import DestinationModel
            from sqlalchemy import select
            from backend.database.connection import SessionLocal

            planner = await TrajectoryPlanner.load_from_redis()
            target_distance = 1000000.0
            if SessionLocal:
                try:
                    async with connection.SessionLocal() as db:
                        stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
                        res = await db.execute(stmt)
                        dest = res.scalars().first()
                        if dest:
                            target_distance = dest.avg_distance_km
                except Exception as e:
                    print(f"[Engine] DB error loading target distance: {e}")

            # Synchronize simulator parameters to ensure we have the latest trajectory values
            await self.sync_with_trajectory()

            outputs = planner.calculate(target_distance)
            required_fuel_kg = outputs["total_fuel_loaded"]
            # Use the simulator's fuel_capacity which was set by sync_with_trajectory()
            # to match the actual total fuel loaded (main + backup + emergency tanks).
            # Previously this used planner.fuel_capacity (a small default like 30,000 kg)
            # which is not the actual fuel available in the simulator's tanks.
            available_fuel_kg = self.fuel_capacity

            if available_fuel_kg < required_fuel_kg:
                msg = f"MISSION REJECTED: Insufficient Fuel. Required: {required_fuel_kg:,.0f} kg, Available: {available_fuel_kg:,.0f} kg"
                await self.log_event("ERROR", msg)
                return {"status": "error", "message": msg}

            self.reset_state()
            await self.sync_with_trajectory()
            self.state = "Launch"
            self.launch_time = datetime.utcnow()

            await self.log_event("INFO", f"Mission Initialized on {self.difficulty} Mode - Engine Ignition Command")
            await self.log_event("INFO", f"Trajectory Assessment: Distance = {self.target_distance:,.0f} km")
            
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
            
        return {"status": "success", "message": "Mission started/resumed", "state": self.state}

    async def pause(self):
        if self.is_active:
            self.is_active = False
            await self.log_event("INFO", "Simulation paused")
            await self.flush_buffers_to_db(force=True)
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
        await self.sync_with_trajectory()
        
        # Wipe dynamic databases
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    from backend.database.connection import clear_transaction_tables
                    await clear_transaction_tables(db)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Failed to clear tables on reset: {e}")

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

    async def process_pending_outcome_checks(self):
        if not hasattr(self, 'pending_outcome_checks'):
            self.pending_outcome_checks = []
        
        remaining_checks = []
        for check in self.pending_outcome_checks:
            check["ticks_remaining"] -= 1
            if check["ticks_remaining"] <= 0:
                # Evaluate prediction accuracy
                actual_success = self.success_probability
                predicted_success = check["predicted_success"]
                pred_err = abs(predicted_success - actual_success)
                pred_accuracy = max(0.0, min(1.0, 1.0 - (pred_err / 100.0)))
                
                # Save to mission_experiences
                if connection.SessionLocal:
                    try:
                        async with connection.SessionLocal() as db:
                            exp = MissionExperienceModel(
                                timestamp=datetime.utcnow(),
                                situation=f"Mitigated {check['event_type']} via {check['action_key']}",
                                state_snapshot=check["state_snapshot"],
                                active_events=check["active_events"],
                                chosen_action=check["action_key"],
                                expected_outcome=json.dumps({"success_probability": round(predicted_success, 1)}),
                                actual_outcome=json.dumps({"success_probability": round(actual_success, 1)}),
                                success_score=round(actual_success, 1),
                                mission_result="SUCCESS" if self.state == "Completed" or actual_success > 50.0 else "FAILURE"
                            )
                            db.add(exp)
                            
                            # Log to AutonomyMetricsModel
                            metric = AutonomyMetricsModel(
                                timestamp=datetime.utcnow(),
                                decision_accuracy=0.9 if actual_success > 60 else 0.5,
                                prediction_accuracy=round(pred_accuracy, 3),
                                success_rate=0.95 if self.state == "Completed" else 0.8,
                                risk_reduction=round(max(0.0, check["initial_success_probability"] - self.risk_score), 1),
                                resource_efficiency=round(self.fuel / 100.0, 2),
                                autonomy_level=self.autonomy_level,
                                maturity_index=round(self.autonomy_level * 0.2 + pred_accuracy * 0.8, 2)
                            )
                            await db.commit()

                            # Hook Phase 3.5 LLM outcome evaluator
                            try:
                                from backend.agent.llm_reasoning import llm_reasoning_engine
                                await llm_reasoning_engine.update_actual_outcomes(
                                    action_key=check["action_key"],
                                    initial_success=check["initial_success_probability"],
                                    final_success=actual_success,
                                    initial_risk=check.get("initial_risk", 15.0),
                                    final_risk=self.risk_score
                                )
                            except Exception as llm_ex:
                                print(f"[LLM Outcome Hook Error] {llm_ex}")
                    except Exception as ex:
                        print(f"[DB ERROR] Pending check database write failed: {ex}")
            else:
                remaining_checks.append(check)
        self.pending_outcome_checks = remaining_checks

    async def save_mission_experience_summary(self, result: str):
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    exp = MissionExperienceModel(
                        timestamp=datetime.utcnow(),
                        situation=f"Mission finished in state {self.state} with result {result}",
                        state_snapshot=self.get_telemetry_data().model_dump_json(),
                        active_events=json.dumps([e["event_type"] for e in self.active_events]),
                        chosen_action="Mission End",
                        expected_outcome=json.dumps({"success_probability": 100.0 if result == "SUCCESS" else 0.0}),
                        actual_outcome=json.dumps({"success_probability": self.success_probability}),
                        success_score=round(self.success_probability, 1),
                        mission_result=result
                    )
                    db.add(exp)
                    
                    # Add an autonomy metrics summary
                    metric = AutonomyMetricsModel(
                        timestamp=datetime.utcnow(),
                        decision_accuracy=0.95 if result == "SUCCESS" else 0.40,
                        prediction_accuracy=0.90,
                        success_rate=1.0 if result == "SUCCESS" else 0.0,
                        risk_reduction=50.0 if result == "SUCCESS" else 0.0,
                        resource_efficiency=round(self.fuel / 100.0, 2),
                        autonomy_level=self.autonomy_level,
                        maturity_index=round(self.autonomy_level * 0.2 + 0.72, 2)
                    )
                    db.add(metric)
                    
                    await db.commit()
                    print(f"[DB] Saved mission end experience summary: {result}")
            except Exception as e:
                print(f"[DB ERROR] Mission experience summary save failed: {e}")

    async def run_simulation_loop(self):
        dt = 1.0
        try:
            while self.is_active:
                await self.update_physics(dt)
                await self.update_lifecycle_phase()
                await self.process_scenario_ticks(dt)
                # DISABLED: await self.check_event_generator(dt)  — No automatic anomaly generation
                await self.calculate_success_scores()
                await self.calculate_risk()
                await self.calculate_resilience_scores()
                
                # Check for autonomous recovery trigger (Feature 11)
                if self.risk_score > 80.0:
                    await self.trigger_autonomous_recovery()
                    
                await self.save_state_to_storages()
                await self.broadcast_telemetry()
                await self.append_snapshot_memory()
                await self.process_pending_outcome_checks()

                # Trigger autonomous agent decisions if active events exist and autonomy > 0
                if self.autonomy_level > 0 and not self.agent_workflow_running:
                    unresolved = [e for e in self.active_events if e.get("status") not in ["MITIGATING", "RESOLVED"]]
                    if unresolved:
                        self.agent_workflow_running = True
                        async def run_workflow():
                            try:
                                await self.trigger_agent_decision_workflow()
                            finally:
                                self.agent_workflow_running = False
                        asyncio.create_task(run_workflow())

                self.tick_counter += 1
                await self.flush_buffers_to_db()

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.log_event("ERROR", f"Simulation engine exception: {e}")

    async def trigger_agent_decision_workflow(self):
        unresolved_events = [e for e in self.active_events if e.get("status") not in ["MITIGATING", "RESOLVED"]]
        if not unresolved_events:
            return

        try:
            from backend.agent.langgraph import graph_orchestrator
            telemetry = self.get_telemetry_data().model_dump()
            decisions = await graph_orchestrator.run_decision_workflow(
                telemetry=telemetry,
                active_events=unresolved_events,
                action_options=self.action_options,
                difficulty=self.difficulty,
                autonomy_level=self.autonomy_level
            )
            for d in decisions:
                event_id = d["event_id"]
                chosen_action = d["chosen_action"]
                
                # Autonomy level checks for execution
                should_execute = False
                if self.autonomy_level == 4:
                    should_execute = True
                elif self.autonomy_level == 3:
                    # Classify if safe
                    is_safe = chosen_action not in ["fuel_leak_ignore", "solar_storm_ignore", "fuel_leak_emergency_shutdown"]
                    if is_safe:
                        should_execute = True
                        
                if should_execute:
                    await self.execute_action(event_id, chosen_action)
        except Exception as e:
            print(f"[Autonomy Error] Decision workflow failed: {e}")

    async def update_physics(self, dt: float):
        # We need TrajectoryPlanner to get the parameters
        from backend.trajectory.planner import TrajectoryPlanner
        planner = await TrajectoryPlanner.load_from_redis()
        
        # Load destination target distance from DB
        from backend.database.models import DestinationModel
        from sqlalchemy import select
        from backend.database.connection import SessionLocal
        
        target_distance = 1000000.0
        if SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
                    res = await db.execute(stmt)
                    dest = res.scalars().first()
                    if dest:
                        target_distance = dest.avg_distance_km
            except Exception as e:
                print(f"[Engine] DB error loading target distance: {e}")
        
        self.destination = planner.destination
        if getattr(self, "fuel_capacity", 0.0) <= 0.0:
            self.fuel_capacity = getattr(self, "fuel_required", planner.fuel_capacity) or planner.fuel_capacity
        self.payload_mass = planner.payload_mass
        self.cruise_speed = planner.cruise_speed
        self.engine_thrust = planner.engine_thrust
        
        # Calculate nominal travel time
        outputs = planner.calculate(target_distance)
        nominal_travel_time_seconds = outputs["travel_time_h"] * 3600.0
        
        # Initialize speed_multiplier if not exists
        if getattr(self, "speed_multiplier", None) is None:
            self.speed_multiplier = 1.0        # Initialize fuel tanks if not setup
        if getattr(self, "initial_main_fuel", None) is None:
            self.initial_main_fuel = outputs["required_mission_fuel"]
            self.initial_backup_fuel = outputs["reserve_fuel"]
            self.initial_emergency_fuel = outputs["emergency_fuel"]
            
            self.main_fuel = self.initial_main_fuel
            self.backup_fuel = self.initial_backup_fuel
            self.emergency_fuel = self.initial_emergency_fuel
            
            self.fuel_mass = outputs["total_fuel_loaded"]
            self.fuel_capacity = outputs["total_fuel_loaded"]
            self.fuel_required = outputs["fuel_required_kg"]

        virtual_dt = dt * self.speed_multiplier
        
        # Substep integration for numerical stability and consistency
        # Max substep size is 1.0 second
        max_substep = 1.0
        if virtual_dt > max_substep:
            num_substeps = math.ceil(virtual_dt / max_substep)
            substep_dt = virtual_dt / num_substeps
        else:
            num_substeps = 1
            substep_dt = virtual_dt

        self.burn_rate_kg_s = 0.0

        for _ in range(num_substeps):
            if self.distance >= self.target_distance:
                break
            # Crew oxygen decay scaled by Life Support performance (with a 2x safety margin factor)
            perf_life = self.subsystems["Life Support"]["performance"]
            base_depletion_rate = (100.0 / nominal_travel_time_seconds) * 0.5
            difficulty_factor = {"Easy": 0.5, "Normal": 1.0, "Hard": 1.5, "Extreme": 2.2}[self.difficulty]
            oxygen_decay = base_depletion_rate * difficulty_factor * (2.0 - perf_life) * substep_dt
            self.oxygen = max(0.0, self.oxygen - oxygen_decay)
            
            # Engine propulsion physics (scaled by Propulsion performance)
            perf_prop = self.subsystems["Propulsion"]["performance"]
            effective_thrust_kn = self.engine_thrust * perf_prop
            
            # Check active anomalies that impact propulsion/distance/fuel
            fuel_leak_active = any(e["event_type"] == "Fuel Leak" for e in self.active_events)
            thruster_failure_active = any(e["event_type"] == "Thruster Failure" for e in self.active_events)
            nav_drift_active = any(e["event_type"] == "Navigation Drift" for e in self.active_events)
            
            if thruster_failure_active:
                effective_thrust_kn *= 0.7

            # Determine if engines are firing in this phase
            # Deceleration physics
            # Time to decelerate from self.velocity to 0.1 km/s: t = (v - 0.1) / a
            # a = (thrust_force / mass) / 1000.0 km/s^2
            # Calculate dynamic acceleration available for deceleration
            inertia_fuel_mass_decel = min(self.fuel_mass, 50000.0)
            total_mass_decel = self.dry_mass + self.payload_mass + inertia_fuel_mass_decel
            a_decel_calc = ((effective_thrust_kn * 1000.0) / total_mass_decel) / 1000.0 if total_mass_decel > 0 else 0.01
            if a_decel_calc <= 0.0:
                a_decel_calc = 0.001
                
            dist_rem = max(0.0, self.target_distance - self.distance)
            current_vel = self.velocity
            target_vel = 0.1
            
            if current_vel > target_vel:
                t_decel_needed = (current_vel - target_vel) / a_decel_calc
                d_decel_needed = 0.5 * (current_vel + target_vel) * t_decel_needed
            else:
                d_decel_needed = 0.0

            is_decel_phase = self.state in ["Approach", "Landing / Deployment"]
            is_decel_burning = is_decel_phase and (dist_rem <= d_decel_needed)
            
            engines_firing = (self.state in ["Launch", "Orbit Insertion", "Course Correction"]) or is_decel_burning
            self.thrust_force = (effective_thrust_kn * 1000.0) if engines_firing else 0.0 # in Newtons

            # Acceleration a = F / m
            inertia_fuel_mass = min(self.fuel_mass, 50000.0)
            total_mass = self.dry_mass + self.payload_mass + inertia_fuel_mass
            self.a = (self.thrust_force / total_mass) / 1000.0 # in km/s^2

            await self.process_active_event_impacts(substep_dt)

            # Velocity integration and caps
            effective_cruise_speed = self.cruise_speed
            if thruster_failure_active:
                effective_cruise_speed *= 0.8

            if self.state in ["Launch", "Orbit Insertion", "Course Correction"]:
                self.velocity = min(effective_cruise_speed, max(0.0, self.velocity + self.a * substep_dt))
            elif self.state in ["Cruise", "Scientific Operations"]:
                self.velocity = effective_cruise_speed
            elif self.state in ["Approach", "Landing / Deployment"]:
                if dist_rem <= d_decel_needed:
                    # Decelerating
                    self.velocity = max(0.1, self.velocity - self.a * substep_dt)
                else:
                    # Coasting during approach segment until decel point
                    self.velocity = effective_cruise_speed
            else: # Pre-Launch, Completed, Emergency
                self.velocity = 0.0
                self.a = 0.0

            # Distance integration
            if self.state != "Pre-Launch":
                self.distance = min(self.target_distance, self.distance + self.velocity * substep_dt)
            else:
                self.distance = 0.0

            # Navigation performance scales coordinate drift error
            perf_nav = self.subsystems["Navigation"]["performance"]
            self.position_error += (0.5 * (1.0 - perf_nav)) * substep_dt

            # Target distance affected by Navigation Drift
            if nav_drift_active:
                self.target_distance = target_distance * 1.15
            else:
                self.target_distance = target_distance

            # Distance Remaining & Mission Progress
            distance_remaining = max(0.0, self.target_distance - self.distance)
            self.distance_remaining = distance_remaining
            self.mission_progress = min(100.0, (self.distance / self.target_distance) * 100.0)

            # Fuel consumption
            if engines_firing:
                isp = 300.0
                g0 = 9.80665
                burn_rate_kg_s = (effective_thrust_kn * 1000.0) / (isp * g0)
            else:
                burn_rate_kg_s = 0.0
                
            if fuel_leak_active:
                burn_rate_kg_s += 0.5
                
            self.burn_rate_kg_s = burn_rate_kg_s
            fuel_consumed_kg = burn_rate_kg_s * substep_dt
            
            # Tank selection drawing sequence priority
            emergency_triggered = (self.risk_score > 50.0) or \
                                   any(e.get("status") == "MITIGATING" for e in self.active_events) or \
                                   (self.state == "Emergency")

            backup_triggered = any(e["event_type"] in ["Fuel Leak", "Navigation Drift", "Sensor Malfunction", "Trajectory Deviation", "Position Estimation Error"] for e in self.active_events)

            if emergency_triggered:
                draw_order = ["emergency", "backup", "main"]
            elif backup_triggered:
                draw_order = ["backup", "main", "emergency"]
            else:
                draw_order = ["main", "backup", "emergency"]

            rem_consumption = fuel_consumed_kg
            for tank in draw_order:
                if rem_consumption <= 0:
                    break
                if tank == "main":
                    if self.main_fuel > 0:
                        deduct = min(self.main_fuel, rem_consumption)
                        self.main_fuel -= deduct
                        rem_consumption -= deduct
                elif tank == "backup":
                    if self.backup_fuel > 0:
                        deduct = min(self.backup_fuel, rem_consumption)
                        self.backup_fuel -= deduct
                        rem_consumption -= deduct
                elif tank == "emergency":
                    if self.emergency_fuel > 0:
                        deduct = min(self.emergency_fuel, rem_consumption)
                        self.emergency_fuel -= deduct
                        rem_consumption -= deduct

            self.fuel_mass = max(0.0, self.main_fuel + self.backup_fuel + self.emergency_fuel)
            self.fuel = (self.fuel_mass / self.fuel_capacity) * 100.0

            # Mission Duration
            self.duration += substep_dt

        # Update 3D position coordinates based on final integrated distance
        angle = self.distance * 0.00015
        radius = 20.0 + (self.mission_progress * 0.4)
        
        self.position["x"] = radius * math.cos(angle) + (self.angular_velocity["x"] * 10)
        self.position["y"] = 4.0 * math.sin(angle * 2.0) + (self.angular_velocity["y"] * 10)
        self.position["z"] = radius * math.sin(angle) + (self.angular_velocity["z"] * 10)

        # ETA time
        seconds_remaining = self.distance_remaining / self.velocity if self.velocity > 0.0 else self.distance_remaining / self.cruise_speed
        self.eta_time = ist_now() + timedelta(seconds=seconds_remaining)

        # Success / Failure conditions evaluation
        failed = False
        failure_cause = ""
        
        if self.fuel <= 0.0 or self.fuel_mass <= 0.0:
            failed = True
            failure_cause = "Fuel Exhaustion"
        elif self.oxygen <= 0.0:
            failed = True
            failure_cause = "Life Support Failure (Oxygen Depleted)"
        elif self.subsystems["Propulsion"]["health"] <= 0.0:
            failed = True
            failure_cause = "Critical Subsystem Failure (Propulsion)"
        elif self.subsystems["Power"]["health"] <= 0.0:
            failed = True
            failure_cause = "Critical Subsystem Failure (Power Grid)"
        elif self.subsystems["Life Support"]["health"] <= 0.0:
            failed = True
            failure_cause = "Critical Subsystem Failure (Life Support System)"
        elif self.duration >= 1.5 * nominal_travel_time_seconds:
            failed = True
            failure_cause = "Mission Timeout (Trajectory Over-drift)"

        if failed:
            self.state = "Emergency"
            self.is_active = False
            self.velocity = 0.0
            self.a = 0.0
            
            summary = {
                "distance_travelled": float(self.distance),
                "avg_velocity": float(self.distance / (self.duration / 3600.0) if self.duration > 0 else 0.0),
                "fuel_efficiency": float(self.distance / (self.fuel_capacity - self.fuel_mass) if (self.fuel_capacity - self.fuel_mass) > 0 else 0.0),
                "agent_decisions": self.agent_decisions,
                "recovery_actions": self.recovery_actions,
                "mission_outcome": "FAILURE"
            }
            
            await self.log_event("ERROR", f"MISSION FAILURE: {failure_cause}")
            await self.update_db_objectives(status="FAILED")
            await self.save_mission_experience_summary(result="FAILURE")
            
            backup_pct = (self.backup_fuel / self.initial_backup_fuel) * 100.0 if getattr(self, "initial_backup_fuel", 0) > 0 else 0.0
            emergency_pct = (self.emergency_fuel / self.initial_emergency_fuel) * 100.0 if getattr(self, "initial_emergency_fuel", 0) > 0 else 0.0

            # Broadcast Mission Failure
            await manager.broadcast_json({
                "type": "MISSION_FAILED",
                "data": {
                    "failure_cause": failure_cause,
                    "distance_remaining": float(distance_remaining),
                    "fuel_remaining_kg": float(self.fuel_mass),
                    "fuel_remaining_pct": float(self.fuel),
                    "backup_fuel_pct": float(max(0.0, min(100.0, backup_pct))),
                    "emergency_fuel_pct": float(max(0.0, min(100.0, emergency_pct))),
                    "mission_progress": float(self.mission_progress),
                    "summary": summary
                }
            })
            
        elif self.distance >= self.target_distance:
            # Reached destination, check success parameters
            fuel_reserve_ok = self.fuel >= 5.0
            systems_ok = (
                self.subsystems["Propulsion"]["health"] > 10.0 and
                self.subsystems["Power"]["health"] > 10.0 and
                self.subsystems["Life Support"]["health"] > 10.0
            )
            
            if fuel_reserve_ok and systems_ok:
                self.state = "Completed"
                self.is_active = False
                self.velocity = 0.0
                self.a = 0.0
                
                science_score = self.subsystems["Science Systems"]["performance"] * 100.0
                mission_score = (self.health * 0.4) + (self.fuel * 0.4) + (max(0.0, 100.0 - self.position_error) * 0.2)
                
                summary = {
                    "distance_travelled": float(self.distance),
                    "avg_velocity": float(self.distance / (self.duration / 3600.0) if self.duration > 0 else 0.0),
                    "fuel_efficiency": float(self.distance / (self.fuel_capacity - self.fuel_mass) if (self.fuel_capacity - self.fuel_mass) > 0 else 0.0),
                    "agent_decisions": self.agent_decisions,
                    "recovery_actions": self.recovery_actions,
                    "mission_outcome": "SUCCESS"
                }
                
                await self.log_event("INFO", "Mission Completed - Hail Mary has achieved stable orbit!")
                await self.update_db_objectives(status="ACHIEVED")
                await self.save_mission_experience_summary(result="SUCCESS")
                
                backup_used = ((self.initial_backup_fuel - self.backup_fuel) / self.initial_backup_fuel * 100.0) if self.initial_backup_fuel > 0 else 0.0

                # Broadcast Mission Success
                await manager.broadcast_json({
                    "type": "MISSION_SUCCESS",
                    "data": {
                        "destination": self.destination,
                        "duration": float(self.duration),
                        "fuel_remaining_pct": float(self.fuel),
                        "backup_fuel_used_pct": float(max(0.0, min(100.0, backup_used))),
                        "commander_decisions": len(self.recovery_actions),
                        "recovery_actions": len(self.agent_decisions),
                        "science_score": float(science_score),
                        "mission_score": float(mission_score),
                        "summary": summary
                    }
                })
            else:
                # Failed due to criteria upon reaching destination
                self.state = "Emergency"
                self.is_active = False
                self.velocity = 0.0
                self.a = 0.0
                
                cause = "Fuel reserve depleted at destination" if not fuel_reserve_ok else "Critical system failures at destination"
                summary = {
                    "distance_travelled": float(self.distance),
                    "avg_velocity": float(self.distance / (self.duration / 3600.0) if self.duration > 0 else 0.0),
                    "fuel_efficiency": float(self.distance / (self.fuel_capacity - self.fuel_mass) if (self.fuel_capacity - self.fuel_mass) > 0 else 0.0),
                    "agent_decisions": self.agent_decisions,
                    "recovery_actions": self.recovery_actions,
                    "mission_outcome": "FAILURE"
                }
                
                await self.log_event("ERROR", f"MISSION FAILURE AT DESTINATION: {cause}")
                await self.update_db_objectives(status="FAILED")
                await self.save_mission_experience_summary(result="FAILURE")
                
                backup_pct = (self.backup_fuel / self.initial_backup_fuel) * 100.0 if getattr(self, "initial_backup_fuel", 0) > 0 else 0.0
                emergency_pct = (self.emergency_fuel / self.initial_emergency_fuel) * 100.0 if getattr(self, "initial_emergency_fuel", 0) > 0 else 0.0

                await manager.broadcast_json({
                    "type": "MISSION_FAILED",
                    "data": {
                        "failure_cause": cause,
                        "distance_remaining": float(distance_remaining),
                        "fuel_remaining_kg": float(self.fuel_mass),
                        "fuel_remaining_pct": float(self.fuel),
                        "backup_fuel_pct": float(max(0.0, min(100.0, backup_pct))),
                        "emergency_fuel_pct": float(max(0.0, min(100.0, emergency_pct))),
                        "mission_progress": float(self.mission_progress),
                        "summary": summary
                    }
                })

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
            prop_speed = event.get("propagation_speed", 1.0)
            
            # Mitigation timers execution
            if status == "MITIGATING":
                event["mitigation_timer"] -= dt
                damage_scale = 0.5  # mitigations reduce system damages by 50%
                if event["mitigation_timer"] <= 0:
                    resolved_indices.append(idx)
                    continue
            else:
                damage_scale = 1.0

            # Dynamic impact multipliers application from Phase 2.8 Custom / Templates
            impact_mults = event.get("impact_multipliers", {})
            if isinstance(impact_mults, str):
                try:
                    impact_mults = json.loads(impact_mults)
                except:
                    impact_mults = {}
            
            if impact_mults:
                for var, val in impact_mults.items():
                    # val is generally negative for decays
                    decay_rate = val * diff_factor * damage_scale * prop_speed * dt
                    if var == "fuel":
                        # Convert percentage decrement to mass decrement
                        mass_deduct = (abs(decay_rate) / 100.0) * self.fuel_capacity
                        # Deduct from physical tanks using active draw sequence
                        rem_consumption = mass_deduct
                        emergency_triggered = (self.risk_score > 50.0) or \
                                               any(e.get("status") == "MITIGATING" for e in self.active_events) or \
                                               (self.state == "Emergency")
                        backup_triggered = any(e["event_type"] in ["Fuel Leak", "Navigation Drift", "Sensor Malfunction", "Trajectory Deviation", "Position Estimation Error"] for e in self.active_events)
                        if emergency_triggered:
                            draw_order = ["emergency", "backup", "main"]
                        elif backup_triggered:
                            draw_order = ["backup", "main", "emergency"]
                        else:
                            draw_order = ["main", "backup", "emergency"]

                        for tank in draw_order:
                            if rem_consumption <= 0:
                                break
                            if tank == "main":
                                if self.main_fuel > 0:
                                    deduct = min(self.main_fuel, rem_consumption)
                                    self.main_fuel -= deduct
                                    rem_consumption -= deduct
                            elif tank == "backup":
                                if self.backup_fuel > 0:
                                    deduct = min(self.backup_fuel, rem_consumption)
                                    self.backup_fuel -= deduct
                                    rem_consumption -= deduct
                            elif tank == "emergency":
                                if self.emergency_fuel > 0:
                                    deduct = min(self.emergency_fuel, rem_consumption)
                                    self.emergency_fuel -= deduct
                                    rem_consumption -= deduct
                        self.fuel_mass = max(0.0, self.main_fuel + self.backup_fuel + self.emergency_fuel)
                        self.fuel = (self.fuel_mass / self.fuel_capacity) * 100.0
                        affected_subsystems.add("Propulsion")
                    elif var == "power":
                        self.power = max(10.0, self.power + decay_rate)
                        affected_subsystems.add("Power")
                    elif var == "oxygen":
                        self.oxygen = max(0.0, self.oxygen + decay_rate)
                        affected_subsystems.add("Life Support")
                    elif var == "health":
                        self.health = max(0.0, self.health + decay_rate)
                    elif var == "position_error":
                        self.position_error = max(0.0, self.position_error + abs(decay_rate))
                        affected_subsystems.add("Navigation")
                    elif var == "temperature":
                        self.temperature = max(-100.0, min(150.0, self.temperature + decay_rate))
                        affected_subsystems.add("Thermal Control")
                    elif var == "velocity":
                        self.velocity = max(0.0, self.velocity + decay_rate)
                        affected_subsystems.add("Propulsion")
                    elif var.startswith("subsystems."):
                        sub_name = var.split(".")[1]
                        if sub_name in self.subsystems:
                            self.subsystems[sub_name]["health"] = max(0.0, self.subsystems[sub_name]["health"] + decay_rate)
                            affected_subsystems.add(sub_name)
            else:
                # Fallback to hardcoded events mapping
                if event_type == "Fuel Leak":
                    affected_subsystems.add("Propulsion")
                    self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 1.2 * diff_factor * damage_scale * dt)
                    leak_rate = 0.3 * diff_factor * damage_scale
                    
                    # Convert percentage leak rate to mass decrement in kg
                    mass_deduct = (leak_rate * dt / 100.0) * self.fuel_capacity
                    rem_consumption = mass_deduct
                    emergency_triggered = (self.risk_score > 50.0) or \
                                           any(e.get("status") == "MITIGATING" for e in self.active_events) or \
                                           (self.state == "Emergency")
                    backup_triggered = any(e["event_type"] in ["Fuel Leak", "Navigation Drift", "Sensor Malfunction", "Trajectory Deviation", "Position Estimation Error"] for e in self.active_events)
                    if emergency_triggered:
                        draw_order = ["emergency", "backup", "main"]
                    elif backup_triggered:
                        draw_order = ["backup", "main", "emergency"]
                    else:
                        draw_order = ["main", "backup", "emergency"]

                    for tank in draw_order:
                        if rem_consumption <= 0:
                            break
                        if tank == "main":
                            if self.main_fuel > 0:
                                deduct = min(self.main_fuel, rem_consumption)
                                self.main_fuel -= deduct
                                rem_consumption -= deduct
                        elif tank == "backup":
                            if self.backup_fuel > 0:
                                deduct = min(self.backup_fuel, rem_consumption)
                                self.backup_fuel -= deduct
                                rem_consumption -= deduct
                        elif tank == "emergency":
                            if self.emergency_fuel > 0:
                                deduct = min(self.emergency_fuel, rem_consumption)
                                self.emergency_fuel -= deduct
                                rem_consumption -= deduct
                    self.fuel_mass = max(0.0, self.main_fuel + self.backup_fuel + self.emergency_fuel)
                    self.fuel = (self.fuel_mass / self.fuel_capacity) * 100.0
                elif event_type == "Power Fluctuation":
                    affected_subsystems.add("Power")
                    affected_subsystems.add("Navigation")
                    self.subsystems["Power"]["health"] = max(0.0, self.subsystems["Power"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                    self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 0.5 * diff_factor * damage_scale * dt)
                    self.power_decay_time += dt
                    decay_lambda = 0.012 * diff_factor * damage_scale
                    self.power = max(10.0, self.power_decay_start * math.exp(-decay_lambda * self.power_decay_time))
                elif event_type == "Solar Storm":
                    affected_subsystems.add("Power")
                    affected_subsystems.add("Communication")
                    self.subsystems["Power"]["health"] = max(0.0, self.subsystems["Power"]["health"] - 2.0 * diff_factor * damage_scale * dt)
                    self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 2.5 * diff_factor * damage_scale * dt)
                    self.power_decay_time += dt
                    decay_lambda = 0.012 * diff_factor * damage_scale
                    self.power = max(10.0, self.power_decay_start * math.exp(-decay_lambda * self.power_decay_time))
                    has_active_comm_fail = True
                elif event_type == "Communication Loss":
                    affected_subsystems.add("Communication")
                    self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 1.8 * diff_factor * damage_scale * dt)
                    has_active_comm_fail = True
                elif event_type == "Radiation Burst":
                    affected_subsystems.add("Life Support")
                    affected_subsystems.add("Science Systems")
                    self.subsystems["Life Support"]["health"] = max(0.0, self.subsystems["Life Support"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                    self.subsystems["Science Systems"]["health"] = max(0.0, self.subsystems["Science Systems"]["health"] - 1.2 * diff_factor * damage_scale * dt)
                elif event_type == "Navigation Drift":
                    affected_subsystems.add("Navigation")
                    self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 1.5 * diff_factor * damage_scale * dt)
                    self.position_error += random.uniform(0.2, 0.6) * diff_factor * damage_scale * dt
                    self.angular_velocity["x"] += random.uniform(-0.01, 0.01) * dt
                    self.angular_velocity["y"] += random.uniform(-0.01, 0.01) * dt
                elif event_type == "Thruster Failure":
                    affected_subsystems.add("Propulsion")
                    self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 2.5 * diff_factor * damage_scale * dt)
                    self.a *= 0.5
                    self.angular_velocity["z"] += random.uniform(-0.02, 0.02) * dt
                elif event_type == "Micrometeorite Impact":
                    affected_subsystems.add("Thermal Control")
                    affected_subsystems.add("Propulsion")
                    self.subsystems["Thermal Control"]["health"] = max(0.0, self.subsystems["Thermal Control"]["health"] - 3.0 * diff_factor * damage_scale * dt)
                    self.subsystems["Propulsion"]["health"] = max(0.0, self.subsystems["Propulsion"]["health"] - 1.0 * diff_factor * damage_scale * dt)
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
        # A. Propulsion degradation -> Thruster Failure
        if self.subsystems["Propulsion"]["health"] < 30.0 and not any(e["event_type"] == "Thruster Failure" for e in self.active_events):
            await self.trigger_cascade_event("Thruster Failure", "Propulsion degradation triggers asymmetric thruster feedback failure.")
            
        # B. Power degradation -> Power Fluctuation & degrades Comm/Nav
        if self.subsystems["Power"]["health"] < 30.0:
            if not any(e["event_type"] == "Power Fluctuation" for e in self.active_events):
                await self.trigger_cascade_event("Power Fluctuation", "Critical power grid depletion triggers systemic voltage oscillations.")
            self.subsystems["Communication"]["health"] = max(0.0, self.subsystems["Communication"]["health"] - 0.5 * dt)
            self.subsystems["Navigation"]["health"] = max(0.0, self.subsystems["Navigation"]["health"] - 0.5 * dt)

        # C. Navigation degradation -> Position Estimation Error / Nav Drift
        if self.subsystems["Navigation"]["health"] < 30.0 and not any(e["event_type"] == "Position Estimation Error" for e in self.active_events):
            await self.trigger_cascade_event("Position Estimation Error", "Critical navigation systems failure induces high Kalman filter drift.")

        # D. Life Support degradation -> Pressure Loss
        if self.subsystems["Life Support"]["health"] < 30.0 and not any(e["event_type"] == "Pressure Loss" for e in self.active_events):
            await self.trigger_cascade_event("Pressure Loss", "Structural microfractures trigger localized cabin compartment decompression.")

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
                    from backend.database.models import MissionEventModel
                    db_event = MissionEventModel(
                        event_type=event_type,
                        severity="HIGH",
                        timestamp=datetime.utcnow(),
                        description=description,
                        affected_system="Propulsion" if event_type in ["Thruster Failure", "Engine Failure"] else "Electrical Systems",
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
                    from backend.database.models import EventDependencyModel
                    parent_type = "Fuel Leak" if event_type in ["Thruster Failure", "Engine Failure"] else "Solar Storm"
                    dep = EventDependencyModel(
                        parent_event_type=parent_type,
                        child_event_type=event_type,
                        propagation_probability=1.0
                    )
                    db.add(dep)
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Dependency link failed: {e}")

        # Formulate root causes
        root_causes = [description]
        
        new_event = {
            "id": db_event_id or random.randint(10000, 99999),
            "event_type": event_type,
            "severity": "HIGH",
            "description": description,
            "affected_system": "Propulsion" if event_type in ["Thruster Failure", "Engine Failure"] else "Electrical Systems",
            "recommended_actions": "Activate backup Attitude Controller." if event_type == "Thruster Failure" else "Divert Deflectors.",
            "duration": random.uniform(20.0, 40.0),
            "status": "ACTIVE",
            "propagation_speed": 1.0,
            "probability": 1.0,
            "impact_multipliers": "{}",
            "trigger_time": 0.0,
            "root_causes": root_causes,
            "selected_root_cause": root_causes[0]
        }
        self.active_events.append(new_event)
        
        # Track timing
        self.recovery_start_times[new_event["id"]] = datetime.utcnow().timestamp()
        self.recovery_initial_metrics[new_event["id"]] = {
            "fuel": self.fuel,
            "power": self.power,
            "oxygen": self.oxygen,
            "health": self.health,
            "success_probability": self.success_probability,
            "risk_score": self.risk_score
        }

        # Broadcast WS Anomaly Injected for cascaded event
        await manager.broadcast_json({
            "type": "Anomaly Injected",
            "event_id": new_event["id"],
            "event_type": event_type,
            "severity": "HIGH",
            "system": new_event["affected_system"]
        })

    async def resolve_active_event(self, event: Dict[str, Any]):
        event_type = event["event_type"]
        e_id = event["id"]
        await self.log_event("INFO", f"Anomaly resolved: {event_type}")

        # Update Trajectory Planner active events on resolution
        mapped_event = None
        if event_type == "Fuel Leak":
            mapped_event = "fuel_leak"
        elif event_type == "Thruster Failure":
            mapped_event = "thruster_failure"
        elif event_type == "Navigation Drift":
            mapped_event = "navigation_drift"

        if mapped_event:
            try:
                from backend.trajectory.planner import TrajectoryPlanner
                from backend.database.connection import SessionLocal
                from backend.database.models import DestinationModel
                from sqlalchemy import select

                planner = await TrajectoryPlanner.load_from_redis()
                if mapped_event in planner.active_events:
                    planner.active_events.remove(mapped_event)
                    await planner.save_to_redis()
                    if SessionLocal:
                        async with SessionLocal() as db_session:
                            stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
                            res_db = await db_session.execute(stmt)
                            dest_row = res_db.scalars().first()
                            if dest_row:
                                outputs = planner.calculate(dest_row.avg_distance_km)
                                await manager.broadcast_json({
                                    "type": "TRAJECTORY_UPDATE",
                                    "data": {
                                        "inputs": planner.to_dict(),
                                        "outputs": outputs
                                    }
                                })
            except Exception as ex:
                print(f"[Trajectory Hook Error] Failed to update resolved event in planner: {ex}")

        # Compute recovery metrics
        now_ts = datetime.utcnow().timestamp()
        detect_t = 1.5  # default/mock detection delay seconds
        rec_t = 5.0     # default/mock recovery duration seconds
        
        if e_id in self.recovery_start_times:
            rec_t = round(now_ts - self.recovery_start_times[e_id], 1)
            
        initials = self.recovery_initial_metrics.get(e_id, {})
        init_health = initials.get("health", 100.0)
        damage_sustained = max(0.0, init_health - self.health)
        damage_prev = round(max(0.0, 25.0 - damage_sustained), 1)
        
        success_change = round(self.success_probability - initials.get("success_probability", 80.0), 1)
        risk_red = round(initials.get("risk_score", 0.0) - self.risk_score, 1)
        resource_pres = round(self.fuel - initials.get("fuel", self.fuel), 1)

        # Update global recovery efficiency running average
        prev_eff = self.recovery_efficiency
        new_eff = max(0.0, min(100.0, (damage_prev / 25.0) * 100.0))
        self.recovery_efficiency = round(0.7 * prev_eff + 0.3 * new_eff, 1)

        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    from backend.database.models import RecoveryMetricsModel
                    metric = RecoveryMetricsModel(
                        scenario_id=self.active_scenario["id"] if self.active_scenario else None,
                        timestamp=datetime.utcnow(),
                        detection_time=detect_t,
                        recovery_time=rec_t,
                        damage_prevented=damage_prev,
                        mission_success_change=success_change,
                        risk_reduction=risk_red,
                        resource_preservation=resource_pres
                    )
                    db.add(metric)
                    
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
                print(f"[DB ERROR] Anomaly resolution metrics save failed: {e}")

        # Update Redis recovery cache
        try:
            redis = await get_redis()
            await redis.set("hail_mary:test:recovery_metrics", json.dumps({
                "detection_time": detect_t,
                "recovery_time": rec_t,
                "damage_prevented": damage_prev,
                "risk_reduction": risk_red
            }))
        except Exception as e:
            print(f"[Redis ERROR] Recovery metrics caching failed: {e}")

        if event_type in ["Power Fluctuation", "Solar Storm"]:
            self.power_decay_start = self.power
            self.power_decay_time = 0.0
            
        if not any(e["event_type"] in ["Power Fluctuation", "Solar Storm"] for e in self.active_events):
            self.power = min(100.0, self.power + 5.0)

        # Broadcast WS events
        await manager.broadcast_json({
            "type": "Recovery Completed",
            "event_id": e_id,
            "event_type": event_type,
            "recovery_time": rec_t
        })
        
        await manager.broadcast_json({
            "type": "EVENT_RESOLVED",
            "event_id": event["id"],
            "event_type": event_type
        })

    async def check_event_generator(self, dt: float):
        # DISABLED: Automatic event generation removed.
        # Anomalies are only created via manual user injection.
        pass

    async def generate_random_event(self):
        # DISABLED: Automatic event generation removed.
        # Anomalies are only created via manual user injection.
        return


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
            risk_rec = RiskHistoryModel(
                timestamp=datetime.utcnow(),
                risk_score=self.risk_score,
                risk_level=self.risk_level
            )
            self.risk_write_buffer.append(risk_rec)

    async def save_state_to_storages(self):
        telemetry = self.get_telemetry_data()
        mission = self.get_mission_info()

        redis = await get_redis()
        await redis.set("hail_mary:telemetry", telemetry.model_dump_json())
        await redis.set("hail_mary:mission", mission.model_dump_json())

        if connection.SessionLocal:
            # Store historical telemetry to buffer
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
            self.telemetry_write_buffer.append(db_telemetry)
            
            # Store subsystem health logs to buffer
            for sub_name, sub_data in self.subsystems.items():
                sub_log = SubsystemHealthModel(
                    timestamp=datetime.utcnow(),
                    subsystem_name=sub_name,
                    health=sub_data["health"],
                    status=sub_data["status"],
                    risk_score=sub_data["risk"],
                    performance=sub_data["performance"]
                )
                self.subsystem_write_buffer.append(sub_log)

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
        
        # Save running snapshots to DB logs table buffer
        if connection.SessionLocal:
            mem_rec = MissionMemoryModel(
                timestamp=datetime.utcnow(),
                telemetry_snapshot=telemetry.model_dump_json(),
                active_events=json.dumps([e["event_type"] for e in self.active_events]),
                available_actions=json.dumps([a["action_key"] for e in self.active_events for a in self.action_options.get(e["event_type"], [])]),
                chosen_action=None,
                outcome=None
            )
            self.memory_write_buffer.append(mem_rec)

    async def broadcast_telemetry(self):
        telemetry = self.get_telemetry_data()
        mission = self.get_mission_info()
        
        # 1. Always broadcast TELEMETRY_TICK
        await manager.broadcast_json({
            "type": "TELEMETRY_TICK",
            "telemetry": telemetry.model_dump()
        })
        
        # 2. Check if mission state changed
        current_mission_state = {
            "state": mission.state,
            "duration": mission.duration,
            "risk_score": mission.risk_score,
            "risk_level": mission.risk_level
        }
        if current_mission_state != self.last_broadcast_state:
            self.last_broadcast_state = current_mission_state
            await manager.broadcast_json({
                "type": "MISSION_STATE",
                "mission": mission.model_dump()
            })
            
        # 3. Check if active events list changed
        current_events_hash = json.dumps([
            {"id": ev["id"], "status": ev.get("status")} 
            for ev in self.active_events
        ], sort_keys=True)
        
        if current_events_hash != self.last_active_events_hash:
            self.last_active_events_hash = current_events_hash
            await manager.broadcast_json({
                "type": "ACTIVE_EVENTS",
                "active_events": [
                    {k: v for k, v in ev.items() if k not in ["duration", "mitigation_timer"]} 
                    for ev in self.active_events
                ]
            })

    async def flush_buffers_to_db(self, force=False):
        if not force and self.tick_counter % 10 != 0:
            return

        # Pop items to avoid thread race conditions
        telemetry_items = self.telemetry_write_buffer
        self.telemetry_write_buffer = []
        
        subsystem_items = self.subsystem_write_buffer
        self.subsystem_write_buffer = []
        
        risk_items = self.risk_write_buffer
        self.risk_write_buffer = []
        
        memory_items = self.memory_write_buffer
        self.memory_write_buffer = []
        
        resilience_items = self.resilience_write_buffer
        self.resilience_write_buffer = []
        
        if not (telemetry_items or subsystem_items or risk_items or memory_items or resilience_items or force):
            return
            
        if not connection.SessionLocal:
            return

        async def do_flush():
            try:
                async with connection.SessionLocal() as db:
                    # Update active MissionModel details
                    mission = self.get_mission_info()
                    stmt = select(MissionModel).limit(1)
                    result = await db.execute(stmt)
                    db_mission = result.scalars().first()
                    if db_mission:
                        db_mission.state = mission.state
                        db_mission.duration = mission.duration
                        db_mission.launch_time = self.launch_time if self.launch_time else db_mission.launch_time
                    
                    if telemetry_items:
                        db.add_all(telemetry_items)
                    if subsystem_items:
                        db.add_all(subsystem_items)
                    if risk_items:
                        db.add_all(risk_items)
                    if memory_items:
                        db.add_all(memory_items)
                    if resilience_items:
                        db.add_all(resilience_items)
                        
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Async batch write failed: {e}")

        if force:
            await do_flush()
        else:
            asyncio.create_task(do_flush())

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
        target_event["mitigation_timer"] = 1.0  # takes 1 simulation tick to complete
        target_event["chosen_action"] = action_key
        
        # Record the decision or recovery action
        action_record = {
            "event": event_type,
            "action": action_key,
            "timestamp": ist_now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if getattr(self, "agent_workflow_running", False):
            self.agent_decisions.append(action_record)
        else:
            self.recovery_actions.append(action_record)
        
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

        # Record consensus
        await self.record_consensus(event_type, action_key)

        # Add to pending checks for 1 tick later verification
        if not hasattr(self, 'pending_outcome_checks'):
            self.pending_outcome_checks = []
        self.pending_outcome_checks.append({
            "ticks_remaining": 1,
            "action_key": action_key,
            "event_type": event_type,
            "initial_success_probability": self.success_probability,
            "initial_risk": self.risk_score,
            "predicted_success_delta": deltas.get("success_delta", 0.0),
            "predicted_success": min(100.0, max(0.0, self.success_probability + deltas.get("success_delta", 0.0))),
            "state_snapshot": self.get_telemetry_data().model_dump_json(),
            "active_events": json.dumps([e["event_type"] for e in self.active_events])
        })

        # Broadcast update over WS
        await self.log_event("INFO", f"Sandbox Action Executed: '{action_key}' - Mitigating event: '{event_type}'.")
        await manager.broadcast_json({
            "type": "ACTION_EXECUTED",
            "event_id": event_id,
            "action_key": action_key,
            "status": "MITIGATING",
            "predictions_deltas": deltas
        })
        await manager.broadcast_json({
            "type": "DECISION_EXECUTED",
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

    async def record_consensus(self, event_type: str, action_key: str):
        if not connection.SessionLocal:
            return
        from backend.database.models import ConsensusRecordModel
        # Specialists rating heuristics
        nav_rating = 0.95 if "backup" in action_key or "revector" in action_key else 0.40
        fuel_rating = 0.90 if "reduce_speed" in action_key or "shutdown" in action_key else 0.50
        safety_rating = 0.95 if "shield" in action_key or "seal" in action_key or "divert" in action_key else 0.30
        science_rating = 0.85 if "star_field" in action_key or "diagnostic" in action_key else 0.60
        
        pred_rating = 0.88
        lrn_rating = 0.85
        
        consensus_score = (nav_rating + fuel_rating + safety_rating + science_rating + pred_rating + lrn_rating) / 6.0 * 100.0
        
        try:
            async with connection.SessionLocal() as db:
                rec = ConsensusRecordModel(
                    timestamp=datetime.utcnow(),
                    decision_key=f"{event_type}_{action_key}",
                    nav_recommendation=f"Navigation: Suggests {action_key} (Rating: {nav_rating:.2f})",
                    fuel_recommendation=f"Fuel: Suggests {action_key} (Rating: {fuel_rating:.2f})",
                    safety_recommendation=f"Safety: Suggests {action_key} (Rating: {safety_rating:.2f})",
                    science_recommendation=f"Science: Suggests {action_key} (Rating: {science_rating:.2f})",
                    prediction_rating=pred_rating,
                    learning_rating=lrn_rating,
                    consensus_score=round(consensus_score, 1),
                    commander_override=False
                )
                db.add(rec)
                await db.commit()
                
                # Broadcast
                await manager.broadcast_json({
                    "type": "CONSENSUS_UPDATED",
                    "consensus_score": round(consensus_score, 1),
                    "decision_key": rec.decision_key
                })
        except Exception as e:
            print(f"[Ops Center] Failed to write consensus log: {e}")

    async def update_lifecycle_phase(self):
        if not self.is_active or self.state in ["Completed", "Emergency"]:
            return
            
        from backend.database.models import MissionTimelineModel
        old_phase = self.state
        progress = self.mission_progress
        
        if progress == 0.0:
            new_phase = "Pre-Launch"
        elif progress <= 5.0:
            new_phase = "Launch"
        elif progress <= 15.0:
            new_phase = "Orbit Insertion"
        elif progress <= 60.0:
            new_phase = "Cruise"
        elif progress <= 70.0:
            new_phase = "Course Correction"
        elif progress <= 85.0:
            new_phase = "Scientific Operations"
        elif progress <= 95.0:
            new_phase = "Approach"
        elif progress < 100.0:
            new_phase = "Landing / Deployment"
        else:
            new_phase = "Completed"
            
        if new_phase != old_phase and old_phase != "Emergency":
            self.state = new_phase
            await self.log_event("INFO", f"Mission Phase transition: {old_phase} -> {new_phase}")
            
            # Update matching timeline checkpoint in database to COMPLETED
            if connection.SessionLocal:
                try:
                    async with connection.SessionLocal() as db:
                        stmt = update(MissionTimelineModel).where(MissionTimelineModel.phase == old_phase).values(status="COMPLETED")
                        await db.execute(stmt)
                        await db.commit()
                except Exception as e:
                    print(f"[Ops Center] Failed to update timeline record: {e}")
                    
            # Broadcast WS event
            await manager.broadcast_json({
                "type": "PHASE_UPDATED",
                "phase": new_phase,
                "message": f"Spacecraft entered {new_phase} segment."
            })

    async def trigger_autonomous_recovery(self):
        # Prevent double recovery triggers
        if hasattr(self, "_recovery_active") and self._recovery_active:
            return
            
        self._recovery_active = True
        await self.log_event("WARNING", "CRITICAL RISK DETECTED (>80%)! Initiating Autonomous Recovery Protocol.")
        
        # Broadcast WS event
        await manager.broadcast_json({
            "type": "RECOVERY_ACTIVATED",
            "risk_score": round(self.risk_score, 1),
            "message": "Ops Center activated self-recovery sequences."
        })
        
        # 1. Evaluate strategies
        # Standard conservative plan is usually the safest under critical risk
        proposed = "Conservative"
        details = "Shuts down primary thrusters, diverts solar grids to life support systems and armor magnetic deflectors."
        
        # 2. Select and execute recovery
        old_risk = self.risk_score
        
        # Execute recovery corrections (resolve the active event or improve system health)
        await asyncio.sleep(2.0)
        
        if self.active_events:
            event_to_resolve = self.active_events[0]
            await self.log_event("INFO", f"Recovery Plan selected: {proposed}. Resolving {event_to_resolve['event_type']} via emergency backup bypass.")
            event_to_resolve["status"] = "MITIGATING"
            event_to_resolve["mitigation_timer"] = 1.0 # fast resolve
        else:
            await self.log_event("INFO", f"Recovery Plan selected: {proposed}. Recharging solar grids.")
            self.power = min(100.0, self.power + 30.0)
            
        # Re-evaluate risk
        self.health = min(100.0, self.health + 15.0)
        for sub in self.subsystems:
            self.subsystems[sub]["health"] = min(100.0, self.subsystems[sub]["health"] + 15.0)
            
        # Write record to database RecoveryActionModel
        if connection.SessionLocal:
            from backend.database.models import RecoveryActionModel
            try:
                async with connection.SessionLocal() as db:
                    rec = RecoveryActionModel(
                        timestamp=datetime.utcnow(),
                        initial_risk_score=old_risk,
                        proposed_strategy=proposed,
                        action_details=details,
                        outcome_details="Hull Armor patched, subsystems rebooted, solar grids stabilized.",
                        final_risk_score=round(self.risk_score * 0.5, 1), # half risk
                        success=True
                    )
                    db.add(rec)
                    await db.commit()
            except Exception as e:
                print(f"[Ops Center] Failed to log recovery action: {e}")
                
        await self.log_event("INFO", f"Autonomous Recovery completed. Risk mitigated to safe level.")
        self._recovery_active = False

    async def inject_anomaly(
        self,
        event_type: str,
        severity: str = "HIGH",
        duration: float = 30.0,
        affected_system: str = None,
        propagation_speed: float = 1.0,
        probability: float = 1.0,
        impact_multipliers: Dict[str, float] = None,
        trigger_time: float = 0.0
    ) -> int:
        # Resolve affected system and desc from registry templates if not provided
        tmpl = self.anomaly_templates.get(event_type, {})
        system = affected_system or tmpl.get("affected_system", "Diagnostics")
        desc = tmpl.get("desc", f"Manual anomaly alert: {event_type}")
        rec_action = tmpl.get("action", "Perform systems sweep.")
        
        # Merge or default multipliers
        mults = impact_multipliers or tmpl.get("multipliers", {})
        
        # Register standard action options on the fly if needed
        if event_type not in self.action_options:
            action_key_1 = f"{event_type.lower().replace(' ', '_')}_mitigate"
            action_key_2 = f"{event_type.lower().replace(' ', '_')}_ignore"
            self.action_options[event_type] = [
                {"action_key": action_key_1, "action_name": "Initiate Standard Mitigation", "description": f"Perform standard recovery actions to address {event_type}."},
                {"action_key": action_key_2, "action_name": "Ignore Threat", "description": "Observe and take no immediate action."}
            ]
            # Action predictions
            fuel_d, power_d = 0.0, 0.0
            for var, val in mults.items():
                if var == "fuel":
                    fuel_d = val * 2 - 2.0
                elif var == "power":
                    power_d = val * 2 - 2.0
            self.action_predictions[action_key_1] = {
                "fuel_delta": round(fuel_d, 1),
                "power_delta": round(power_d, 1),
                "risk_reduction": 80.0,
                "success_delta": 10.0
            }
            self.action_predictions[action_key_2] = {
                "fuel_delta": round(fuel_d * 5, 1),
                "power_delta": round(power_d * 5, 1),
                "risk_reduction": 0.0,
                "success_delta": -15.0
            }

        db_event_id = None
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    from backend.database.models import MissionEventModel
                    db_event = MissionEventModel(
                        event_type=event_type,
                        severity=severity,
                        timestamp=datetime.utcnow(),
                        description=desc,
                        affected_system=system,
                        probability=probability,
                        recommended_actions=rec_action,
                        resolved=False
                    )
                    db.add(db_event)
                    await db.flush()
                    db_event_id = db_event.id
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Manual injection save failed: {e}")

        # Formulate root causes dynamically
        root_causes = [desc]
        
        new_active_event = {
            "id": db_event_id or random.randint(10000, 99999),
            "event_type": event_type,
            "severity": severity,
            "description": desc,
            "affected_system": system,
            "recommended_actions": rec_action,
            "duration": duration,
            "status": "ACTIVE",
            "mitigation_timer": 0.0,
            "chosen_action": None,
            "propagation_speed": propagation_speed,
            "probability": probability,
            "impact_multipliers": json.dumps(mults) if isinstance(mults, dict) else mults,
            "trigger_time": trigger_time,
            "root_causes": root_causes,
            "selected_root_cause": root_causes[0]
        }
        
        self.active_events.append(new_active_event)
        
        # Track recovery timings
        now_ts = datetime.utcnow().timestamp()
        self.recovery_start_times[new_active_event["id"]] = now_ts
        self.recovery_initial_metrics[new_active_event["id"]] = {
            "fuel": self.fuel,
            "power": self.power,
            "oxygen": self.oxygen,
            "health": self.health,
            "success_probability": self.success_probability,
            "risk_score": self.risk_score
        }

        # Apply instant impact effects if any
        for var, val in mults.items():
            if var == "fuel" and val < 0:
                self.fuel = max(0.0, self.fuel + val * 5.0)
            elif var == "power" and val < 0:
                self.power = max(10.0, self.power + val * 5.0)

        # Broadcast WS event
        await self.log_event(severity, f"ANOMALY INJECTED: {event_type} - {desc}")
        await manager.broadcast_json({
            "type": "NEW_EVENT",
            "event": {
                "id": new_active_event["id"],
                "event_type": event_type,
                "severity": severity,
                "description": desc,
                "affected_system": system,
                "recommended_actions": rec_action,
                "status": "ACTIVE"
            }
        })
        
        # Broadcast specifically for the Testing Center
        await manager.broadcast_json({
            "type": "Anomaly Injected",
            "event_id": new_active_event["id"],
            "event_type": event_type,
            "severity": severity,
            "system": system
        })

        redis = await get_redis()
        await redis.set("hail_mary:active_events", json.dumps([
            {k: v for k, v in ev.items() if k not in ["duration", "mitigation_timer"]} 
            for ev in self.active_events
        ]))
        await redis.set("hail_mary:test:current_anomalies", json.dumps([e["event_type"] for e in self.active_events]))

        # Update Trajectory Planner active events on manual/automatic injection
        mapped_event = None
        if event_type == "Fuel Leak":
            mapped_event = "fuel_leak"
        elif event_type == "Thruster Failure":
            mapped_event = "thruster_failure"
        elif event_type == "Navigation Drift":
            mapped_event = "navigation_drift"

        if mapped_event:
            try:
                from backend.trajectory.planner import TrajectoryPlanner
                from backend.database.connection import SessionLocal
                from backend.database.models import DestinationModel
                from sqlalchemy import select

                planner = await TrajectoryPlanner.load_from_redis()
                if mapped_event not in planner.active_events:
                    planner.active_events.append(mapped_event)
                    await planner.save_to_redis()
                    if SessionLocal:
                        async with SessionLocal() as db_session:
                            stmt = select(DestinationModel).where(DestinationModel.name == planner.destination)
                            res_db = await db_session.execute(stmt)
                            dest_row = res_db.scalars().first()
                            if dest_row:
                                outputs = planner.calculate(dest_row.avg_distance_km)
                                await manager.broadcast_json({
                                    "type": "TRAJECTORY_UPDATE",
                                    "data": {
                                        "inputs": planner.to_dict(),
                                        "outputs": outputs
                                    }
                                })
            except Exception as ex:
                print(f"[Trajectory Hook Error] Failed to inject event in planner: {ex}")

        return new_active_event["id"]

    async def process_scenario_ticks(self, dt: float):
        if not self.active_scenario:
            return
            
        self.scenario_timer += dt
        
        # Trigger any timed events
        untriggered = [ev for ev in self.active_scenario["events"] if ev["id"] not in self.scenario_triggered_events]
        
        for ev in untriggered:
            if self.scenario_timer >= ev["trigger_time"]:
                self.scenario_triggered_events.add(ev["id"])
                
                # Ingest event variables
                mults = ev.get("impact_multipliers", {})
                if isinstance(mults, str):
                    try:
                        mults = json.loads(mults)
                    except:
                        mults = {}
                        
                await self.inject_anomaly(
                    event_type=ev["event_type"],
                    severity=ev["severity"],
                    duration=ev["duration"],
                    affected_system=ev["affected_system"],
                    propagation_speed=ev.get("propagation_speed", 1.0),
                    probability=ev.get("probability", 1.0),
                    impact_multipliers=mults,
                    trigger_time=ev["trigger_time"]
                )

        # Check if all scenario events have finished and resolved
        all_triggered = len(self.scenario_triggered_events) == len(self.active_scenario["events"])
        no_active = len(self.active_events) == 0
        
        if all_triggered and no_active:
            # Scenario completed!
            scen_name = self.active_scenario["name"]
            await self.log_event("INFO", f"TEST SCENARIO COMPLETED: {scen_name}. All systems stabilized.")
            
            # Save stress test benchmark summary
            await self.save_benchmark_result(scen_name)
            
            # Broadcast scenario completed
            await manager.broadcast_json({
                "type": "Scenario Completed",
                "scenario_name": scen_name,
                "resilience_score": self.resilience_score
            })
            
            # Clear active scenario
            self.active_scenario = None

    async def calculate_resilience_scores(self):
        # Calculate Survivability
        self.survivability_score = round(self.health, 1)
        
        # Calculate Adaptability
        self.adaptability_score = round(max(0.0, 100.0 - self.risk_score), 1)
        
        # Calculate System Stability (100 - standard deviation of subsystems health)
        import statistics
        sub_healths = [s["health"] for s in self.subsystems.values()]
        if len(sub_healths) > 1:
            try:
                std_dev = statistics.stdev(sub_healths)
            except:
                std_dev = 0.0
            self.system_stability = round(max(0.0, 100.0 - std_dev), 1)
        else:
            self.system_stability = 100.0
            
        # Calculate overall resilience score
        self.resilience_score = round(
            0.30 * self.survivability_score +
            0.30 * self.adaptability_score +
            0.20 * self.recovery_efficiency +
            0.20 * self.system_stability,
            1
        )
        
        # Save to DB ResilienceScoreModel
        if connection.SessionLocal:
            from backend.database.models import ResilienceScoreModel
            rec = ResilienceScoreModel(
                timestamp=datetime.utcnow(),
                resilience_score=self.resilience_score,
                adaptability_score=self.adaptability_score,
                survivability_score=self.survivability_score,
                recovery_efficiency=self.recovery_efficiency,
                system_stability=self.system_stability,
                overall_robustness=self.resilience_score
            )
            self.resilience_write_buffer.append(rec)
                
        # Cache in Redis
        redis = await get_redis()
        await redis.set("hail_mary:test:resilience_score", json.dumps({
            "resilience": self.resilience_score,
            "survivability": self.survivability_score,
            "adaptability": self.adaptability_score,
            "stability": self.system_stability,
            "recovery_efficiency": self.recovery_efficiency
        }))
        
        # Broadcast WS
        await manager.broadcast_json({
            "type": "Risk Updated",
            "resilience_score": self.resilience_score,
            "risk_score": self.risk_score
        })

    async def save_benchmark_result(self, scenario_name: str):
        if not connection.SessionLocal:
            return
            
        try:
            async with connection.SessionLocal() as db:
                from backend.database.models import BenchmarkResultModel, StressTestResultModel
                
                # Check active event names
                events_list = [ev["event_type"] for ev in self.active_events] or ["Solar Storm", "Fuel Leak"]
                injected = ", ".join(events_list)
                
                benchmark = BenchmarkResultModel(
                    timestamp=datetime.utcnow(),
                    scenario_name=scenario_name,
                    injected_event=injected,
                    subsystem_impact=json.dumps({k: v["health"] for k, v in self.subsystems.items()}),
                    mission_impact=json.dumps({
                        "fuel": self.fuel,
                        "power": self.power,
                        "oxygen": self.oxygen,
                        "health": self.health,
                        "success_probability": self.success_probability
                    }),
                    recovery_outcome="SUCCESS" if self.health > 40.0 else "CRITICAL_DAMAGE",
                    risk_evolution=json.dumps([round(self.risk_score, 1)]),
                    final_mission_state=self.state
                )
                db.add(benchmark)
                
                # Also save to stress test results
                stress = StressTestResultModel(
                    timestamp=datetime.utcnow(),
                    scenario_name=scenario_name,
                    num_events=len(events_list),
                    average_success_prob=self.success_probability,
                    average_risk=self.risk_score,
                    average_resource_loss=round(100.0 - self.fuel, 1),
                    average_recovery_time=15.0,  # mock avg recovery secs
                    details_json=json.dumps({"resilience_score": self.resilience_score})
                )
                db.add(stress)
                
                await db.commit()
                
                # Broadcast WS
                await manager.broadcast_json({
                    "type": "Benchmark Updated",
                    "scenario_name": scenario_name,
                    "success_probability": self.success_probability
                })
        except Exception as e:
            print(f"[DB ERROR] Benchmark save failed: {e}")

    async def start_preset_scenario(self, idx: int):
        presets = {
            1: {
                "name": "Solar Storm Emergency",
                "desc": "Simultaneous solar storm CME grids discharge and secondary panels failure.",
                "events": [
                    {"event_type": "Solar Storm", "severity": "CRITICAL", "duration": 40.0, "affected_system": "Power", "trigger_time": 0.0, "impact_multipliers": {"power": -1.5, "subsystems.Power": -2.0}},
                    {"event_type": "Power Failure", "severity": "HIGH", "duration": 30.0, "affected_system": "Power", "trigger_time": 5.0, "impact_multipliers": {"power": -2.0, "subsystems.Power": -3.0}}
                ]
            },
            2: {
                "name": "Deep Space Fuel Crisis",
                "desc": "Compounded Port tank valves leak and main thrusters bypass failures.",
                "events": [
                    {"event_type": "Fuel Leak", "severity": "HIGH", "duration": 45.0, "affected_system": "Propulsion", "trigger_time": 0.0, "impact_multipliers": {"fuel": -0.8, "subsystems.Propulsion": -1.5}},
                    {"event_type": "Thruster Failure", "severity": "HIGH", "duration": 35.0, "affected_system": "Propulsion", "trigger_time": 4.0, "impact_multipliers": {"subsystems.Propulsion": -3.0}}
                ]
            },
            3: {
                "name": "Communication Blackout",
                "desc": "Total high gain antenna carrier synchronization loss and Earth station drops.",
                "events": [
                    {"event_type": "Communication Loss", "severity": "CRITICAL", "duration": 50.0, "affected_system": "Communication", "trigger_time": 0.0, "impact_multipliers": {"subsystems.Communication": -3.0}},
                    {"event_type": "Signal Corruption", "severity": "HIGH", "duration": 30.0, "affected_system": "Communication", "trigger_time": 6.0, "impact_multipliers": {"subsystems.Communication": -1.5}}
                ]
            },
            4: {
                "name": "Navigation Failure",
                "desc": "Asymmetrical IMU drift combined with optical star trackers shutter faults.",
                "events": [
                    {"event_type": "Navigation Drift", "severity": "HIGH", "duration": 40.0, "affected_system": "Navigation", "trigger_time": 0.0, "impact_multipliers": {"subsystems.Navigation": -2.0, "position_error": 0.5}},
                    {"event_type": "Star Tracker Failure", "severity": "HIGH", "duration": 35.0, "affected_system": "Navigation", "trigger_time": 8.0, "impact_multipliers": {"subsystems.Navigation": -2.5, "position_error": 1.2}}
                ]
            },
            5: {
                "name": "Engine Catastrophic Failure",
                "desc": "Complete main combustion chamber cut and RCS attitude alignment loss.",
                "events": [
                    {"event_type": "Engine Failure", "severity": "CATASTROPHIC", "duration": 60.0, "affected_system": "Propulsion", "trigger_time": 0.0, "impact_multipliers": {"velocity": -1.2, "subsystems.Propulsion": -5.0}},
                    {"event_type": "Attitude Control Failure", "severity": "HIGH", "duration": 40.0, "affected_system": "Propulsion", "trigger_time": 5.0, "impact_multipliers": {"subsystems.Propulsion": -2.0, "position_error": 0.6}}
                ]
            },
            6: {
                "name": "Mars Landing Emergency",
                "desc": "Attitude jets failures, structural pressure leaks during entry decelerations.",
                "events": [
                    {"event_type": "Attitude Control Failure", "severity": "HIGH", "duration": 30.0, "affected_system": "Propulsion", "trigger_time": 0.0, "impact_multipliers": {"subsystems.Propulsion": -2.5, "position_error": 0.8}},
                    {"event_type": "Pressure Loss", "severity": "HIGH", "duration": 35.0, "affected_system": "Life Support", "trigger_time": 6.0, "impact_multipliers": {"oxygen": -2.0, "subsystems.Life Support": -3.0}}
                ]
            },
            7: {
                "name": "Life Support Crisis",
                "desc": "Cabin seal blowouts, CO2 saturated filters, and O2 drops.",
                "events": [
                    {"event_type": "Life Support Failure", "severity": "CRITICAL", "duration": 45.0, "affected_system": "Life Support", "trigger_time": 0.0, "impact_multipliers": {"oxygen": -3.0, "subsystems.Life Support": -5.0}},
                    {"event_type": "CO2 Filter Failure", "severity": "MEDIUM", "duration": 30.0, "affected_system": "Life Support", "trigger_time": 5.0, "impact_multipliers": {"oxygen": -1.0, "subsystems.Life Support": -1.5}}
                ]
            },
            8: {
                "name": "Perfect Storm",
                "desc": "Extreme scenario triggering storm, comm loss, fuel leak, and navigation failures.",
                "events": [
                    {"event_type": "Solar Storm", "severity": "CRITICAL", "duration": 50.0, "affected_system": "Power", "trigger_time": 0.0, "impact_multipliers": {"power": -1.5, "subsystems.Power": -2.0}},
                    {"event_type": "Communication Loss", "severity": "HIGH", "duration": 40.0, "affected_system": "Communication", "trigger_time": 4.0, "impact_multipliers": {"subsystems.Communication": -2.0}},
                    {"event_type": "Fuel Leak", "severity": "HIGH", "duration": 45.0, "affected_system": "Propulsion", "trigger_time": 10.0, "impact_multipliers": {"fuel": -0.5, "subsystems.Propulsion": -1.5}},
                    {"event_type": "Navigation Drift", "severity": "HIGH", "duration": 30.0, "affected_system": "Navigation", "trigger_time": 15.0, "impact_multipliers": {"subsystems.Navigation": -1.5, "position_error": 0.5}}
                ]
            },
            9: {
                "name": "Total Systems Failure",
                "desc": "Catastrophic cascade degrading all 7 onboard subsystems health metrics.",
                "events": [
                    {"event_type": "Power Failure", "severity": "CATASTROPHIC", "duration": 50.0, "affected_system": "Power", "trigger_time": 0.0, "impact_multipliers": {"power": -2.0, "subsystems.Power": -4.0}},
                    {"event_type": "Life Support Failure", "severity": "CATASTROPHIC", "duration": 50.0, "affected_system": "Life Support", "trigger_time": 2.0, "impact_multipliers": {"oxygen": -2.5, "subsystems.Life Support": -4.0}},
                    {"event_type": "Engine Failure", "severity": "CATASTROPHIC", "duration": 50.0, "affected_system": "Propulsion", "trigger_time": 4.0, "impact_multipliers": {"velocity": -1.0, "subsystems.Propulsion": -4.0}}
                ]
            },
            10: {
                "name": "Judge Demo Showcase",
                "desc": "Sequential Solar Storm, Comm Loss, and Meteorite Impact optimized for demo evaluations.",
                "events": [
                    {"event_type": "Solar Storm", "severity": "HIGH", "duration": 30.0, "affected_system": "Power", "trigger_time": 0.0, "impact_multipliers": {"power": -1.2, "subsystems.Power": -1.5}},
                    {"event_type": "Communication Loss", "severity": "HIGH", "duration": 30.0, "affected_system": "Communication", "trigger_time": 8.0, "impact_multipliers": {"subsystems.Communication": -1.5}},
                    {"event_type": "Micrometeorite Impact", "severity": "HIGH", "duration": 30.0, "affected_system": "Thermal Control", "trigger_time": 16.0, "impact_multipliers": {"health": -0.8, "subsystems.Thermal Control": -2.5}}
                ]
            }
        }
        
        scen = presets.get(idx)
        if not scen:
            return
            
        self.active_events = []
        
        db_scen_id = None
        if connection.SessionLocal:
            try:
                async with connection.SessionLocal() as db:
                    from backend.database.models import TestScenarioModel, ScenarioEventModel
                    db_scen = TestScenarioModel(
                        name=scen["name"],
                        description=scen["desc"],
                        is_custom=False,
                        created_at=datetime.utcnow()
                    )
                    db.add(db_scen)
                    await db.flush()
                    db_scen_id = db_scen.id
                    
                    for index, ev in enumerate(scen["events"]):
                        db_ev = ScenarioEventModel(
                            scenario_id=db_scen_id,
                            event_type=ev["event_type"],
                            severity=ev["severity"],
                            duration=ev["duration"],
                            affected_system=ev["affected_system"],
                            propagation_speed=1.0,
                            probability=1.0,
                            impact_multipliers=json.dumps(ev["impact_multipliers"]),
                            trigger_time=ev["trigger_time"]
                        )
                        db.add(db_ev)
                        
                    await db.commit()
            except Exception as e:
                print(f"[DB ERROR] Save scenario preset failed: {e}")

        events_parsed = []
        for index, ev in enumerate(scen["events"]):
            events_parsed.append({
                "id": index + 1,
                "event_type": ev["event_type"],
                "severity": ev["severity"],
                "duration": ev["duration"],
                "affected_system": ev["affected_system"],
                "propagation_speed": 1.0,
                "probability": 1.0,
                "impact_multipliers": ev["impact_multipliers"],
                "trigger_time": ev["trigger_time"]
            })
            
        self.active_scenario = {
            "id": db_scen_id or random.randint(1000, 9999),
            "name": scen["name"],
            "desc": scen["desc"],
            "events": events_parsed
        }
        self.scenario_timer = 0.0
        self.scenario_triggered_events = set()
        self.recovery_efficiency = 100.0
        self.recovery_start_times = {}
        self.recovery_mitigate_times = {}
        self.recovery_initial_metrics = {}
        
        await self.log_event("INFO", f"TEST SCENARIO STARTED: {scen['name']} - {scen['desc']}")
        
        await manager.broadcast_json({
            "type": "Scenario Started",
            "scenario_name": scen["name"],
            "description": scen["desc"],
            "num_events": len(events_parsed)
        })
        
        try:
            redis = await get_redis()
            await redis.set("hail_mary:test:active_scenario", json.dumps({
                "id": self.active_scenario["id"],
                "name": scen["name"],
                "desc": scen["desc"],
                "timer": 0.0
            }))
        except Exception as e:
            print(f"[Redis ERROR] Caching active scenario failed: {e}")

# Global Simulator instance
simulator = SpacecraftSimulator()
