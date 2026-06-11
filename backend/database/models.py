from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class MissionModel(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)
    launch_time = Column(DateTime, default=datetime.utcnow)
    state = Column(String(50), default="Idle")  # Idle, Launch, Cruise, Maneuver, Emergency, Completed
    duration = Column(Float, default=0.0)  # in seconds
    target_distance = Column(Float, default=1000000.0)  # in km

class TelemetryModel(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    fuel = Column(Float, nullable=False)
    power = Column(Float, nullable=False)
    oxygen = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    health = Column(Float, nullable=False)
    velocity = Column(Float, nullable=False)
    distance = Column(Float, nullable=False)
    mission_progress = Column(Float, nullable=False)

class EventModel(Base):
    """General logs events table from Phase 1"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(50), default="INFO")
    message = Column(String(500), nullable=False)

# --- PHASE 2 MODELS ---

class MissionEventModel(Base):
    """Specific unpredictable space events logged to PostgreSQL"""
    __tablename__ = "mission_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    description = Column(String(500), nullable=False)
    affected_system = Column(String(100), nullable=False)  # Propulsion, Life Support, Electrical, Antennas, Nav Computers
    probability = Column(Float, default=0.0)
    recommended_actions = Column(String(500), default="")
    resolved = Column(Boolean, default=False, index=True)
    resolution_time = Column(DateTime, nullable=True)

class RiskHistoryModel(Base):
    """Risk score tracker mapped over time for trends plotting"""
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    risk_score = Column(Float, nullable=False)  # 0 to 100
    risk_level = Column(String(50), nullable=False)  # LOW, MODERATE, HIGH, CRITICAL

class EventStatisticsModel(Base):
    """Dynamic statistics aggregator inside DB"""
    __tablename__ = "event_statistics"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), unique=True, nullable=False)
    frequency_count = Column(Integer, default=0)
    last_occurred = Column(DateTime, default=datetime.utcnow)

# --- PHASE 2.5 MODELS ---

class MissionObjectiveModel(Base):
    """Status records for mission objectives and victory conditions"""
    __tablename__ = "mission_objectives"

    id = Column(Integer, primary_key=True, index=True)
    objective_name = Column(String(100), nullable=False)
    description = Column(String(200), nullable=False)
    success_conditions = Column(String(500), nullable=False)  # JSON String
    failure_conditions = Column(String(500), nullable=False)  # JSON String
    status = Column(String(50), default="PENDING")  # PENDING, ACHIEVED, FAILED

class EventDependencyModel(Base):
    """Propagation dependencies graph representation"""
    __tablename__ = "event_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    parent_event_type = Column(String(100), nullable=False, index=True)
    child_event_type = Column(String(100), nullable=False)
    propagation_probability = Column(Float, default=0.0)

class SubsystemHealthModel(Base):
    """Historical records of sub-system performance levels over time"""
    __tablename__ = "subsystem_health"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    subsystem_name = Column(String(100), nullable=False)
    health = Column(Float, nullable=False)  # 0 to 100
    status = Column(String(50), nullable=False)  # OPERATIONAL, DEGRADED, CRITICAL, FAILED
    risk_score = Column(Float, nullable=False)
    performance = Column(Float, nullable=False)  # 0.0 to 1.0

class ActionOptionModel(Base):
    """Exposed response items in the Decision Sandbox"""
    __tablename__ = "action_options"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    action_key = Column(String(100), nullable=False, unique=True)
    action_name = Column(String(150), nullable=False)
    description = Column(String(500), nullable=False)

class ActionPredictionModel(Base):
    """Outcome statistics forecasted for selectable options"""
    __tablename__ = "action_predictions"

    id = Column(Integer, primary_key=True, index=True)
    action_key = Column(String(100), nullable=False, index=True)
    fuel_delta = Column(Float, default=0.0)
    power_delta = Column(Float, default=0.0)
    risk_reduction = Column(Float, default=0.0)
    success_delta = Column(Float, default=0.0)

class MissionMemoryModel(Base):
    """Running snapshot storage logs of the simulator environment"""
    __tablename__ = "mission_memory"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    telemetry_snapshot = Column(String(2000), nullable=False)  # JSON string
    active_events = Column(String(1000), default="[]")  # JSON string
    available_actions = Column(String(1000), default="[]")  # JSON string
    chosen_action = Column(String(100), nullable=True)
    outcome = Column(String(1000), nullable=True)  # JSON string

class MissionReplayModel(Base):
    """Timeline logs storing playback history runs"""
    __tablename__ = "mission_replays"

    id = Column(Integer, primary_key=True, index=True)
    replay_name = Column(String(100), nullable=False)
    history_data = Column(String(2000000), nullable=False)  # Large JSON payload
    created_at = Column(DateTime, default=datetime.utcnow)

class MonteCarloResultModel(Base):
    """Aggregators caching Monte Carlo forecast results"""
    __tablename__ = "monte_carlo_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    iterations = Column(Integer, nullable=False)
    avg_success_prob = Column(Float, nullable=False)
    avg_fuel_remaining = Column(Float, nullable=False)
    avg_mission_time = Column(Float, nullable=False)
    avg_risk = Column(Float, nullable=False)
    failure_distribution = Column(String(1000), nullable=False)  # JSON count map
