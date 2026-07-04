---
name: modern-python-conventions
description: >-
  Opinionated conventions for writing idiomatic, modern Python (3.11–3.13):
  typing discipline, Protocol-based design, dataclasses, async patterns,
  stdlib-first solutions, and pitfall avoidance. Use this skill whenever
  writing, reviewing, or refactoring Python code — backend services, FastAPI
  apps, CLIs, scripts, data pipelines, or tests — even if the user doesn't ask
  for "modern" or "idiomatic" style. Trigger on any Python coding task,
  Python code review, "make this pythonic", type-hint questions, asyncio
  work, dataclass/Protocol design, or when choosing between stdlib and a
  third-party dependency.
---

# Modern Python Conventions

Write Python as if mypy --strict, ruff, and a senior reviewer are always
watching. Target 3.11+ unless told otherwise; prefer 3.12 syntax where noted.

## Core stance

1. **Types everywhere.** Every function signature fully annotated, including
   tests and `-> None`. Types are the design tool, not decoration.
2. **Protocols over inheritance.** Depend on structural interfaces
   (`typing.Protocol`), inject implementations. Subclassing is for genuine
   is-a with shared behavior, which is rare.
3. **Dataclasses for data, plain classes for behavior.** `@dataclass(frozen=True, slots=True)`
   is the default record. Reach for a plain class only when identity or rich
   behavior dominates.
4. **stdlib first.** `pathlib`, `itertools`, `functools`, `collections`,
   `datetime` (aware, UTC), `sqlite3`, `json`, `re`, `enum` cover more than
   people think. Every dependency must earn its install.
5. **Pure core, effects at the edge.** Business logic as pure functions on
   immutable data; IO (network, disk, DB, clock, randomness) injected and kept
   in adapters. This is what makes TDD cheap.
6. **Errors are part of the API.** Raise specific exceptions; never bare
   `except:`; never silence with `pass`. `Optional` return means "absence is
   normal", exception means "something went wrong" — don't mix the two.

## Fast idiom table

| Instead of | Write |
|---|---|
| `os.path.join(a, b)` | `Path(a) / b` |
| `open(f)` then manual close | `with path.open() as fh:` (or `path.read_text()`) |
| `dict.has_key` / `k in d.keys()` | `k in d` |
| `type(x) == T` | `isinstance(x, T)` (or `match`) |
| `if len(xs) > 0:` | `if xs:` |
| index loops `for i in range(len(xs))` | `for x in xs:` / `enumerate` / `zip(strict=True)` |
| `%` or `.format()` | f-strings (incl. `f"{x=}"` for debug) |
| mutable default `def f(x=[])` | `def f(x: list[int] | None = None)` then `x = x or []` |
| `datetime.utcnow()` | `datetime.now(tz=UTC)` — utcnow is naive and deprecated |
| `assert` for runtime validation | explicit `raise ValueError(...)` (asserts vanish under `-O`) |
| `from module import *` | explicit imports |
| string enums as bare `str` | `enum.StrEnum` |
| `Union[X, None]` / `Optional[X]` | `X | None` |
| `List[int]`, `Dict[str, int]` | `list[int]`, `dict[str, int]` |

## Structural conventions

- **Modules small and cohesive**; no `utils.py` grab-bags. Name modules after
  the concept (`normalize.py`, `ports.py`, `keywords.py`).
- **`if __name__ == "__main__":`** delegates to a `main() -> int` for
  testability; scripts exit via `raise SystemExit(main())`.
- **Config**: one frozen `Settings` dataclass built from env at startup;
  nothing else reads `os.environ`.
- **Logging**: module-level `logger = logging.getLogger(__name__)`; key=value
  structured messages; never `print` in library code.
- **Tooling assumption**: uv for env/deps, ruff (lint+format), mypy strict,
  pytest. `pyproject.toml` is the single config home.

## When to open a reference file

- Designing interfaces, generics, `Protocol`, `TypedDict`-vs-dataclass, 3.12
  type-parameter syntax → **references/typing.md**
- Modeling records, enums, validation, immutability, `__post_init__` →
  **references/data-classes.md**
- Anything `async` — TaskGroup, cancellation, timeouts, mixing sync/async,
  httpx patterns → **references/async.md**
- Reaching for a dependency, or manipulating paths/dates/iterables/regexes/
  sqlite → **references/stdlib.md**
- Exception design, `ExceptionGroup`, context managers, `contextlib`,
  resource cleanup → **references/errors-and-context.md**
- Reviewing code or debugging weirdness (late-binding closures, aliasing,
  float traps, GIL/concurrency myths) → **references/pitfalls.md**

Read the matching file *before* writing code in that area; skim the pitfalls
file before any code review.
