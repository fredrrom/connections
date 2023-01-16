# CoPs

![Tests](https://github.com/fredrrom/mlatp/blob/master/.github/workflows/tests.yml/badge.svg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Reinforcement learning environments for the classical and intuitionistic first-order connection calculi. 

## Installation

To install the environments, use `pip install cops`. The following command will pull and install the latest commit from this repository, along with its Python dependencies

```
pip install git+https://github.com/fredrrom/cops.git 
```

Note that currently only Python 3.10 is supported.

## Usage

The environments follow the [OpenAI Gym](https://www.gymlibrary.dev/) interface, but cannot be registered as gym environments as their state and action spaces do not inherit from `gym.spaces`. Creating environment instances and interacting with them is very simple- here's leanCoP implemented using the `ConnectionEnv` environment:

```python
from cops.calculi.classical_connection import ConnectionEnv

env = ConnectionEnv("path_to_CNF_file")
observation, info = env.reset()

while True:
    action = env.action_space[0]
    observation, reward, done, info = env.step(action)

    if done:
        break
```

Note that leanCoP is equivalent to an agent always choosing action 0 in the `ConnectionEnv` environment. The same is true for ileanCoP and the `IConnectionEnv` environment. 

Although the environments cannot be registered as gym eniroments directly, they can be used as backends for your own gym environments (with more well defined, non-dynamically sized, state spaces) as done in the `GraphEnv` environment in `cops.envs.graph_env.py`. An example of training a PPO agent on the `GraphEnv` environment using [RLlib](https://docs.ray.io/en/latest/rllib/index.html) is given in `experiments/graphcop.py`. The notebook also includes an explanation of the `GraphEnv` environment.

## License
[MIT](https://choosealicense.com/licenses/mit/)