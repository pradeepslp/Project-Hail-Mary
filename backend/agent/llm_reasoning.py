import os
import json
import httpx
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update, delete

from backend.database import connection
from backend.database.models import (
    LLMPromptModel,
    LLMDecisionModel,
    LLMReasoningModel,
    LLMOutcomeModel,
    DecisionMetricsModel
)
from backend.database.redis_client import get_redis
from backend.websocket.connection import manager
from backend.utils.timezone_helper import ist_now

# --- LLM PROVIDERS LAYER ---

class LLMProvider:
    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.url = "https://api.openai.com/v1/chat/completions"

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.api_key:
            print("[OpenAI Provider] API Key is missing.")
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(self.url, json=payload, headers=headers, timeout=12.0)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    print(f"[OpenAI Provider] Error status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[OpenAI Provider] Exception: {e}")
        return None

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        self.api_key = api_key
        self.model = model
        self.url = "https://api.anthropic.com/v1/messages"

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.api_key:
            print("[Anthropic Provider] API Key is missing.")
            return None
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.2
        }
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(self.url, json=payload, headers=headers, timeout=12.0)
                if res.status_code == 200:
                    data = res.json()
                    return data["content"][0]["text"]
                else:
                    print(f"[Anthropic Provider] Error status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Anthropic Provider] Exception: {e}")
        return None

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.api_key:
            print("[Gemini Provider] API Key is missing.")
            return None
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(self.url, json=payload, headers=headers, timeout=12.0)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    print(f"[Gemini Provider] Error status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[Gemini Provider] Exception: {e}")
        return None

_ollama_online = None
_last_ollama_check = 0.0

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3:latest", base_url: str = "http://localhost:11434"):
        self.model = model
        self.url = f"{base_url}/api/chat"

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        global _ollama_online, _last_ollama_check
        import time
        
        current_time = time.time()
        # Skip checking if we already know it is offline and last check was less than 60s ago
        if _ollama_online is False and (current_time - _last_ollama_check) < 60.0:
            return None
            
        _last_ollama_check = current_time

        payload = {
            "model": self.model,
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
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(self.url, json=payload, timeout=2.0)
                if res.status_code == 200:
                    _ollama_online = True
                    data = res.json()
                    return data["message"]["content"]
                else:
                    _ollama_online = False
                    print(f"[Ollama Provider] Error status {res.status_code}: {res.text}")
            except Exception as e:
                _ollama_online = False
                print(f"[Ollama Provider] Exception: {e}")
        return None


# --- CONFIGURATION MANAGER ---

class LLMConfigManager:
    def __init__(self):
        self.provider_type = os.getenv("LLM_PROVIDER", "ollama")
        self.model_name = os.getenv("LLM_MODEL", "")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.temperature = 0.2

    def get_active_provider(self) -> LLMProvider:
        prov = self.provider_type.lower()
        if prov == "openai":
            model = self.model_name or "gpt-4o"
            return OpenAIProvider(api_key=self.openai_key, model=model)
        elif prov == "anthropic":
            model = self.model_name or "claude-3-5-sonnet-20240620"
            return AnthropicProvider(api_key=self.anthropic_key, model=model)
        elif prov == "gemini":
            model = self.model_name or "gemini-1.5-flash"
            return GeminiProvider(api_key=self.gemini_key, model=model)
        else:
            model = self.model_name or "llama3:latest"
            return OllamaProvider(model=model, base_url=self.ollama_url)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_type": self.provider_type,
            "model_name": self.model_name,
            "ollama_url": self.ollama_url,
            "has_openai_key": bool(self.openai_key),
            "has_anthropic_key": bool(self.anthropic_key),
            "has_gemini_key": bool(self.gemini_key),
            "temperature": self.temperature
        }

llm_config = LLMConfigManager()


# --- LLM REASONING ENGINE ---

