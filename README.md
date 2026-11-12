# playstation-tools

`pst` is a command-line tool for jailbroken PS4 and PS5 consoles on the local network. It shows
what a console runs, updates payloads from their developers' releases, and handles game folders,
PS4 fake packages, saves, Y2JB and profile avatars. Use it with games you own, on consoles you
own.

The flake builds `pst` for x86_64-linux and aarch64-linux. On the PS5 it works through payloads:
Payload Manager 0.6.3 or newer and ftpsrv have to be running, and `pst` starts the App Dumper,
Garlic SaveMgr, the Web File Manager and shsrv when a command needs them. The console facts it
rests on were measured on a PS5 CFI-1116A at firmware 13.40.

The flake also has a NixOS module for a NixOS that runs on the PS5 itself. It builds the kernel
only, and the research behind it ran nothing on a console, so treat it as untested on hardware.

## Install

Try it once without installing, with your PS5's address in place of the example one:

```bash
PST_PS5=192.0.2.10 nix run github:Daaboulex/playstation-tools -- status
```

To install it, add the flake:

```nix
{
  inputs.playstation-tools.url = "github:Daaboulex/playstation-tools";
}
```

Then add the overlay and the package:

```nix
{
  nixpkgs.overlays = [ inputs.playstation-tools.overlays.default ];
  environment.systemPackages = [ pkgs.playstation-tools ];
}
```

The overlay adds `pst` to nixpkgs as `playstation-tools`. `packages.<system>.default` is the same
package for a configuration that takes no overlay. Both come with the patched LibOrbisPkg
`pkgtool` that `pst fpkg` runs.

## Use

`pst` reads only environment variables.

| Variable | Used for |
|---|---|
| `PST_PS5` | The PS5's address. Every PS5 command needs it. |
| `PST_PS4` | The PS4's address, the default for `pst fpkg --send`. |
| `PST_STATE` | Where saves, backups, built packages and snapshots go. The default is `$XDG_STATE_HOME/pst`, else `~/.local/state/pst`. |
| `GITHUB_TOKEN` | Optional. It raises the GitHub API rate limit and is sent only to api.github.com. |

Set the address, then ask the console what it runs:

```bash
export PST_PS5=192.0.2.10
pst status
```

That prints the running payloads, the autoload list, the installed payloads, the games and the
storage. The other commands, by what they are for:

| For | Commands |
|---|---|
| The console's state and its payloads | `status`, `payloads`, `payload-update`, `snapshot`, `temps` |
| A dumped game as a folder on the PS5 | `prep`, `casecheck`, `send`, `dumper`, `fself` |
| PS4 fake packages from your dumps | `fpkg` |
| Save backup, editing and conversion | `save-list`, `save-pull`, `save-push`, `save-inspect`, `save-convert`, `save-checksum`, `itt-merge` |
| Y2JB setup | `y2jb` |
| Profile avatars | `avatar`, `avatar-pack` |

Every command, with its arguments and what it does: [docs/COMMANDS.md](docs/COMMANDS.md).

Commands that write to a console back up what they replace first, upload under a temporary name
and rename into place, and refuse when the state is not what they expect.

## Linux on the PS5

`nixosModules.default` puts the PS5 Linux patch set
([ps5-linux-patches](https://github.com/ps5-linux/ps5-linux-patches)) onto a kernel:

```nix
{
  imports = [ inputs.playstation-tools.nixosModules.default ];
  ps5-linux.kernel.enable = true;
}
```

`ps5-linux.kernel.enable` adds the patch set to `boot.kernelPatches` with `X86_PS5`, the Salina
AHCI and MTS Ethernet drivers, IOMMU passthrough and the built-in `amdgpu/ps5_vcn.bin`. By
default it also sets `boot.kernelPackages` to the kernel.org release the patch set targets. A
configuration that sets `boot.kernelPackages` itself, such as to a CachyOS kernel, gets the patch
set on that kernel instead.

That switch is the module's only option, described in [docs/OPTIONS.md](docs/OPTIONS.md).
[docs/ps5-linux.md](docs/ps5-linux.md) is the research on Linux and NixOS on a PS5 at 13.40, with
what the module builds and each step that is still missing.

## Known limits

- `pst fpkg` builds base games only, from ItemzFlow dumps. It refuses the dump of an update.
- `pst payload-update` refuses a payload that came from Payload Manager's own repository. Payload
  Manager updates those itself.
- `pst save-convert` rewrites Alchemy IGB and Toys for Bob saves only.
- The NixOS module is for x86_64 only. Boot files, fan and boost, and Wi-Fi are not in it yet.
- A kernel other than the default one builds only once the patch set applies to its source.

## When something fails

A failure is one line on standard error that starts with `pst:`, and `pst` exits with status 1.
When GitHub's rate limit is the cause, the line names the time the limit resets, and setting
`GITHUB_TOKEN` raises the limit.

What a command replaced on the console is kept under `$PST_STATE`: `backups/` for Y2JB and
avatars, and `saves/` for the backup `pst save-push` pulls before it writes. The pages on saves,
Y2JB and avatars say how to put a backup back.

## More

- [docs/console-apis.md](docs/console-apis.md): services, ports and endpoints
- [docs/console-setup.md](docs/console-setup.md): payloads, DNS, temperatures
- [docs/game-folders.md](docs/game-folders.md): dumps, case-sensitive storage, compressed games
- [docs/fpkg.md](docs/fpkg.md): PS4 fake packages and the pkgtool patch
- [docs/saves.md](docs/saves.md): save commands and per-game formats
- [docs/igb-v12.md](docs/igb-v12.md): the Alchemy IGB version 12 layout
- [docs/y2jb.md](docs/y2jb.md): Y2JB, its icon and renaming an app
- [docs/avatars.md](docs/avatars.md): profile avatars
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): the dev shell, the checks, updating the patch set
- [CONTRIBUTING.md](CONTRIBUTING.md): the rules for a change and the console safety rules

## License

MIT, see [LICENSE](LICENSE).
[`patches/liborbispkg-chunk-sha-size.patch`](patches/liborbispkg-chunk-sha-size.patch) changes
LibOrbisPkg and is LGPL-3.0-or-later like LibOrbisPkg itself.
