import sys
import traceback
from copy import deepcopy

from connections.env import *

import argparse

parser = argparse.ArgumentParser(description='ileanCoP Python version')
parser.add_argument("file", help="The conjecture you want to prove")
parser.add_argument("logic", help="Which modal logic")
parser.add_argument("domain", help="Which domain")
args = parser.parse_args()

Settings = Settings(iterative_deepening=True,
                    logic=args.logic,
                    domain=args.domain)

env = ConnectionEnv(args.file, settings=Settings)

try:
    observation = env.reset()
    while True:
        action = env.action_space[0]
        print(action)
        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
