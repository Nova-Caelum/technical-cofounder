# PRD: toy-run

## Acceptance set

- T1 file_state: greeting.txt holds the greeting Hello, world
- T2 command_check: WHOLE-PATH: running greet.py prints the line stored in greeting.txt (whole path)

## What we are building

One command, `python3 greet.py`, that prints the greeting kept in `greeting.txt`. Option A: a text file plus a reader script. HARD: standard library only. HARD: the text lives in the file.

## Components

- **greeting file**: holds the text. Passes T1.
- **greet command**: reads and prints it. Passes T2. Kept by test; cites principle stdlib-only.

## Principles

- **stdlib-only**: ship with the Python standard library and nothing else. Cited by greet command.

## v2 recap

- **localized greetings**: greetings in other languages. Reopen when: a test asks for a second language.

v1 set: greeting file, greet command

## Decisions inherited

| Decision | Source | Date |
|---|---|---|
| Option A | 02_decide/Decision.md | toy |

## Not claimed

- No flags, no languages, no packaging.

## Closeout: rules enforced only by prose

None found. Every rule above names its mechanism.
