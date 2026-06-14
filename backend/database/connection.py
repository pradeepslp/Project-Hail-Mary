import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.database.models import Base
from dotenv import load_dotenv
from backend.utils.timezone_helper import ist_now

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Dynamically translate postgresql:// to postgresql+asyncpg:// for SQLAlchemy async driver
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

fallback_db = "sqlite+aiosqlite:///hail_mary.db"
engine = None
SessionLocal = None

async def seed_db(session_maker):
    async with session_maker() as db:
        from sqlalchemy import select
        import json
        import os
        from backend.database.models import (
            MissionObjectiveModel, 
            EventDependencyModel, 
            ActionOptionModel, 
            ActionPredictionModel,
            DestinationModel
        )
        
        # 0. Seed destinations
        try:
            res_dest = await db.execute(select(DestinationModel).limit(1))
            if res_dest.scalars().first() is None:
                json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "destinations.json")
                if os.path.exists(json_path):
                    with open(json_path, "r") as f:
                        dest_data = json.load(f)
                    for item in dest_data:
                        dest = DestinationModel(name=item["name"], avg_distance_km=item["avg_distance_km"])
                        db.add(dest)
                    await db.commit()
                    print(f"[DB] Seeded {len(dest_data)} destinations.")
        except Exception as e:
            print(f"[DB] Error seeding destinations: {e}")
        
        # Check if already seeded
        try:
            res = await db.execute(select(MissionObjectiveModel).limit(1))
            if res.scalars().first() is not None:
                return  # Already seeded
        except Exception:
            # Table doesn't exist or other query error
            return

        print("[DB] Seeding default mission objectives, event dependencies, and sandbox actions...")
        
        # 1. Mission Objectives
        obj = MissionObjectiveModel(
            objective_name="Reach Tau Ceti Orbit",
            description="Safely navigate the spacecraft to Tau Ceti star system, maintaining basic resource reserves.",
            success_conditions='{"distance": 1000000.0, "fuel": 10.0, "health": 50.0, "power": 20.0}',
            failure_conditions='{"fuel": 0.0, "health": 0.0, "power": 0.0}',
            status="PENDING"
        )
        db.add(obj)
        
        # 2. Event Dependencies
        deps = [
            EventDependencyModel(parent_event_type="Solar Storm", child_event_type="Communication Loss", propagation_probability=0.7),
            EventDependencyModel(parent_event_type="Communication Loss", child_event_type="Navigation Drift", propagation_probability=0.5),
            EventDependencyModel(parent_event_type="Fuel Leak", child_event_type="Thruster Failure", propagation_probability=0.6),
            EventDependencyModel(parent_event_type="Thruster Failure", child_event_type="Navigation Drift", propagation_probability=0.4),
            EventDependencyModel(parent_event_type="Power Fluctuation", child_event_type="Sensor Malfunction", propagation_probability=0.5)
        ]
        db.add_all(deps)
        
        # 3. Action Options
        options = [
            # Fuel Leak
            ActionOptionModel(event_type="Fuel Leak", action_key="fuel_leak_ignore", action_name="Ignore Anomaly", description="Observe parameters and take no immediate action. High risk of resource depletion."),
            ActionOptionModel(event_type="Fuel Leak", action_key="fuel_leak_reduce_speed", action_name="Reduce Cruise Speed", description="Slow speed to reduce engine strain and slow down leak rate."),
            ActionOptionModel(event_type="Fuel Leak", action_key="fuel_leak_activate_backup", action_name="Activate Backup Tank", description="Close main cross-feed valves and draw propellant from auxiliary backup tank."),
            ActionOptionModel(event_type="Fuel Leak", action_key="fuel_leak_emergency_shutdown", action_name="Emergency Shutdown", description="Instantly close all lines and cut fuel feed to engines."),
            
            # Solar Storm
            ActionOptionModel(event_type="Solar Storm", action_key="solar_storm_ignore", action_name="Ignore Anomaly", description="Keep secondary grids active. High risk of electronics failure."),
            ActionOptionModel(event_type="Solar Storm", action_key="solar_storm_retract_panels", action_name="Retract Secondary Panels", description="Puts solar grids into secure configurations and deploy carbon shields."),
            ActionOptionModel(event_type="Solar Storm", action_key="solar_storm_divert_power", action_name="Divert Power to Deflectors", description="Activate active magnetic deflection shield surrounding the hull."),

            # Thruster Failure
            ActionOptionModel(event_type="Thruster Failure", action_key="thruster_fail_revector", action_name="Re-vector Remaining Bells", description="Adjust active thruster gimbals to counteract asymmetric torque."),
            ActionOptionModel(event_type="Thruster Failure", action_key="thruster_fail_backup_controller", action_name="Enable Backup Controller", description="Switch attitude control systems to standby navigation computers."),

            # Communication Loss
            ActionOptionModel(event_type="Communication Loss", action_key="comm_loss_automated_sweep", action_name="Initiate Automated Sweeps", description="Scan antenna arrays to reacquire the signal carrier frequency."),
            ActionOptionModel(event_type="Communication Loss", action_key="comm_loss_realign_gimbal", action_name="Manual Antenna Realignment", description="Rotate high gain antenna directly to last coordinates."),

            # Navigation Drift
            ActionOptionModel(event_type="Navigation Drift", action_key="nav_drift_star_field", action_name="Perform Star-Field Overlay", description="Calibrate drift coefficients against starry constellation guides."),

            # Micrometeorite Impact
            ActionOptionModel(event_type="Micrometeorite Impact", action_key="meteor_seal_pressure", action_name="Seal Bulkheads", description="Close isolation hatches to prevent depressurization."),
            ActionOptionModel(event_type="Micrometeorite Impact", action_key="meteor_run_diagnostic", action_name="Run Damage Diagnostic", description="Use ultrasound scanning to identify hairline micro-fractures.")
        ]
        db.add_all(options)

        # 4. Action Predictions
        predictions = [
            ActionPredictionModel(action_key="fuel_leak_ignore", fuel_delta=-12.0, power_delta=0.0, risk_reduction=0.0, success_delta=-15.0),
            ActionPredictionModel(action_key="fuel_leak_reduce_speed", fuel_delta=-3.0, power_delta=0.0, risk_reduction=40.0, success_delta=-2.0),
            ActionPredictionModel(action_key="fuel_leak_activate_backup", fuel_delta=15.0, power_delta=-2.0, risk_reduction=80.0, success_delta=8.0),
            ActionPredictionModel(action_key="fuel_leak_emergency_shutdown", fuel_delta=0.0, power_delta=5.0, risk_reduction=95.0, success_delta=-20.0),

            ActionPredictionModel(action_key="solar_storm_ignore", fuel_delta=0.0, power_delta=-25.0, risk_reduction=0.0, success_delta=-20.0),
            ActionPredictionModel(action_key="solar_storm_retract_panels", fuel_delta=0.0, power_delta=-10.0, risk_reduction=75.0, success_delta=5.0),
            ActionPredictionModel(action_key="solar_storm_divert_power", fuel_delta=0.0, power_delta=-20.0, risk_reduction=90.0, success_delta=10.0),

            ActionPredictionModel(action_key="thruster_fail_revector", fuel_delta=-2.0, power_delta=-2.0, risk_reduction=70.0, success_delta=6.0),
            ActionPredictionModel(action_key="thruster_fail_backup_controller", fuel_delta=0.0, power_delta=-5.0, risk_reduction=85.0, success_delta=8.0),

            ActionPredictionModel(action_key="comm_loss_automated_sweep", fuel_delta=0.0, power_delta=-4.0, risk_reduction=80.0, success_delta=10.0),
            ActionPredictionModel(action_key="comm_loss_realign_gimbal", fuel_delta=0.0, power_delta=-2.0, risk_reduction=60.0, success_delta=5.0),

            ActionPredictionModel(action_key="nav_drift_star_field", fuel_delta=0.0, power_delta=-3.0, risk_reduction=85.0, success_delta=12.0),

            ActionPredictionModel(action_key="meteor_seal_pressure", fuel_delta=0.0, power_delta=-2.0, risk_reduction=80.0, success_delta=10.0),
            ActionPredictionModel(action_key="meteor_run_diagnostic", fuel_delta=0.0, power_delta=-5.0, risk_reduction=60.0, success_delta=4.0)
        ]
        db.add_all(predictions)
        
        await db.commit()
        print("[DB] Successfully seeded static objectives and action predictions.")

