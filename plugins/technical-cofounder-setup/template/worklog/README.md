# worklog/

The shared memory across sessions and agents in this project.

- **`entries/<timestamp>-<slug>.md`** — one file per entry, and the record. Each
  carries frontmatter (`date`, `author`, `summary`, `tags`) and the entry's detail
  below it. Open them in any editor. The team's `worklog_append` tool writes
  them; when Hyperspace Engine holds the worklog, the engine's store is the
  database and mirrors every entry into this same folder as a file, so the folder
  reads the same either way.
- **The task console's Worklog tab** shows the same entries as a table you can
  filter and sort.

The SessionStart hook (`hooks/session-preload.sh`) reads the 3 most recent
entries and adds them to context at the start of every session, so an
agent picks up where the last one left off without you having to repeat
yourself.

If you took the Obsidian view at setup, `worklog.base` beside this file is a live
table over every entry — see [`../OBSIDIAN.md`](../OBSIDIAN.md), which also covers
the two Obsidian Sync settings that stop `.base` files and community plugins from
travelling between your devices.
