# Agent Protocol

This file is the standing operating protocol for any AI agent (or human
contributor) picking up work on the `iphone-whatsapp-media-export` project.
It is intentionally task-agnostic: you will be handed one or more task specs
from `TASKS/TODO/` — this document tells you how to execute them.

Read this file end-to-end before starting.

---

## How to pick up a task

1. The maintainer will point you at one or more spec files in `TASKS/TODO/`.
2. Read the spec(s) fully. If anything is ambiguous, ask before coding.
3. Create a git worktree for your work (see **Worktree workflow** below).
4. Implement the task(s) on a feature branch inside the worktree.
5. When dev is complete, follow the **Task lifecycle** to move the spec
   into QA and open a PR.
6. Wait for tester sign-off before the task is considered done.

---

## Task lifecycle — MANDATORY

```
TASKS/TODO/   →   (agent picks up task)   →   TASKS/QA/   →   (tester approves)   →   TASKS/DONE/
```

**Every agent must do this on dev completion:**

1. Copy the task spec from `TASKS/TODO/<task>.md` into `TASKS/QA/<task>.md`
2. Replace the content with a QA card using the template below
3. Delete the original from `TASKS/TODO/`
4. Commit the file move as part of your feature commit (or as a follow-up
   commit on the same branch)

**QA card template** (`TASKS/QA/<task>.md`):

```markdown
# QA — <Task title>

**Branch:** `feature/<short-slug>`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/<N>
**Dev completed by:** <agent name or handle>

---

## What was built
<!-- 3–6 bullet points describing what changed and why -->

---

## Definition of Done
<!-- Concrete, runnable checks. Each line is a checkbox the tester will tick.
     Prefer commands the tester can paste into a terminal. -->
- [ ] ...
- [ ] ...
```

After the tester approves, the file is moved to `TASKS/DONE/` and the PR
is merged.

---

## Project structure (read this first)

```
whatsapp_extractor/
  constants.py     — FILE_TYPES, APPLE_EPOCH, DEFAULT_TYPES, GIF_MESSAGE_TYPES
  utils.py         — pure helpers (dates, JID parsing, safe names)
  metadata.py      — EXIF + macOS xattr/Spotlight; XMP sidecar on Windows/Linux
  backup.py        — find_backup_path() (cross-platform), find_chatstorage()
  database.py      — Manifest.db and ChatStorage queries
  extractor.py     — build_dest_path(), extract() loop
  cli.py           — argparse for extract_whatsapp_media.py
  contacts_cli.py  — argparse for list_contacts.py
  gui.py           — tkinter GUI (zero extra deps)

extract_whatsapp_media.py   ← thin entry point (3 lines)
list_contacts.py            ← thin entry point (3 lines)
gui.py                      ← thin entry point (3 lines)

TASKS/
  TODO/   ← specs for features not yet started
  QA/     ← dev-complete features awaiting tester sign-off
  DONE/   ← tester-approved, merged features
```

Keep entry points thin — all logic lives inside the `whatsapp_extractor/`
package. Reuse existing helpers instead of duplicating them.

---

## Worktree workflow

Each agent works in its own **git worktree** — a separate directory on
disk that shares the same repo. This keeps parallel work conflict-free.

**Create a worktree** (run once from the main project directory):

```bash
git checkout main
git pull
git worktree add ../wa-<feature-slug> -b feature/<feature-slug>
cd ../wa-<feature-slug>
```

Replace `<feature-slug>` with a short kebab-case name describing the task
(e.g. `size-filter`, `encrypted-backup`). If a single branch covers
multiple related tasks, use a combined slug.

**When dev is done:**

```bash
# from inside ../wa-<feature-slug>
git add -p
git commit -m "<type>: <summary>"
git push -u origin feature/<feature-slug>
gh pr create --fill   # or open the PR on github.com
```

Move the task spec to `TASKS/QA/` per the lifecycle above.

**After the PR is merged**, clean up from the main project directory:

```bash
git worktree remove ../wa-<feature-slug>
git branch -d feature/<feature-slug>
```

---

## Parallel work — avoiding conflicts

When more than one agent is working simultaneously, the maintainer will
assign tasks that touch disjoint files. If you notice your task needs to
modify a file another agent owns, stop and flag it before proceeding.

High-traffic files to be aware of:
- `extractor.py` — the main extraction loop; only one agent at a time
- `cli.py` — argparse flags; coordinate if adding new flags
- `database.py` — query helpers; usually safe for additive changes

---

## Commit & PR conventions

- Conventional-commit-style prefixes: `feat:`, `fix:`, `docs:`, `refactor:`,
  `test:`, `chore:`
- One logical change per commit where practical
- PR description should link the task spec and summarise the user-facing
  change
- Do not force-push to `main`. Feature branches may be rebased before
  merge.

---

## Testing expectations

- Run the CLI at least once in `--dry-run` mode against a real backup
  before opening the PR
- If your change touches the GUI, launch it and verify the affected panel
- Include any manual-test commands the tester should run in the QA card's
  Definition of Done
