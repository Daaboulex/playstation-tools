# Options

Every option the modules of this flake declare. This file is generated from the module sources: change a description there, then run `nix run .#std-write-option-reference`.

## NixOS module

### `ps5-linux.kernel.enable`

Whether to enable the PS5 Linux patch set (ps5-linux-patches) with the options and the
built-in VCN firmware it needs. By default the kernel is the kernel.org
release the patch set targets; a configuration that sets
`boot.kernelPackages` itself, such as to a CachyOS kernel, gets the patch
set on that kernel instead, which builds once the patch set applies to it
.

Type: `boolean`. Default: `false`.
