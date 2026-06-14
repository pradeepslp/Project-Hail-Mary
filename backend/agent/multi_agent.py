import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from backend.database import connection
from backend.database.models import (
    AgentRegistryModel,
    AgentRecommendationModel,
    AgentConsensusModel,
    CommanderDecisionModel,
    AgentMemoryModel,
    AgentMetricsModel
)
from backend.database.redis_client import get_redis
from backend.websocket.connection import manager
from backend.utils.timezone_helper import ist_now

# --- SPECIALIST AGENTS ---

class NavigationAgent:
    def __init__(self):
        self.name = "Navigation Agent"
        self.role = "Trajectory Specialist"
        self.responsibilities = "Route Optimization, Distance Analysis, Travel Time Analysis, Course Correction, Orbital Maneuvers"

    def analyze(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        event_type = event.get("event_type", "Unknown")
        pos_err = telemetry.get("position_error", 0.0)
        
        # Calculate option scores
        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0  # neutral
            if "star_field" in k:
                scores[k] = 95.0
            elif "revector" in k:
                scores[k] = 90.0
            elif "reduce_speed" in k:
                scores[k] = 75.0
            elif "comm_loss" in k:
                scores[k] = 65.0
            elif "ignore" in k:
                scores[k] = 15.0

        # Choose option with highest score
        chosen_key = max(scores, key=scores.get) if scores else None
        
        # Deterministic confidence based on tracking accuracy
        confidence = max(50.0, min(98.0, 100.0 - pos_err))
        
        # Reasoning text
        reasoning = (
            f"Current trajectory shows position drift error of {pos_err:.2f} km. "
            f"Recommended Action: {chosen_key}. This optimizes speed alignment and minimizes deviation."
        )

        return {
            "agent_name": self.name,
            "role": self.role,
            "chosen_action": chosen_key,
            "confidence": round(confidence, 1),
            "reasoning": reasoning,
            "scores": scores
        }

class ResourceAgent:
    def __init__(self):
        self.name = "Resource Agent"
        self.role = "Propulsion & Consumables Officer"
        self.responsibilities = "Fuel Management, Power Management, Oxygen Management, Resource Forecasting"

    def analyze(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        event_type = event.get("event_type", "Unknown")
        fuel = telemetry.get("fuel", 100.0)
        power = telemetry.get("power", 100.0)
        oxygen = telemetry.get("oxygen", 100.0)

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "backup" in k:
                scores[k] = 95.0
            elif "retract" in k:
                scores[k] = 90.0
            elif "seal_pressure" in k:
                scores[k] = 88.0
            elif "reduce_speed" in k:
                scores[k] = 75.0
            elif "divert_power" in k:
                scores[k] = 60.0  # consumes high battery power
            elif "ignore" in k:
                scores[k] = 10.0

        chosen_key = max(scores, key=scores.get) if scores else None
        
        # Confidence increases as resources decay (urgency increases)
        min_resource = min(fuel, power, oxygen)
        confidence = max(55.0, min(98.0, 110.0 - min_resource))

        reasoning = (
            f"Consumables capacity: fuel={fuel:.1f}%, power={power:.1f}%, oxygen={oxygen:.1f}%. "
            f"Consumables safety requires {chosen_key} to prevent system depletion."
        )

        return {
            "agent_name": self.name,
            "role": self.role,
            "chosen_action": chosen_key,
            "confidence": round(confidence, 1),
            "reasoning": reasoning,
            "scores": scores
        }

class SafetyAgent:
    def __init__(self):
        self.name = "Safety Agent"
        self.role = "Hull Integrity & Crew Officer"
        self.responsibilities = "Risk Assessment, Failure Detection, Emergency Analysis, Crew Protection"

    def analyze(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        event_type = event.get("event_type", "Unknown")
        health = telemetry.get("health", 100.0)
        risk_score = telemetry.get("risk_score", 10.0)

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "divert_power" in k:
                scores[k] = 95.0
            elif "seal_pressure" in k:
                scores[k] = 94.0
            elif "emergency_shutdown" in k:
                scores[k] = 92.0
            elif "backup_controller" in k:
                scores[k] = 85.0
            elif "ignore" in k:
                scores[k] = 5.0

        chosen_key = max(scores, key=scores.get) if scores else None
        
        # Confidence linked to health hazard metrics
        confidence = max(60.0, min(98.0, 50.0 + risk_score * 0.8))

        reasoning = (
            f"Hull structural diagnostic registers {health:.1f}% integrity, risk coefficient is {risk_score:.1f}. "
            f"Initiating recommendation for {chosen_key} to protect crew cabin modules."
        )

        return {
            "agent_name": self.name,
            "role": self.role,
            "chosen_action": chosen_key,
            "confidence": round(confidence, 1),
            "reasoning": reasoning,
            "scores": scores
        }

class ScienceAgent:
    def __init__(self):
        self.name = "Science Agent"
        self.role = "Sensor and Analytics Officer"
        self.responsibilities = "Science Objectives, Research Opportunities, Exploration Priorities, Mission Discovery Goals"

    def analyze(self, telemetry: Dict[str, Any], event: Dict[str, Any], options: List[Dict[str, str]]) -> Dict[str, Any]:
        event_type = event.get("event_type", "Unknown")
        progress = telemetry.get("mission_progress", 0.0)

        scores = {}
        for opt in options:
            k = opt["action_key"]
            scores[k] = 50.0
            if "run_diagnostic" in k:
                scores[k] = 92.0
            elif "star_field" in k:
                scores[k] = 88.0
            elif "automated_sweep" in k:
                scores[k] = 82.0
            elif "ignore" in k:
                scores[k] = 40.0

        chosen_key = max(scores, key=scores.get) if scores else None
        confidence = max(50.0, min(92.0, 70.0 + progress * 0.2))

        reasoning = (
            f"Mission progress stands at {progress:.1f}% distance. "
            f"Specialist sensors support {chosen_key} to gather payload telemetry spectrum logs."
        )

        return {
            "agent_name": self.name,
            "role": self.role,
            "chosen_action": chosen_key,
            "confidence": round(confidence, 1),
            "reasoning": reasoning,
            "scores": scores
        }

# --- COMMANDER AGENT & COLLABORATION ENGINE ---

class MultiAgentEngine:
    def __init__(self):
        self.nav_agent = NavigationAgent()
        self.resource_agent = ResourceAgent()
        self.safety_agent = SafetyAgent()
        self.science_agent = ScienceAgent()

        # Decision Scoring Weights: Success, Safety, Fuel, Time (Nav), Science
        self.weights = {
            "success": 0.35,
            "safety": 0.25,
            "fuel": 0.20,
            "time": 0.10,
            "science": 0.10
        }

    async def run_collaboration_pipeline(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        options: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        event_id = event.get("id", 0)
        event_type = event.get("event_type", "Unknown")

        # 1. Broadcast Analysis Started
        await manager.broadcast_json({
            "type": "AGENT_ANALYSIS_STARTED",
            "event_id": event_id,
            "event_type": event_type
        })

        # 2. Run specialist agents sequentially
        nav_rec = self.nav_agent.analyze(telemetry, event, options)
        await self.log_recommendation_ws_db(event_id, nav_rec)

        res_rec = self.resource_agent.analyze(telemetry, event, options)
        await self.log_recommendation_ws_db(event_id, res_rec)

        safe_rec = self.safety_agent.analyze(telemetry, event, options)
        await self.log_recommendation_ws_db(event_id, safe_rec)

        science_rec = self.science_agent.analyze(telemetry, event, options)
        await self.log_recommendation_ws_db(event_id, science_rec)

        # 3. Calculate Decision Utility Scores
        decision_scores = {}
        for opt in options:
            k = opt["action_key"]
            
            # Estimate success delta baseline or from prediction deltas
            success_delta = 5.0
            from backend.simulator.engine import simulator
            pred = simulator.action_predictions.get(k)
            if pred:
                success_delta = pred.get("success_delta", 5.0)
                
            est_success = min(100.0, max(0.0, telemetry.get("success_probability", 80.0) + success_delta))

            # Grab scores from each specialist agent
            nav_s = nav_rec["scores"].get(k, 50.0)
            res_s = res_rec["scores"].get(k, 50.0)
            safe_s = safe_rec["scores"].get(k, 50.0)
            sci_s = science_rec["scores"].get(k, 50.0)

            # Utility score formula
            U = (
                self.weights["success"] * est_success +
                self.weights["safety"] * safe_s +
                self.weights["fuel"] * res_s +
                self.weights["time"] * nav_s +
                self.weights["science"] * sci_s
            )
            decision_scores[k] = round(U, 1)

        # Choose the optimal action
        chosen_action = max(decision_scores, key=decision_scores.get)
        commander_utility = decision_scores[chosen_action]

        # 4. Consensus agreement calculation
        votes = [
            nav_rec["chosen_action"],
            res_rec["chosen_action"],
            safe_rec["chosen_action"],
            science_rec["chosen_action"]
        ]
        agree_votes = sum(1 for v in votes if v == chosen_action)
        agreement_score = (agree_votes / 4.0) * 100.0

        # Broadcast consensus
        await manager.broadcast_json({
            "type": "CONSENSUS_UPDATED",
            "event_id": event_id,
            "agreement_score": agreement_score,
            "chosen_action": chosen_action
        })
        await self.save_consensus_to_db(event_id, agreement_score, chosen_action, votes)

        # 5. Commander Reasoning & Debate Builder
        commander_reasoning = self.build_commander_reasoning(chosen_action, agreement_score, votes, event_type)
        debate_dialog = self.build_debate_dialog(nav_rec, res_rec, safe_rec, science_rec, chosen_action, agreement_score, event_type)

        # 6. Save Commander Decision to DB & Redis Cache
        decision_id = await self.save_commander_decision_db(
            event_id=event_id,
            chosen_action=chosen_action,
            confidence=round(agreement_score * 0.8 + 20.0, 1),
            reasoning=commander_reasoning,
            utility_score=commander_utility
        )

        # Write to agent Redis memory & debate
        await self.save_redis_memory(event_id, chosen_action, agreement_score, commander_reasoning, nav_rec, res_rec, safe_rec, science_rec, debate_dialog)

        # Broadcast Commander Decision
        await manager.broadcast_json({
            "type": "COMMANDER_DECISION_CREATED",
            "event_id": event_id,
            "decision_id": decision_id,
            "chosen_action": chosen_action,
            "confidence": round(agreement_score * 0.8 + 20.0, 1),
            "reasoning": commander_reasoning,
            "utility_score": commander_utility,
            "debate": debate_dialog
        })

        return {
            "decision_id": decision_id,
            "chosen_action": chosen_action,
            "confidence": round(agreement_score * 0.8 + 20.0, 1),
            "reasoning": commander_reasoning,
            "utility_score": commander_utility,
            "agreement_score": agreement_score,
            "debate": debate_dialog,
            "sub_agents": {
                "nav": nav_rec,
                "fuel": res_rec,
                "safety": safe_rec,
                "science": science_rec
            }
        }

    async def log_recommendation_ws_db(self, event_id: int, rec: Dict[str, Any]):
        # Broadcast recommendation
        await manager.broadcast_json({
            "type": "AGENT_RECOMMENDATION_CREATED",
            "event_id": event_id,
            "agent_name": rec["agent_name"],
            "recommendation": rec["chosen_action"],
            "confidence": rec["confidence"],
            "reasoning": rec["reasoning"]
        })

        # Save to DB
        if not connection.SessionLocal:
            return
        try:
            async with connection.SessionLocal() as db:
                model = AgentRecommendationModel(
                    timestamp=ist_now(),
                    event_id=event_id,
                    agent_name=rec["agent_name"],
                    recommendation=rec["chosen_action"],
                    confidence=rec["confidence"],
                    reasoning=rec["reasoning"],
                    action_key=rec["chosen_action"]
                )
                db.add(model)
                await db.commit()
        except Exception as e:
            print(f"[DB Error] Recommendation save failed: {e}")

    async def save_consensus_to_db(self, event_id: int, score: float, decision: str, votes: List[str]):
        if not connection.SessionLocal:
            return
        try:
            async with connection.SessionLocal() as db:
                model = AgentConsensusModel(
                    timestamp=ist_now(),
                    event_id=event_id,
                    agreement_score=score,
                    consensus_decision=decision,
                    details_json=json.dumps({
                        "votes": votes,
                        "voters": ["Navigation Specialist", "Resource Officer", "Safety Monitor", "Science Analyst"]
                    })
                )
                db.add(model)
                await db.commit()
        except Exception as e:
            print(f"[DB Error] Consensus save failed: {e}")

    async def save_commander_decision_db(self, event_id: int, chosen_action: str, confidence: float, reasoning: str, utility_score: float) -> int:
        if not connection.SessionLocal:
            return 0
        try:
            async with connection.SessionLocal() as db:
                model = CommanderDecisionModel(
                    timestamp=ist_now(),
                    event_id=event_id,
                    chosen_action=chosen_action,
                    confidence=confidence,
                    reasoning=reasoning,
                    utility_score=utility_score,
                    outcome_details="{}"
                )
                db.add(model)
                await db.flush()
                d_id = model.id
                await db.commit()
                return d_id
        except Exception as e:
            print(f"[DB Error] Commander decision save failed: {e}")
            return 0

    async def save_redis_memory(
        self,
        event_id: int,
        action: str,
        consensus: float,
        reasoning: str,
        nav: Dict[str, Any],
        res: Dict[str, Any],
        safe: Dict[str, Any],
        science: Dict[str, Any],
        debate: List[Dict[str, str]]
    ):
        try:
            redis = await get_redis()
            
            # Set state
            state_payload = {
                "event_id": event_id,
                "chosen_action": action,
                "confidence": consensus,
                "timestamp": ist_now().isoformat(),
                "sub_agents": {
                    "nav": nav,
                    "fuel": res,  # Map resource agent to expected fuel sub-agent key
                    "safety": safe,
                    "science": science
                }
            }
            await redis.set("hail_mary:agent:state", json.dumps(state_payload))
            await redis.set("hail_mary:agent:reasoning", reasoning)
            await redis.set("hail_mary:agent:consensus_state", json.dumps({"score": consensus, "voters": ["nav", "fuel", "safety", "science"]}))
            await redis.set("hail_mary:agent:current_debate", json.dumps(debate))

            # Push to sliding memory queue
            mem_payload = {
                "action": action,
                "confidence": consensus,
                "timestamp": ist_now().isoformat()
            }
            await redis.rpush("hail_mary:agent:memory", json.dumps(mem_payload))
            await redis.ltrim("hail_mary:agent:memory", -100, -1)

            # Store per-agent memories
            for agent in [nav, res, safe, science]:
                name_clean = agent["agent_name"].lower().replace(" ", "_")
                await redis.rpush(f"hail_mary:agent:memory:{name_clean}", json.dumps({
                    "event_id": event_id,
                    "recommendation": agent["chosen_action"],
                    "confidence": agent["confidence"],
                    "timestamp": ist_now().isoformat()
                }))
                await redis.ltrim(f"hail_mary:agent:memory:{name_clean}", -50, -1)
        except Exception as e:
            print(f"[Redis Cache Error] Multi-agent Redis caching failed: {e}")

    def build_commander_reasoning(self, action: str, consensus: float, votes: List[str], event_type: str) -> str:
        action_clean = " ".join(action.split("_")[2:]) if "_" in action else action
        if consensus >= 75.0:
            return f"Specialist team achieved high consensus of {consensus:.1f}% approval for '{action_clean}'. Executive command has approved implementation."
        elif consensus >= 50.0:
            return f"Specialists support policy alignment of '{action_clean}' at moderate consensus ({consensus:.1f}%). Authorized under standard operating limits."
        else:
            return f"Specialists split on resolution strategies. Commander utility formulas selected '{action_clean}' as maximizing long-term survival rates."

    def build_debate_dialog(
        self,
        nav: Dict[str, Any],
        res: Dict[str, Any],
        safe: Dict[str, Any],
        sci: Dict[str, Any],
        chosen: str,
        consensus: float,
        event_type: str
    ) -> List[Dict[str, str]]:
        dialogue = []
        
        # Navigation
        dialogue.append({
            "sender": nav["agent_name"],
            "role": nav["role"],
            "message": f"Trajectory analysis complete. Our trajectory offsets are affected. I recommend executing '{nav['chosen_action']}' (confidence: {nav['confidence']}%)."
        })
        
        # Resource
        dialogue.append({
            "sender": res["agent_name"],
            "role": res["role"],
            "message": f"Checking consumables: fuel and electrical storage grid health are critical parameters. I recommend '{res['chosen_action']}' (confidence: {res['confidence']}%)."
        })

        # Safety
        dialogue.append({
            "sender": safe["agent_name"],
            "role": safe["role"],
            "message": f"Integrity scan completes. Risk index registers threat propagation vector. Recommending immediate action '{safe['chosen_action']}' (confidence: {safe['confidence']}%)."
        })

        # Science
        dialogue.append({
            "sender": sci["agent_name"],
            "role": sci["role"],
            "message": f"Spectroscopy radar is locked. Exploration scanners suggest diagnostics and '{sci['chosen_action']}' (confidence: {sci['confidence']}%)."
        })

        # Commander
        chosen_clean = " ".join(chosen.split("_")[2:]) if "_" in chosen else chosen
        dialogue.append({
            "sender": "Mission Commander Agent",
            "role": "Mission Commander",
            "message": f"Specialist views compiled. Decision agreement stands at {consensus:.1f}%. I authorize core mitigation action: '{chosen_clean}'."
        })

        return dialogue

# Global instance
multi_agent_engine = MultiAgentEngine()
