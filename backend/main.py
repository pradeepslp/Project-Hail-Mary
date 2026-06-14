import json
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.database import connection
from backend.database.redis_client import init_redis, get_redis
from backend.websocket.connection import manager
from backend.api.routes import router as api_router
from backend.api.routes_phase5 import router as phase5_router
from backend.api.routes_phase6 import router as phase6_router
from backend.api.routes_llm import router as llm_router
from backend.api.routes_trajectory import router as trajectory_router
from backend.simulator.engine import simulator
from backend.simulator.swarm_engine import swarm_simulator
from backend.utils.timezone_helper import ist_now

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[Server] Starting Project Hail Mary API Core...")
    await connection.init_db()
    
    # Pre-seed Phase 4 Knowledge Graph Node/Edge structure
    if connection.SessionLocal:
        try:
            async with connection.SessionLocal() as db:
                from backend.agent.knowledge_graph import seed_knowledge_graph
                await seed_knowledge_graph(db)
                
                # Wipe any remaining transaction/anomaly tables to guarantee clean state
                from backend.database.connection import clear_transaction_tables
                await clear_transaction_tables(db)
                await db.commit()
                print("[DB] Cleared historical transaction tables on startup.")
        except Exception as e:
            print(f"[Server] Failed to pre-seed knowledge graph/clear tables: {e}")

    await init_redis()
    try:
        await simulator.sync_with_trajectory()
        print("[Simulator] Synced simulator state with current trajectory on startup.")
    except Exception as e:
        print(f"[Server] Failed to sync simulator with trajectory on startup: {e}")
    await simulator.log_event("INFO", "Mission Control digital twin simulation server started")
    await swarm_simulator.start()
    yield
    # Shutdown
    print("[Server] Shutting down simulation tasks...")
    if simulator.running_task and not simulator.running_task.done():
        simulator.running_task.cancel()
    if swarm_simulator.running_task and not swarm_simulator.running_task.done():
        swarm_simulator.running_task.cancel()
    # Close Redis client connection
    redis = await get_redis()
    if hasattr(redis, "close"):
        await redis.close()

app = FastAPI(
    title="Project Hail Mary API",
    description="Digital Twin and Mission Simulation Foundation Engine",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware to allow the frontend dashboard to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST paths
app.include_router(api_router)
app.include_router(phase5_router)
app.include_router(phase6_router)
app.include_router(llm_router)
app.include_router(trajectory_router, prefix="/api")


# WebSocket path for streaming dashboard data
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Fetch current simulator states
        telemetry = simulator.get_telemetry_data()
        mission = simulator.get_mission_info()

        # Retrieve historic events from Redis to populate log console
        redis = await get_redis()
        events = await redis.lrange("hail_mary:events", 0, -1)
        
        # Send hydration packet
        await websocket.send_json({
            "type": "INIT",
            "mission": mission.model_dump(),
            "telemetry": telemetry.model_dump(),
            "events": events or [],
            "active_events": [
                {k: v for k, v in ev.items() if k != "duration"} 
                for ev in simulator.active_events
            ]
        })

        # Maintain connection
        while True:
            # Disconnects are raised from receive_text
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Connection error: {e}")
        manager.disconnect(websocket)