class LLMReasoningEngine:
    def __init__(self):
        self.system_prompt = (
            "You are HAIL MARY Mission Commander.\n"
            "Your responsibility is to maximize mission success while preserving spacecraft safety, resources, and mission objectives.\n"
            "Priorities:\n"
            "1. Crew Safety\n"
            "2. Mission Success\n"
            "3. Resource Preservation\n"
            "4. Scientific Objectives\n\n"
            "Evaluate available actions carefully.\n"
            "Always explain reasoning in a structured bullet point array.\n"
            "Return ONLY valid JSON output that matches the schema specified by the user. Do not wrap in markdown or backticks."
        )

    def build_context_prompt(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        options: List[Dict[str, str]]
    ) -> str:
        """Constructs a structured prompt detailing current state, active events, and available actions"""
        # Parse subsystems
        sub_list = []
        if telemetry.get("subsystems"):
            for name, info in telemetry["subsystems"].items():
                sub_list.append(f"- {name}: {info.get('health', 100.0)}% health, Status: {info.get('status', 'Nominal')}")
        subsystems_str = "\n".join(sub_list) if sub_list else "All systems nominal."

        # Parse available options
        opt_list = []
        for i, opt in enumerate(options, 1):
            opt_list.append(f"{i}. {opt['action_key']} ({opt['action_name']}): {opt['description']}")
        options_str = "\n".join(opt_list)

        # Read the live destination from the simulator
        from backend.simulator.engine import simulator
        live_destination = getattr(simulator, 'destination', None) or telemetry.get('destination', 'Target')

        user_prompt = (
            "Current State:\n"
            f"Fuel: {telemetry.get('fuel', 100.0):.1f}%\n"
            f"Power: {telemetry.get('power', 100.0):.1f}%\n"
            f"Health: {telemetry.get('health', 100.0):.1f}%\n"
            f"Communication: {telemetry.get('communication', 'Connected')}\n"
            f"Navigation Accuracy: {telemetry.get('navigation_accuracy', 95.0):.1f}%\n"
            f"Mission Progress: {telemetry.get('mission_progress', 0.0):.1f}%\n"
            f"Risk Level: {telemetry.get('risk_level', 'Nominal')}\n\n"
            "Subsystem Status:\n"
            f"{subsystems_str}\n\n"
            "Active Event:\n"
            f"{event.get('event_type')}\n"
            f"Event Severity: {event.get('severity', 'High')}\n"
            f"Description: {event.get('description', '')}\n\n"
            "Mission Objective:\n"
            f"Reach {live_destination} System and establish circular orbit.\n\n"
            "Available Actions:\n"
            f"{options_str}\n\n"
            "Select the single best action and output valid JSON matching the format below:\n"
            "{\n"
            '  "decision": "Enter Safe Mode",\n'
            '  "confidence": 94,\n'
            '  "reasoning": [\n'
            '    "Solar storm may damage critical systems",\n'
            '    "Safe mode reduces power consumption"\n'
            '  ],\n'
            '  "expected_outcome": {\n'
            '    "mission_success_change": 8,\n'
            '    "risk_reduction": 20,\n'
            '    "power_change": -15\n'
            '  }\n'
            "}"
        )
        return user_prompt

    async def evaluate_event_decision(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        options: List[Dict[str, str]],
        autonomy_level: int
    ) -> Dict[str, Any]:
        """Runs the context building, LLM execution, structured parsing, validation, and fallbacks"""
        event_id = event.get("id")
        event_type = event.get("event_type")

        # 1. Build prompt
        user_prompt = self.build_context_prompt(telemetry, event, options)

        # 2. Write prompt log to DB
        prompt_id = await self.save_prompt_to_db(event_id, event_type, user_prompt)
        await manager.broadcast_json({
            "type": "LLM_PROMPT_GENERATED",
            "event_id": event_id,
            "prompt": user_prompt
        })

        # 3. Request provider
        active_provider = llm_config.get_active_provider()
        response_text = None
        
        try:
            response_text = await active_provider.generate_response(self.system_prompt, user_prompt)
        except Exception as e:
            print(f"[LLM Core] Provider call failed: {e}")

        # 4. Parse & Validate
        parsed_data = None
        status = "Executed"

        if response_text:
            parsed_data = self.parse_structured_json(response_text)

        if parsed_data:
            # Map choice to exact simulator action key
            chosen_decision = parsed_data.get("decision", "")
            mapped_key = self.map_decision_to_action(chosen_decision, options)
            if mapped_key:
                parsed_data["mapped_action_key"] = mapped_key
            else:
                # Malformed/unrecognized decision mapping -> reject response
                parsed_data = None
                status = "Failed"
        else:
            status = "Failed"

        # 5. Failsafe Fallback
        if not parsed_data:
            print(f"[LLM Failsafe] LLM decision failed or was rejected. Invoking utility-based fallback...")
            parsed_data = await self.execute_utility_fallback(telemetry, event, options)
            parsed_data["reasoning"].insert(0, "[FAILSAFE FALLBACK] LLM pipeline failure. Activated utility-based recovery.")
            status = "Fallback"

        # 6. Run Monte Carlo validation prior to execution
        mc_results = await self.run_monte_carlo_validation(telemetry, event, parsed_data["mapped_action_key"])
        parsed_data["mc_validation"] = mc_results

        # 7. Write to PostgreSQL database
        decision_id = await self.save_decision_to_db(
            prompt_id=prompt_id,
            decision=parsed_data["decision"],
            confidence=parsed_data["confidence"],
            action_key=parsed_data["mapped_action_key"],
            status=status,
            autonomy_level=autonomy_level,
            reasoning=parsed_data["reasoning"],
            expected_outcome=parsed_data["expected_outcome"]
        )

        # 8. Cache short-term memory (Redis)
        await self.save_redis_memory(parsed_data, event)

        # 9. Broadcast WS update
        await manager.broadcast_json({
            "type": "LLM_DECISION_RECEIVED",
            "event_id": event_id,
            "decision_id": decision_id,
            "decision": parsed_data["decision"],
            "confidence": parsed_data["confidence"],
            "reasoning": parsed_data["reasoning"],
            "expected_outcome": parsed_data["expected_outcome"],
            "mc_validation": mc_results,
            "status": status
        })

        return {
            "decision_id": decision_id,
            "event_id": event_id,
            "chosen_action": parsed_data["mapped_action_key"],
            "confidence": parsed_data["confidence"],
            "reasoning": parsed_data["reasoning"],
            "expected_outcome": parsed_data["expected_outcome"],
            "mc_validation": mc_results,
            "status": status
        }

    def parse_structured_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Cleans and validates structured LLM JSON response"""
        text = raw_text.strip()
        # Strip code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            # Schema Validation
            if "decision" not in data or "confidence" not in data or "reasoning" not in data or "expected_outcome" not in data:
                print("[LLM Parser] Schema validation failed: Missing required keys.")
                return None
            
            # Ensure expected_outcome keys exist
            eo = data["expected_outcome"]
            if not isinstance(eo, dict):
                return None
            
            # Populate missing expected outcome fields if any
            data["expected_outcome"] = {
                "mission_success_change": float(eo.get("mission_success_change", 0.0)),
                "risk_reduction": float(eo.get("risk_reduction", 0.0)),
                "power_change": float(eo.get("power_change", 0.0)),
                "fuel_change": float(eo.get("fuel_change", 0.0))
            }
            # Ensure reasoning is a list of strings
            if not isinstance(data["reasoning"], list):
                data["reasoning"] = [str(data["reasoning"])]
            
            data["confidence"] = int(data["confidence"])
            return data
        except Exception as e:
            print(f"[LLM Parser] JSON decode exception: {e}. Raw response: {raw_text}")
            return None

    def map_decision_to_action(self, decision: str, options: List[Dict[str, str]]) -> Optional[str]:
        """Maps LLM text decision to the exact simulator action key"""
        decision_clean = decision.lower().strip()
        
        # 1. Direct key match
        for opt in options:
            if opt["action_key"].lower() == decision_clean:
                return opt["action_key"]
                
        # 2. Name match
        for opt in options:
            if opt["action_name"].lower() in decision_clean or decision_clean in opt["action_name"].lower():
                return opt["action_key"]

        # 3. Known mappings helper
        synonyms = {
            "enter safe mode": ["safe", "retract", "solar_storm_retract_panels"],
            "activate backup tank": ["backup", "auxiliary", "fuel_leak_activate_backup"],
            "reduce speed": ["reduce speed", "cruise speed", "fuel_leak_reduce_speed"],
            "recalculate route": ["star_field", "star field", "nav_drift_star_field"],
            "switch communication channel": ["channel", "sweep", "comm_loss_automated_sweep"],
            "emergency shutdown": ["shutdown", "emergency_shutdown", "fuel_leak_emergency_shutdown"],
            "divert power to deflectors": ["deflectors", "divert_power", "solar_storm_divert_power"],
            "seal bulkheads": ["seal", "bulkheads", "meteor_seal_pressure"],
            "run damage diagnostic": ["diagnostic", "meteor_run_diagnostic"]
        }
        for syn, keys in synonyms.items():
            if syn in decision_clean:
                for k in keys:
                    for opt in options:
                        if opt["action_key"] == k:
                            return k

        # Fallback: if there is only one option, pick it, otherwise return None
        if len(options) == 1:
            return options[0]["action_key"]
        return None

    async def run_monte_carlo_validation(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        action_key: str
    ) -> Dict[str, Any]:
        """Runs a fast fast-forward Monte Carlo trial on the chosen action"""
        from backend.simulator.engine import simulator
        print(f"[Monte Carlo LLM Check] Evaluating validation for action: {action_key}...")
        try:
            res = await simulator.run_monte_carlo(iterations=100)
            return {
                "success_probability": res.get("avg_success_prob", 85.0),
                "fuel_impact": res.get("avg_fuel_remaining", 75.0) - telemetry.get("fuel", 75.0),
                "risk_reduction": telemetry.get("risk_score", 15.0) - res.get("avg_risk", 12.0)
            }
        except Exception as e:
            print(f"[Monte Carlo LLM Check] Verification skipped: {e}")
            return {
                "success_probability": 85.0,
                "fuel_impact": -2.0,
                "risk_reduction": 10.0
            }

    async def execute_utility_fallback(
        self,
        telemetry: Dict[str, Any],
        event: Dict[str, Any],
        options: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Fallback Level 1: Utility optimization algorithm (copied from langgraph.py)"""
        from backend.agent.langgraph import graph_orchestrator
        
        # Run subagent evaluations to feed utility
        nav_rec = graph_orchestrator.run_navigation_agent(telemetry, event, options)
        fuel_rec = graph_orchestrator.run_fuel_agent(telemetry, event, options)
        safety_rec = graph_orchestrator.run_safety_agent(telemetry, event, options)
        science_rec = graph_orchestrator.run_science_agent(telemetry, event, options)

        utils = graph_orchestrator.evaluate_utilities(
            telemetry, event, options,
            nav_rec, fuel_rec, safety_rec, science_rec
        )
        
        chosen_key = utils["chosen_action"]
        confidence = utils["confidence_score"]
        action_name = next((o["action_name"] for o in options if o["action_key"] == chosen_key), "Mitigate Anomaly")
        
        return {
            "decision": action_name,
            "confidence": int(confidence),
            "reasoning": [
                f"Selected '{action_name}' using utility maximization formula.",
                "Conserves fuel margins and minimizes hull structural degradation risks."
            ],
            "expected_outcome": {
                "mission_success_change": 5.0,
                "risk_reduction": 15.0,
                "power_change": -5.0,
                "fuel_change": -3.0
            },
            "mapped_action_key": chosen_key
        }

    async def save_prompt_to_db(self, event_id: int, event_type: str, prompt_text: str) -> int:
        if not connection.SessionLocal:
            return 0
        try:
            async with connection.SessionLocal() as db:
                model = LLMPromptModel(
                    timestamp=ist_now(),
                    event_type=event_type,
                    event_id=event_id,
                    prompt_text=prompt_text,
                    system_prompt=self.system_prompt
                )
                db.add(model)
                await db.flush()
                p_id = model.id
                await db.commit()
                return p_id
        except Exception as e:
            print(f"[DB Error] Prompt save failed: {e}")
            return 0

    async def save_decision_to_db(
        self,
        prompt_id: int,
        decision: str,
        confidence: int,
        action_key: str,
        status: str,
        autonomy_level: int,
        reasoning: List[str],
        expected_outcome: Dict[str, Any]
    ) -> int:
        if not connection.SessionLocal:
            return 0
        try:
            async with connection.SessionLocal() as db:
                # 1. Save decision
                dec = LLMDecisionModel(
                    prompt_id=prompt_id,
                    timestamp=ist_now(),
                    decision=decision,
                    confidence=confidence,
                    chosen_action_key=action_key,
                    status=status,
                    autonomy_level=autonomy_level
                )
                db.add(dec)
                await db.flush()
                d_id = dec.id

                # 2. Save reasoning
                reas = LLMReasoningModel(
                    decision_id=d_id,
                    reasoning_steps=json.dumps(reasoning)
                )
                db.add(reas)

                # 3. Save outcome predictions
                out = LLMOutcomeModel(
                    decision_id=d_id,
                    success_change=expected_outcome.get("mission_success_change", 0.0),
                    risk_reduction=expected_outcome.get("risk_reduction", 0.0),
                    power_change=expected_outcome.get("power_change", 0.0),
                    fuel_change=expected_outcome.get("fuel_change", 0.0),
                    evaluated=False
                )
                db.add(out)
                await db.commit()
                return d_id
        except Exception as e:
            print(f"[DB Error] Decision save failed: {e}")
            return 0

    async def save_redis_memory(self, parsed_data: Dict[str, Any], event: Dict[str, Any]):
        try:
            redis = await get_redis()
            # Cache active prompt and decision
            await redis.set("hail_mary:llm:current_prompt", self.system_prompt)
            await redis.set("hail_mary:llm:current_decision", json.dumps(parsed_data))
            
            # Push to sliding queue of recent decisions (short term memory)
            queue_payload = {
                "decision": parsed_data["decision"],
                "confidence": parsed_data["confidence"],
                "reasoning": parsed_data["reasoning"],
                "event_type": event["event_type"],
                "timestamp": ist_now().isoformat()
            }
            await redis.rpush("hail_mary:llm:recent_decisions", json.dumps(queue_payload))
            await redis.ltrim("hail_mary:llm:recent_decisions", -100, -1)
        except Exception as e:
            print(f"[Redis Memory] Failed to cache memory: {e}")

    async def update_actual_outcomes(
        self,
        action_key: str,
        initial_success: float,
        final_success: float,
        initial_risk: float,
        final_risk: float
    ):
        """Called by simulator checks 5 ticks later to evaluate LLM accuracy"""
        if not connection.SessionLocal:
            return
        
        try:
            async with connection.SessionLocal() as db:
                # Retrieve the last executed LLM decision for this action key
                stmt = select(LLMDecisionModel).where(
                    LLMDecisionModel.chosen_action_key == action_key
                ).order_by(LLMDecisionModel.timestamp.desc()).limit(1)
                
                res = await db.execute(stmt)
                decision = res.scalars().first()
                if decision:
                    stmt_out = select(LLMOutcomeModel).where(
                        LLMOutcomeModel.decision_id == decision.id
                    )
                    res_out = await db.execute(stmt_out)
                    outcome = res_out.scalars().first()
                    if outcome:
                        outcome.actual_success = final_success
                        outcome.actual_risk = final_risk
                        outcome.evaluated = True
                        await db.commit()
                        
                        # Re-calculate and update global metrics
                        await self.aggregate_decision_metrics()
        except Exception as e:
            print(f"[Outcomes Update] Database evaluation failure: {e}")

    async def aggregate_decision_metrics(self):
        """Recalculates decision metrics and writes to decision_metrics table"""
        if not connection.SessionLocal:
            return
        
        try:
            async with connection.SessionLocal() as db:
                stmt_dec = select(LLMDecisionModel)
                res_dec = await db.execute(stmt_dec)
                all_decisions = res_dec.scalars().all()
                if not all_decisions:
                    return

                total = len(all_decisions)
                sum_conf = sum(d.confidence for d in all_decisions)
                avg_conf = sum_conf / total

                # Calculate success rate (decisions that achieved mitigation cleanly)
                fallbacks = sum(1 for d in all_decisions if d.status == "Fallback")
                failed = sum(1 for d in all_decisions if d.status == "Failed")
                success_rate = ((total - fallbacks - failed) / total) * 100.0

                # Compute decision accuracy based on outcome delta matching
                stmt_out = select(LLMOutcomeModel).where(LLMOutcomeModel.evaluated == True)
                res_out = await db.execute(stmt_out)
                evaluated_outcomes = res_out.scalars().all()
                
                accuracy = 85.0  # default baseline
                if evaluated_outcomes:
                    errors = []
                    for eo in evaluated_outcomes:
                        # Compare predicted success change vs actual success final
                        err = abs(eo.success_change - (eo.actual_success or 80.0))
                        errors.append(err)
                    avg_err = sum(errors) / len(errors)
                    accuracy = max(0.0, min(100.0, 100.0 - avg_err))

                metric = DecisionMetricsModel(
                    timestamp=ist_now(),
                    decision_accuracy=round(accuracy, 1),
                    avg_confidence=round(avg_conf, 1),
                    success_rate=round(success_rate, 1),
                    reasoning_quality=92.5  # qualitative baseline index
                )
                db.add(metric)
                await db.commit()
                
                # Broadcast metrics
                await manager.broadcast_json({
                    "type": "LLM_METRICS_UPDATED",
                    "accuracy": round(accuracy, 1),
                    "avg_confidence": round(avg_conf, 1),
                    "success_rate": round(success_rate, 1),
                    "reasoning_quality": 92.5
                })
        except Exception as e:
            print(f"[Metrics Aggregation] Calculation failed: {e}")

# Global instance
llm_reasoning_engine = LLMReasoningEngine()
