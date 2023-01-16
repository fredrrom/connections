import subprocess as sp
import os
import signal
import time
import pandas as pd

def collect_metadata(directory, filename, rows):
    file = os.path.splitext(filename)[0]
    filepath = os.path.join(directory, filename)

    row = {}
    with open(filepath, 'r') as searchfile:
        for line in searchfile:
            if '% File     : ' in line:
                row['File'] = (line[13:line.find(' :', 13)])
            if '% Problem  : ' in line:
                row['Problem'] = line[13:line.find('\n', 13)]
            if '% Status   : ' in line:
                row['Status'] = line[13:line.find('\n', 13)]
    rows[file] = row

def run(cmd, prover, directory, filename, rows, time_limit):
    file = os.path.splitext(filename)[0]
    sh = True
    if cmd[0] == 'python3':
        cmd.append(os.path.join(directory, filename))
        sh=False
    prover_status = prover + ' Status (' + str(time_limit) + "s)"
    prover_time = prover + ' Time (' + str(time_limit) + "s)"
    start_time = time.time()
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, shell=sh, \
        preexec_fn=os.setsid) as process:
        try:
            output, errors = process.communicate(timeout=time_limit)
            end_time = time.time() - start_time
            if errors:
                print(output, errors)
                print("File incorrectly formated: " + file)
            else:
                if 'Non-Theorem' in output.splitlines()[-1]:
                    rows[file][prover_status] = 'Non-Theorem'
                elif 'Depth limit' in output.splitlines()[-1]:
                    rows[file][prover_status] = 'Stack'
                else:
                    rows[file][prover_status] = 'Theorem'
                print(output)
        except sp.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            end_time = time.time() - start_time
            rows[file][prover_status] = 'Timeout'
    rows[file][prover_time] = end_time

def run_win(cmd, prover, directory, filename, rows, time_limit):
    file = os.path.splitext(filename)[0]
    sh = True
    if cmd[0] == 'python':
        cmd.append("/".join((directory, filename)))
        sh=False
    prover_status = prover + ' Status (' + str(time_limit) + "s)"
    prover_time = prover + ' Time (' + str(time_limit) + "s)"
    start_time = time.time()
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, shell=sh, \
        creationflags=sp.CREATE_NEW_PROCESS_GROUP) as process:
        try:
            output, errors = process.communicate(timeout=time_limit)
            end_time = time.time() - start_time
            if errors:
                print(output, errors)
                print("File incorrectly formated: " + file)
            else:
                if 'Non-Theorem' in output.splitlines()[-1]:
                    rows[file][prover_status] = 'Timeout'
                else:
                    rows[file][prover_status] = 'Theorem'
        except sp.TimeoutExpired:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.kill()
            end_time = time.time() - start_time
            rows[file][prover_status] = 'Timeout'
    rows[file][prover_time] = end_time

def run_max_inf(cmd, prover, directory, filename, time_limit):
    file = os.path.splitext(filename)[0]
    cmd.append(os.path.join(directory, filename))

    start_time = time.time()
    result = sp.run(cmd, shell=False, stdout=sp.PIPE, text=True)
    end_time = time.time() - start_time
    if result.stderr:
        #print("File incorrectly formated: " + file)
        return (file,'Error',0)
    else:
        #print(file)
        if 'Non-Theorem' in result.stdout.splitlines()[-1]:
            prover_status = 'Timeout'
        elif 'No proof found' in result.stdout.splitlines()[-1]:
            prover_status = 'Timeout'
        else:
            prover_status = 'Theorem'
    return (file,prover_status,end_time)

def run_parallel(cmd, prover, directory, filename, time_limit):
    file = os.path.splitext(filename)[0]
    cmd.append(os.path.join(directory, filename))
    start_time = time.time()
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, shell=True, \
        creationflags=sp.CREATE_NEW_PROCESS_GROUP) as process:
        try:
            output, errors = process.communicate(timeout=time_limit)
            end_time = time.time() - start_time
            if errors:
                #print("File incorrectly formated: " + file)
                return (file,'Error',0)
            else:
                if 'Non-Theorem' in output.splitlines()[-1]:
                    prover_status = 'Timeout'
                else:
                    prover_status = 'Theorem'
        except sp.TimeoutExpired:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.kill()
            end_time = time.time() - start_time
            prover_status = 'Timeout'
    return (file,prover_status,end_time)


def run_parallel_unix(cmd, prover, directory, filename, time_limit):
    file = os.path.splitext(filename)[0]
    cmd.append(os.path.join(directory, filename))
    #print(cmd)
    start_time = time.time()
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, \
        preexec_fn=os.setsid) as process:
        try:
            output, errors = process.communicate(timeout=time_limit)
            end_time = time.time() - start_time
            if errors:
                #print("File incorrectly formated: " + file)
                #print(errors)
                return (file,'Error',0)
            else:
                #print(output)
                if 'Non-Theorem' in output.splitlines()[-1]:
                    prover_status = 'Timeout'
                elif 'No proof found' in output.splitlines()[-1]:
                    prover_status = 'Timeout'
                else:
                    prover_status = 'Theorem'
        except sp.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            end_time = time.time() - start_time
            prover_status = 'Timeout'
    return (file,prover_status,end_time)


def remove_equality_files():
    eq_files = "TPTP-v3.3.0_ALL_eq_cnf"
    noeq_files = "TPTP-v3.3.0_ALL_noeq_cnf"
    if not os.path.exists(noeq_files):
        os.makedirs(noeq_files)
    for folder in os.listdir(eq_files):
        noeq_folder = os.path.join(noeq_files,folder)
        eq_folder = os.path.join(eq_files,folder)
        if not os.path.exists(noeq_folder):
            os.makedirs(noeq_folder)
        for file in os.listdir(eq_folder):
            oldpath = os.path.join(eq_folder,file)
            with open(oldpath) as f:
                if '=' not in f.read():
                    newpath = os.path.join(noeq_folder,file)
                    os.popen('cp ' + oldpath + ' ' + newpath)
