from datetime import datetime as _datetime
from backend.utils.timezone_helper import ist_now

class datetime(_datetime):
    @classmethod
    def utcnow(cls):
        return ist_now()
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


# --- PHASE 3 AGENT MODELS ---

class AgentDecisionModel(Base):
    """Stores high-level autonomous agent decisions"""
    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_id = Column(Integer, nullable=True)
    chosen_action = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    expected_outcome = Column(String(2000), nullable=False)  # JSON String
    actual_outcome = Column(String(2000), nullable=True)   # JSON String (post-mitigation check)
    executed_autonomously = Column(Boolean, default=False)
    autonomy_level = Column(Integer, default=0)

class AgentReasoningModel(Base):
    """Stores detailed commander agent reasoning records"""
    __tablename__ = "agent_reasoning"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    reasoning_text = Column(String(4000), nullable=False)
    utility_scores = Column(String(2000), nullable=False)  # JSON String

class AgentMemoryModel(Base):
    """Stores short and long term memory representations of event outcomes"""
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    memory_type = Column(String(50), default="LONG_TERM")  # SHORT_TERM or LONG_TERM
    event_type = Column(String(100), nullable=False, index=True)
    action_key = Column(String(100), nullable=False)
    outcome_delta = Column(String(2000), nullable=False)  # JSON String (deltas experienced)
    success = Column(Boolean, default=True)

class AgentConfidenceModel(Base):
    """Stores real-time confidence metrics with contributing factors"""
    __tablename__ = "agent_confidence"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_key = Column(String(100), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)
    factors = Column(String(2000), nullable=False)  # JSON String

class AgentMetricsModel(Base):
    """Stores running decision accuracy and agreement indicators"""
    __tablename__ = "agent_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_accuracy = Column(Float, nullable=False)
    mission_success_rate = Column(Float, nullable=False)
    avg_confidence = Column(Float, nullable=False)
    agreement_rate = Column(Float, nullable=False)

class AgentCollaborationModel(Base):
    """Stores collaborative ratings from navigation, fuel, safety, and science specialists"""
    __tablename__ = "agent_collaboration"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_id = Column(Integer, nullable=True, index=True)
    nav_recommendation = Column(String(4000), nullable=False)  # JSON String
    fuel_recommendation = Column(String(4000), nullable=False)  # JSON String
    safety_recommendation = Column(String(4000), nullable=False)  # JSON String
    science_recommendation = Column(String(4000), nullable=False)  # JSON String
    commander_decision = Column(String(100), nullable=False)


# --- PHASE 4 SELF-LEARNING MODELS ---

class MissionExperienceModel(Base):
    """Stores mission outcomes and situations for offline training data"""
    __tablename__ = "mission_experiences"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    situation = Column(String(500), nullable=True)
    state_snapshot = Column(String(2000), nullable=False)  # JSON String
    active_events = Column(String(1000), default="[]")  # JSON String
    chosen_action = Column(String(100), nullable=False)
    expected_outcome = Column(String(1000), nullable=False)  # JSON String
    actual_outcome = Column(String(1000), nullable=True)   # JSON String
    success_score = Column(Float, nullable=False)
    mission_result = Column(String(50), nullable=False)  # SUCCESS, FAILURE

class KnowledgeGraphNodeModel(Base):
    """Stores entities in the mission knowledge representation"""
    __tablename__ = "knowledge_graph_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)  # Event, Subsystem, Action, Outcome, Risk, Objective
    properties = Column(String(2000), default="{}")  # JSON String

class KnowledgeGraphEdgeModel(Base):
    """Stores directed relationships between nodes"""
    __tablename__ = "knowledge_graph_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(Integer, nullable=False, index=True)
    target_node_id = Column(Integer, nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True)  # Causes, Triggers, Mitigates, Improves, Damages
    weight = Column(Float, default=1.0)

class StrategyHistoryModel(Base):
    """Logs evaluations and recommendations of different action plans"""
    __tablename__ = "strategy_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    strategies_evaluated = Column(String(2000), nullable=False)  # JSON String
    recommended_strategy = Column(String(100), nullable=False)
    historical_success_rate = Column(Float, nullable=False)

class FailurePatternModel(Base):
    """Caches discovered failure propagation chains"""
    __tablename__ = "failure_patterns"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    pattern_name = Column(String(250), nullable=False)
    event_sequence = Column(String(1000), nullable=False)  # JSON String list
    occurrence_count = Column(Integer, default=0)
    severity_index = Column(Float, default=0.0)

