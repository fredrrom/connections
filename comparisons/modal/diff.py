import multiprocessing
import itertools
import subprocess
import os
import signal
import time
import pandas as pd

SAVE_LOGS = False

out_path = 'output'
fof_path = '../../../conjectures/QMLTP-v1.1/problems/'
translator_path = 'leancop_mtrans_v3/leancop_mtrans.sh'
leancop_path = 'mleancop10f_trace_v/mleancop10_arg.sh'
pycop_path = 'mleancop_trace.py'
logics = itertools.product(['S4','S5','D','T'],['constant','cumulative','varying'])
fof_filter = lambda filename : '+' in filename and '.p' in filename and filename.count('.') == 1 and 'MML' not in filename# and 'SYM009' in filename

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
    for logic,domain in logics:
        start_time = time.time()
        with open(f"{out_path}/out/{problem}_{logic}_{domain}_mpycop.out", 'w+') as f:
            with subprocess.Popen(['python',pycop_path,problem,logic,domain], stdout=f, preexec_fn=os.setsid) as process:
                try:
                    output, errors = process.communicate(timeout=1)
                    if output is not None: f.write(output)
                except subprocess.TimeoutExpired as err:
                    if err.stdout is not None:
                        f.write(err.stdout.decode("utf-8"))
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                info[f'mpyCoP {logic} {domain} time'] = time.time() - start_time

        start_time = time.time()
        prolog_domain = 'const'
        if domain == 'cumulative':
            prolog_domain = 'cumul'
        if domain  == 'varying':
            prolog_domain = 'vary'
        with open(f"{out_path}/out/{problem}_{logic}_{domain}_mleancop.out", 'w+') as f:
            with subprocess.Popen([leancop_path, problempath, logic.lower(), prolog_domain], stdout=f, preexec_fn=os.setsid) as process:
                try:
                    output, errors = process.communicate(timeout=1)
                    if output is not None: f.write(output)
                except subprocess.TimeoutExpired as err:
                    if err.stdout is not None:
                        f.write(err.stdout.decode("utf-8"))
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                info[f'mleanCoP {logic} {domain} time'] = time.time() - start_time

        with open(f'{out_path}/out/{problem}_{logic}_{domain}_mpycop.out') as file_1, open(f'{out_path}/out/{problem}_{logic}_{domain}_mleancop.out') as file_2:

            with open(f'{out_path}/log/{problem}_{logic}_{domain}_mpycop.log', "w+") as new_py:
                for line in file_1.readlines():
                    if line[:2] in ['st','Ba']:
                        continue
                    new_py.write(line)

            skip_count = 0
            with open(f'{out_path}/log/{problem}_{logic}_{domain}_mleancop.log', "w+") as new_lean:
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

        with open(f'{out_path}/log/{problem}_{logic}_{domain}_mpycop.log', "r") as file_1, open(f'{out_path}/log/{problem}_{logic}_{domain}_mleancop.log', "r") as file_2:
            lines_1, lines_2 = file_1.readlines(), file_2.readlines()
            ipy_status, ilean_status = False, False
            if lines_1:
                ipy_status = 'Theorem' in lines_1[-1] and not 'Non-Theorem' in lines_1[-1]
                lines_1 = lines_1[:-1]
            if lines_2:
                ilean_status = 'Theorem' in lines_2[-1]
                lines_2 = lines_2[:-2]
            info[f'mpyCoP {logic} {domain} status'] = 'Theorem' if ipy_status else 'Timeout'
            info[f'mleanCoP {logic} {domain} status'] = 'Theorem' if ilean_status else 'Timeout'
            info[f'mpyCoP {logic} {domain} inferences'] = len(lines_1)
            info[f'mleanCoP {logic} {domain} inferences'] = len(lines_2)
            info[f'Diff inference {logic} {domain}'] = None
            for i, (line_py, line_lean) in enumerate(zip(lines_1, lines_2)):
                if line_py[:2] != line_lean[:2]:
                    info[f'Diff inference {logic} {domain}'] = i + 1
                    break
        if not SAVE_LOGS:
            os.remove(f'{out_path}/out/{problem}_{logic}_{domain}_mpycop.out')
            os.remove(f'{out_path}/out/{problem}_{logic}_{domain}_mleancop.out')
            os.remove(f'{out_path}/log/{problem}_{logic}_{domain}_mpycop.log')
            os.remove(f'{out_path}/log/{problem}_{logic}_{domain}_mleancop.log')
    if not SAVE_LOGS:
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

    for logic,domain in logics:
        # Extract diff
        df2 = df[(df[f'mpyCoP {logic} {domain} status'] != df[f'mleanCoP {logic} {domain} status']) | df[f'Diff inference {logic} {domain}'].notna()].filter(regex=f'{logic} {domain}|Problem').dropna()
        df2.to_csv(f'diff_{logic}_{domain}.csv', index=False)

        filtered_df = df[df[f'mleanCoP {logic} {domain} status'] == 'Theorem']
        problem_column = filtered_df['Problem']
        problem_column.to_csv(f'problems_{logic}_{domain}.txt', index=False, header=None, sep='\t')