async def init_db():
    global engine, SessionLocal
    
    if DATABASE_URL:
        db_host = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        print(f"[DB] Attempting connection to PostgreSQL at {db_host}...")
        try:
            engine = create_async_engine(
                DATABASE_URL, 
                echo=False,
                pool_size=15,
                max_overflow=25,
                pool_recycle=1800,
                pool_timeout=30,
                pool_pre_ping=True
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
            await seed_db(SessionLocal)
            print("[DB] Successfully connected and initialized PostgreSQL database.")
            return
        except Exception as e:
            print(f"[DB] WARNING: Failed to connect to PostgreSQL: {e}. Falling back to SQLite...")
            
    # Fallback SQLite init
    print(f"[DB] Initializing fallback SQLite database at {fallback_db}...")
    engine = create_async_engine(fallback_db, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
    await seed_db(SessionLocal)
    print("[DB] Successfully initialized SQLite database.")

async def get_db():
    """Dependency for obtaining database sessions in routes"""
    global SessionLocal
    if SessionLocal is None:
        await init_db()
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def clear_transaction_tables(db):
    from sqlalchemy import delete, update
    from backend.database.models import (
        EventModel,
        MissionEventModel,
        AgentDecisionModel,
        AgentReasoningModel,
        AgentMemoryModel,
        AgentConfidenceModel,
        AgentMetricsModel,
        AgentCollaborationModel,
        ConsensusRecordModel,
        RecoveryActionModel,
        ContingencyPlanModel,
        MissionMemoryModel,
        RiskHistoryModel,
        SubsystemHealthModel,
        MaintenanceForecastModel,
        ForecastResultModel,
        MissionTimelineModel
    )
    tables = [
        EventModel,
        MissionEventModel,
        AgentDecisionModel,
        AgentReasoningModel,
        AgentMemoryModel,
        AgentConfidenceModel,
        AgentMetricsModel,
        AgentCollaborationModel,
        ConsensusRecordModel,
        RecoveryActionModel,
        ContingencyPlanModel,
        MissionMemoryModel,
        RiskHistoryModel,
        SubsystemHealthModel,
        MaintenanceForecastModel,
        ForecastResultModel
    ]
    for table in tables:
        try:
            await db.execute(delete(table))
        except Exception as e:
            print(f"[DB] Error clearing table {table.__tablename__}: {e}")
            
    try:
        await db.execute(update(MissionTimelineModel).values(status="PENDING"))
    except Exception as e:
        print(f"[DB] Error resetting timeline status: {e}")

