import os
import sys
from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))

from connections.calculi.intuitionistic import *
from connections.utils.unification_intu import flatten_list

import argparse

parser = argparse.ArgumentParser(description='ileanCoP Python version')
parser.add_argument("file", help="The conjecture you want to prove")
args = parser.parse_args()

env = IConnectionEnv(args.file, iterative_deepening=True)
import traceback
import sys

try:
    observation = env.reset()
    depth = 2
    while True:
        if depth != observation.max_depth:
            depth = observation.max_depth
            print(f'pathlim___________:{depth+1}')
        action = env.action_space[0]
        if observation is not None:
            if observation.goal is not None:
                # for action in actions
                if action is not None and action.type in ['re','ex']:
                    lit_1 = observation.goal.literal
                    if action.type == 're':
                        lit_2 = action.path_lit
                    else:
                        lit_2 = action.clause_copy[action.lit_idx]
                    pre_1, pre_2 = observation._pre_eq(lit_1, lit_2)
                    s = pre_unify(pre_1.args, [], pre_2.args, action.sigma.copy())
                    if s is not None:
                        print(f'  weak_prefix_unify : {[subst(s,pre) for pre in pre_1.args], [subst(s,pre) for pre in pre_2.args]}')
                        print(f'  weak_prefix_unify_success')
                        print(action)

        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
