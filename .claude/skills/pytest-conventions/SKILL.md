---
name: pytest-conventions
description: >-
  pytest mastery distilled from the official docs: fixture design and conftest
  architecture, parametrized table-driven tests, markers, assertion patterns,
  pytest.raises, configuration, and the plugin ecosystem (pytest-asyncio,
  hypothesis, coverage). Use this skill whenever writing, organizing, or
  debugging Python tests — new test files, fixture design, "how do I test
  this", flaky or slow suites, TDD red-green loops, conftest questions, or
  configuring pytest in pyproject.toml — even if the user just says "add
  tests" or "make this testable". Pairs with modern-python-conventions
  (language) and fastapi-conventions (route testing).
---

# pytest Conventions

Assume pytest 8.x, config in pyproject.toml, mypy-strict test code (tests are
code; they get types too).

## Core stance

1. **Tests specify behavior, not implementation.** Name them as sentences
   about the system: `test_registry_inferred_requires_nonzero_flags`, not
   `test_resolver_2`. If renaming a private function breaks tests, they were
   testing the wrong thing.
2. **Arrange–Act–Assert, visibly.** Three blocks, blank-line separated, one
   logical assertion per test (several `assert` lines about one outcome is
   fine; two *behaviors* is two tests).
3. **The pyramid is real.** Bulk of tests hit pure domain functions (fast,
   no IO); a thinner ring exercises adapters against recorded fixtures; a few
   end-to-end tests prove the wiring. Slow suites die of neglect.
4. **Determinism is non-negotiable.** Inject clocks, seed or inject
   randomness, no live network ever, no sleeps — a flaky test is a broken
   test, fix or delete it same day.
5. **Fixtures are dependency injection, not a junk drawer.** Each fixture
   provides one thing, named for what it *is* (`client`, `tmp_db`,
   `seeded_jobs`), composed via arguments. Deep implicit fixture chains that
   require archaeology are a design smell.
6. **Fakes over mocks.** A `FakeJobRepo` implementing the real Protocol
   survives refactors and fails loudly; `MagicMock` accepts every typo
   silently. `unittest.mock` is for the rare "assert this boundary was
   called" case, always `autospec`/`spec`ced.

## Fast rules

| Situation | Rule |
|---|---|
| Same logic, many cases | `@pytest.mark.parametrize` table with `ids` — never copy-paste tests |
| Setup needs teardown | yield fixture, cleanup after `yield` |
| Test needs files | `tmp_path` (never write to the repo or /tmp yourself) |
| Test needs env/attr change | `monkeypatch` (auto-undone) — not manual save/restore |
| Expecting an exception | `pytest.raises(ExcType, match=r"...")` — always the narrowest type |
| Floats | `pytest.approx`, never `==` |
| Known-broken case | `xfail(strict=True)` with reason — not skip, not commented out |
| Platform/env conditional | `skipif` with a reason string |
| Shared setup across files | `conftest.py` at the lowest common directory |
| Async test | pytest-asyncio, `asyncio_mode = "auto"`, one mode repo-wide |
| Print-debugging a test | `pytest -x -k name --lf -s` and read the introspected assert first |

## Layout

```
backend/tests/
├── conftest.py          # app-wide fixtures only (client, tmp_db, settings)
├── fixtures/            # recorded real data: greenhouse/, registries/, ...
├── unit/                # mirrors src/ package structure; pure, fast
├── adapters/            # fixture-driven adapter tests
└── integration/         # few; real DB file, real migrations
```

Test files mirror source modules (`normalize.py` → `test_normalize.py`);
finding the tests for a module must never require search.

## When to open a reference file

- Designing fixtures, conftest layering, factories, built-ins
  (`tmp_path`/`monkeypatch`/`capsys`) → **references/fixtures.md**
- Table-driven tests, ids, indirect parametrization, markers, skip/xfail →
  **references/parametrize-and-markers.md**
- Assertion patterns, `raises`, `approx`, warnings, failure-output reading →
  **references/assertions-and-failures.md**
- pyproject config, CLI workflow, pytest-asyncio, hypothesis, coverage,
  xdist → **references/config-and-plugins.md**

Read fixtures.md before creating any conftest; it prevents the fixture-soup
failure mode.
