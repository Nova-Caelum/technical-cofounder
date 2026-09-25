# Problem: toy-run

## Ask (verbatim)

Add a greeting to the project: a greeting.txt file holding the line "Hello, world", and a greet.py command that prints whatever greeting.txt says.

In one sentence: running `python3 greet.py` prints the greeting stored in `greeting.txt`.

## Path

bounded: two new files in an existing project, no interface anyone else depends on.

## Problem

A newcomer wants one command that prints a greeting, with the text kept in a file they can edit without touching code.

## Constraints

- HARD: standard library only.
- HARD: the greeting text lives in `greeting.txt`, not in the code.

## Assumptions Register

| Assumption | Confidence | Load-bearing | Verified via | Actual behavior |
|---|---|---|---|---|
| `python3 -m unittest tests/test_greet.py` imports `greet` from the project root | high | yes | ran it in the toy project | the root is on `sys.path` when unittest is started there |

## Out of scope

- Greetings in other languages (deferred at decide).
- Any command-line flags.

## Schema findings

none
