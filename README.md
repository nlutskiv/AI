# Gridworld LLM Agent

A small harness that drops an LLM into a 2D gridworld and lets it perceive,
reason, and act in a loop. The interesting part isn't the world — it's the
**interface between the LLM and the environment**.

The agent has fog of war (it only sees 8 tiles around itself), keeps a running
memory map of what it has explored, and chooses one action per turn. Every
decision is logged to JSONL so you can replay a run after the fact.

The system runs **with or without an API key** — when no key is set it falls
back to a deterministic heuristic so the harness itself can always be tested.

---

## Quick start

```bash
git clone <this-repo>
cd gridworld
pip install -r requirements.txt          # only needed for LLM mode
export OPENAI_API_KEY=sk-...              # optional; mock mode works without
python main.py --task discover --delay 0.5
```

To run without an API key (heuristic-only mode):

```bash
python main.py --task discover --mock --delay 0.2
```

CLI flags:

| flag           | default       | meaning                                     |
|----------------|---------------|---------------------------------------------|
| `--task`       | `discover`    | which task to run (`discover`, `fetch_apple`, `survey`) |
| `--max-steps`  | `80`          | hard cap on agent steps                     |
| `--delay`      | `0.5`         | seconds to sleep between steps              |
| `--mock`       | `false`       | force heuristic-only mode                   |
| `--no-log`     | `false`       | disable JSONL logging                       |
| `--model`      | `gpt-4o-mini` | OpenAI model name                           |

---

## Tasks

The harness ships with three tasks. They share the same observation format,
action space, and agent code — only the layout, success condition, and the
"directive" given to the LLM change. This is on purpose: the harness should be
task-agnostic.

### `discover` — no goal stated

The world contains a key, a locked door, and an apple. The LLM is told only:
*"Act purposefully based on what you observe."* Nothing about keys opening
doors, nothing about the apple being a goal. The interesting question is
whether the model spontaneously chains *see key → pick up → see door →
remember key → open door → reach apple* purely from environment structure and
the action mechanics.

```
###############
#A...#........#
#....#........#
#....#........#
#....D........#
#....#...T....#
#....#........#
#....#...K....#
#....#........#
###############
```

### `fetch_apple` — same world, goal stated

Identical layout, but the LLM is told its objective is to reach the apple.
Use this as a baseline for comparison against `discover`.

### `survey` — open exploration, no collectible

A different layout with no key, door, or apple — just open space and traps.
The directive is *"explore as much of the map as you can, avoid traps."*
Success is reaching 55% map coverage. This tests whether the harness works
for tasks that aren't goal-fetching.

---

## Architecture

```
                      +-------------+
                      |   World     |  <-- ground truth, agent never reads this
                      |  (env.py)   |
                      +------+------+
                             |
              get_observation| step(action)
                             v
                      +-------------+
                      |   Agent     |
                      |  (agent.py) |
                      |             |
                      |  - memory   |  <-- fog-of-war discovered map
                      |  - history  |
                      +------+------+
                             |
                build_prompt | validate
                             v
                      +-------------+        +---------------+
                      |  LLMClient  | -fail->|  MockPolicy   |
                      |   (llm.py)  |        | (heuristic)   |
                      +-------------+        +---------------+
```

- **World** holds full ground truth and exposes only `get_observation()` and
  `step(action)`. The agent has no access to internal state.
- **Agent** owns its own discovered map, action history, and the system
  prompt (which embeds the task brief). It wraps the LLM and validates every
  response.
- **LLMClient** is a thin OpenAI wrapper. It returns `None` on any failure
  (no key, library missing, malformed JSON, etc.) and the agent falls back to
  the deterministic policy. The harness never crashes because of the model.
- **MockPolicy** is intentionally not smart — it's a safety net, not a
  competing agent.

---

## Observation format

Every turn the agent receives:

```json
{
  "position": [10, 8],
  "direction": "W",
  "inventory": ["key"],
  "hp": 5,
  "current_tile": ".",
  "last_action": "MOVE_FORWARD",
  "last_action_result": "ok",
  "visible": {
    "front_left": "#", "front": ".", "front_right": "K",
    "left":       "#",                 "right":       ".",
    "back_left":  "#", "back":  ".", "back_right":  "."
  },
  "steps": 12
}
```

