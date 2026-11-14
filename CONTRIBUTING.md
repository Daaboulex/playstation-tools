# Contributing

These hold for everyone working on this project, people and AI assistants alike. This project's own
rules follow at the end.

## Report a bug or ask for something

Open an issue with the bug, request or task form.

## Track work

- An open task is an issue in the repo it belongs to. Nothing else is a task list: no notes file,
  no assistant memory or queue, no session.
- Before opening an issue, search the open ones. What an existing issue covers is added to it: one
  matter is one issue.
- An assistant opens an issue in two cases only: the person it works for asked for something that
  is not finished when work ends, or it verified a defect.
- An idea, a maybe or a question is said once and dropped. It becomes an issue, with `later`, only
  when that person says keep it.
- An issue has one type, which its form sets. Add `later` to an idea nobody owes and `waiting` to
  one blocked on a person, a delivery or a decision. An issue that is not ours to solve, or no
  longer true, is closed with one sentence saying why.
- An issue's goal stays in the words it was opened with. Later work ticks its "Done when" list and
  comments; it does not rewrite the goal.
- Never record state, such as what was exported, what runs where or what was done: that is read at
  its source. Record only what someone must still act on. A one-off, such as a file exported for a
  meeting, is not recorded.
- Before starting work, read the repo's open issues. When work ends, close what is done, and open
  an issue for what was asked and is not finished.

## Make a change

- Read the code the change touches first.
- Run `nix flake check` before you commit. A red `main` is fixed before anything else.
- The commit message says why the change was made. A decision that shapes the project also gets
  one short file in `docs/`.
- A fix names the cause it removes. When a later fix names another cause for the same failure, the
  earlier fix comes out in that change unless it is proven on its own. Unmeasured is not proven.
- A doc says only what the code cannot: a decision, a fact about an outside system, or a trap no
  check catches. It never repeats what the code, a check's message or a command's usage says, and
  never copies state such as counts, versions or what runs where: that is read at its source. A
  wrong line is deleted or fixed when seen.
- An open point is written as the question that is open, never as an errand: no line about a person
  asking, waiting on or confirming something with someone else.
- Nothing that exists only on your own machine goes into the project, or into an issue, a pull
  request or a comment on one: no personal names, addresses, machines, hardware, paths, tools or
  habits.
- Never hide an error. Read a result from the check's own exit code.

## Improve these rules

These rules grow with the work. A rule for this project goes under This project below. A rule for
every repo goes to `Daaboulex/nix-packaging-standard` as an issue or a change, and reaches each
repo with the next release.

## This project

[`pst.py`](pst.py) is a single-file Python tool for jailbroken PS4 and PS5 consoles;
[`check.py`](check.py) is its check. The README says which environment variables configure it,
[`docs/COMMANDS.md`](docs/COMMANDS.md) says what each command does, and the rest of
[`docs/`](docs/) holds the console knowledge each command rests on.

### Rules

- Run `nix flake check --no-eval-cache` before every commit and read its exit code; commit only
  when it is green. No force flags.
- No comments in any file. ASCII only.
- No per-owner value in a tracked file: no console or LAN address, console user or account
  id, user name, token, real save, console database, game library, or Sony, YouTube or game
  artwork, and no packages. These come from `PST_PS5`, `PST_PS4`, `PST_STATE`,
  `GITHUB_TOKEN` or a command's arguments. Check fixtures are synthetic or scrubbed.
- Fail closed: on ambiguity (no row or more than one, an unknown save type, an unknown flag set)
  raise `Fail` with a message saying what was found. Never swallow an error; every failure
  reaches the user as one `pst: ...` line.
- [`check.py`](check.py) never touches a console or the network: stub the transport, as
  `FakeFtp` does.
