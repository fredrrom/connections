import multiprocessing
import subprocess
import os
import signal
import time
import pandas as pd

SAVE_LOGS = True

out_path = 'output'
fof_path = '../../../conjectures/TPTP-v6.4.0/Problems/'
translator_path = 'leancop_trans_v22fb/leancop_trans.sh'
leancop_path = 'leancop10f_trace/leancop10.sh'
pycop_path = 'leancop_trace.py'
fof_filter = lambda filename : '+' in filename and '.p' in filename and filename.count('.') == 1 and filename[:3] in ['SET']#'SET061+1.p' in filename# #'CSR103' in filename \
    #and filename[:3] in ['SET']#, 'GEO', 'NUM', 'SEU', 'SWV', 'SWW', 'SYN']

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
                if line[:2] in ['st','Ba']:
                    continue
                new_py.write(line)

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
            ilean_status = 'Theorem' in lines_2[-1] or 'Unsatisfiable' in lines_2[-1]
            lines_2 = lines_2[:-3]
        info['pyCoP status'] = 'Theorem' if ipy_status else 'Timeout'
        info['leanCoP status'] = 'Theorem' if ilean_status else 'Timeout'
        info['pyCoP inferences'] = len(lines_1)
        info['leanCoP inferences'] = len(lines_2)
        info['Diff inference'] = None
        for i, (line_py, line_lean) in enumerate(zip(lines_1, lines_2)):
            if line_py[:2] != line_lean[:2]:
                info['Diff inference'] = i + 1
                break
    if not SAVE_LOGS:
        os.remove(problem)
        os.remove(f'{out_path}/out/{problem}_leancop.out')
        os.remove(f'{out_path}/out/{problem}_pycop.out')
        os.remove(f'{out_path}/log/{problem}_pycop.log')
        os.remove(f'{out_path}/log/{problem}_leancop.log')
    return info


if __name__ == '__main__':
    num_processes = multiprocessing.cpu_count() - 1
    results = []
    for folder in os.listdir(fof_path):
        if not os.path.isdir(os.path.join(fof_path,folder)):
            continue
        problems = [os.path.join(fof_path,folder,filename) for filename in os.listdir(fof_path+folder) if fof_filter(filename)]
        with multiprocessing.Pool(processes=num_processes) as pool:
            results.extend(pool.map(run_theorem_prover, problems))
    results = filter(None,results)
    df = pd.DataFrame(results) 
    df.to_csv("results.csv", index=False)

    # Extract solved problems
    filtered_df = df[df['leanCoP status'] == 'Theorem']  
    problem_column = filtered_df['Problem']
    problem_column.to_csv('problems.txt', index=False, header=None, sep='\t')
    
    # Extract diff problems
    df2 = df[(df['pyCoP status'] != df['leanCoP status']) | (df['Diff inference'].notna())]
    df2.to_csv("diff.csv", index=False)

    """
    df.reset_index(inplace=True)  # Reset the index of the DataFrame
    count_pycop_1 = df[df['pyCoP status'] == 'Theorem'][df['pyCoP time'] < 1].groupby(df['Problem'].str[:3]).size()
    count_leancop_1 = df[df['leanCoP status'] == 'Theorem'][df['leanCoP time'] < 1].groupby(df['Problem'].str[:3]).size()
    count_pycop_10 = df[df['pyCoP status'] == 'Theorem'][df['pyCoP time'] < 10].groupby(df['Problem'].str[:3]).size()
    count_leancop_10 = df[df['leanCoP status'] == 'Theorem'][df['leanCoP time'] < 10].groupby(df['Problem'].str[:3]).size()

    # Create a DataFrame with the first three letters of problem as the index
    df3 = pd.DataFrame({'pyCoP 1s': count_pycop_1, 'leanCoP 1s': count_leancop_1, 'pyCoP 10s': count_pycop_10, 'leanCoP 10s': count_leancop_10}).reset_index()
    df3.columns = ['Domain', 'pyCoP 1s', 'leanCoP 1s', 'pyCoP 10s', 'leanCoP 10s']
    df3.to_csv("count.csv", index=False)

    print(df3.drop('Domain', axis=1).sum())
    """
