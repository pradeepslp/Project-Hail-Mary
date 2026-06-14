import json
import random
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import RLTrainingDataModel, PredictiveModelModel
from backend.utils.timezone_helper import ist_now

# Action spaces mappings
ACTIONS = [
    "Reduce Speed",
    "Activate Backup Tank",
    "Safe Mode",
    "Route Change",
    "Emergency Shutdown",
    "Communication Switch"
]

class SpacecraftEnvironment:
    """A Gym-like environment wrapper simulating spacecraft physics transitions locally for policy training"""
    def __init__(self, initial_state: dict):
        self.initial_state = initial_state
        self.reset()

    def reset(self) -> dict:
        self.state = {
            "fuel": self.initial_state.get("fuel", 100.0),
            "power": self.initial_state.get("power", 100.0),
            "health": self.initial_state.get("health", 100.0),
            "risk": self.initial_state.get("risk_score", 0.0),
            "distance": self.initial_state.get("distance", 0.0),
            "mission_progress": self.initial_state.get("mission_progress", 0.0),
            "subsystems": self.initial_state.get("subsystems", {
                "Propulsion": 100.0, "Power": 100.0, "Navigation": 100.0, 
                "Communication": 100.0, "Life Support": 100.0, "Thermal Control": 100.0, "Science Systems": 100.0
            }),
            "events": self.initial_state.get("active_events", [])
        }
        self.steps = 0
        return self.state

    def step(self, action: str) -> tuple:
        """Executes a local transition step based on action choice"""
        self.steps += 1
        
        # 1. State transitions simulation
        fuel_decay = 0.5
        power_decay = 0.3
        health_decay = 0.2
        
        # Action impacts modifiers
        if action == "Reduce Speed":
            fuel_decay = 0.1
            self.state["risk"] = max(0.0, self.state["risk"] - 5.0)
        elif action == "Activate Backup Tank":
            self.state["fuel"] = min(100.0, self.state["fuel"] + 15.0)
            self.state["power"] = max(10.0, self.state["power"] - 2.0)
        elif action == "Safe Mode":
            power_decay = 0.05
            fuel_decay = 0.2
            self.state["risk"] = max(0.0, self.state["risk"] - 15.0)
        elif action == "Route Change":
            fuel_decay = 1.5
            self.state["risk"] = max(0.0, self.state["risk"] - 25.0)
            self.state["health"] = min(100.0, self.state["health"] + 2.0)
        elif action == "Emergency Shutdown":
            fuel_decay = 0.0
            power_decay = 1.0
            self.state["risk"] = max(0.0, self.state["risk"] - 30.0)
        elif action == "Communication Switch":
            power_decay = 0.6
            self.state["risk"] = max(0.0, self.state["risk"] - 10.0)

        # Apply event penalties if events are active
        if self.state["events"]:
            health_decay += 2.5 * len(self.state["events"])
            fuel_decay += 0.8 * len(self.state["events"])

        # Update base state variables
        self.state["fuel"] = max(0.0, self.state["fuel"] - fuel_decay)
        self.state["power"] = max(10.0, self.state["power"] - power_decay)
        self.state["health"] = max(0.0, self.state["health"] - health_decay)
        
        # Recalculate compound risk score
        health_avg = self.state["health"]
        self.state["risk"] = 0.3 * (100.0 - self.state["fuel"]) + 0.3 * (100.0 - self.state["power"]) + 0.4 * (100.0 - health_avg)
        self.state["risk"] = min(100.0, max(0.0, self.state["risk"]))
        
        # Progress distance
        speed = 2000.0
        if action == "Reduce Speed": speed = 800.0
        elif action == "Emergency Shutdown": speed = 0.0
        self.state["distance"] += speed
        self.state["mission_progress"] = min(100.0, (self.state["distance"] / 1000000.0) * 100)

        # 2. Reward calculation
        # Reward = (SuccessScore + SafetyScore) / FuelPenalty - RiskPenalty
        success_score = 0.25 * self.state["fuel"] + 0.2 * self.state["power"] + 0.2 * self.state["health"] + 0.35 * max(0.0, 100.0 - self.state["risk"])
        safety_score = self.state["health"]
        # Fuel penalty increases as fuel falls
        fuel_penalty = max(1.0, (100.0 - self.state["fuel"]) / 20.0)
        risk_penalty = self.state["risk"]
        
        reward = ((success_score + safety_score) / fuel_penalty) - risk_penalty
        
        # 3. Check termination conditions
        done = False
        if self.state["fuel"] <= 0 or self.state["power"] <= 10 or self.state["health"] <= 0:
            done = True
            reward -= 100.0  # major penalty for failure
        elif self.state["mission_progress"] >= 100.0:
            done = True
            reward += 150.0  # major reward for success
        elif self.steps >= 50:
            done = True  # max episode length

        return self.state, round(reward, 2), done, {}

