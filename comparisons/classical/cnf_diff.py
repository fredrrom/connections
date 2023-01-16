import os

from cops.calculi.classical import *

smallest_size = float('inf')
smallest_name = None
out_path = 'output'
cnf_path = '../../conjectures/TPTP-v3.3.0_SYN_noeq_cnf/'
leancop_path = 'leancop10f_trace/leancop10.sh'

with open(f'{out_path}/cnf_diff.log', "w+") as diff_file:
    for problem in os.listdir(cnf_path):
        print(problem)
        env = ConnectionEnv(cnf_path + problem)
        observation = env.reset()
        with open(f'{out_path}/pycop.out', 'w+') as file:
            for i in range(5000):
                action = env.action_space[0]
                file.write(str(action) + '\n')
                observation, reward, done, info = env.step(action)
                if done:
                    print(info)
                    break

        filepath = cnf_path + problem
        import subprocess as sp
        import signal

        with sp.Popen([leancop_path, filepath], stdout=sp.PIPE, stderr=sp.PIPE, text=True,
                      preexec_fn=os.setsid) as process:
            with open(f'{out_path}/leancop.out', 'w+') as file:
                try:
                    output, errors = process.communicate(timeout=1)
                    file.write(output)
                except sp.TimeoutExpired:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)

        with open(f'{out_path}/pycop.out') as file_1, open(f'{out_path}/leancop.out') as file_2:

            with open(f'{out_path}/pycop.log', "w+") as new_py:
                for line in file_1.readlines():
                    if ("re" in line) or ("ex" in line):
                        new_py.write(line)

            with open(f'{out_path}/leancop.log', "w+") as new_lean:
                for line in file_2.readlines():
                    if (("reduction(" in line) or ("extension(" in line)) and ("!" not in line):
                        new_lean.write(line)

        with open(f'{out_path}/pycop.log', "w+") as file_1, open(f'{out_path}/leancop.log', "w+") as file_2:
            lines_1 = file_1.readlines()
            lines_2 = file_2.readlines()
            if len(lines_1) != len(lines_2):
                print(f'py: {lines_1}')
                print(f'lean: {lines_2}')
                diff_file.write(f"{problem} Unequal number of steps {len(lines_1)} {len(lines_2)}" + '\n')
            for i, (line_py, line_lean) in enumerate(zip(lines_1, lines_2)):
                split = line_py.split(':')
                if split[0][0] != line_lean[0] or split[1][1] != line_lean[10]:
                    if smallest_size > len(env.matrix.clauses):
                        smallest_size = len(env.matrix.clauses)
                        smallest_name = problem
                    diff_file.write(f"{problem} Diff at line: {i + 1}" + '\n')
                    break
    diff_file.write(f"Smallest problem: {smallest_name}")
