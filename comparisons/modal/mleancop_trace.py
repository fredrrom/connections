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

settings = Settings(logic=args.logic, domain=args.domain)

env = ConnectionEnv(args.file, settings=settings)

try:
    observation = env.reset()
    info = {"status": "No action"}
    while True:
        if not env.action_space:
            break
        action = next(iter(next(iter(env.action_space.values())).values()))
        if observation is not None:
            if action is not None and action.action_type in ["reduction", "extension"]:
                left_node = env.state.tableau.get_node(action.node_id)
                if left_node is None or left_node.literal is None:
                    continue
                lit_1 = left_node.literal
                if (
                    action.action_type == "reduction"
                    and action.path_node_id is not None
                ):
                    right_node = env.state.tableau.get_node(action.path_node_id)
                    if right_node is None or right_node.literal is None:
                        continue
                    lit_2 = right_node.literal
                elif action.lit_idx is not None and action.clause_copy is not None:
                    lit_2 = action.clause_copy[action.lit_idx]
                else:
                    continue
                pre_1, pre_2 = observation.prefix_substitution.relation_pair(
                    lit_1,
                    lit_2,
                    fresh_variable=observation._next_prefix_variable(),
                )
                new_s = deepcopy(observation.term_substitution)
                new_s.update(action.sub_updates)
                observation.prefix_substitution.bind_term_substitution(new_s)
                ok, _ = observation.prefix_substitution.unify(pre_1, pre_2)
                if ok:
                    print(
                        f"  weak_prefix_unify : {[new_s(pre) for pre in pre_1.parts], [new_s(pre) for pre in pre_2.parts]}"
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
