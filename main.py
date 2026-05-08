import argparse
import time

from world import World
from agent import Agent
from logger import JSONLLogger
from tasks import TASKS


def parse_args():
    p = argparse.ArgumentParser(
        description="Run an LLM agent in a 2D gridworld.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--task", default="discover", choices=list(TASKS.keys()),
                   help="which task to run")
    p.add_argument("--max-steps", type=int, default=80,
                   help="hard cap on the number of agent steps")
    p.add_argument("--delay", type=float, default=0.5,
                   help="seconds to sleep between steps (0 = no delay)")
    p.add_argument("--mock", action="store_true",
                   help="force heuristic-only mode, never call the LLM")
    p.add_argument("--no-log", action="store_true",
                   help="disable JSONL logging")
    p.add_argument("--model", default="gpt-4o-mini",
                   help="OpenAI model name")
    return p.parse_args()


def main():
    args = parse_args()
    task = TASKS[args.task]

    world = World(layout=task["layout"], start=task["start"], facing=task["facing"])
    agent = Agent(
        world.width, world.height,
        task_brief=task["brief"],
        force_mock=args.mock,
        model=args.model,
    )

    logger = None if args.no_log else JSONLLogger()

    print("=" * 60)
    print(f"Task:        {args.task}")
    print(f"Brief:       {task['brief']}")
    print(f"Description: {task['description']}")
    print(f"Mode:        {'mock' if agent.llm.use_mock else f'llm ({args.model})'}")
    if logger:
        print(f"Log file:    {logger.path}")
    print("=" * 60)

    if logger:
        logger.log(
            event="start",
            task=args.task,
            brief=task["brief"],
            description=task["description"],
            max_steps=args.max_steps,
            mock=agent.llm.use_mock,
            model=args.model,
            world={
                "width": world.width,
                "height": world.height,
                "layout": ["".join(row) for row in world.grid],
                "start": list(world.agent_pos),
                "facing": world.direction,
            },
        )

    world.render()

    final_outcome = "TIMEOUT"
    final_message = ""

    for step in range(args.max_steps):
        obs = world.get_observation()
        decision = agent.act(obs)

        action = decision["action"]
        reason = decision.get("reason", "")
        source = decision.get("source", "unknown")

        print(f"\n--- step {step + 1} ---")
        print(f"action: {action}  [{source}]")
        print(f"reason: {reason}")

        if logger:
            logger.log(
                event="step",
                step=step + 1,
                obs=obs,
                action=action,
                reason=reason,
                source=source,
            )

        world.step(action)
        world.render()

        done, win, msg = task["is_done"](world, agent)
        if done:
            final_outcome = "WIN" if win else "LOSS"
            final_message = msg or world.last_action_result or ""
            print(f"\n*** {final_outcome}: {final_message} (after {world.steps} steps) ***")
            break

        if args.delay > 0:
            time.sleep(args.delay)
    else:
        print(f"\n*** TIMEOUT: ran out of steps after {args.max_steps} ***")

    # ---------- summary ----------
    explored, total, frac = agent.coverage()
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Outcome:       {final_outcome}")
    if final_message:
        print(f"Reason:        {final_message}")
    print(f"Steps taken:   {world.steps}")
    print(f"Map coverage:  {explored}/{total} tiles ({frac:.0%})")
    print(f"LLM calls:     {agent.llm_call_count}")
    print(f"Fallback used: {agent.fallback_call_count}")

    if logger:
        logger.log(
            event="end",
            outcome=final_outcome,
            message=final_message,
            steps=world.steps,
            explored=explored,
            total_tiles=total,
            coverage=frac,
            llm_calls=agent.llm_call_count,
            fallback_calls=agent.fallback_call_count,
        )
        logger.close()
        print(f"Log written to: {logger.path}")


if __name__ == "__main__":
    main()