class SuccessPatternModel(Base):
    """Caches discovered reliable strategy patterns"""
    __tablename__ = "success_patterns"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    pattern_name = Column(String(250), nullable=False)
    decision_sequence = Column(String(1000), nullable=False)  # JSON String list
    efficiency_score = Column(Float, default=0.0)
    success_probability = Column(Float, default=0.0)

class RLTrainingDataModel(Base):
    """Logs reinforcement learning exploration transitions"""
    __tablename__ = "rl_training_data"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    episode = Column(Integer, nullable=False, index=True)
    step = Column(Integer, nullable=False)
    state = Column(String(2000), nullable=False)  # JSON String
    action = Column(String(100), nullable=False)
    reward = Column(Float, nullable=False)
    next_state = Column(String(2000), nullable=False)  # JSON String
    td_error = Column(Float, default=0.0)

class PredictiveModelModel(Base):
    """Stores hyperparameters and metadata of trained local models"""
    __tablename__ = "predictive_models"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    model_name = Column(String(100), nullable=False, index=True)
    model_type = Column(String(50), nullable=False)  # RandomForest, LinearRegression, etc.
    accuracy_score = Column(Float, nullable=False)
    parameters = Column(String(4000), default="{}")  # JSON String of weights / features

class MaintenanceForecastModel(Base):
    """Logs predictive health failure warnings for subsystems"""
    __tablename__ = "maintenance_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    subsystem_name = Column(String(100), nullable=False, index=True)
    current_health = Column(Float, nullable=False)
    predicted_degradation_rate = Column(Float, nullable=False)
    expected_failure_time = Column(Float, nullable=False)  # in seconds / ticks
    recommendation = Column(String(500), nullable=False)

class AutonomyMetricsModel(Base):
    """Logs AI evolution parameters over time"""
    __tablename__ = "autonomy_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_accuracy = Column(Float, nullable=False)
    prediction_accuracy = Column(Float, nullable=False)
    success_rate = Column(Float, nullable=False)
    risk_reduction = Column(Float, nullable=False)
    resource_efficiency = Column(Float, nullable=False)
    autonomy_level = Column(Integer, nullable=False)
    maturity_index = Column(Float, nullable=False)


# --- PHASE 5 OPERATIONS MODELS ---

class MissionPlanModel(Base):
    __tablename__ = "mission_plans"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    destination = Column(String(100), nullable=False)
    payload = Column(String(100), nullable=False)
    duration = Column(Float, nullable=False)
    available_fuel = Column(Float, nullable=False)
    science_objectives = Column(String(2000), nullable=False)  # JSON string
    constraints = Column(String(2000), nullable=False)  # JSON string
    route_plan = Column(String(2000), nullable=False)  # JSON string
    resource_plan = Column(String(2000), nullable=False)  # JSON string
    risk_assessment = Column(String(2000), nullable=False)  # JSON string
    success_forecast = Column(Float, nullable=False)
    status = Column(String(50), default="PLANNED")  # PLANNED, EXECUTING, COMPLETED, FAILED

class MissionTimelineModel(Base):
    __tablename__ = "mission_timelines"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    time_offset = Column(String(50), nullable=False)  # e.g., T+00, T+12
    phase = Column(String(50), nullable=False)
    event_name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    status = Column(String(50), default="PENDING")  # PENDING, COMPLETED, SKIPPED

class MissionStrategyModel(Base):
    __tablename__ = "mission_strategies"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(100), nullable=False)  # Aggressive, Balanced, Conservative, Science-Focused, Resource-Focused
    success_probability = Column(Float, nullable=False)
    projected_fuel = Column(Float, nullable=False)
    projected_power = Column(Float, nullable=False)
    projected_risk = Column(Float, nullable=False)
    description = Column(String(500), nullable=False)

class ContingencyPlanModel(Base):
    __tablename__ = "contingency_plans"

    id = Column(Integer, primary_key=True, index=True)
    emergency_type = Column(String(100), nullable=False)  # Fuel Crisis, Comm Loss, etc.
    trigger_condition = Column(String(500), nullable=False)
    priority = Column(String(50), nullable=False)  # CRITICAL, HIGH, MEDIUM
    response_protocol = Column(String(2000), nullable=False)  # JSON string action list
    status = Column(String(50), default="PENDING")  # PENDING, ACTIVE, RESOLVED

class ConsensusRecordModel(Base):
    __tablename__ = "consensus_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_key = Column(String(100), nullable=False)
    nav_recommendation = Column(String(1000), nullable=False)  # JSON/Text
    fuel_recommendation = Column(String(1000), nullable=False)
    safety_recommendation = Column(String(1000), nullable=False)
    science_recommendation = Column(String(1000), nullable=False)
    prediction_rating = Column(Float, nullable=False)
    learning_rating = Column(Float, nullable=False)
    consensus_score = Column(Float, nullable=False)
    commander_override = Column(Boolean, default=False)

