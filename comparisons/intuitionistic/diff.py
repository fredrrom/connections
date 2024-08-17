import multiprocessing
import subprocess
import os
import signal
import time
import pandas as pd

SAVE_LOGS = True

out_path = 'output'
fof_path = '../../../conjectures/ILTP-v1.1.2-firstorder/Problems/'
translator_path = 'leancop_itrans_v13fc/leancop_itrans.sh'
leancop_path = 'ileancop10f_trace_extended/ileancop10.sh'
pycop_path = 'ileancop_trace.py'
fof_filter = lambda filename : '+' in filename and '.p' in filename and filename.count('.') == 1 and 'SWV230+1.p' in filename# \
    #and filename[:3] in ['KRS','SET','SWV','SYN','SYJ']

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
    os.makedirs(f'{out_path}/out', exist_ok=True)
    os.makedirs(f'{out_path}/log', exist_ok=True)
    start_time = time.time()
    with open(f"{out_path}/out/{problem}_ipycop.out", 'w+') as f:
        with subprocess.Popen(['python',pycop_path,problem], stdout=f, preexec_fn=os.setsid) as process:
            try:
                output, errors = process.communicate(timeout=5)
                if output is not None: f.write(output)
            except subprocess.TimeoutExpired as err:
                if err.stdout is not None:
                    f.write(err.stdout.decode("utf-8"))
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            info['ipyCoP time'] = time.time() - start_time

    start_time = time.time()
    with open(f"{out_path}/out/{problem}_ileancop.out", 'w+') as f:
        with subprocess.Popen([leancop_path, problempath], stdout=f, preexec_fn=os.setsid) as process:
            try:
                output, errors = process.communicate(timeout=5)
                if output is not None: f.write(output)
            except subprocess.TimeoutExpired as err:
                if err.stdout is not None:
                    f.write(err.stdout.decode("utf-8"))
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            info['ileanCoP time'] = time.time() - start_time

    with open(f'{out_path}/out/{problem}_ipycop.out') as file_1, open(f'{out_path}/out/{problem}_ileancop.out') as file_2:

        with open(f'{out_path}/log/{problem}_ipycop.log', "w+") as new_py:
            for line in file_1.readlines():
                if line[:2] in ['st','Ba']:
                    continue
                new_py.write(line)

        skip_count = 0
        with open(f'{out_path}/log/{problem}_ileancop.log', "w+") as new_lean:
            trace = file_2.readlines()[1:]
            for i, line in enumerate(trace):
                if skip_count:
                    skip_count -= 1
                    continue
                if i < len(trace) - 2 and '!' in trace[i+2]:
                    skip_count = 2
                    continue
                if 'check' in line:
                    skip_count = 1
                    continue
                new_lean.write(line)

    with open(f'{out_path}/log/{problem}_ipycop.log', "r") as file_1, open(f'{out_path}/log/{problem}_ileancop.log', "r") as file_2:
        lines_1, lines_2 = file_1.readlines(), file_2.readlines()
        ipy_status, ilean_status = False, False
        if lines_1:
            ipy_status = 'Theorem' in lines_1[-1]
            lines_1 = lines_1[:-1]
        if lines_2:
            ilean_status = 'Theorem' in lines_2[-1]
            lines_2 = lines_2[:-2]
        info['ipyCoP status'] = 'Theorem' if ipy_status else 'Timeout'
        info['ileanCoP status'] = 'Theorem' if ilean_status else 'Timeout'
        info['ipyCoP inferences'] = len(lines_1)
        info['ileanCoP inferences'] = len(lines_2)
        info['Diff inference'] = None
        for i, (line_py, line_lean) in enumerate(zip(lines_1, lines_2)):
            if line_py[:2] != line_lean[:2]:
                info['Diff inference'] = i + 1
                break
    if not SAVE_LOGS:
        os.remove(f'{out_path}/out/{problem}_ipycop.out')
        os.remove(f'{out_path}/out/{problem}_ileancop.out')
        os.remove(f'{out_path}/log/{problem}_ipycop.log')
        os.remove(f'{out_path}/log/{problem}_ileancop.log')
        os.remove(problem)
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
    df.to_csv('results', index=False)

    # Extract diff
    df2 = df[(df['ipyCoP status'] != df['ileanCoP status']) | (df['Diff inference'].notna())]
    df2.to_csv("diff.csv", index=False)

    # Extract solved problems
    filtered_df = df[df['ileanCoP status'] == 'Theorem']
    problem_column = filtered_df['Problem']
    problem_column.to_csv('problems.txt', index=False, header=None, sep='\t')
