# Contributing to playstation-tools

`pst.py` is a single-file Python tool for jailbroken PS4 and PS5 consoles; `check.py` is its
check. The README says what each command does and which environment variables configure it;
`docs/` holds the console knowledge each command rests on.

## Rules

- Run `nix flake check --no-eval-cache` before every commit and read its exit code; commit only
  when it is green. No force flags.
- No comments in any file, except the README's `generated:` markers the packaging standard
  requires. ASCII only.
- No per-owner value in a tracked file: no console or LAN address, console user or account
  id, user name, token, real save, console database, game library, or Sony, YouTube or game
  artwork, and no packages. These come from `PST_PS5`, `PST_PS4`, `PST_STATE`,
  `GITHUB_TOKEN` or a command's arguments. Check fixtures are synthetic or scrubbed.
- Fail closed: on ambiguity (no row or more than one, an unknown save type, an unknown flag set)
  raise `Fail` with a message saying what was found. Never swallow an error; every failure
  reaches the user as one `pst: ...` line.
- `check.py` never touches a console or the network: stub the transport, as `FakeFtp` does.
- The repository follows github:Daaboulex/nix-packaging-standard: its lint (ruff, nixfmt, typos,
  rumdl and more) runs in the pre-commit hook and in the flake check. The synced files
  (`.envrc`, `.editorconfig`, `.github/workflows/`) are copied from the standard, never edited
  here.
- Commits: `type(scope): summary`, 72 characters at most, lowercase after the prefix, a body
  that says why and what was discarded, a `Test:` line naming what ran, and a `Cause:` line on
  a fix. One logical change per commit. Scopes: pst, check, module, flake, readme, docs, overlays.

## Commands by what they touch

| Class | Commands |
|---|---|
| Offline | prep, casecheck, fpkg without --send, save-inspect, save-convert, save-checksum, itt-merge |
| Reads a console | status, payloads, snapshot, save-list |
| Starts a payload | dumper, temps (shsrv), the save commands (Garlic), y2jb --pkg (the Web File Manager) |
| Writes a console | payload-update, y2jb, avatar, avatar-pack, send, fself, save-push, fpkg --send |
| Deletes local data | fpkg --remove-dump |

Run a command that writes a console only when that exact run was asked for; `check.py` never
runs one.

## Console safety

- Change `app.db` and `appinfo.db` only the way `rename_y2jb` does: a local copy, refuse unless
  exactly one row matches, a byte-for-byte JSON round trip, `PRAGMA integrity_check`, a local
  backup, a staged upload and a rename, with no game or app running. A damaged database can
  delete installed games and saves.
- Saves: the game is closed, a backup is pulled first, `sce_sys` is never written, no file is
  added that the save lacks, and every file is read back and compared by sha256.
- Never overwrite a console file in place: upload under a temporary name or folder, check the
  size, then rename (`ftp_store`, `ftp_replace`, the staging in `cmd_send`).
- No download without a GitHub sha256 digest (`verified_download`).
- Never fake-activate an account, never update a console past 13.60 (14.00 and later block the
  exploits), and stop what you started (`pst temps --stop`): shsrv, Garlic and FTP have no
  login.

## Adding a command

Keep the pure part (parsing, planning, building bytes) apart from the transport, so the check
can run it without a console. Add a check that fails without the change, a row in the README's
command table, and a row in `docs/console-apis.md` for any new endpoint. New state goes under
`state_dir()`.

## Where things live

- `pst.py`, in sections: environment and state, transport, console services, GitHub releases,
  status and payloads, game folders, PS4 fPKG, Y2JB, avatars, console saves, save formats, CLI.
- `check.py` and `fixtures/` (synthetic or scrubbed files only); `fixtures/playgo-trigger.nix`
  is the pkgtool patch's heal test.
- `module.nix` is the NixOS module for Linux on the PS5; `kernel.nix` builds the kernel.org
  release the patch set's `.config` names, with the tarball hash from `kernel.json`, which
  `nix run .#after-lock-update` (`scripts/sync-kernel-pin.sh`) writes.
- `package.nix` builds `pst`; `overlay.nix` adds it to nixpkgs; `overlays/` holds temporary
  fixes to nixpkgs packages in the standard's shape (a reason, a date, and the build that shows
  the fix is no longer needed); `patches/` holds the patch files they apply.
- `docs/`: console facts and formats, each with how and when it was established.
- `browser/`, `dns/`: files that go onto the console as they are.
- Console state, saves and backups live in `PST_STATE`, never in the repository.
