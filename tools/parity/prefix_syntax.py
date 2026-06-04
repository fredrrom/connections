from __future__ import annotations

from connections.core.formula import Function, Prefix, Term, Variable


def parse_prefix(text: str, *, variables: dict[str, Variable] | None = None) -> Prefix:
    stripped = text.strip()
    if stripped.startswith("-"):
        stripped = stripped[1:].strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        raise ValueError(f"prefix must be written as a list: {text!r}")
    body = stripped[1:-1].strip()
    if not body:
        return Prefix()
    var_cache = {} if variables is None else variables
    return Prefix(tuple(_parse_term(part, var_cache) for part in _split_terms(body)))


def parse_term(text: str, *, variables: dict[str, Variable] | None = None) -> Term:
    return _parse_term(text, {} if variables is None else variables)


def _parse_term(text: str, variables: dict[str, Variable]) -> Term:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty prefix term")
    open_paren = _top_level_open_paren(stripped)
    if open_paren is None:
        if _is_variable_symbol(stripped):
            return variables.setdefault(stripped, Variable(stripped))
        return Function(stripped)
    if not stripped.endswith(")"):
        raise ValueError(f"malformed prefix term: {text!r}")
    symbol = stripped[:open_paren].strip()
    args_text = stripped[open_paren + 1 : -1].strip()
    args = () if not args_text else tuple(
        _parse_term(part, variables) for part in _split_terms(args_text)
    )
    return Function(symbol, args)


def _split_terms(text: str) -> tuple[str, ...]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(f"unbalanced prefix term list: {text!r}")
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        raise ValueError(f"unbalanced prefix term list: {text!r}")
    parts.append(text[start:].strip())
    return tuple(parts)


def _top_level_open_paren(text: str) -> int | None:
    for index, char in enumerate(text):
        if char == "(":
            return index
    return None


def _is_variable_symbol(symbol: str) -> bool:
    return symbol[0].isupper() or symbol[0] == "_"


__all__ = [
    "parse_prefix",
    "parse_term",
]
