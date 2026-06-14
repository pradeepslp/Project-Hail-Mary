import math
from typing import Dict, List, Any
from backend.utils.timezone_helper import ist_now

def get_digital_twin_forecast(telemetry: dict, active_events: list) -> dict:
    """Computes Newtonian analytical projections for 1h, 6h, 24h, and 7d horizons"""
    fuel = telemetry.get("fuel", 100.0)
    power = telemetry.get("power", 100.0)
    health = telemetry.get("health", 100.0)
    progress = telemetry.get("mission_progress", 0.0)
    velocity = telemetry.get("velocity", 0.0)
    pos_err = telemetry.get("position_error", 0.0)
    comm_connected = telemetry.get("communication", "Connected") == "Connected"

    # Compile current decay rates per tick (second) based on active events
    fuel_rate = 0.0
    power_lambda = 0.0
    health_decay = 0.0
    pos_err_rate = 0.0

    # Base decay rates
    oxygen_decay = 0.05
    
    # State specific baseline consumption
    sim_state = telemetry.get("state", "Cruise")
    if sim_state == "Launch":
        fuel_rate = 0.9
    elif sim_state == "Maneuver":
        fuel_rate = 0.25

    # Event specific multipliers
    for ev in active_events:
        ev_type = ev.get("event_type")
        status = ev.get("status", "ACTIVE")
        damage_scale = 0.5 if status == "MITIGATING" else 1.0

        if ev_type == "Fuel Leak":
            fuel_rate += 0.3 * damage_scale
            health_decay += 0.12 * damage_scale
        elif ev_type in ["Power Fluctuation", "Solar Storm"]:
            power_lambda = 0.012 * damage_scale
            health_decay += 0.15 * damage_scale
        elif ev_type == "Navigation Drift":
            pos_err_rate += 0.4 * damage_scale
            health_decay += 0.15 * damage_scale
        elif ev_type == "Thruster Failure":
            health_decay += 0.25 * damage_scale
        elif ev_type == "Micrometeorite Impact":
            health_decay += 0.3 * damage_scale
        elif ev_type == "Communication Loss":
            health_decay += 0.18 * damage_scale

    horizons = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
        "7d": 604800
    }

    forecast = {}
    for label, T in horizons.items():
        # Project values
        p_fuel = max(0.0, fuel - fuel_rate * T)
        p_power = max(10.0, power * math.exp(-power_lambda * T)) if power_lambda > 0 else power
        p_health = max(0.0, health - health_decay * T)
        p_pos_err = pos_err + pos_err_rate * T
        
        # Calculate risk
        p_fuel_risk = 100.0 - p_fuel
        p_power_risk = 100.0 - p_power
        p_health_risk = 100.0 - p_health
        p_comm_risk = 0.0 if comm_connected else 100.0
        p_risk = (0.3 * p_fuel_risk) + (0.3 * p_power_risk) + (0.2 * p_health_risk) + (0.2 * p_comm_risk)
        p_risk = min(100.0, max(0.0, p_risk))
        
        # Calculate success probability
        p_comm_score = 100.0 if comm_connected else 0.0
        p_nav_score = max(0.0, 100.0 - p_pos_err)
        p_success = (
            0.25 * p_fuel + 
            0.20 * p_power + 
            0.20 * p_health + 
            0.15 * p_comm_score + 
            0.20 * p_nav_score
        )
        p_success = min(100.0, max(0.0, p_success))
        
        # Progress projection
        p_progress = min(100.0, progress + (velocity * T / 1000000.0) * 100)

        forecast[label] = {
            "fuel": round(p_fuel, 1),
            "power": round(p_power, 1),
            "health": round(p_health, 1),
            "success": round(p_success, 1),
            "risk": round(p_risk, 1),
            "progress": round(p_progress, 1)
        }
        
    return forecast

def compare_strategies(telemetry: dict, active_events: list, options: list) -> list:
    """Evaluates and ranks alternative sandbox strategies side-by-side using 1-hour horizons"""
    rankings = []
    
    # Baseline delta maps matching simulator predictions
    deltas = {
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

    for opt in options:
        k = opt["action_key"]
        
        # Apply predicted delta instantly to build modified state
        d_val = deltas.get(k, {"fuel_delta": 0.0, "power_delta": 0.0, "risk_reduction": 0.0, "success_delta": 0.0})
        
        mod_tel = {
            **telemetry,
            "fuel": min(100.0, max(0.0, telemetry.get("fuel", 100.0) + d_val["fuel_delta"])),
            "power": min(100.0, max(10.0, telemetry.get("power", 100.0) + d_val["power_delta"])),
        }
        
        # Treat events as mitigating if action is executed
        mod_events = []
        for ev in active_events:
            mod_events.append({
                **ev,
                "status": "MITIGATING"
            })
            
        # Run 1-hour digital twin forecast on this hypothetical state
        fc = get_digital_twin_forecast(mod_tel, mod_events)["1h"]
        
        rankings.append({
            "action_key": k,
            "action_name": opt["action_name"],
            "projected_success": fc["success"],
            "projected_fuel": fc["fuel"],
            "projected_power": fc["power"],
            "projected_risk": fc["risk"]
        })
        
    # Rank descending by success probability, ascending by risk
    rankings = sorted(rankings, key=lambda x: (x["projected_success"], -x["projected_risk"]), reverse=True)
    return rankings