class RLPolicyLearner:
    """Implements discretized Q-learning policy optimization offline over database memories"""
    def __init__(self):
        self.q_table = {}  # state_bin -> {action: q_value}
        self.alpha = 0.1   # learning rate
        self.gamma = 0.95  # discount factor
        self.epsilon = 0.2 # exploration probability

    def get_state_bin(self, state: dict) -> str:
        """Discretizes continuous parameters into unique state binned string keys"""
        f_bin = "F_HIGH" if state["fuel"] > 40 else "F_LOW"
        p_bin = "P_HIGH" if state["power"] > 40 else "P_LOW"
        h_bin = "H_HIGH" if state["health"] > 50 else "H_LOW"
        r_bin = "R_HIGH" if state["risk"] > 50 else "R_LOW"
        e_bin = "EV" if state["events"] else "NO_EV"
        return f"{f_bin}_{p_bin}_{h_bin}_{r_bin}_{e_bin}"

    def select_action(self, state_bin: str) -> str:
        """Epsilon-greedy action selection selection"""
        if state_bin not in self.q_table:
            self.q_table[state_bin] = {act: 0.0 for act in ACTIONS}

        if random.random() < self.epsilon:
            return random.choice(ACTIONS)
        
        # Argmax
        q_vals = self.q_table[state_bin]
        best_val = max(q_vals.values())
        best_actions = [act for act, val in q_vals.items() if val == best_val]
        return random.choice(best_actions)

    async def train_policy(self, db: AsyncSession, initial_state: dict, episodes: int = 50) -> dict:
        """Runs offline reinforcement learning episodes updating the discretized Q-table"""
        env = SpacecraftEnvironment(initial_state)
        total_steps = 0
        episode_rewards = []
        td_errors = []

        print(f"[RL Policy] Starting training of {episodes} episodes...")

        # Initialize / load model state
        for ep in range(episodes):
            state = env.reset()
            state_bin = self.get_state_bin(state)
            done = False
            ep_reward = 0.0

            step_count = 0
            while not done:
                action = self.select_action(state_bin)
                next_state, reward, done, _ = env.step(action)
                next_state_bin = self.get_state_bin(next_state)

                if next_state_bin not in self.q_table:
                    self.q_table[next_state_bin] = {act: 0.0 for act in ACTIONS}

                # Q-learning Bellman update
                old_q = self.q_table[state_bin][action]
                max_next_q = max(self.q_table[next_state_bin].values())
                td_target = reward + self.gamma * max_next_q
                td_error = td_target - old_q
                
                self.q_table[state_bin][action] = old_q + self.alpha * td_error
                
                ep_reward += reward
                td_errors.append(abs(td_error))
                total_steps += 1
                step_count += 1

                # Log transition data to Postgres
                train_rec = RLTrainingDataModel(
                    timestamp=ist_now(),
                    episode=ep + 1,
                    step=step_count,
                    state=json.dumps(state),
                    action=action,
                    reward=reward,
                    next_state=json.dumps(next_state),
                    td_error=round(td_error, 3)
                )
                db.add(train_rec)

                state = next_state
                state_bin = next_state_bin

            episode_rewards.append(ep_reward)

        await db.commit()

        # Fit model metadata tracking
        avg_reward = sum(episode_rewards) / len(episode_rewards)
        avg_td = sum(td_errors) / len(td_errors) if td_errors else 0.0
        
        # Save predictive model weights snapshot
        model_rec = PredictiveModelModel(
            timestamp=ist_now(),
            model_name="Q_Learning_Policy",
            model_type="Q-Table",
            accuracy_score=round(1.0 - (min(1.0, avg_td / 100.0)), 3),
            parameters=json.dumps(self.q_table)
        )
        db.add(model_rec)
        await db.commit()

        print(f"[RL Policy] Completed. Avg Reward: {avg_reward:.2f}, Avg TD Error: {avg_td:.3f}")
        return {
            "status": "success",
            "episodes_trained": episodes,
            "total_steps": total_steps,
            "average_reward": round(avg_reward, 1),
            "average_td_error": round(avg_td, 3)
        }

# Global RL trainer instance
rl_policy = RLPolicyLearner()
