# Gridworld LLM Agent

A small harness that drops an LLM into a 2D gridworld and lets it perceive,
reason, and act in a loop. The interesting part isn't the world — it's the
**interface between the LLM and the environment**: how observations are
represented, how actions are constrained, what the agent remembers, and how
the system stays reliable when the model misbehaves.

The agent has fog of war (it only sees the 8 tiles around itself), keeps a
running memory map of what it has explored, and chooses one action per turn.
Every decision is logged to JSONL so any run can be replayed step by step
afterward. The system runs **with or without an API key** — when no key is
set, a deterministic heuristic drives the agent so the harness itself can
always be tested.

> Submission for the Humanoid Intern Challenge: *"LLM Agent in a Virtual
> World."* Built solo over a few days, with Claude used as a pair programmer.

---

## Quick start

```bash
git clone <this-repo>
cd gridworld
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...                # or on Windows: $env:OPENAI_API_KEY="sk-..."
python main.py --task fetch_apple --delay 0.5
```

To run without an API key (deterministic heuristic mode):

```bash
python main.py --task survey --mock --delay 0.2
```

CLI flags:

| flag           | default       | meaning                                     |
|----------------|---------------|---------------------------------------------|
| `--task`       | `discover`    | task name (`discover`, `fetch_apple`, `survey`) |
| `--max-steps`  | `80`          | hard cap on agent steps                     |
| `--delay`      | `0.5`         | seconds to sleep between steps              |
| `--mock`       | `false`       | force heuristic-only mode                   |
| `--no-log`     | `false`       | disable JSONL logging                       |
| `--model`      | `gpt-4o-mini` | OpenAI model name                           |

---

## Tasks

The harness ships with three tasks. They share the same observation format,
action space, and agent code — only the layout, the success condition, and
the directive given to the LLM change. Adding a new task is one entry in
`tasks.py`.

### `discover` — no goal stated

The world contains a key, a locked door, and an apple. The LLM is told only
*"Act purposefully based on what you observe."* Nothing about keys opening
doors, nothing about the apple being a goal. The interesting question is
whether the model spontaneously chains *see key → pick up → see door →
remember key → open door → reach apple* purely from environment structure
and the action mechanics.

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
Acts as a baseline against `discover`.

### `survey` — open exploration, no collectible

A different layout with no key, door or apple — just open space, corridors
and traps. The directive is *"explore as much of the map as you can, avoid
traps."* Success is reaching 55% map coverage. Tests whether the harness
generalises beyond goal-fetching tasks.

---

## Architecture

