import sys

from connections.env import *

import argparse

parser = argparse.ArgumentParser(description='ileanCoP Python version')
parser.add_argument("file", help="The conjecture you want to prove")
args = parser.parse_args()

settings = Settings(iterative_deepening=True,
                    logic='intuitionistic')

env = ConnectionEnv(args.file, settings=settings)

import traceback
import sys

try:
    observation = env.reset()
    while True:
        action = env.action_space[0]
        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
