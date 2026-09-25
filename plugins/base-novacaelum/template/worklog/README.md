# worklog/

The shared memory across sessions and agents in this project.

- **`entries/<timestamp>-<slug>.md`** — one file per entry, written by the
  `worklog_append` tool on this plugin's local MCP server. Each entry
  carries frontmatter (`date`, `author`, `summary`, `tags`) and is the
  canonical record.
- **`worklog.csv`** — regenerated from every entry on each append (columns:
  `date,author,summary,tags,file`). A derived index for quick scanning —
  never edit it by hand, and if it and `entries/` ever disagree, `entries/`
  is right.

The SessionStart hook (`hooks/session-preload.sh`) reads the 3 most recent
entries and adds them to context at the start of every session, so an
agent picks up where the last one left off without you having to repeat
yourself.