```
                      +-------------+
                      |   World     |  <-- ground truth, agent never reads this
                      |  (world.py) |
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
  (no key, library missing, malformed JSON, etc.) and the agent falls back
  to the deterministic policy. The harness never crashes because of the
  model.
- **MockPolicy** is intentionally not smart — it's a safety net, not a
  competing agent. (As it turns out in the [Results](#results), it
  outperforms small LLMs on the exploration task anyway.)

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

The agent additionally gets, in each prompt:
- a rendered ASCII memory map of every tile observed so far (with `?` for
  unseen tiles and `@` for the current position),
- the last 5 (action, result) pairs, so it can detect loops.

Two design choices worth flagging:

1. **8 tiles, named relative to the agent's facing.** Not absolute compass
   directions. Because the action space is also relative
   (`MOVE_FORWARD`, `TURN_LEFT`), keeping observations relative removes a
   coordinate-rotation step the LLM would otherwise have to do mentally.
2. **A persistent memory map is included in the prompt.** Without this the
   LLM forgets where the door was the moment it walks past it. The map is
   what makes multi-step reasoning ("I saw a key earlier, go back to it")
   tractable in principle. (In practice — see Results — small models
   ignore it.)

---

## Action space

```
MOVE_FORWARD   move one tile in the direction you are facing
TURN_LEFT      rotate 90° counterclockwise
TURN_RIGHT     rotate 90° clockwise
PICK_UP        pick up the item under you
OPEN_DOOR      open a door directly in front of you (consumes a key)
WAIT           do nothing
```

Six actions. Kept small on purpose. The whole point of having a
deterministic turn/move/pickup primitive set is that the LLM doesn't need
to think about geometry — it just needs to think about *what to do next*.
Every LLM response is parsed and validated against this set; anything else
is rejected and the fallback policy decides instead.

---

## Logs

Every run writes a JSONL file to `logs/run_<timestamp>.jsonl`. One JSON
object per line, line-buffered so you can `tail -f` it during a run.

Events:
- `start`  — task, brief, full world layout
- `step`   — observation, action chosen, model's reasoning, source (`llm` or
  `fallback`)
- `end`    — outcome, coverage, llm/fallback call counts

Six annotated runs are committed under `examples/` and discussed in the next
section.

---

## Results

I ran the three tasks across `gpt-4o-mini` and `gpt-4o`, plus one heuristic
control. All five LLM runs **timed out** within the step budget, but each
failed in a different way — and that turns out to be the most informative
finding in this submission.

| # | task         | driver          | outcome | log                                                                | failure mode                                                                                |
|---|--------------|-----------------|---------|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| 1 | `discover`   | `gpt-4o-mini`   | TIMEOUT | [`01_discover_4o-mini_timeout.jsonl`](examples/01_discover_4o-mini_timeout.jsonl)         | found and picked up the key, then drifted with no plan to use it on the door                |
| 2 | `fetch_apple`| `gpt-4o-mini`   | TIMEOUT | [`02_fetch-apple_4o-mini_timeout.jsonl`](examples/02_fetch-apple_4o-mini_timeout.jsonl)   | found the key, then traced the same 4-tile square for ~45 steps, ignoring the stated goal   |
| 3 | `fetch_apple`| `gpt-4o`        | TIMEOUT | [`03_fetch-apple_4o_run1_timeout.jsonl`](examples/03_fetch-apple_4o_run1_timeout.jsonl)   | navigated correctly toward the door, then misread a diagonal tile as "directly in front"    |
| 4 | `fetch_apple`| `gpt-4o`        | TIMEOUT | [`04_fetch-apple_4o_run2_timeout.jsonl`](examples/04_fetch-apple_4o_run2_timeout.jsonl)   | walked into a trap it could see, then explored away from the goal even when one turn from it |
| 5 | `survey`     | `gpt-4o-mini`   | TIMEOUT | [`05_survey_4o-mini_timeout.jsonl`](examples/05_survey_4o-mini_timeout.jsonl)             | got into a 1-wide corridor and ran the same 3-action cycle for **70 consecutive turns**     |
| 6 | `survey`     | heuristic       | **WIN** | [`06_survey_heuristic_win.jsonl`](examples/06_survey_heuristic_win.jsonl)                 | 12-line scripted policy reached 55% coverage in 77 steps                                    |

A few specific moments worth pulling out (all reproducible by replaying the
linked log):

- **Run 2, fetch_apple/4o-mini:** for steps 19–60 the agent cycles through
  positions `(13,7) → (13,6) → (12,6) → (12,7)` while every reason field
  reads *"I need to move forward to find the apple."* The model can describe
  its goal but cannot keep its actions consistent with it.
- **Run 3, fetch_apple/4o:** at step 42 the agent is at (6,5) facing North.
  The door at (5,4) is in its `front_left` (diagonal). The model says
  *"There is a door directly in front of me"* and uses `OPEN_DOOR` —
  which fails because the env checks the tile directly North, not the
  diagonal. The agent then tries `OPEN_DOOR` from three different facings
  while glued to the same tile, never moving up one square so the door
  would actually be in front of it.
- **Run 5, survey/4o-mini:** at step 11 the agent enters a 1-wide vertical
  corridor at (1,2). For the next 69 steps it executes the cycle
  `TURN_LEFT → TURN_RIGHT → MOVE_FORWARD (blocked: wall)` while every
  reason paraphrases *"to explore a new direction."* Total unique positions
  visited in 80 steps: **3.**

**The most striking result is that the deterministic 12-line heuristic
finishes the `survey` task while `gpt-4o-mini` does not.** Inspecting the
LLM run shows it producing grammatically valid reasoning while taking the
same blocked action 30 times in a row. The bottleneck for small LLMs in
this kind of harness isn't language fluency — it's sustained use of spatial
memory. The map is in the context window; the model just doesn't ground its
decisions in it.

This is the headline finding I would have written up regardless of whether
the LLM solved the puzzles. The harness is sensitive enough to expose
specific cognitive failures (loss of goal-tracking, diagonal/orthogonal
confusion, ignoring observed traps, failing to consult memory) and pin each
one to a precise step in a logged run. That's more useful than five clean
wins would have been.

---

## Design notes — what worked, what didn't

**Why fog of war.** The first version gave the LLM the full map. A* solves
that puzzle in one line of Python — the LLM was decoration. Once the agent
only sees 8 tiles around itself, the LLM's role becomes real: it has to
reason about what it has seen, what it remembers, and where to go next.

**Why no goal in the `discover` task prompt.** The action description for
`OPEN_DOOR` says it consumes a key, so the LLM knows the *mechanic*. What
it isn't told is that it *should* go open the door. Comparing `discover`
against `fetch_apple` makes the gap visible: stating the goal explicitly
changes the failure mode (Run 1 vs Run 2) but doesn't fix it.

**Why a deterministic fallback.** LLMs return malformed JSON, time out, get
rate-limited. If the harness collapses every time that happens you can't
demo anything. The fallback policy is dumb on purpose — it just keeps the
loop alive and tags itself in the logs as `[fallback]` so you can see
exactly when the LLM dropped out. (One run in development was accidentally
all-fallback because `OPENAI_API_KEY` wasn't set in the shell — the harness
didn't crash, it just printed a clear `[llm] mock mode (OPENAI_API_KEY not
set)` line and ran. That kind of soft-fail is worth a lot in practice.)

**Things I tried and threw out.**

- *Asking the LLM for a multi-step plan up front, then executing.* Plans
  read fine but went stale the moment the world surprised the agent
  (a trap, an unexpected wall). Switched to per-step decisions — simpler
  and more reliable.
- *Absolute compass directions in the observation.* The LLM kept confusing
  itself after turning. Switched to facing-relative names (`front`, `left`,
  etc.) and the confusion went away — except for the diagonal-vs-direct
  case in Run 3.
- *Letting the LLM emit raw movement vectors instead of named actions.* It
  occasionally tried to walk diagonally, which the env doesn't support.
  The enumerated action space is restrictive but eliminates a whole class
  of invalid outputs.
- *Adding "do not loop" instructions to the system prompt.* No measurable
  effect — Run 5 happened with that text in the prompt.

**Things I didn't have time for, and would do next.**

- A loop detector at the *harness* level (e.g. detect "same observation +
  same action 3 times in a row" and inject a perturbation), since the
  prompt-level instruction clearly doesn't work.
- Frontier-based exploration hints in the prompt (mark unvisited adjacent
  tiles to bias the model toward new ground).
- Comparing the same runs across `claude-3.5-sonnet` and `gpt-4o`. The
  diagonal misread in particular feels like the kind of error a bigger
  model might fix.

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
├── examples/        # six annotated run logs (see Results)
├── requirements.txt
└── README.md
```

---

*Built solo. Claude was used as a pair programmer for code review and
documentation. Every design decision and every interpretation of the run
logs in this README is mine.*
