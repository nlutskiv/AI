from world import world
from agent import Agent

agent  = Agent()
world = world()

for _ in range(20):
    obs = world.get_observation()
    decision = agent.act(obs)

    print("OBS:", obs)
    print("ACTION:", decision)

    world.step(decision["action"])
    world.render()