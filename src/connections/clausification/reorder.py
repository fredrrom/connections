from __future__ import annotations

from typing import TypeVar

ItemT = TypeVar("ItemT")


def mreorder_items(items: list[ItemT], rounds: int) -> list[ItemT]:
    result = list(items)
    for _ in range(rounds):
        size = len(result)
        split = size // 3
        if split == 0:
            return result
        first = result[:split]
        remainder = result[split:]
        middle = remainder[:-split]
        last = remainder[-split:]
        result = _mreorder2_items(last, first, middle)
    return result


def _mreorder2_items(
    first: list[ItemT], second: list[ItemT], third: list[ItemT]
) -> list[ItemT]:
    output: list[ItemT] = []
    for i in range(len(first)):
        output.append(first[i])
        output.append(second[i])
        output.append(third[i])
    output.extend(third[len(first) :])
    return output


__all__ = ["mreorder_items"]
