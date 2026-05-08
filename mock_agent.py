import random


class MockPolicy:
    """Deterministic-ish heuristic agent.

    Used as a fallback whenever the LLM is unavailable or returns garbage.
    It is NOT trying to be smart — it just keeps the system runnable.

    Strategy:
      - if standing on a key, PICK_UP
      - if facing a door and have a key, OPEN_DOOR
      - if a key/apple is in front, MOVE_FORWARD toward it
      - if a trap is in front, turn away
      - if forward is open, walk forward (most of the time)
      - otherwise turn toward the most open side
    """

    BLOCKED = {"#", "D"}

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def decide(self, obs):
        v = obs["visible"]
        cur = obs["current_tile"]
        inv = obs["inventory"]

        if cur == "K":
            return {"action": "PICK_UP", "reason": "[mock] key under me"}

        if v["front"] == "D" and "key" in inv:
            return {"action": "OPEN_DOOR", "reason": "[mock] door ahead, I have a key"}

        if v["front"] == "A":
            return {"action": "MOVE_FORWARD", "reason": "[mock] apple ahead"}

        if v["front"] == "K":
            return {"action": "MOVE_FORWARD", "reason": "[mock] key ahead"}

        if v["front"] == "T":
            return {"action": "TURN_RIGHT", "reason": "[mock] trap ahead, turn away"}

        if v["front"] not in self.BLOCKED:
            if self.rng.random() < 0.75:
                return {"action": "MOVE_FORWARD", "reason": "[mock] explore forward"}

        left_open = v["left"] not in self.BLOCKED
        right_open = v["right"] not in self.BLOCKED
        if left_open and not right_open:
            return {"action": "TURN_LEFT", "reason": "[mock] left is open"}
        if right_open and not left_open:
            return {"action": "TURN_RIGHT", "reason": "[mock] right is open"}
        return {
            "action": self.rng.choice(["TURN_LEFT", "TURN_RIGHT"]),
            "reason": "[mock] random turn",
        }
