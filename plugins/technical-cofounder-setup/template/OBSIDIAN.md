# Using this project in Obsidian

You said yes to the Obsidian view during setup, so this project has a `.obsidian/`
folder and a `worklog/worklog.base` table in it. This page explains what those are
and how to get the most out of them.

**You do not need any of this to use the project.** Everything here is plain text on
your disk and works in any editor. Obsidian is a nicer way to read it.

---

## 1. Markdown, in one minute

Almost every file here is a `.md` file — Markdown. It is **plain text with a few
punctuation conventions** that tools agree to render nicely:

```
# A heading          →  big heading
**important**        →  bold
- a list item        →  a bullet
[label](./file.md)   →  a link
```

That is most of it. Two consequences worth internalising:

- **Any editor can open these files.** TextEdit, Notepad, VS Code, anything. Nothing
  is locked in a proprietary format, and nothing needs Obsidian.
- **Some files start with a fenced block of `key: value` lines** between `---`
  markers. That is *frontmatter* — structured fields attached to the file. Your
  worklog entries use it for `date`, `author`, `summary` and `tags`, and that is what
  makes the table in §3 possible.

## 2. Opening this project as a vault

A **vault** is just a folder Obsidian has been pointed at. It does not move or convert
anything.

1. Install Obsidian — free, from [obsidian.md](https://obsidian.md).
2. Open it, choose **Open folder as vault**, and select this project's folder.
3. Trust the author when it asks. That prompt is about the `.obsidian/` config in this
   folder, which is ours and which enables only Obsidian's own built-in plugins.

The sidebar is now your project. The `worklog/entries/` folder is the shared memory
your agents write to, and you can read it like any other notes.

## 3. Bases — the worklog table

**Bases is one of Obsidian's built-in (core) plugins.** It turns a folder of notes into
a database view by reading their frontmatter. No installation needed; setup already
enabled it.

Open **`worklog/worklog.base`** and you get a live table of every worklog entry, with
its date, author, summary and tags as columns. Two views ship with it: *Recent* and
*All*. Click a row to open the entry.

Things worth knowing:

- **The table is a view, not the data.** The files in `worklog/entries/` are the truth.
  Deleting a row is not a thing you can do from the table.
- Add a frontmatter field to your entries and you can add it as a column. The `.base`
  file is plain YAML; it is readable and editable.

## 4. Community plugins — what they are and how to get them

Obsidian ships with **core plugins** (made by Obsidian, already present, just toggled
on or off) and supports **community plugins** (written by other people, downloaded
from inside the app).

**This project needs zero community plugins.** Everything above uses core plugins
only. But they are the main reason people like Obsidian, so:

1. **Settings → Community plugins.** The first time, you have to turn off *Restricted
   mode* — Obsidian's way of making you opt in before third-party code runs.
2. **Browse**, search, **Install**.
3. **Then enable it.** This is the step everyone misses: *install* and *enable* are two
   separate actions, and a plugin you installed but did not enable simply does nothing.
   The toggle is in the same settings pane.

Some plugins need a restart before their settings take effect. If one seems inert
after you changed something, quit and reopen Obsidian before assuming it is broken.

### Making it yours

- **Settings → Appearance → Themes → Manage** to browse community themes. This is the
  single fastest way to make Obsidian feel like your own tool rather than someone
  else's. *Minimal* and *Things* are common starting points.
- **Settings → Editor** controls readable line length, whether headings fold, and
  whether you see the Markdown source or the rendered result as you type. If Markdown
  syntax is distracting, that pane is where you turn it down.
- **Settings → Hotkeys** if you live on the keyboard. The command palette
  (`Cmd/Ctrl-P`) is worth learning first.

None of this affects the project. Themes and editor settings are yours.

## 5. Obsidian Sync, and the two traps

**Obsidian Sync is a paid, end-to-end-encrypted sync service from Obsidian itself.** It
keeps a vault consistent across your devices — laptop, desktop, phone. It is optional.
Dropbox, iCloud or git are alternatives; Sync is the one that handles Obsidian's own
config properly, which is why it is worth mentioning here.

It is a core plugin: **Settings → Core plugins → Sync** to turn it on, then sign in.

Now the two things that will quietly bite you. Both are defaults, both are one toggle,
and neither announces itself.

### Trap 1 — `worklog.base` will not sync

**Only Markdown notes sync unconditionally.** Everything else runs through *selective
sync*, and by default that covers images, audio, video and PDFs — **and nothing else.**

`worklog.base` is not a Markdown file. So on a fresh Sync setup it does not travel, and
on your second device the table is simply absent, with no error to tell you why.

**Fix:** Settings → Sync → **Selective sync** → turn on **Sync all other types.**

Do it *before* the first full sync if you can. Excluding a file type after it has
already uploaded does not remove it from the remote vault.

### Trap 2 — your plugins will not follow you

Under **Vault configuration sync**, these already sync by default: main settings,
appearance, themes and snippets, hotkeys, the active *core* plugin list and its
settings.

**Community plugins are not in that list.** You have to enable two more toggles by
hand:

- **Installed community plugin list**
- **Active community plugin list**

Without them, you set up Obsidian exactly how you like it on one machine, open the
vault on another, and none of your plugins are there — while your themes and hotkeys
*did* arrive, which makes it look like sync is working fine.

### One more thing that is not a trap but looks like one

Files and folders starting with `.` are excluded from sync automatically — **except
`.obsidian` itself**, which is deliberately included. That is why your vault config
travels at all.

---

## Where to get help

- [Obsidian Help](https://help.obsidian.md) — official docs, genuinely good
- [Obsidian Forum](https://forum.obsidian.md) — for the "why is this happening" class of question
- Or ask your agent. It can read every file in this vault and knows what setup put here.
