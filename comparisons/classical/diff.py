import multiprocessing
import subprocess
import os
import signal
import time
import pandas as pd

out_path = 'output'
fof_path = '../../../conjectures/TPTP-v6.4.0/Problems/'
translator_path = 'leancop_trans_v22fb/leancop_trans.sh'
leancop_path = 'leancop10f_trace/leancop10.sh'
pycop_path = 'leancop_trace.py'
fof_filter = lambda filename : '+' in filename and '.p' in filename and filename.count('.') == 1

def run_theorem_prover(problempath):
    problem = os.path.basename(os.path.normpath(problempath))
    print(problem)
    with subprocess.Popen([translator_path, problempath, problem], preexec_fn=os.setsid) as process:
        try:
            output, errors = process.communicate(timeout=1)
        except subprocess.TimeoutExpired as err:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    if not os.path.exists(problem):
        return None
    
    info = {}
    info['Problem'] = problem
    start_time = time.time()
    with open(f"{out_path}/out/{problem}_pycop.out", 'w+') as f:
        with subprocess.Popen(['python',pycop_path,problem], stdout=f, preexec_fn=os.setsid) as process:
            try:
                output, errors = process.communicate(timeout=1)
                if output is not None: f.write(output)
            except subprocess.TimeoutExpired as err:
                if err.stdout is not None:
                    f.write(err.stdout.decode("utf-8"))
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            info['pyCoP time'] = time.time() - start_time

    start_time = time.time()
    with open(f"{out_path}/out/{problem}_leancop.out", 'w+') as f:
        with subprocess.Popen([leancop_path, problempath], stdout=f, preexec_fn=os.setsid) as process:
            try:
                output, errors = process.communicate(timeout=1)
                if output is not None: f.write(output)
            except subprocess.TimeoutExpired as err:
                if err.stdout is not None:
                    f.write(err.stdout.decode("utf-8"))
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            info['leanCoP time'] = time.time() - start_time

    with open(f'{out_path}/out/{problem}_pycop.out') as file_1, open(f'{out_path}/out/{problem}_leancop.out') as file_2:

        with open(f'{out_path}/log/{problem}_pycop.log', "w+") as new_py:
            for line in file_1.readlines():
                new_py.write(line)

        skip_count = 0
        with open(f'{out_path}/log/{problem}_leancop.log', "w+") as new_lean:
            trace = file_2.readlines()[1:]
            for i, line in enumerate(trace):
                if '!' in trace[i]:
                    continue
                new_lean.write(line)

    with open(f'{out_path}/log/{problem}_pycop.log', "r") as file_1, open(f'{out_path}/log/{problem}_leancop.log', "r") as file_2:
        lines_1, lines_2 = file_1.readlines(), file_2.readlines()
        ipy_status, ilean_status = False, False
        if lines_1:
            ipy_status = 'Theorem' in lines_1[-1]
            lines_1 = lines_1[:-1]
        if lines_2:
            ilean_status = 'Theorem' in lines_2[-1]
            lines_2 = lines_2[:-2]
        info['pyCoP status'] = 'Theorem' if ipy_status else 'Timeout'
        info['leanCoP status'] = 'Theorem' if ilean_status else 'Timeout'
        info['pyCoP inferences'] = len(lines_1)
        info['leanCoP inferences'] = len(lines_2)
        info['Diff inference'] = None
        for i, (line_py, line_lean) in enumerate(zip(lines_1, lines_2)):
            if line_py[:2] != line_lean[:2]:
                info['Diff inference'] = i + 1
                break
    os.remove(problem)
    os.remove(f'{out_path}/out/{problem}_pycop.out')
    os.remove(f'{out_path}/out/{problem}_leancop.out')
    os.remove(f'{out_path}/log/{problem}_pycop.log')
    os.remove(f'{out_path}/log/{problem}_leancop.log')
    return info


if __name__ == '__main__':
    num_processes = multiprocessing.cpu_count()
    results = []
    for folder in os.listdir(fof_path):
        if not os.path.isdir(os.path.join(fof_path,folder)):
            continue
        problems = [os.path.join(fof_path,folder,filename) for filename in os.listdir(fof_path+folder) if fof_filter(filename)]
        with multiprocessing.Pool(processes=num_processes) as pool:
            results.extend(pool.map(run_theorem_prover, problems))
    results = filter(None,results)
    df = pd.DataFrame(results) 
    df = df[(df['pyCoP status'] != df['leanCoP status']) | (df['Diff inference'].notna())]
    df.to_csv("diff.csv", index=False)
