import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.database.connection import get_db
from backend.database.models import (
    LLMPromptModel,
    LLMDecisionModel,
    LLMReasoningModel,
    LLMOutcomeModel,
    DecisionMetricsModel,
    DestinationModel,
    MissionObjectiveModel,
    CommanderDecisionModel
)
from backend.agent.llm_reasoning import llm_config, llm_reasoning_engine
from backend.simulator.engine import simulator
from backend.utils.timezone_helper import ist_now

router = APIRouter(prefix="/api/llm", tags=["LLM Decision Intelligence"])

# --- REQUEST SCHEMAS ---

class LLMConfigUpdate(BaseModel):
    provider_type: str
    model_name: Optional[str] = None
    ollama_url: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    gemini_key: Optional[str] = None
    temperature: Optional[float] = 0.2

class LLMTriggerRequest(BaseModel):
    event_id: int

# --- ENDPOINTS ---

@router.get("/config")
async def get_llm_config():
    """Fetch the active provider type and configuration flags"""
    return llm_config.to_dict()

@router.post("/config")
async def update_llm_config(req: LLMConfigUpdate):
    """Dynamically configure the active LLM provider and credentials"""
    llm_config.provider_type = req.provider_type
    if req.model_name is not None:
        llm_config.model_name = req.model_name
    if req.ollama_url is not None:
        llm_config.ollama_url = req.ollama_url
    if req.openai_key is not None:
        llm_config.openai_key = req.openai_key
    if req.anthropic_key is not None:
        llm_config.anthropic_key = req.anthropic_key
    if req.gemini_key is not None:
        llm_config.gemini_key = req.gemini_key
    if req.temperature is not None:
        llm_config.temperature = req.temperature

    return {"status": "success", "message": "LLM Configuration updated.", "config": llm_config.to_dict()}

