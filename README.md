# Connections

[![tests](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml)

Reinforcement learning environments for classical, intuitionistic, and modal first-order connection calculi. 

## Requirements

 - Python 3.10

## Installation

The following command will pull and install the latest commit from this repository, along with its Python dependencies

```
pip install git+https://github.com/fredrrom/connections.git 
```

## Usage

The environments closely follow the [OpenAI Gym](https://www.gymlibrary.dev/)/[Gymnasium](https://gymnasium.farama.org/) interface. Creating environment instances and interacting with them is very simple. Here is a simple connection prover implemented using the `ConnectionEnv` environment:

```python
from connections.calculi.classical import ConnectionEnv

env = ConnectionEnv("problem_path")
observation, info = env.reset()

while True:
    action = env.action_space[0]
    observation, reward, done, info = env.step(action)

    if done:
        break
```

Note that the above is equivalent (i.e., has the same proof search trace) to leanCoP version 1.0f. The same is true for ileanCoP/`IConnectionEnv` and MleanCoP/`MConnectionEnv`. These versions of leanCoP can be found in the `comparisons` directory.

`MConnectionEnv` currently supports modal logics S4, S5, D, and T each for the constant, cumulative, and varying domains. Logic and domain can be specifified during the creation of the environment as follows:

```python
env = MConnectionEnv("problem_path", logic="S5", domain="varying")
```

**NB** The environments cannot be registered as gym environments, as their state and action spaces do not inherit from `gym.spaces`. 
They are, however, designed to be used as backends for your own gym environments.

## File Formats

TPTP formatted files can be translated into the format accepted by Connections environments using the prolog code in:
- `comparisons/classical/leancop_trans_v22f` for classical logic
- `comparisons/intuitionistic/leancop_trans_v22f` for intuitionistic logic
- `comparisons/modal/leancop_mtrans_v3` for modal logics

To guarantee correct translation, please use SWI-Prolog version 8.4.3.