Two design choices worth flagging:

1. **8 tiles, named relative to the agent's facing.** Not absolute compass
   directions. Because the action space is also relative
   (`MOVE_FORWARD`, `TURN_LEFT`), keeping observations relative removes a
   coordinate-rotation step the LLM would otherwise have to do mentally.
2. **A persistent memory map**, included in the prompt as ASCII with `?` for
   unseen tiles and `@` for the current position. Without this the LLM forgets
   where the door was the moment it walks past it. The map is what makes
   multi-step reasoning ("I saw a key earlier, go back to it") tractable.

---

## Action space

```
MOVE_FORWARD   move one tile in the direction you are facing
TURN_LEFT      rotate 90° counterclockwise
TURN_RIGHT     rotate 90° clockwise
PICK_UP        pick up the item under you
OPEN_DOOR      open a door directly in front of you
WAIT           do nothing
```

Six actions. Kept small on purpose. The whole point of building a deterministic
turn/move/pickup primitive set is that the LLM doesn't need to think about
geometry — it just needs to think about *what to do next*.

---

## Logs

Every run writes a JSONL file to `logs/run_<timestamp>.jsonl`. One JSON object
per line, line-buffered so you can `tail -f` it during a run.

Events:
- `start`  — task, brief, world layout
- `step`   — observation, action, reason, source (`llm` or `fallback`)
- `end`    — outcome, coverage, llm/fallback call counts

Example excerpt:

```json
{"event": "start", "task": "discover", "brief": "Act purposefully based on what you observe.", ...}
{"event": "step", "step": 1, "obs": {"position": [10, 8], "direction": "W", "visible": {"front_right": "K", ...}}, "action": "TURN_RIGHT", "reason": "There is a key to my front-right, I want to face it.", "source": "llm"}
{"event": "step", "step": 2, "action": "MOVE_FORWARD", "reason": "Approaching the key.", "source": "llm"}
...
{"event": "end", "outcome": "WIN", "steps": 23, "llm_calls": 23, "fallback_calls": 0}
```

---

## Design notes

**Why fog of war.** The first version gave the LLM the full map. A* solves
that puzzle in one line of Python — the LLM was decoration. Once the agent
only sees 8 tiles around itself, the LLM's role becomes real: it has to
reason about what it has seen, what it remembers, and where to go next. The
harness stops being trivial.

**Why no goal in the `discover` task prompt.** The action description for
`OPEN_DOOR` says it consumes a key, so the LLM knows the *mechanic*. What it
isn't told is that it *should* go open the door. The interesting question is
whether the LLM treats "there's a key, there's a door" as a puzzle worth
solving on its own. Comparing `discover` against `fetch_apple` (same world,
explicit goal) makes that gap visible.

**Why a deterministic fallback.** LLMs return malformed JSON, time out, or
get rate-limited. If the harness collapses every time that happens you can't
demo anything. The fallback policy is dumb on purpose — it just keeps the
loop alive and tags itself in the logs as `[fallback]` so you can see exactly
where the LLM dropped out.

**What didn't work.**

- *Asking the LLM for a multi-step plan up front.* The plans were fine but
  went stale the moment the world surprised the agent (a trap, an unexpected
  wall). Switched to per-step decisions — simpler and more reliable.
- *Absolute compass directions in the observation.* The LLM kept confusing
  itself after turning. Switched to facing-relative names (`front`, `left`,
  etc.) and the confusion went away.
- *Letting the LLM emit raw movement vectors instead of named actions.* It
  occasionally tried to walk diagonally, which the env doesn't support. The
  enumerated action space is restrictive but eliminates a whole class of
  invalid outputs.

---

## File structure

```
gridworld/
├── main.py          # CLI entry, run loop, summary
├── world.py         # environment: grid, step(), get_observation()
├── agent.py         # agent: memory, prompt building, LLM + fallback
├── llm.py           # OpenAI wrapper, returns None on any failure
├── mock_agent.py    # deterministic heuristic, used as fallback
├── prompts.py       # system prompt template (task brief is a slot)
├── tasks.py         # task registry: layout, brief, success condition
├── logger.py        # JSONL line-buffered logger
├── requirements.txt
└── README.md
```
