# Development

`pst` is an original project by Daaboulex: first-party, with no external upstream to follow.
[`pst.py`](../pst.py) is the tool and [`check.py`](../check.py) is its check. The rules for a
change, the command classes and the console safety rules are in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## The dev shell

`nix develop` gives a shell with `pst`, Python with Pillow, `pkgtool`, `jq` and `curl`. The flake
builds against the `nixos-unstable` branch of nixpkgs.

## Checks

```bash
nix flake check --no-eval-cache
```

It runs [`check.py`](../check.py) (no console, no network), `pst fpkg` on a synthetic dump that
only the patched `pkgtool` can package, and on x86_64-linux the packaging standard's lint, ruff
included. On aarch64-linux the check does not run the lint. The dev shell installs the same lint
as a pre-commit hook, which is what runs it there.

On x86_64-linux it also evaluates the NixOS module with `ps5-linux.kernel.enable` on
(`module-eval-nixos`) and generates that kernel's config (`ps5-kernel-config`).

## The kernel config guard

Every system build that enables `ps5-linux.kernel.enable` reads the generated kernel config and
fails if one of the PS5 options is missing. [ps5-linux.md](ps5-linux.md) names the options and
says why the guard is there.

## Updating the PS5 patch set

The patch set follows upstream's main branch: the scheduled lock refresh moves it,
`nix run .#after-lock-update` writes the hash of the release it targets into
[`kernel.json`](../kernel.json), and CI generates that kernel's config before the refresh lands.

Run `nix run .#after-lock-update` from the repository root. It does nothing when `kernel.json`
already holds the hash of the release the patch set targets.
