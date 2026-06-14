from datetime import datetime
from backend.trajectory.planner import TrajectoryPlanner
from backend.utils.timezone_helper import ist_now

def test_ist_now_timezone():
    now = ist_now()
    # Check that it returns Asia/Kolkata timezone offset (+05:30)
    assert now.tzinfo is not None
    assert now.tzinfo.utcoffset(now).total_seconds() == 5.5 * 3600

def test_trajectory_planner_calculations():
    planner = TrajectoryPlanner(
        origin="Earth",
        destination="Mars",
        fuel_capacity=50000.0,
        payload_mass=10000.0,
        cruise_speed=30.0,
        engine_thrust=1500.0
    )
    
    # Martian distance: 225,300,000 km
    results = planner.calculate(225300000.0)
    
    assert results["distance_km"] == 225300000.0
    # Travel Time (hours) = (225300000 / 30) / 3600 = 7510000 / 3600 = 2086.11
    assert abs(results["travel_time_h"] - 2086.11) < 0.1
    # Fuel capacity is positive and feasibility should be calculated
    assert results["fuel_required_kg"] > 0
    
def test_trajectory_planner_with_events():
    planner = TrajectoryPlanner(
        origin="Earth",
        destination="Mars",
        fuel_capacity=50000.0,
        payload_mass=10000.0,
        cruise_speed=30.0,
        engine_thrust=1500.0,
        active_events=["fuel_leak", "thruster_failure", "navigation_drift"]
    )
    
    # Calculate with events
    results = planner.calculate(225300000.0)
    
    # Since navigation drift is active, effective distance should be 225300000 * 1.15
    # Since thruster failure is active, effective speed is 30 * 0.8 = 24.0 km/s
    expected_dist = 225300000.0 * 1.15
    assert results["distance_km"] == expected_dist
    
    expected_duration = expected_dist / 24.0
    expected_time_h = expected_duration / 3600.0
    assert abs(results["travel_time_h"] - expected_time_h) < 0.1
