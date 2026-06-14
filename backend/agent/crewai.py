import json
from typing import List, Dict, Any
from backend.utils.timezone_helper import ist_now

class CrewAgent:
    def __init__(self, role: str, goal: str, backstory: str, tools: List[str]):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": self.tools
        }

class CrewAIAgentDefinitions:
    def __init__(self):
        self.nav_agent = CrewAgent(
            role="Navigation Specialist",
            goal="Ensure the spacecraft maintains correct trajectory, minimizes orbital drift, and calculates accurate orbital speeds.",
            backstory="Experienced astrogation computer programmed with advanced celestial mechanics. Specializes in route correction.",
            tools=["Calculate Drift Error", "Optimize Trajectory Route"]
        )
        self.fuel_agent = CrewAgent(
            role="Propulsion and Resource Officer",
            goal="Monitor propellant burn rate, manage battery power decay, and optimize secondary electrical grid distribution.",
            backstory="Deep-space thermodynamic engine manager designed to handle propellant physics and minimize voltage drop rates.",
            tools=["Assess Fuel Pressure", "Optimize Grid Voltage"]
        )
        self.safety_agent = CrewAgent(
            role="Safety and Hull Integrity Monitor",
            goal="Observe structural integrity risk thresholds and coordinate immediate emergency action procedures.",
            backstory="Sub-second diagnostic framework built to evaluate micro-fractures, radiation shielding, and thermal warnings.",
            tools=["Execute Emergency Isolation", "Run Structural Scans"]
        )
        self.science_agent = CrewAgent(
            role="Scientific Officer and Sensor Analyst",
            goal="Analyze anomalous sensor data, prioritize scientific collection targets, and evaluate unknown object traps.",
            backstory="Exploration computer calibrated to record telemetry spectra, manage telescope payloads, and prioritize data logs.",
            tools=["Analyze LIDAR Reflection", "Prioritize Spectral Scan"]
        )
        self.commander_agent = CrewAgent(
            role="Mission Commander",
            goal="Orchestrate overall spacecraft operations, make final decision actions, and coordinate emergency responses.",
            backstory="Heuristic Autonomous Intelligence system designed as final executive authority for Project Hail Mary.",
            tools=["Execute Remote Mitigation", "Broadcast Systems Warning"]
        )

    def get_agent_profile(self, name: str) -> Dict[str, Any]:
        mapping = {
            "Navigation": self.nav_agent,
            "Fuel": self.fuel_agent,
            "Safety": self.safety_agent,
            "Science": self.science_agent,
            "Commander": self.commander_agent
        }
        return mapping.get(name, self.commander_agent).to_dict()
