# Connections

[![tests](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml)
[![License: MIT](https://img.shields.io/github/license/fredrrom/connections)](https://github.com/fredrrom/connections/blob/main/LICENSE)

Reinforcement learning environments for classical, intuitionistic, and modal first-order connection calculi in Python. 

## Requirements

 - Python 3.10 or later
 - Git
 - SWI Prolog 8.4.3 (For TPTP/QMLTP translation and to run pyCoP provers)

## Installation

### Reinforcement Learning Environments

To begin using the reinforcement learning environments, simply install the `connections` Python package using the folllowing command:

```
pip install git+https://github.com/fredrrom/connections.git 
```

### Conjectures and pyCoP provers

Each `connections` environment is initialized with a first-order conjecture as input. These conjectures are read in a custom cnf format. 

To translate TPTP/QMLTP formated files or run the standalone pyCoP provers, either clone the repository:

```
git clone https://github.com/fredrrom/connections.git
```

or download the repository [ZIP](https://github.com/fredrrom/connections/archive/refs/heads/main.zip).

## Getting Started

The environments closely follow the [OpenAI Gym](https://www.gymlibrary.dev/)/[Gymnasium](https://gymnasium.farama.org/) interface. Here is a simple connection prover implemented using the `ConnectionEnv` environment:

```python
from connections.calculi.classical import ConnectionEnv

env = ConnectionEnv("problem_path")
observation = env.reset()

while True:
    action = env.action_space[0]
    observation, reward, done, info = env.step(action)

    if done:
        break
```

`MConnectionEnv` currently supports modal logics S4, S5, D, and T each for the constant, cumulative, and varying domains. Logic and domain can be specifified during the creation of the environment as follows:

```python
env = MConnectionEnv("problem_path", logic="S5", domain="varying")
```

**NB** The environments cannot be registered as gym environments, as their state and action spaces do not inherit from `gym.spaces`. 
They are, however, designed to be used as backends for your own gym environments.

## A Worked Example
Consider double-negation elimination, that $p$ is equivalent to $\lnot \lnot p$. This is a theorem in classical logic, and is saved in the file `tests/cnf_problems/SYN001+1.p`

That file contains 5 clauses, which are found by means of Definition 3 in Otten's "Restricting Backtracking in Connection Calculi". 

Running the following code (from inside the connections directory):
```python
from connections.calculi.classical import ConnectionEnv

env = ConnectionEnv("tests/cnf_problems/SYN001+1.p")
observation = env.reset()

while True:
    action = env.action_space[0]
    observation, reward, done, info = env.step(action)
    if done:
        print(env.state.proof_sequence, "\n")
        print(info)
        break
```

should print 
```
[st0: [p_defini(1), p_defini(2)], ex0: p_defini(1) -> [-p_defini(1), p], ex1: p -> [-p_defini(1), -p], re0: -p_defini(1) <- p_defini(1), ex0: p_defini(2) -> [-p_defini(2), p], ex0: p -> [-p_defini(2), -p], re0: -p_defini(2) <- p_defini(2)]

{'status': 'Theorem'}
```
The latter line tells us that this is a theorem, i.e. that the formula is valid. The former line gives us the proof sequence reached at the end, from which one can reconstruct a proof tree or tableau. 

## TPTP/QMLTP Translation

To translate TPTP/QMLTP formatted files into the `connections` format, run the following command

```
translation/<logic>/translate.sh <file>
```

where `<file>` is the name of the problem file in TPTP/QMLTP syntax and `<logic>` is one of `classical`, `intuitionistic`, and `modal` depending on the target proof logic.

To guarantee correct translation, please use SWI-Prolog version 8.4.3 and ensure that the `PROLOG_PATH` and `TPTP` variables in `translation/<logic>/translate.sh` are set to your SWI Prolog installation location and TPTP/QMLTP directory location, respectively.

## The pyCoP, ipyCoP and mpyCoP Connection Provers

`pycop.py` contains the standalone provers pyCoP, ipyCoP, and mpyCoP for classical, intuitionistic, and modal logics, respectively.

The provers can be invoked (at the top level directory of this repository) with the following command

```
python pycop.py <file> [logic] [domain]
```

where `<file>` is the path to the problem file in TPTP/QMLTP syntax, the optional argument `[logic]` is one of `classical` (default), `intuitionistic`, `D`, `T`, `S4`, or `S5`, and the optional argument `[domain]` is one of `constant` (default), `cumulative`, and `varying`. Note that the value of `[domain]` is inconsequential if `[logic]` is  `classical` or `intuitionistic`. If the formula in `<file>` is valid for the logic `[logic]` (with `[domain]` domains if logic is modal), then the prover reports `Theorem`.

These connection provers are equivalent to version 1.0f of the leanCoP, ileanCoP and MleanCoP provers for classical, intuitionistic and modal logic, respectively, which can be found in the `comparisons` directory.