@router.get("/decisions")
async def get_llm_decisions(db: AsyncSession = Depends(get_db)):
    """Fetch recent LLM autonomous decisions logs"""
    stmt = (
        select(LLMDecisionModel)
        .order_by(LLMDecisionModel.timestamp.desc())
        .limit(20)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    results = []
    for r in records:
        # Load reasoning steps
        stmt_reas = select(LLMReasoningModel).where(LLMReasoningModel.decision_id == r.id)
        res_reas = await db.execute(stmt_reas)
        reas_rec = res_reas.scalars().first()
        reasoning_list = json.loads(reas_rec.reasoning_steps) if reas_rec else []

        # Load expected outcomes
        stmt_out = select(LLMOutcomeModel).where(LLMOutcomeModel.decision_id == r.id)
        res_out = await db.execute(stmt_out)
        out_rec = res_out.scalars().first()
        expected = {}
        actual = {}
        if out_rec:
            expected = {
                "mission_success_change": out_rec.success_change,
                "risk_reduction": out_rec.risk_reduction,
                "power_change": out_rec.power_change,
                "fuel_change": out_rec.fuel_change
            }
            actual = {
                "actual_success": out_rec.actual_success,
                "actual_risk": out_rec.actual_risk,
                "evaluated": out_rec.evaluated
            }

        # Load prompt text
        stmt_p = select(LLMPromptModel).where(LLMPromptModel.id == r.prompt_id)
        res_p = await db.execute(stmt_p)
        p_rec = res_p.scalars().first()
        prompt_text = p_rec.prompt_text if p_rec else ""

        results.append({
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "decision": r.decision,
            "confidence": r.confidence,
            "chosen_action_key": r.chosen_action_key,
            "status": r.status,
            "autonomy_level": r.autonomy_level,
            "reasoning": reasoning_list,
            "expected_outcome": expected,
            "actual_outcome": actual,
            "prompt_text": prompt_text
        })

    return results

@router.get("/metrics")
async def get_llm_metrics(db: AsyncSession = Depends(get_db)):
    """Fetch aggregated decision metrics and performance indices"""
    stmt = (
        select(DecisionMetricsModel)
        .order_by(DecisionMetricsModel.timestamp.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    metric = res.scalars().first()

    if metric:
        return {
            "decision_accuracy": metric.decision_accuracy,
            "avg_confidence": metric.avg_confidence,
            "success_rate": metric.success_rate,
            "reasoning_quality": metric.reasoning_quality
        }
    
    # Baseline defaults if empty
    return {
        "decision_accuracy": 85.0,
        "avg_confidence": 78.0,
        "success_rate": 90.0,
        "reasoning_quality": 92.5
    }

@router.post("/trigger")
async def trigger_llm_decision(req: LLMTriggerRequest, background_tasks: BackgroundTasks):
    """Triggers a manual evaluation call to the LLM Commander for an active event"""
    target_event = None
    for ev in simulator.active_events:
        if ev["id"] == req.event_id:
            target_event = ev
            break
            
    if not target_event:
        raise HTTPException(status_code=404, detail=f"Active event ID {req.event_id} not found.")

    event_type = target_event["event_type"]
    options = simulator.action_options.get(event_type, [])
    if not options:
        raise HTTPException(status_code=400, detail=f"No mitigation options configured for anomaly {event_type}.")

    telemetry = simulator.get_telemetry_data().model_dump()

    # Define background execution task
    async def evaluate_and_execute():
        dec = await llm_reasoning_engine.evaluate_event_decision(
            telemetry=telemetry,
            event=target_event,
            options=options,
            autonomy_level=simulator.autonomy_level
        )
        if dec.get("status") in ["Executed", "Fallback"]:
            # Auto-execute if autonomy authorizes
            await simulator.execute_action(req.event_id, dec["chosen_action"])

    background_tasks.add_task(evaluate_and_execute)
    return {"status": "success", "message": f"LLM evaluation triggered in the background for event {event_type}."}


# --- CHAT SCHEMAS & ROUTES ---

class ChatRequest(BaseModel):
    message: str
    history: Optional[str] = ""
    crew: Optional[List[Dict[str, Any]]] = None
    objectives: Optional[List[Dict[str, Any]]] = None

@router.post("/chat")
async def chat_with_gemini(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Conversational AI query endpoint routed to Google Gemini 2.5 Flash"""
    try:
        from backend.services.gemini_service import gemini_service
        
        # 1. Gather Telemetry
        telemetry = simulator.get_telemetry_data().model_dump()
        
        # 2. Gather Mission Info
        mission_info = simulator.get_mission_info().model_dump()
        
        # 3. Trajectory Planner calculations
        try:
            from backend.trajectory.planner import TrajectoryPlanner
            planner = await TrajectoryPlanner.load_from_redis()
            stmt_dest = select(DestinationModel).where(DestinationModel.name == planner.destination)
            res_dest = await db.execute(stmt_dest)
            dest = res_dest.scalars().first()
            distance = dest.avg_distance_km if dest else 0.0
            trajectory_outputs = planner.calculate(distance)
            trajectory_context = {
                "origin": planner.origin,
                "destination": planner.destination,
                "payload_mass": planner.payload_mass,
                "mission_type": planner.mission_type,
                "active_events": planner.active_events,
                "outputs": trajectory_outputs
            }
        except Exception as e:
            trajectory_context = {"status": "unavailable", "error": str(e)}

        # 4. Active Anomalies
        active_anomalies = [
            {k: v for k, v in ev.items() if k != "duration"}
            for ev in simulator.active_events
        ]
        
        # 5. Agent Recommendations
        agent_context = {}
        try:
            from backend.database.redis_client import get_redis
            redis = await get_redis()
            state_str = await redis.get("hail_mary:agent:state")
            reasoning_str = await redis.get("hail_mary:agent:reasoning")
            debate_str = await redis.get("hail_mary:agent:current_debate")
            
            agent_context = {
                "agent_state": json.loads(state_str) if state_str else {},
                "agent_reasoning": reasoning_str.decode("utf-8") if isinstance(reasoning_str, bytes) else (reasoning_str or ""),
                "debate": json.loads(debate_str) if debate_str else []
            }
        except Exception as e:
            agent_context = {"status": "unavailable", "error": str(e)}
            
        # 6. Commander Decisions
        try:
            stmt_dec = select(CommanderDecisionModel).order_by(CommanderDecisionModel.timestamp.desc()).limit(5)
            res_dec = await db.execute(stmt_dec)
            recent_decisions = [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "event_id": r.event_id,
                    "chosen_action": r.chosen_action,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "utility_score": r.utility_score
                }
                for r in res_dec.scalars().all()
            ]
        except Exception as e:
            recent_decisions = []
            
        # 7. Mission Objectives
        try:
            stmt_obj = select(MissionObjectiveModel)
            res_obj = await db.execute(stmt_obj)
            objectives = [
                {
                    "name": o.objective_name,
                    "description": o.description,
                    "status": o.status
                }
                for o in res_obj.scalars().all()
            ]
        except Exception as e:
            objectives = req.objectives or []
            
        # 8. Crew Status
        crew_status = req.crew or [
            {"name": "Ryland Grace", "role": "Mission Commander", "health": 100, "morale": 100},
            {"name": "Yury Kovalev", "role": "Chief Engineer", "health": 100, "morale": 100},
            {"name": "Dimitri Demchenko", "role": "Life Support Officer", "health": 100, "morale": 100}
        ]
        
        # 9. Mission Timeline (History)
        mission_timeline = simulator.mission_history[-15:]

        # Build Full Context
        mission_context = f"""
Current Live Mission Context:

--- Telemetry ---
- Elapsed Time: {telemetry.get("mission_elapsed", "N/A")}
- Mission Progress: {telemetry.get("mission_progress", 0.0):.1f}%
- Destination: {mission_info.get("destination", "Mars")}
- Distance Remaining: {telemetry.get("distance_remaining", "N/A")}
- Hull Health: {telemetry.get("health", 100.0):.1f}%
- Fuel: {telemetry.get("fuel", 100.0):.1f}%
- Reactor Power: {telemetry.get("power", 100.0):.1f}%
- Cabin Oxygen: {telemetry.get("oxygen", 100.0):.1f}%
- Cabin Temp: {telemetry.get("temperature", 25.0):.1f}°C
- Velocity: {telemetry.get("velocity", 0.0):.1f} km/s
- Communication State: {telemetry.get("communication", "ONLINE")}
- Success Probability: {telemetry.get("success_probability", 95.0):.1f}%
- Failure Probability: {telemetry.get("failure_probability", 5.0):.1f}%

--- Subsystem Health Status ---
{json.dumps(telemetry.get("subsystems", {}), indent=2)}

--- Active Anomalies & Events ---
{json.dumps(active_anomalies, indent=2) if active_anomalies else "No active anomalies."}

--- Trajectory Planning ---
- Origin: {trajectory_context.get("origin", "N/A")}
- Destination: {trajectory_context.get("destination", "N/A")}
- Trajectory Feasibility: {trajectory_context.get("outputs", {}).get("feasibility", "N/A")}
- ETA: {trajectory_context.get("outputs", {}).get("eta", "N/A")}

--- Crew Status ---
{json.dumps(crew_status, indent=2)}

--- Mission Objectives ---
{json.dumps(objectives, indent=2)}

--- Recent Agent Recommendations & Specialist Consensus ---
{json.dumps(agent_context, indent=2)}

--- Commander Decisions Log ---
{json.dumps(recent_decisions, indent=2)}

--- Mission Timeline (Recent Events Log) ---
{json.dumps(mission_timeline, indent=2)}

--- Conversation Memory (Relevant Past Records) ---
{req.history if req.history else "No past records."}
"""

        system_prompt = """
You are HAIL MARY (Conversational Mission Intelligence), a friendly extraterrestrial engineer and trusted mission companion travelling alongside the astronaut on the HAIL MARY spacecraft.

You have access to:
- Telemetry
- Mission Planner
- Trajectory Planner
- Crew Status
- Active Events
- Agent Decisions

You are responsible for:
- Mission Awareness
- Risk Assessment
- Navigation Guidance
- Crew Assistance

Tone and Speech Patterns:
- Speak in a voice that is calm, warm, highly intelligent, curious, supportive, reassuring, analytical, and patient.
- Never sound aggressive, militaristic, robotic monotone, alarmist, or emotionless.
- Use short sentences and clear, reassuring phrasing.
- Show gentle enthusiasm when discussing discoveries, and calm, reassuring confidence during emergencies.
- Keep your responses short (1-3 sentences maximum) for fluid conversations, unless the user specifically asks for deep details or structured explanations.
- Always answer using current mission data. Never invent telemetry values. If information is unavailable, state that clearly.

Available System Actions (If you decide to recommend or execute an action, append these tokens exactly to the END of your text response):
- Start Sim: [ACTION: start_mission]
- Pause Sim: [ACTION: pause_simulation]
- Resume Sim: [ACTION: resume_mission]
- Open Replay: [ACTION: replay_last_decision]
- Export PDF Report: [ACTION: generate_report]
- What-If Sandbox: [ACTION: run_what_if]
- Inject Dual Failure: [ACTION: simulate_dual_failure]
- Open Analytics: [ACTION: export_analytics]
- Switch Space/Earth Modes: [ACTION: switch_mode]
- Open Graph: [ACTION: open_kg]
- Open 3D View: [ACTION: open_3d]
- Approve Recommendation: [ACTION: approve_anomaly]
- Reject Recommendation: [ACTION: reject_anomaly]
- Compare Alternatives: [ACTION: compare_alternatives]
- Rerun Simulations: [ACTION: rerun_simulations]
- Activate Backup Tank: [ACTION: activate_backup_tank]
- Enter Safe Mode: [ACTION: enter_safe_mode]
- Change Route: [ACTION: change_route]
- Replay Mission Events: [ACTION: replay_mission_events]
- Generate Mission Summary: [ACTION: generate_mission_summary]

You can highlight metrics by appending:
- [HIGHLIGHT: fuel]
- [HIGHLIGHT: power]
- [HIGHLIGHT: oxygen]
- [HIGHLIGHT: health]
- [HIGHLIGHT: velocity]
- [HIGHLIGHT: progress]
- [HIGHLIGHT: crew]
- [HIGHLIGHT: objectives]
- [HIGHLIGHT: 3d]
- [HIGHLIGHT: intelligence]
"""

        prompt = f"{mission_context}\n\nUser Question:\n{req.message}"
        
        # Generate response using Gemini Service
        response_text = await gemini_service.generate_response(prompt, system_instruction=system_prompt)
        
        # Log to db
        await simulator.log_event("AI", f"Conversational AI response: {response_text[:80]}...")
        
        return {"response": response_text}
        
    except ValueError as ve:
        # Key not configured yet - fall back to mock helper with clear message
        print(f"[Gemini API fallback] {ve}")
        return {"response": "[Fallback Warning: Gemini API key is not configured in your .env file yet. Please set GEMINI_API_KEY to activate.]"}
    except Exception as ex:
        print(f"[Gemini API Error] {ex}")
        raise HTTPException(status_code=500, detail=str(ex))
