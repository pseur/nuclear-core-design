import gym
import colorenv

def step_render(env, action):
    print(env.step(action)[1:])
    env.render()

env = gym.make('ColorEnv-v0')
step_render(env,0)
step_render(env,1)
step_render(env,2)
step_render(env,2)
