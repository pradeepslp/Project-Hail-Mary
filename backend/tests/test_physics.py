import pytest
import asyncio
from backend.simulator.engine import SpacecraftSimulator
from backend.trajectory.planner import TrajectoryPlanner

@pytest.mark.anyio
async def test_deceleration_distance_physics():
    # Setup trajectory planner in Redis
    planner = TrajectoryPlanner(
        origin="Earth",
        destination="Mars",
        fuel_capacity=390000.0,
        payload_mass=10000.0,
        cruise_speed=30.0,
        engine_thrust=1500.0
    )
    await planner.save_to_redis()

    # Setup simulator
    simulator = SpacecraftSimulator()
    simulator.reset_state()
    
    # Setup mock destination / target distance
    simulator.target_distance = 1000000.0
    simulator.distance_remaining = 1000000.0
    
    # Mock total fuel loaded to match synced trajectory
    simulator.initial_main_fuel = 300000.0
    simulator.initial_backup_fuel = 60000.0
    simulator.initial_emergency_fuel = 30000.0
    simulator.main_fuel = 300000.0
    simulator.backup_fuel = 60000.0
    simulator.emergency_fuel = 30000.0
    simulator.fuel_mass = 390000.0
    simulator.fuel_capacity = 390000.0
    
    # Put simulator in "Approach" phase and progress = 86%
    simulator.state = "Approach"
    simulator.mission_progress = 86.0
    simulator.distance = 860000.0
    simulator.velocity = 30.0
    
    # Calculate deceleration time and distance
    # With 1500 kN thrust, dry_mass=5000, payload_mass=10000, inertia_fuel_mass=min(390000, 50000) = 50000
    # total_mass = 65000 kg.
    # a = (1,500,000 / 65,000) / 1000.0 = 0.0230769 km/s^2
    # t_decel = (30.0 - 0.1) / 0.0230769 = 29.9 / 0.0230769 = 1295.66 seconds
    # d_decel = 0.5 * (30.0 + 0.1) * 1295.66 = 19500 km approx.
    # Since distance remaining is 1000000 - 860000 = 140000 km, and 140000 > 19500,
    # the engines should NOT be firing yet, and velocity should remain 30.0.
    
    await simulator.update_physics(1.0)
    
    assert simulator.burn_rate_kg_s == 0.0
    assert simulator.velocity == 30.0
    assert simulator.thrust_force == 0.0
    
    # Now set distance to 990000 km, so distance remaining is 10000 km.
    # Since 10000 <= d_decel_needed (~19500), engines should fire and decelerate.
    simulator.distance = 990000.0
    simulator.distance_remaining = 10000.0
    
    await simulator.update_physics(1.0)
    
    assert simulator.thrust_force > 0.0
    assert simulator.burn_rate_kg_s > 0.0
    assert simulator.velocity < 30.0
