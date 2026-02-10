import argparse
import sys
import traceback
from copy import deepcopy

from connections.search.env import *

parser = argparse.ArgumentParser(description="ileanCoP Python version")
parser.add_argument("file", help="The conjecture you want to prove")
parser.add_argument("logic", help="Which modal logic")
parser.add_argument("domain", help="Which domain")
args = parser.parse_args()

settings = Settings(iterative_deepening=True, logic=args.logic, domain=args.domain)

env = ConnectionEnv(args.file, settings=settings)

try:
    observation = env.reset()
    depth = 2
    while True:
        if depth != observation.max_depth:
            depth = observation.max_depth
            print(f"pathlim___________:{depth + 1}")
        action = env.action_space[0]
        if observation is not None:
            if observation.goal is not None:
                # for action in actions
                if action is not None and action.action_type in [
                    "reduction",
                    "extension",
                ]:
                    lit_1 = observation.goal.literal
                    if action.action_type == "reduction":
                        lit_2 = action.path_node.literal
                    else:
                        lit_2 = action.clause_copy[action.lit_idx]
                    pre_1, pre_2 = observation.prefix_substitution.relation_pair(
                        lit_1,
                        lit_2,
                        fresh_variable=observation._next_prefix_variable(),
                    )
                    new_s = deepcopy(observation.substitution)
                    new_s.update(action.sub_updates)
                    s = observation.prefix_substitution.unify(pre_1, pre_2, new_s)
                    if s is not None:
                        print(
                            f"  weak_prefix_unify : {[s(pre) for pre in pre_1.parts], [s(pre) for pre in pre_2.parts]}"
                        )
                        print(f"  weak_prefix_unify_success")
                        print(action)

        observation, reward, done, info = env.step(action)
        if done:
            break
    print(info)
except Exception:
    print(traceback.format_exc())
    print(sys.exc_info()[2])
