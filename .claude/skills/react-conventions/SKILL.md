---
name: react-conventions
description: >-
  Modern React (18/19) reference and conventions distilled from react.dev:
  every hook and when NOT to use it, effect discipline, state modeling,
  memo/Suspense/context APIs, and TypeScript-strict component patterns. Use
  this skill whenever writing, reviewing, or refactoring React code — new
  components, custom hooks, state management decisions, performance work,
  "why does this re-render", useEffect bugs, React + TypeScript typing — even
  if the user doesn't mention React by name but is working in .jsx/.tsx files
  or a Vite/Next frontend.
---

# React Conventions (react.dev distilled)

Assume React 18+ with TypeScript strict and function components only. React 19
differences are flagged inline. Source domain: the react.dev reference,
distilled and opinionated — verify bleeding-edge API details against the live
docs when precision matters.

## Core stance

1. **Render is a pure function of props + state.** No side effects, no
   mutation, no reading refs during render. If render isn't pure, StrictMode's
   double-invoke will expose it — that's the feature working.
2. **Most effects shouldn't exist.** `useEffect` is for synchronizing with
   *external* systems (network, DOM APIs, subscriptions, timers) — not for
   reacting to state with more state. Deriving during render or handling in
   the event handler beats an effect ~80% of the time.
3. **State is the minimal source of truth.** Never store what you can
   compute. Duplicated/derived state in `useState` + a syncing effect is the
   single most common React bug pattern.
4. **Server state ≠ client state.** Fetched data belongs to a query library
   (TanStack Query) with caching/invalidation; `useState` + fetch-in-effect is
   the legacy pattern — it has race conditions the library already solved.
5. **Composition over configuration.** Children and small components before
   boolean-prop explosions; extract a custom hook the moment logic is shared
   or a component mixes two concerns.
6. **Keys are identity.** Stable, data-derived keys; index-as-key only for
   static never-reordering lists. Changing a key is the idiomatic way to
   *reset* a component's state.

## Fast rules

| Situation | Rule |
|---|---|
| Next state depends on previous | Updater form: `setCount(c => c + 1)` |
| State is an object/array | Replace, never mutate: `setUser({...user, name})` |
| Expensive computation from props/state | `useMemo`, not state+effect |
| Resetting a subtree on entity change | `key={entity.id}` on the subtree |
| Value needed by handlers but not render | `useRef`, not state |
| 3+ `useState` updated together | `useReducer` |
| Prop drilling >2 levels of stable data | Context (split value if it churns) |
| Fetching on mount | Query library; if raw effect, handle cleanup/races |
| Form in React 19 | Actions: `<form action={fn}>`, `useActionState` |
| A ref to a component (19) | Plain `ref` prop — `forwardRef` is legacy |

## When to open a reference file

- Any hook's exact behavior, rules-of-hooks, custom hooks, `use()` →
  **references/hooks.md**
- Writing/debugging `useEffect`, dependency arrays, cleanup, StrictMode
  double-fire, "effect runs twice/loops" → **references/effects.md**
- Modeling state, lifting, reducers, context architecture, controlled vs
  uncontrolled, forms & React 19 actions → **references/state-and-data.md**
- `memo`, `lazy`, `Suspense`, error boundaries, portals, transitions,
  performance/re-render work → **references/apis-and-performance.md**
- Typing props/refs/events/generics/children in TS →
  **references/typescript.md**

Read the matching file before writing code in that area; effects.md is the
mandatory read before touching any `useEffect`.