- The repository follows github:Daaboulex/nix-packaging-standard: its lint (ruff, nixfmt, typos,
  rumdl and more) runs in the pre-commit hook. `nix flake check` runs the same lint, ruff
  included, on x86_64-linux and not on aarch64-linux, where the hook is what runs it. `nix fmt`
  does not run ruff. The synced files ([`.envrc`](.envrc), [`.editorconfig`](.editorconfig),
  [`.github/workflows/`](.github/workflows/)) are copied from the standard, never edited here.
- Commits: `type(scope): summary`, 72 characters at most, lowercase after the prefix, a body
  that says why and what was discarded, a `Test:` line naming what ran, and a `Cause:` line on
  a fix. One logical change per commit. Scopes: pst, check, module, flake, readme, docs, overlays.

### Commands by what they touch

| Class | Commands |
|---|---|
| Offline | prep, casecheck, fpkg without --send, save-inspect, save-convert, save-checksum, itt-merge |
| Reads a console | status, payloads, snapshot, save-list, save-pull |
| Starts a payload | dumper, temps (shsrv), save-list, save-pull, save-push (Garlic), y2jb --pkg (the Web File Manager) |
| Writes a console | payload-update, y2jb, avatar, avatar-pack, send, fself, save-push, fpkg --send |
| Deletes local data | fpkg --remove-dump |

Run a command that writes a console only when that exact run was asked for;
[`check.py`](check.py) never runs one.

### Console safety

- Change `app.db` and `appinfo.db` only the way `rename_y2jb` does: a local copy, refuse unless
  exactly one row matches, a byte-for-byte JSON round trip, `PRAGMA integrity_check`, a local
  backup, a staged upload and a rename, with no game or app running. A damaged database can
  delete installed games and saves.
- Saves: the game is closed, a backup is pulled first, `sce_sys` is never written, no file is
  added that the save lacks, and every file is read back and compared by sha256.
- Never overwrite a console file in place: upload under a temporary name or folder, check the
  size, then rename (`ftp_store`, `ftp_replace`, the staging in `cmd_send`).
- No download without a GitHub sha256 digest (`verified_download`).
- Never update a console past 13.60 (14.00 and later block the exploits), and stop what you
  started (`pst temps --stop`): shsrv, Garlic and FTP have no login.

### Adding a command

Keep the pure part (parsing, planning, building bytes) apart from the transport, so the check
can run it without a console. Add a check that fails without the change, a row in
[`docs/COMMANDS.md`](docs/COMMANDS.md), the command's name in the README's table of commands, and
a row in [`docs/console-apis.md`](docs/console-apis.md) for any new endpoint. New state goes
under `state_dir()`.

### Where things live

- [`pst.py`](pst.py), in sections: environment and state, transport, console services, GitHub
  releases, status and payloads, game folders, PS4 fPKG, Y2JB, avatars, console saves, save
  formats, CLI.
- [`check.py`](check.py) and [`fixtures/`](fixtures/) (synthetic or scrubbed files only);
  [`fixtures/playgo-trigger.nix`](fixtures/playgo-trigger.nix) is the pkgtool patch's heal test.
- [`module.nix`](module.nix) is the NixOS module for Linux on the PS5;
  [`kernel.nix`](kernel.nix) builds the kernel.org release the patch set's `.config` names, with
  the tarball hash from [`kernel.json`](kernel.json), which `nix run .#after-lock-update`
  ([`scripts/sync-kernel-pin.sh`](scripts/sync-kernel-pin.sh)) writes.
- [`package.nix`](package.nix) builds `pst`; [`overlay.nix`](overlay.nix) adds it to nixpkgs;
  [`overlays/`](overlays/) holds temporary fixes to nixpkgs packages in the standard's shape (a
  reason, a date, and the build that shows the fix is no longer needed); [`patches/`](patches/)
  holds the patch files they apply.
- [`docs/`](docs/): console facts and formats, each with how and when it was established.
- [`dns/`](dns/): a file that goes onto the console as it is.
- Console state, saves and backups live in `PST_STATE`, never in the repository.
