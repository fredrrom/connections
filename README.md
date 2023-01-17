# CoPs

[![tests](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/CoPs/actions/workflows/python-app.yml)

Reinforcement learning environments for the classical and intuitionistic first-order connection calculi. 

## Requirements

 - Python 3.10

## Installation

The following command will pull and install the latest commit from this repository, along with its Python dependencies

```
pip install git+https://github.com/fredrrom/cops.git 
```

## Usage

The environments closely follow the [OpenAI Gym](https://www.gymlibrary.dev/) interface. Creating environment instances and interacting with them is very simple. Here is leanCoP implemented using the `ConnectionEnv` environment:

```python
from cops.calculi.classical import ConnectionEnv

env = ConnectionEnv("path_to_CNF_formatted_file")
observation, info = env.reset()

while True:
    action = env.action_space[0]
    observation, reward, done, info = env.step(action)

    if done:
        break
```

Note that leanCoP is equivalent to an agent always choosing the first available action in the `ConnectionEnv` environment's action space. The same is true for ileanCoP and the `IConnectionEnv` environment.

Also note that the environments cannot be registered as gym environments, as their state and action spaces do not inherit from `gym.spaces`. 
They are, however, designed to be used as backends for your own gym environments. 
An example of training an [RLlib](https://docs.ray.io/en/latest/rllib/index.html) PPO agent on a gym environment using the `ConnectionEnv` environment as a backend is given in [RNNAutoencoderCoP](https://github.com/fredrrom/RNNAutoencoderCoP).

TPTP formatted files can be translated to the enivronments' accepted format using the prolog code in `comparisons/classical/leancop_trans_v22f`
