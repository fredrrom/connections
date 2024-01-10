import sys
import os 
import subprocess
import signal
import multiprocessing
from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))

import argparse

parser = argparse.ArgumentParser(description='Python equivalent of version 1.0f of leanCoP, ileanCoP, and mleanCoP')
parser.add_argument("dir", help="Directory to translate")
parser.add_argument('logic', nargs='?', default='classical', help="Which logic")
args = parser.parse_args()

if args.logic == 'classical':
    translator_path = 'translation/classical/translate.sh'
elif args.logic == 'intuitionistic':
    translator_path = 'translation/intuitionistic/translate.sh'
else:
    translator_path = 'translation/modal/translate.sh'

def run_theorem_prover(problempath):
    problem = os.path.basename(os.path.normpath(problempath))
    problem = os.path.join('translated_dir',problem)
    with subprocess.Popen([translator_path, problempath, problem], preexec_fn=os.setsid) as process:
        try:
            output, errors = process.communicate(timeout=1)
        except subprocess.TimeoutExpired as err:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    if not os.path.exists(problem):
        return None
    
if __name__ == '__main__':
    num_processes = multiprocessing.cpu_count() - 1
    fof_filter = lambda filename : '+' in filename and '.p' in filename and filename.count('.') == 1
    problems = [os.path.join(args.dir,filename) for filename in os.listdir(args.dir) if fof_filter(filename)]
    if not os.path.exists('translated_dir'):
        os.makedirs('translated_dir')
    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(run_theorem_prover, problems)