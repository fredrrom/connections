import sys
import os 
import subprocess
import signal
import traceback
from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))

import argparse

parser = argparse.ArgumentParser(description='Python equivalent of version 1.0f of leanCoP, ileanCoP, and mleanCoP')
parser.add_argument("file", help="The conjecture you want to prove")
parser.add_argument('logic', nargs='?', default='classical', help="Which logic")
parser.add_argument('domain', nargs='?', default='constant', help="Which domain")
args = parser.parse_args()

if args.logic == 'classical':
    translator_path = 'translation/classical/translate.sh'
elif args.logic == 'intuitionistic':
    translator_path = 'translation/intuitionistic/translate.sh'
else:
    translator_path = 'translation/modal/translate.sh'

problem = os.path.basename(os.path.normpath(args.file))
with subprocess.Popen([translator_path, args.file, problem], preexec_fn=os.setsid) as process:
    try:
        output, errors = process.communicate(timeout=1)
    except subprocess.TimeoutExpired as err:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
if os.path.exists(problem):
    os.remove(problem)

if args.logic == 'classical':
    from connections.calculi.classical import *
    env = ConnectionEnv(args.file)
elif args.logic == 'intuitionistic':
    from connections.calculi.intuitionistic import *
    env = IConnectionEnv(args.file)
else:
    from connections.calculi.modal import *
    env = MConnectionEnv(args.file, args.logic, args.domains)

print(env)

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
