import os
import sys
from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))

from connections.calculi.modal import *

import argparse

parser = argparse.ArgumentParser(description='ileanCoP Python version')
parser.add_argument("file", help="The conjecture you want to prove")
parser.add_argument("logic", help="Which modal logic")
parser.add_argument("domain", help="Which domain")
args = parser.parse_args()

env = MConnectionEnv(args.file, args.logic, args.domains)
import traceback
import sys

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
