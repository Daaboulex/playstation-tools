# playstation-tools

<!-- BEGIN generated:badges -->
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![NixOS unstable](https://img.shields.io/badge/NixOS-unstable-78C0E8?logo=nixos&logoColor=white)](https://nixos.org)
<!-- END generated:badges -->

`pst` is a command-line tool for jailbroken PS4 and PS5 consoles on the local network: console
status and payload updates from developer releases, game folders and PS4 fake packages from
your own dumps, save backup, editing and conversion, Y2JB setup, and profile avatars. It talks
to the payloads already running on the console (Payload Manager, ftpsrv, the App Dumper, Garlic
SaveMgr, the Web File Manager); see [docs/console-apis.md](docs/console-apis.md).

Use it with games you own, on consoles you own.

<!-- BEGIN generated:upstream -->
## Project

| | |
|---|---|
| **Type** | Original project (first-party; no external upstream) |
| **Author** | Daaboulex |
| **License** | MIT (see LICENSE) |

<!-- END generated:upstream -->

## Installation

```bash
nix run github:Daaboulex/playstation-tools -- status
```

As a flake input, `packages.<system>.default` is `pst`, with the patched LibOrbisPkg `pkgtool`
that `pst fpkg` runs on its `PATH`, and `overlays.default` adds it to nixpkgs as
`playstation-tools`. `nix develop` gives a shell with `pst`, Python with Pillow, `pkgtool`, `jq`
and `curl`.

## Configuration

`pst` reads only environment variables:

| Variable | Used for |
|---|---|
| `PST_PS5` | the PS5's address; every PS5 command needs it |
| `PST_PS4` | the PS4's address, the default for `pst fpkg --send` |
| `PST_STATE` | where saves, backups, built packages and snapshots go; default `$XDG_STATE_HOME/pst`, else `~/.local/state/pst` |
| `GITHUB_TOKEN` | optional; raises the GitHub API rate limit; sent only to api.github.com |

## NixOS module

`nixosModules.default` puts the PS5 Linux patch set
([ps5-linux-patches](https://github.com/ps5-linux/ps5-linux-patches)) onto a kernel, for a NixOS
that runs on the PS5 itself:

```nix
{
  imports = [ inputs.playstation-tools.nixosModules.default ];
  ps5-linux.kernel.enable = true;
}
```

`ps5-linux.kernel.enable` adds the patch set to `boot.kernelPatches` with `X86_PS5`, the Salina
AHCI and MTS Ethernet drivers, IOMMU passthrough and the built-in `amdgpu/ps5_vcn.bin`, and
sets `boot.kernelPackages` by default to the kernel.org release the patch set targets. A
configuration that sets `boot.kernelPackages` itself, such as to a CachyOS kernel, gets the
patch set on that kernel instead; it builds once the patch set applies to that kernel's source.

Every system build reads the generated kernel config and fails if one of those options is
missing. The patch set follows upstream's main branch: the scheduled lock refresh moves it,
`nix run .#after-lock-update` writes the hash of the release it targets into `kernel.json`, and CI generates
that kernel's config before the refresh lands. Boot files, fan and boost, and Wi-Fi are not in
the module yet; see [docs/ps5-linux.md](docs/ps5-linux.md).

## Commands

| Command | Does |
|---|---|
| `pst status` | Running payloads, autoload list, installed payloads, games, storage |
| `pst payloads` | Each installed payload against its developer's newest GitHub release |
| `pst payload-update <name>` | Installs the developer's newest release after checking GitHub's sha256 |
| `pst snapshot` | Records console state and developer versions to `$PST_STATE/inventory/<date>.json` |
| `pst dumper` | Starts the App Dumper |
| `pst temps [--watch N] [--count N] [--stop]` | SoC and CPU temperature and CPU clock from shsrv's banner; `--stop` ends shsrv |
| `pst prep <dump>` | Writes `sce_sys/param.json` for a PS4 dump from its `param.sfo` |
| `pst casecheck <dump>` | Lists files the game names with different capitals than the dump has |
| `pst send <dump> [--fself]` | Uploads a dump to `/data/homebrew/<TITLEID>` through a staging folder, sizes checked; `--fself` then fake-signs it with the App Dumper |
| `pst fself <TITLEID>` | Fake-signs a game already in `/data/homebrew` |
| `pst fpkg <dump>... [--plan] [--dir D] [--send [PS4]] [--remove-dump]` | Builds PS4 fake packages from ItemzFlow dumps of base games |
| `pst y2jb [--install [--pkg PKG]] [--icon PNG] [--rename]` | Sends the newest Y2JB autoloader update, sha256 checked; see [docs/y2jb.md](docs/y2jb.md) |
| `pst avatar <picture> [--user HEX] [--fill]` | Sets a picture as a user's profile avatar |
| `pst avatar-pack <pack> <picture or folder>... [--fill]` | Stores pictures as ready avatars in `/data/avatars/<pack>/` |
| `pst save-list` | Every game save on the console, by title and slot |
| `pst save-pull <TITLEID> <slot> [--dir D]` | Copies a save, encrypted and decrypted, with a sha256 manifest |
| `pst save-push <dir> <TITLEID> <slot> [--dir D]` | Backs the save up, writes the files in `<dir>` into it and reads them back |
| `pst save-inspect <file>` | Names a save file's format and byte order and lists its field and class names |
| `pst save-convert <in> <out> --to le\|be` | Rewrites an Alchemy IGB or Toys for Bob save in the other byte order |
| `pst save-checksum <file>...` | Names the checksum in a save's last 4 bytes |
| `pst itt-merge <ps5 file> <out> [--source F] [--unlock-all]` | Builds an It Takes Two PS5 save from another platform's progress |

Commands that write to a console back up what they replace first, upload under a temporary
name and rename into place, and refuse when the state is not what they expect.

## Documentation

- [docs/console-apis.md](docs/console-apis.md): services, ports and endpoints
- [docs/console-setup.md](docs/console-setup.md): payloads, DNS, the Browser tile, temperatures
- [docs/game-folders.md](docs/game-folders.md): dumps, case-sensitive storage, compressed games
- [docs/fpkg.md](docs/fpkg.md): PS4 fake packages and the pkgtool patch
- [docs/saves.md](docs/saves.md): save commands and per-game formats
- [docs/igb-v12.md](docs/igb-v12.md): the Alchemy IGB version 12 layout
- [docs/y2jb.md](docs/y2jb.md): Y2JB, its icon and renaming an app
- [docs/avatars.md](docs/avatars.md): profile avatars
- [docs/ps5-linux.md](docs/ps5-linux.md): Linux and NixOS on a PS5 at 13.40, researched

## Check

`nix flake check --no-eval-cache` runs `check.py` (no console, no network), `pst fpkg` on a
synthetic dump that only the patched `pkgtool` can package, and on x86_64-linux the packaging
standard's lint. The dev shell installs the same lint as a pre-commit hook.

<!-- BEGIN generated:footer -->
## License

MIT, see [LICENSE](LICENSE). `patches/liborbispkg-chunk-sha-size.patch` changes LibOrbisPkg and
is LGPL-3.0-or-later like LibOrbisPkg itself.
<!-- END generated:footer -->
