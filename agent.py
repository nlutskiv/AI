from llm import LLMClient
from mock_agent import MockPolicy
from prompts import build_system_prompt


VALID_ACTIONS = {
    "MOVE_FORWARD", "TURN_LEFT", "TURN_RIGHT",
    "PICK_UP", "OPEN_DOOR", "WAIT",
}


class Agent:
    """High-level agent.

    Architecture:
      - keeps a memory map of every tile it has ever observed (fog of war)
      - keeps a short action history
      - on every turn, builds a prompt and asks the LLM for an action
      - validates the action; falls back to MockPolicy if invalid/unavailable
      - tracks how often each path was taken
    """

    def __init__(self, width, height, task_brief, force_mock=False, model="gpt-4o-mini"):
        self.width = width
        self.height = height
        self.memory = [["?" for _ in range(width)] for _ in range(height)]
        self.history = []
        self.system_prompt = build_system_prompt(task_brief)
        self.llm = LLMClient(model=model, force_mock=force_mock)
        self.fallback = MockPolicy()
        self.llm_call_count = 0
        self.fallback_call_count = 0
        self.last_prompt = None

    # ---------- memory ----------
    def update_memory(self, obs):
        x, y = obs["position"]
        self.memory[y][x] = obs["current_tile"]

        d = obs["direction"]
        forward = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}[d]
        fx, fy = forward
        rx, ry = -fy, fx  # 90 CW

        rel = {
            "front":       (fx,        fy       ),
            "front_right": (fx + rx,   fy + ry  ),
            "right":       (rx,        ry       ),
            "back_right":  (-fx + rx,  -fy + ry ),
            "back":        (-fx,       -fy      ),
            "back_left":   (-fx - rx,  -fy - ry ),
            "left":        (-rx,       -ry      ),
            "front_left":  (fx - rx,   fy - ry  ),
        }
        for name, (dx, dy) in rel.items():
            tx, ty = x + dx, y + dy
            if 0 <= tx < self.width and 0 <= ty < self.height:
                self.memory[ty][tx] = obs["visible"][name]

    def render_memory(self, agent_pos):
        ax, ay = agent_pos
        lines = []
        for y, row in enumerate(self.memory):
            line = ""
            for x, c in enumerate(row):
                line += "@" if (x, y) == (ax, ay) else c
            lines.append(line)
        return "\n".join(lines)

    def coverage(self):
        explored = sum(1 for row in self.memory for c in row if c != "?")
        total = self.width * self.height
        return explored, total, explored / total

    # ---------- prompt ----------
    def build_user_prompt(self, obs):
        v = obs["visible"]
        recent = self.history[-5:] if self.history else "none yet"
        local_view = (
            f"  {v['front_left']} {v['front']} {v['front_right']}\n"
            f"  {v['left']} @ {v['right']}\n"
            f"  {v['back_left']} {v['back']} {v['back_right']}"
        )
        return (
            f"Position: {obs['position']}\n"
            f"Facing: {obs['direction']}\n"
            f"HP: {obs['hp']}\n"
            f"Inventory: {obs['inventory']}\n"
            f"Tile under you: {obs['current_tile']}\n"
            f"Last action: {obs['last_action']} -> {obs['last_action_result']}\n"
            f"Recent actions: {recent}\n\n"
            f"Local 8-tile view (relative to your facing):\n{local_view}\n\n"
            f"Memory map of what you have explored so far:\n"
            f"{self.render_memory(obs['position'])}\n\n"
            f"Choose your next action."
        )

    # ---------- act ----------
    def act(self, obs):
        self.update_memory(obs)
        prompt = self.build_user_prompt(obs)
        self.last_prompt = prompt

        decision = self.llm.chat(self.system_prompt, prompt)
        source = "llm"
        if decision is None or decision.get("action") not in VALID_ACTIONS:
            decision = self.fallback.decide(obs)
            source = "fallback"
            self.fallback_call_count += 1
        else:
            self.llm_call_count += 1

        decision["source"] = source
        self.history.append((decision["action"], obs["last_action_result"]))
        return decision
