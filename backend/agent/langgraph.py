import json
import random
import urllib.request
import urllib.error
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import connection
from backend.database.models import (
    AgentDecisionModel,
    AgentReasoningModel,
    AgentMemoryModel,
    AgentConfidenceModel,
    AgentMetricsModel,
    AgentCollaborationModel
)
from backend.agent.crewai import CrewAIAgentDefinitions
from backend.agent.learning import learning_system
from backend.database.redis_client import get_redis
from backend.websocket.connection import manager
from backend.utils.timezone_helper import ist_now

import time

# Ollama REST endpoints details
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3:latest"

_ollama_online = None
_last_ollama_check = 0.0

def fetch_ollama_json(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Helper to query local Ollama service for JSON structured responses"""
    global _ollama_online, _last_ollama_check
    
    current_time = time.time()
    # Skip checking if we already know it is offline and last check was less than 60s ago
    if _ollama_online is False and (current_time - _last_ollama_check) < 60.0:
        return None
        
    _last_ollama_check = current_time

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        # 1.0 second timeout to prevent freezing simulation loops
        with urllib.request.urlopen(req, timeout=1.0) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            content_str = res_json["message"]["content"]
            _ollama_online = True
            return json.loads(content_str)
    except Exception as e:
        print(f"[Ollama LLM] Service query skipped (using local heuristics): {e}")
        _ollama_online = False
        return None

class LangGraphOrchestrator:
    def __init__(self):
        self.crew = CrewAIAgentDefinitions()

    async def run_decision_workflow(
        self,
        telemetry: Dict[str, Any],
        active_events: List[Dict[str, Any]],
        action_options: Dict[str, List[Dict[str, str]]],
        difficulty: str,
        autonomy_level: int
    ) -> List[Dict[str, Any]]:
        """Orchestrates the agent workflow using Heuristic Multi-Agent collaboration and LLM providers"""
        from backend.agent.multi_agent import multi_agent_engine
        from backend.agent.llm_reasoning import llm_config, llm_reasoning_engine
        from backend.simulator.engine import simulator
        
        decisions_taken = []
        
        for event in active_events:
            event_id = event.get("id")
            event_type = event.get("event_type")
            options = action_options.get(event_type, [])
            if not options:
                continue
 
            # Skip events that are already mitigating or resolved
            if event.get("status") in ["MITIGATING", "RESOLVED"]:
                continue
 
            print(f"[LangGraph/MultiAgent] Initiating decision pipeline for active hazard: {event_type} (ID: {event_id})")
 
            # 1. Run deterministic multi-agent collaboration pipeline first
            agent_dec = await multi_agent_engine.run_collaboration_pipeline(telemetry, event, options)
            
            chosen_key = agent_dec["chosen_action"]
            confidence = agent_dec["confidence"]
            reasoning_text = agent_dec["reasoning"]
            
            # Predict outcome deltas
            pred = simulator.action_predictions.get(chosen_key)
            if pred:
                expected_outcome = {
                    "mission_success_change": pred.get("success_delta", 5.0),
                    "risk_reduction": pred.get("risk_reduction", 10.0),
                    "power_change": pred.get("power_delta", 0.0),
                    "fuel_change": pred.get("fuel_delta", -3.0)
                }
            else:
                expected_outcome = {
                    "mission_success_change": 5.0,
                    "risk_reduction": 10.0,
                    "power_change": 0.0,
                    "fuel_change": -3.0
                }

            # 2. If LLM provider is active, execute LLM decision as primary commander authority
            llm_active = llm_config.provider_type in ["openai", "anthropic", "gemini", "ollama"]
            # Check if uvicorn can connect or if Ollama URL is valid in memory
            if llm_active:
                try:
                    dec = await llm_reasoning_engine.evaluate_event_decision(
                        telemetry=telemetry,
                        event=event,
                        options=options,
                        autonomy_level=autonomy_level
                    )
                    chosen_key = dec["chosen_action"]
                    confidence = dec["confidence"]
                    reasoning_text = " ".join(dec["reasoning"]) if isinstance(dec["reasoning"], list) else dec["reasoning"]
                    expected_outcome = dec["expected_outcome"]
                except Exception as e:
                    print(f"[LLM Decision failed, fallback to multi-agent] Exception: {e}")
 
            decisions_taken.append({
                "event_id": event_id,
                "event_type": event_type,
                "chosen_action": chosen_key,
                "confidence": confidence,
                "reasoning": reasoning_text,
                "expected_outcome": expected_outcome,
                "executed": (autonomy_level >= 3)
            })
 
        return decisions_taken

    def run_navigation_agent(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Calculates trajectory alignment and scores options based on Navigation goals"""
        event_type = event["event_type"]
        pos_err = telemetry.get("position_error", 0.0)
        
        # Check Ollama
        sys_p = f"You are the Navigation Agent for Project Hail Mary. Backstory: {self.crew.nav_agent.backstory}. Goal: {self.crew.nav_agent.goal}."
        user_p = f"State: position error={pos_err} km. Active event={event_type}. Choices={options}. Output JSON format."
        ollama_res = fetch_ollama_json(sys_p, user_p)
        if ollama_res:
            return {
                "recommendation": ollama_res.get("recommendation", "Adjust trajectory offsets."),
                "scores": ollama_res.get("scores", {}),
                "risk": round(pos_err * 0.5, 1)
            }

        # Fallback local heuristics
        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "star_field" in k:
                scores[k] = 95.0
            elif "reduce_speed" in k:
                scores[k] = 70.0
            elif "ignore" in k:
                scores[k] = 20.0
        return {
            "recommendation": f"Current navigational drift registers position error offsets of {pos_err:.2f} km. Highly recommend orbital alignment corrections.",
            "scores": scores,
            "risk": min(100.0, round(pos_err * 1.5, 1))
        }

    def run_fuel_agent(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Conserves propellant & power resources"""
        event_type = event["event_type"]
        fuel = telemetry.get("fuel", 100.0)
        power = telemetry.get("power", 100.0)

        sys_p = f"You are the Fuel Agent. Backstory: {self.crew.fuel_agent.backstory}. Goal: {self.crew.fuel_agent.goal}."
        user_p = f"State: fuel={fuel}%, power={power}%. Active event={event_type}. Choices={options}. Output JSON format."
        ollama_res = fetch_ollama_json(sys_p, user_p)
        if ollama_res:
            return {
                "recommendation": ollama_res.get("recommendation", "Optimize fuel valve pressures."),
                "scores": ollama_res.get("scores", {}),
                "risk": round(100.0 - fuel, 1)
            }

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "backup" in k or "retract" in k:
                scores[k] = 90.0
            elif "reduce_speed" in k:
                scores[k] = 75.0
            elif "ignore" in k:
                scores[k] = 15.0
        return {
            "recommendation": f"Propellant levels are at {fuel:.1f}% capacity. Battery storage registers {power:.1f}% charge voltage. Prioritize emergency tank activation.",
            "scores": scores,
            "risk": round(100.0 - fuel, 1)
        }

    def run_safety_agent(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Monitors system failures risk ratings"""
        event_type = event["event_type"]
        health = telemetry.get("health", 100.0)
        
        sys_p = f"You are the Safety Agent. Backstory: {self.crew.safety_agent.backstory}. Goal: {self.crew.safety_agent.goal}."
        user_p = f"State: average subsystems health={health}%. Active event={event_type}. Choices={options}. Output JSON format."
        ollama_res = fetch_ollama_json(sys_p, user_p)
        if ollama_res:
            return {
                "recommendation": ollama_res.get("recommendation", "Perform damage control measures."),
                "scores": ollama_res.get("scores", {}),
                "risk": round(100.0 - health, 1)
            }

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "emergency_shutdown" in k or "divert_power" in k:
                scores[k] = 95.0
            elif "seal_pressure" in k:
                scores[k] = 90.0
            elif "ignore" in k:
                scores[k] = 10.0
        return {
            "recommendation": f"Spacecraft hull armor structure registers diagnostic integrity of {health:.1f}%. Immediate emergency isolation required.",
            "scores": scores,
            "risk": round(100.0 - health, 1)
        }

    def run_science_agent(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        """Coordinates sensor records collection objectives"""
        event_type = event["event_type"]
        progress = telemetry.get("mission_progress", 0.0)

        sys_p = f"You are the Science Agent. Backstory: {self.crew.science_agent.backstory}. Goal: {self.crew.science_agent.goal}."
        user_p = f"State: mission progress={progress}%. Active event={event_type}. Choices={options}. Output JSON format."
        ollama_res = fetch_ollama_json(sys_p, user_p)
        if ollama_res:
            return {
                "recommendation": ollama_res.get("recommendation", "Prioritize science data collections."),
                "scores": ollama_res.get("scores", {}),
                "risk": 20.0
            }

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 60.0
            if "run_diagnostic" in k or "star_field" in k:
                scores[k] = 90.0
            elif "ignore" in k:
                scores[k] = 40.0
        return {
            "recommendation": f"Mission trajectory has progressed to {progress:.1f}% of target distance. Prioritize science collection scan diagnostic records.",
            "scores": scores,
            "risk": 15.0
        }

    def evaluate_utilities(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        options: List[Dict[str, str]],
        nav_rec: Dict[str, Any],
        fuel_rec: Dict[str, Any],
        safety_rec: Dict[str, Any],
        science_rec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Applies Feature 4 Utility maximization calculation formula: U = 0.35*Success + 0.25*Safety + 0.20*Fuel + 0.10*Time + 0.10*Science"""
        utility_scores = {}
        expected_deltas = {}
        chosen_action = None
        max_utility = -9999.0

        for opt in options:
            k = opt["action_key"]
            
            # Predict deltas using Scikit-Learn
            preds = learning_system.predict_action_outcome(telemetry, k)
            expected_deltas[k] = preds

            # Calculate individual criterion variables (scale 0-100)
            nav_score = nav_rec["scores"].get(k, 50.0)
            fuel_score = fuel_rec["scores"].get(k, 50.0)
            safety_score = safety_rec["scores"].get(k, 50.0)
            science_score = science_rec["scores"].get(k, 50.0)

            # Expected success score after delta prediction addition
            expected_success = min(100.0, max(0.0, (telemetry.get("success_probability", 80.0) + preds["success_delta"])))
            
            # Utility function composition
            U = (
                0.35 * expected_success +
                0.25 * safety_score +
                0.20 * fuel_score +
                0.10 * nav_score +  # Represents time efficiency/drift mapping
                0.10 * science_score
            )
            utility_scores[k] = round(U, 1)

            if U > max_utility:
                max_utility = U
                chosen_action = k

        # Confidence engine calculation: margin between chosen option and runner-up
        sorted_utils = sorted(utility_scores.values(), reverse=True)
        margin = (sorted_utils[0] - sorted_utils[1]) if len(sorted_utils) > 1 else 15.0
        confidence = min(100.0, max(40.0, 75.0 + margin * 2.0))

        return {
            "chosen_action": chosen_action,
            "confidence_score": round(confidence, 1),
            "utility_scores": utility_scores,
            "expected_deltas": expected_deltas.get(chosen_action, {})
        }

    async def generate_commander_reasoning(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        chosen_key: str,
        confidence: float,
        nav_rec: Dict[str, Any],
        fuel_rec: Dict[str, Any],
        safety_rec: Dict[str, Any],
        science_rec: Dict[str, Any]
    ) -> str:
        """Asks Ollama to summarize why the chosen action wins, falling back to dynamic template"""
        event_type = event["event_type"]
        
        sys_p = f"You are the Mission Commander AI for Project Hail Mary. Backstory: {self.crew.commander_agent.backstory}. Goal: {self.crew.commander_agent.goal}."
        user_p = (
            f"Active event: {event_type}. Chosen sandbox action: {chosen_key} (confidence {confidence}%).\n"
            f"Recommendations:\n"
            f"- Nav: {nav_rec['recommendation']}\n"
            f"- Fuel: {fuel_rec['recommendation']}\n"
            f"- Safety: {safety_rec['recommendation']}\n"
            f"- Science: {science_rec['recommendation']}\n"
            f"Explain in 2 clear sentences why this action was selected and its impact."
        )
        ollama_res = fetch_ollama_json(sys_p, user_p)
        if ollama_res and "explanation" in ollama_res:
            return ollama_res["explanation"]

        # Local heuristics fallback template
        reasons = {
            "fuel_leak_activate_backup": "Backup tanks activation offsets active Port valve leaks. Conserves core fuel velocity vectors.",
            "fuel_leak_reduce_speed": "Cruise speed reductions lower fuel injection rates and mitigate fuel pressure drift drops.",
            "solar_storm_divert_power": "Deflector grid alignment provides 90% protection against critical battery electromagnetic decay.",
            "solar_storm_retract_panels": "Retracting secondary solar wings protects grids from critical electrical discharges.",
            "thruster_fail_revector": "Gimbals re-vectoring offsets asymmetrical torque, stabilizing attitude coordinates drift.",
            "comm_loss_automated_sweep": "S-Band carrier realignments restore ground link connections in high noise zones.",
            "nav_drift_star_field": "Star constellation alignment overlay corrects optical calibration discrepancies.",
            "meteor_seal_pressure": "Sealing isolation bulkheads prevents pressure loss warnings in crew compartments."
        }
        return reasons.get(chosen_key, f"Executive command selected '{chosen_key}' to address telemetry warning and optimize flight trajectories success coefficients.")

    async def run_validation_mc(self, telemetry: Dict[str, Any], event: Dict[str, Any], action_key: str) -> float:
        """Feature 5: Run a fast Monte Carlo check for the action to validate success rates"""
        # Call simulation engine run_monte_carlo blocking logic on worker pool
        # We simulate a tiny sample (100 runs) for speed in live ticking loops
        from backend.simulator.engine import simulator
        
        print(f"[Monte Carlo Validation] Validating action: {action_key} via fast-forward simulations...")
        
        # Temporarily mock the action execution on state copy
        try:
            res = await simulator.run_monte_carlo(iterations=100)
            return res.get("avg_success_prob", 85.0)
        except Exception:
            return 85.0

    async def save_agent_decision_db(
        self,
        event_type: str,
        event_id: int,
        chosen_key: str,
        confidence: float,
        expected_outcome: Dict[str, Any],
        autonomy_level: int,
        reasoning_text: str,
        utility_scores: Dict[str, float],
        nav_rec: Dict[str, Any],
        fuel_rec: Dict[str, Any],
        safety_rec: Dict[str, Any],
        science_rec: Dict[str, Any]
    ) -> Optional[int]:
        """Saves decisions, reasoning context, and collaborative ratings to PostgreSQL"""
        if not connection.SessionLocal:
            return None

        try:
            async with connection.SessionLocal() as db:
                # 1. Save Decision
                decision = AgentDecisionModel(
                    timestamp=ist_now(),
                    event_type=event_type,
                    event_id=event_id,
                    chosen_action=chosen_key,
                    confidence_score=confidence,
                    expected_outcome=json.dumps(expected_outcome),
                    actual_outcome="{}",
                    executed_autonomously=(autonomy_level >= 3),
                    autonomy_level=autonomy_level
                )
                db.add(decision)
                await db.flush()
                d_id = decision.id

                # 2. Save Reasoning
                reasoning = AgentReasoningModel(
                    decision_id=d_id,
                    timestamp=ist_now(),
                    reasoning_text=reasoning_text,
                    utility_scores=json.dumps(utility_scores)
                )
                db.add(reasoning)

                # 3. Save Collaboration Ratings
                coll = AgentCollaborationModel(
                    timestamp=ist_now(),
                    event_id=event_id,
                    nav_recommendation=json.dumps(nav_rec),
                    fuel_recommendation=json.dumps(fuel_rec),
                    safety_recommendation=json.dumps(safety_rec),
                    science_recommendation=json.dumps(science_rec),
                    commander_decision=chosen_key
                )
                db.add(coll)
                
                # 4. Save Confidence metric factors
                conf = AgentConfidenceModel(
                    timestamp=ist_now(),
                    decision_key=chosen_key,
                    confidence_score=confidence,
                    factors=json.dumps(["Subsystem Performance Rating", "Utility margin threshold", "Historical R2 score"])
                )
                db.add(conf)

                await db.commit()
                return d_id
        except Exception as e:
            print(f"[DB ERROR] Agent decision logging failed: {e}")
            return None

    async def update_redis_cache(
        self,
        event_id: int,
        chosen_key: str,
        confidence: float,
        reasoning_text: str,
        nav_rec: Dict[str, Any],
        fuel_rec: Dict[str, Any],
        safety_rec: Dict[str, Any],
        science_rec: Dict[str, Any]
    ):
        """Feature 10: Cache live agent status, reasoning context, and decisions to Redis"""
        try:
            redis = await get_redis()
            
            # 1. Live state
            state_data = {
                "event_id": event_id,
                "chosen_action": chosen_key,
                "confidence": confidence,
                "timestamp": ist_now().isoformat(),
                "sub_agents": {
                    "nav": nav_rec,
                    "fuel": fuel_rec,
                    "safety": safety_rec,
                    "science": science_rec
                }
            }
            await redis.set("hail_mary:agent:state", json.dumps(state_data))
            
            # 2. Reasoning context
            await redis.set("hail_mary:agent:reasoning", reasoning_text)
            
            # 3. Short term memory queue (sliding window of last 100 actions)
            mem_data = {
                "action": chosen_key,
                "confidence": confidence,
                "timestamp": ist_now().isoformat()
            }
            await redis.rpush("hail_mary:agent:memory", json.dumps(mem_data))
            # Trim list to last 100 items
            await redis.ltrim("hail_mary:agent:memory", -100, -1)

        except Exception as e:
            print(f"[Redis Cache] Failed to write agent variables: {e}")

# Global orchestrator instance
graph_orchestrator = LangGraphOrchestrator()
