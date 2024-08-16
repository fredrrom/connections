import sys
import traceback

from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))

from connections.env import *

import argparse

parser = argparse.ArgumentParser(description='leanCoP Python version')
parser.add_argument("file", help="The conjecture you want to prove")
args = parser.parse_args()

env = ConnectionEnv(args.file, Settings(iterative_deepening=True))

try:
    observation = env.reset()
    while True:
        action = env.action_space[0]
        if action is not None:
            print(action)
        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
