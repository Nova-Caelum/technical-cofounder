# Decision: toy-run

Tests: T1 greeting.txt holds the greeting · T2 WHOLE-PATH: greet.py prints greeting.txt

## Options

### Option A: text file plus a reader script
T1 passes · T2 passes with greet command. Standard library only: satisfies. Text in a file: satisfies.

### ~~Option B: greeting hard-coded in greet.py~~
Struck: violates "the greeting text lives in greeting.txt, not in the code".

## Decision

Option A. It passes T1 and T2 and satisfies both HARD constraints; B violates the second. Decided by: the driver, the user absent.

## Architecture

### greeting file
- **Does:** holds the greeting text.
- **Used by:** greet command reads it.
- **Depends on:** nothing.
- **Passes:** T1

### greet command
- **Does:** prints the contents of greeting.txt.
- **Used by:** a person running `python3 greet.py`.
- **Depends on:** greeting file.
- **Passes:** T2

### localized greetings — deferred → Deferred.md

### Data flow
`python3 greet.py` → greet command reads greeting file → prints the line (T2 walks this).

## Mapping

| Component | Tests | Principles | Status |
|---|---|---|---|
| greeting file | T1 | | kept-by-test |
| greet command | T2 | stdlib-only | kept-by-test |
| localized greetings | | | deferred |

## Cuts

1 deferred, 0 kept by principle; see Deferred.md.