class RecoveryActionModel(Base):
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    initial_risk_score = Column(Float, nullable=False)
    proposed_strategy = Column(String(100), nullable=False)
    action_details = Column(String(1000), nullable=False)
    outcome_details = Column(String(1000), nullable=False)
    final_risk_score = Column(Float, nullable=False)
    success = Column(Boolean, default=True)

class ForecastResultModel(Base):
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    horizon = Column(String(50), nullable=False)  # 1h, 6h, 24h, 7d
    projected_success = Column(Float, nullable=False)
    projected_fuel = Column(Float, nullable=False)
    projected_power = Column(Float, nullable=False)
    projected_risk = Column(Float, nullable=False)
    predicted_failures = Column(String(1000), default="[]")  # JSON List

class FleetAssetModel(Base):
    __tablename__ = "fleet_assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # Orbiter, Lander, Rover, Probe, Satellite, Cargo Ship, Drone, Space Station
    status = Column(String(50), default="Idle")  # Operational, Idle, Damaged, Transit, Action Mitigating
    telemetry_json = Column(String(2000), default="{}")  # fuel, power, bandwidth, oxygen, positions, health, etc.
    active_objectives = Column(String(2000), default="[]")  # JSON List

class FleetMissionModel(Base):
    __tablename__ = "fleet_missions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    target = Column(String(100), nullable=False)
    status = Column(String(50), default="Active")  # Active, Completed, Failed
    progress = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)

class TaskAllocationModel(Base):
    __tablename__ = "task_allocations"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(200), nullable=False)
    asset_id = Column(Integer, nullable=True)
    priority = Column(String(50), default="Medium")  # Critical, High, Medium, Low
    status = Column(String(50), default="Unassigned")  # Unassigned, Assigned, Executing, Completed
    required_resources = Column(String(1000), default="{}")  # JSON String description

class ResourceNetworkModel(Base):
    __tablename__ = "resource_networks"

    id = Column(Integer, primary_key=True, index=True)
    source_asset_id = Column(Integer, nullable=False)
    target_asset_id = Column(Integer, nullable=False)
    resource_type = Column(String(50), nullable=False)  # Fuel, Power, Bandwidth, Parts, Cargo
    transfer_rate = Column(Float, default=0.0)
    status = Column(String(50), default="Idle")  # Transferring, Idle, Completed

class ColonySystemModel(Base):
    __tablename__ = "colony_systems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # Habitat, Power Plant, Mining, Research Lab, Comm Tower
    status = Column(String(50), default="Operational")
    metrics_json = Column(String(2000), default="{}")  # level, efficiency, storage, power_consumption

class InterAgentMessageModel(Base):
    __tablename__ = "inter_agent_messages"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    sender_id = Column(String(100), nullable=False)
    receiver_id = Column(String(100), nullable=False)
    msg_type = Column(String(100), nullable=False)  # Status Update, Request, Warning, Recommendation, Resource Request, Mission Update
    content = Column(String(1000), nullable=False)

class SwarmDecisionModel(Base):
    __tablename__ = "swarm_decisions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_key = Column(String(200), nullable=False)
    votes_json = Column(String(2000), default="{}")  # JSON mapping asset -> votes/recommendation
    chosen_strategy = Column(String(100), nullable=False)
    swarm_consensus_score = Column(Float, default=0.0)

class SharedKnowledgeModel(Base):
    __tablename__ = "shared_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    discovery_type = Column(String(100), nullable=False)  # Resource, Hazard, Strategy, Discovery, Failure
    source = Column(String(100), nullable=False)  # Spacecraft ID
    details = Column(String(2000), nullable=False)
    confidence = Column(Float, default=1.0)

class GlobalRiskMetricsModel(Base):
    __tablename__ = "global_risk_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    fleet_risk = Column(Float, default=0.0)
    mission_risk = Column(Float, default=0.0)
    planetary_risk = Column(Float, default=0.0)
    colony_risk = Column(Float, default=0.0)
    infrastructure_risk = Column(Float, default=0.0)
    threat_assessment = Column(String(1000), default="Nominal")


# --- PHASE 3.5 LLM COMMANDER MODELS ---

class LLMPromptModel(Base):
    __tablename__ = "llm_prompts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(100), nullable=False)
    event_id = Column(Integer, nullable=False)
    prompt_text = Column(String(4000), nullable=False)
    system_prompt = Column(String(2000), nullable=False)

