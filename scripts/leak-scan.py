#!/usr/bin/env python3
"""Leak scan for a public repo: blocks owner, vault, internal-system and client strings.

Modes:
  --staged   lines added in the staged diff, plus staged file names (pre-commit)
  --tree     every tracked file and file name at HEAD/working tree (CI)
  --history  every line ever added in any commit, plus every commit message (CI, release)

Findings print as path:line and a pattern LABEL only. The matched text is never
printed, so a hit cannot re-leak through public CI logs.

Every pattern is assembled from fragments so this file never contains the
literal strings it blocks and passes its own scan.
Exit codes: 0 clean, 1 findings, 2 usage or git error.
"""
import re
import subprocess
import sys

# (label, regex) — case-insensitive unless the label ends with "(case-sensitive)".
PATTERNS = [
    ("owner first name", r"\b" + "Dan" + "iel" + r"\b"),
    ("owner surname", "Egh" + "dami"),
    ("owner laptop host", "Daniels-Mac" + "Book"),
    ("private host", "olym" + "pus"),
    ("vault root", "NovaCaelum" + "_Obs"),
    ("vault workspace", "Agent" + "Secret" + "Base"),
    ("canonical layer", r"(?<![A-Za-z])_agent" + "OS" + r"\b"),
    ("incident id", r"\bINC" + "0" + r"\d{2}\b"),
    ("internal task system (case-sensitive)", "Task" + " Graph"),
    ("internal task tool", "upsert" + "_work" + "_item"),
    ("internal ops server", "nova-caelum" + "-ops"),
    ("internal agent registry", "agent" + "_registry"),
    ("secret entry name", r"\b[A-Z0-9_]*_OPS" + "_BEARER" + r"\b"),
    ("secret entry name", "BWS" + "_ACCESS" + "_TOKEN"),
    ("client name", "Heart" + "flow"),
    ("client name", r"\b" + "Ry" + "an" + r"\b"),
    ("client name", r"\b" + "Dar" + "ren" + r"\b"),
    ("third-party name", "Bol" + "er"),
    ("third-party firm", r"\b" + "B" + "CG" + r"\b"),
    ("agent self file", r"\bself" + r"\.md\b"),
    ("personal home path", "/ho" + "me/" + "dan" + "iel"),
]
# /Users/<name> is blocked unless <name> is an obvious placeholder.
HOME_RE = re.compile("/Us" + "ers/" + r"([^/\s<>'\"`)]+)")
PLACEHOLDERS = {"user", "you", "yourname", "your-name", "username", "name", "me", "$user", "${user}", "shared"}

COMPILED = [
    (label, re.compile(rx) if label.endswith("(case-sensitive)") else re.compile(rx, re.IGNORECASE))
    for label, rx in PATTERNS
]


def hits(text):
    found = [label for label, rx in COMPILED if rx.search(text)]
    for m in HOME_RE.finditer(text):
        if m.group(1).lower() not in PLACEHOLDERS:
            found.append("personal /Users path")
    return found


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.stderr.write("leak-scan: git %s failed\n" % args[0])
        sys.exit(2)
    return r.stdout


def scan_diff(diff, findings, where_prefix=""):
    path, line_no = "?", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else raw[4:]
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+"):
            for label in hits(raw[1:]):
                findings.append((where_prefix + "%s:%d" % (path, line_no), label))
            line_no += 1


def mode_staged():
    findings = []
    for name in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        for label in hits(name):
            findings.append((name + " (file name)", label))
    scan_diff(git("diff", "--cached", "-U0", "--no-color", "--no-ext-diff"), findings)
    return findings


def mode_tree():
    findings = []
    for name in git("ls-files").splitlines():
        for label in hits(name):
            findings.append((name + " (file name)", label))
        try:
            with open(name, encoding="utf-8", errors="strict") as fh:
                for i, line in enumerate(fh, 1):
                    for label in hits(line):
                        findings.append(("%s:%d" % (name, i), label))
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue  # binary, submodule or deleted-in-worktree
    return findings


def mode_history():
    findings = []
    revs = git("rev-list", "--all").split()
    for rev in revs:
        short = rev[:7]
        msg = git("log", "-1", "--format=%B", rev)
        for label in hits(msg):
            findings.append(("commit %s (message)" % short, label))
        for name in git("show", "--name-only", "--format=", rev).splitlines():
            for label in hits(name):
                findings.append(("commit %s %s (file name)" % (short, name), label))
        scan_diff(git("show", "-U0", "--no-color", "--no-ext-diff", "--format=", rev), findings, "commit %s " % short)
    return findings


def main():
    modes = {"--staged": mode_staged, "--tree": mode_tree, "--history": mode_history}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        sys.stderr.write("usage: leak-scan.py --staged | --tree | --history\n")
        return 2
    findings = modes[sys.argv[1]]()
    if not findings:
        print("leak-scan %s: clean" % sys.argv[1])
        return 0
    print("leak-scan %s: %d finding(s). Matched text is withheld on purpose." % (sys.argv[1], len(findings)))
    for where, label in findings:
        print("  %s  [%s]" % (where, label))
    return 1


if __name__ == "__main__":
    sys.exit(main())
