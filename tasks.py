"""Task registry.

Each task defines:
- the world layout
- the agent's starting position and facing
- a "brief" given to the LLM (its directive)
- a function that decides whether the run is done (and won)
- a human-readable description for logs / README

The harness is task-agnostic — main.py just reads from this registry.
"""

LAYOUT_KEY_DOOR = [
    "###############",
    "#A...#........#",
    "#....#........#",
    "#....#........#",
    "#....D........#",
    "#....#...T....#",
    "#....#........#",
    "#....#...K....#",
    "#....#........#",
    "###############",
]

LAYOUT_OPEN = [
    "###############",
    "#.............#",
    "#.###.....###.#",
    "#.#....T....#.#",
    "#.#.###.....#.#",
    "#...#...#.....#",
    "#.T.#...#...T.#",
    "#...#####.#...#",
    "#.............#",
    "###############",
]


def _world_done(world, agent):
    """Default: terminate when world reports done (apple reached or died)."""
    return world.done, world.win, world.last_action_result or ""


def _coverage(agent):
    explored = sum(1 for row in agent.memory for c in row if c != "?")
    total = agent.width * agent.height
    return explored, total, explored / total


def _survey_done(world, agent, target=0.55):
    if world.done and not world.win:  # died
        return True, False, "died during exploration"
    explored, total, frac = _coverage(agent)
    if frac >= target:
        return True, True, f"explored {explored}/{total} tiles ({frac:.0%})"
    return False, False, ""


TASKS = {
    "discover": {
        "layout": LAYOUT_KEY_DOOR,
        "start": (10, 8),
        "facing": "W",
        "brief": "Act purposefully based on what you observe.",
        "is_done": _world_done,
        "description": (
            "No goal stated. The world contains a key, a locked door and an apple. "
            "Will the LLM infer from the environment that it should pick up the key, "
            "open the door, and reach the apple?"
        ),
    },
    "fetch_apple": {
        "layout": LAYOUT_KEY_DOOR,
        "start": (10, 8),
        "facing": "W",
        "brief": (
            "Your objective is to reach the apple tile (A) and stand on it. "
            "Plan your route accordingly."
        ),
        "is_done": _world_done,
        "description": (
            "Same world as 'discover', but the goal is stated explicitly. "
            "Use this as a baseline to compare against 'discover'."
        ),
    },
    "survey": {
        "layout": LAYOUT_OPEN,
        "start": (1, 1),
        "facing": "S",
        "brief": (
            "Explore as much of the map as you can. Avoid traps. "
            "There is no item to collect — your job is to see new tiles."
        ),
        "is_done": _survey_done,
        "description": (
            "Open exploration task on a different map. No collectible. "
            "Tests whether the agent can sustain exploration when there is no "
            "obvious target. Success = 55% of tiles observed."
        ),
    },
}
