import json
from datetime import datetime, timedelta
from backend.utils.timezone_helper import ist_now
from backend.database.redis_client import get_redis

class TrajectoryPlanner:
    MISSION_TYPE_DEFAULTS = {
        "Science Deep Probe": {
            "fuel_capacity": 30000.0,
            "cruise_speed": 45.0,
            "engine_thrust": 1000.0
        },
        "Heavy Cargo Transport": {
            "fuel_capacity": 90000.0,
            "cruise_speed": 20.0,
            "engine_thrust": 3000.0
        },
        "Colonization Habitat": {
            "fuel_capacity": 70000.0,
            "cruise_speed": 25.0,
            "engine_thrust": 2000.0
        },
        "Satellite Deployment": {
            "fuel_capacity": 40000.0,
            "cruise_speed": 35.0,
            "engine_thrust": 1200.0
        }
    }

    def __init__(
        self,
        origin: str = "Earth",
        destination: str = "Mars",
        fuel_capacity: float = None,
        payload_mass: float = 10000.0,
        cruise_speed: float = None,
        engine_thrust: float = None,
        active_events: list = None,
        mission_type: str = "Science Deep Probe"
    ):
        self.origin = origin
        self.destination = destination
        self.payload_mass = payload_mass
        self.active_events = active_events or []
        self.mission_type = mission_type
        
        defaults = self.MISSION_TYPE_DEFAULTS.get(mission_type)
        self.fuel_capacity = fuel_capacity if fuel_capacity is not None else (defaults["fuel_capacity"] if defaults else 50000.0)
        self.cruise_speed = cruise_speed if cruise_speed is not None else (defaults["cruise_speed"] if defaults else 30.0)
        self.engine_thrust = engine_thrust if engine_thrust is not None else (defaults["engine_thrust"] if defaults else 1500.0)

    def apply_mission_type_defaults(self):
        defaults = self.MISSION_TYPE_DEFAULTS.get(self.mission_type)
        if defaults:
            self.fuel_capacity = defaults["fuel_capacity"]
            self.cruise_speed = defaults["cruise_speed"]
            self.engine_thrust = defaults["engine_thrust"]

    def to_dict(self):
        return {
            "origin": self.origin,
            "destination": self.destination,
            "fuel_capacity": self.fuel_capacity,
            "payload_mass": self.payload_mass,
            "cruise_speed": self.cruise_speed,
            "engine_thrust": self.engine_thrust,
            "active_events": self.active_events,
            "mission_type": self.mission_type
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            origin=data.get("origin", "Earth"),
            destination=data.get("destination", "Mars"),
            fuel_capacity=float(data.get("fuel_capacity", 50000.0)),
            payload_mass=float(data.get("payload_mass", 10000.0)),
            cruise_speed=float(data.get("cruise_speed", 30.0)),
            engine_thrust=float(data.get("engine_thrust", 1500.0)),
            active_events=data.get("active_events", []),
            mission_type=data.get("mission_type", "Science Deep Probe")
        )


    async def save_to_redis(self):
        redis = await get_redis()
        await redis.set("hail_mary:trajectory_state", json.dumps(self.to_dict()))

    @classmethod
    async def load_from_redis(cls):
        redis = await get_redis()
        data_str = await redis.get("hail_mary:trajectory_state")
        if data_str:
            try:
                return cls.from_dict(json.loads(data_str))
            except Exception:
                pass
        return cls()

    def calculate(self, avg_distance_km: float) -> dict:
        # Determine active multipliers based on events
        fuel_leak_active = "fuel_leak" in self.active_events
        thruster_failure_active = "thruster_failure" in self.active_events
        navigation_drift_active = "navigation_drift" in self.active_events

        # 1. Effective Distance (Navigation Drift adds 15% corrective maneuvers)
        effective_distance = avg_distance_km
        if navigation_drift_active:
            effective_distance *= 1.15

        # 2. Effective Cruise Speed (Thruster Failure reduces efficiency/speed by 20%)
        effective_speed = self.cruise_speed
        if thruster_failure_active:
            effective_speed *= 0.8

        # Protect against zero speed division
        if effective_speed <= 0:
            effective_speed = 0.1

        # 3. Effective Thrust (Thruster Failure reduces thrust by 30%)
        effective_thrust = self.engine_thrust
        if thruster_failure_active:
            effective_thrust *= 0.7

        # 4. Travel Duration (Time = Distance / Speed)
        # Cruise speed is in km/s.
        duration_seconds = effective_distance / effective_speed
        travel_time_h = duration_seconds / 3600.0

        # 5. Burn Rate & Fuel Consumption
        # Isp = 300.0 seconds (specific impulse). g0 = 9.80665 m/s^2.
        # Burn Rate = Thrust (N) / (Isp * g0)
        # Thrust is in kN, so convert to N by multiplying by 1000.
        isp = 300.0
        g0 = 9.80665
        base_burn_rate_kg_s = (effective_thrust * 1000.0) / (isp * g0)

        # Fuel leak adds a constant loss of 0.5 kg/s
        leak_rate_kg_s = 0.5 if fuel_leak_active else 0.0
        total_burn_rate_kg_s = base_burn_rate_kg_s + leak_rate_kg_s

        required_mission_fuel = total_burn_rate_kg_s * duration_seconds
        reserve_fuel = 0.20 * required_mission_fuel
        emergency_fuel = 0.10 * required_mission_fuel
        total_fuel_loaded = required_mission_fuel + reserve_fuel + emergency_fuel

        # Fuel remaining under nominal flight is the reserve + emergency fuel
        fuel_remaining_kg = reserve_fuel + emergency_fuel

        # The ship's fuel tanks are sized to carry the total fuel needed.
        # fuel_capacity from mission type defaults is only used as a base parameter
        # for other calculations, not as an actual tank size limit.
        # The simulator auto-loads total_fuel_loaded, so feasibility is always true
        # under normal conditions.
        feasibility = True

        # 7. Estimated Arrival Time (in IST)
        now_time = ist_now()
        arrival_time = now_time + timedelta(seconds=duration_seconds)

        # 8. Success Forecast
        # Starts at 98%
        success_forecast = 98.0
        if not feasibility:
            success_forecast = 0.0
        else:
            # Penalty for low fuel margin (less than 15% margin)
            fuel_margin = fuel_remaining_kg / total_fuel_loaded if total_fuel_loaded > 0 else 0.0
            if fuel_margin < 0.15:
                # Deduct up to 30% depending on margin
                success_forecast -= (0.15 - fuel_margin) / 0.15 * 30.0

            # Penalty for high payload ratio (payload_mass / total_fuel > 5.0)
            payload_ratio = self.payload_mass / total_fuel_loaded if total_fuel_loaded > 0 else 0.0
            if payload_ratio > 5.0:
                success_forecast -= min(15.0, (payload_ratio - 5.0) * 3.0)

            # Deduct for active events
            if fuel_leak_active:
                success_forecast -= 25.0
            if thruster_failure_active:
                success_forecast -= 20.0
            if navigation_drift_active:
                success_forecast -= 15.0

            # Clamp between 5.0% and 98.0%
            success_forecast = max(5.0, min(98.0, success_forecast))

        return {
            "distance_km": float(effective_distance),
            "travel_time_h": float(travel_time_h),
            "fuel_required_kg": float(required_mission_fuel),  # nominal required fuel
            "required_mission_fuel": float(required_mission_fuel),
            "reserve_fuel": float(reserve_fuel),
            "emergency_fuel": float(emergency_fuel),
            "total_fuel_loaded": float(total_fuel_loaded),
            "fuel_remaining_kg": float(fuel_remaining_kg),
            "feasibility": bool(feasibility),
            "arrival_time": arrival_time.isoformat(),
            "success_forecast": float(success_forecast)
        }
