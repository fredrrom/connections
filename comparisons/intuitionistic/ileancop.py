import argparse
import sys

from connections.search.env import *

parser = argparse.ArgumentParser(description="ileanCoP Python version")
parser.add_argument("file", help="The conjecture you want to prove")
args = parser.parse_args()

settings = Settings(logic="intuitionistic")

env = ConnectionEnv(args.file, settings=settings)

import sys
import traceback

try:
    observation = env.reset()
    while True:
        if not env.action_space:
            break
        action = next(iter(next(iter(env.action_space.values())).values()))
        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