class LLMDecisionModel(Base):
    __tablename__ = "llm_decisions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision = Column(String(100), nullable=False)
    confidence = Column(Integer, nullable=False)
    chosen_action_key = Column(String(100), nullable=False)
    status = Column(String(50), default="Executed")  # Executed, Failed, Simulated, Fallback
    autonomy_level = Column(Integer, default=4)

class LLMReasoningModel(Base):
    __tablename__ = "llm_reasoning"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, nullable=False, index=True)
    reasoning_steps = Column(String(2000), nullable=False)  # JSON string representation of list of strings

class LLMOutcomeModel(Base):
    __tablename__ = "llm_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, nullable=False, index=True)
    success_change = Column(Float, default=0.0)
    risk_reduction = Column(Float, default=0.0)
    power_change = Column(Float, default=0.0)
    fuel_change = Column(Float, default=0.0)
    actual_success = Column(Float, nullable=True)
    actual_risk = Column(Float, nullable=True)
    evaluated = Column(Boolean, default=False)

class DecisionMetricsModel(Base):
    __tablename__ = "decision_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision_accuracy = Column(Float, default=0.0)
    avg_confidence = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    reasoning_quality = Column(Float, default=0.0)


# --- PHASE 3.0 DETECTABLE DETERMINISTIC AGENTS MODELS ---

class AgentRegistryModel(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    role = Column(String(100), nullable=False)
    responsibilities = Column(String(500), nullable=False)

class AgentRecommendationModel(Base):
    __tablename__ = "agent_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    recommendation = Column(String(200), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(String(500), nullable=False)
    action_key = Column(String(100), nullable=False)

class AgentConsensusModel(Base):
    __tablename__ = "agent_consensus"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    agreement_score = Column(Float, nullable=False)
    consensus_decision = Column(String(100), nullable=False)
    details_json = Column(String(2000), default="{}")

class CommanderDecisionModel(Base):
    __tablename__ = "commander_decisions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    chosen_action = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(String(1000), nullable=False)
    utility_score = Column(Float, nullable=False)
    outcome_details = Column(String(2000), default="{}")


class TestScenarioModel(Base):
    __tablename__ = "test_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    is_custom = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ScenarioEventModel(Base):
    __tablename__ = "scenario_events"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)  # INFO, LOW, MEDIUM, HIGH, CRITICAL, CATASTROPHIC
    duration = Column(Float, nullable=False)
    affected_system = Column(String(100), nullable=False)
    propagation_speed = Column(Float, default=1.0)
    probability = Column(Float, default=1.0)
    impact_multipliers = Column(String(500), default="{}")  # JSON mapping vars -> values
    trigger_time = Column(Float, default=0.0)

class BenchmarkResultModel(Base):
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    scenario_name = Column(String(100), nullable=False)
    injected_event = Column(String(100), nullable=False)
    subsystem_impact = Column(String(1000), default="{}")  # JSON
    mission_impact = Column(String(1000), default="{}")  # JSON
    recovery_outcome = Column(String(1000), default="")
    risk_evolution = Column(String(2000), default="[]")  # JSON list
    final_mission_state = Column(String(100), default="Completed")

class RecoveryMetricsModel(Base):
    __tablename__ = "recovery_metrics"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    detection_time = Column(Float, default=0.0)
    recovery_time = Column(Float, default=0.0)
    damage_prevented = Column(Float, default=0.0)
    mission_success_change = Column(Float, default=0.0)
    risk_reduction = Column(Float, default=0.0)
    resource_preservation = Column(Float, default=0.0)

class StressTestResultModel(Base):
    __tablename__ = "stress_test_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    scenario_name = Column(String(100), nullable=False)
    num_events = Column(Integer, default=2)
    average_success_prob = Column(Float, default=0.0)
    average_risk = Column(Float, default=0.0)
    average_resource_loss = Column(Float, default=0.0)
    average_recovery_time = Column(Float, default=0.0)
    details_json = Column(String(2000), default="{}")

class ResilienceScoreModel(Base):
    __tablename__ = "resilience_scores"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    resilience_score = Column(Float, default=0.0)
    adaptability_score = Column(Float, default=0.0)
    survivability_score = Column(Float, default=0.0)
    recovery_efficiency = Column(Float, default=0.0)
    system_stability = Column(Float, default=0.0)
    overall_robustness = Column(Float, default=0.0)

class DestinationModel(Base):
    __tablename__ = "destinations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    avg_distance_km = Column(Float, nullable=False)
