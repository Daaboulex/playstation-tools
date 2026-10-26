# PS4 fake packages from dumps

`pst fpkg <dump>...` turns ItemzFlow dumps of PS4 base games (`CATEGORY` gd) into
`<CONTENT_ID>.pkg` files for GoldHEN's Package Installer, on Linux. These are for games you own
on consoles you own.

## The plan

It first prints one line per dump: title, package size, and where it goes or why not. The plan
books each queued package's space against its drive, so later dumps see what earlier ones will
use. A dump is refused while ItemzFlow's `<dump>.dumping` marker exists; a package with no
`.work` folder beside it counts as built and is skipped; a `.work` folder means a build is
running or failed and is reported as partial. `--plan` stops after the table and exits
non-zero if any dump cannot be built. Otherwise the queued dumps build in order; one failure is
reported and the rest still build; a summary ends the run, non-zero if any dump was not built.

## Space and placement

Before each build it adds up the space the package and its signed executables need (each file
and each directory takes whole 64 KiB PFS blocks, a signed executable grows by its digests, plus
2% and 128 MB) and picks where to write: next to the dump when that drive has room, so the PS4
installs it from USB and the PC drive is untouched, otherwise `$PST_STATE/fpkg/`. `--dir` names
the place instead; too little space, or an output inside the dump, stops the build. A file or
folder name outside ASCII stops it too, because pkgtool would write it as `?`. `--send` uploads
the package to `/data/pkg` over GoldHEN FTP on the PS4 named by `PST_PS4` (or `--send <address>`),
checks the size and deletes the local copy. `--remove-dump` deletes the dump only after every
step succeeded.

## The build

1. Every plain ELF in the dump (ItemzFlow writes decrypted, unsigned executables) is
   fake-signed by `fake_self` into the fSELF layout that flatz's `make_fself.py` produces with
   its defaults (paid `0x3100000000000002`, ptype fake, no auth info). A file still in SELF form
   stops the build.

   `fake_self` reproduces `make_fself.py`, which flatz published without a licence; it was
   written against that script's published copies and `check.py` pins its output to the script's
   byte for byte. It reads only the program headers, as the script does: a decrypted game
   executable often names a section-header table that is not in the file. Measured on 2026-10-26,
   two other signers do not fit dumps: OpenOrbis `create-fself` rewrites its input into an OELF
   first and its library refuses ELFs without that data, and `make_fself_rust` (MIT) stops on a
   section-header offset past the end of the file and, after a fix for a missing 16-byte
   alignment, still differed on 25 of 2000 fuzzed ELFs.
2. A GP4 project lists the dump with the files ItemzFlow's own GP4 leaves out skipped
   (`sce_sys/about`, the package metadata pkgtool regenerates, the `.dds` images).
3. LibOrbisPkg's `pkgtool pkg_build` writes the package and `pkg_validate` checks it. The work
   folder beside it is removed on success and kept on failure.

pkgtool replaces the game's PlayGo chunk layout with one chunk, and makes a keystone from the
zero passcode when the dump has none. An update (`-patch` folder) is not merged.

## The pkgtool patch

The flake's pkgtool carries `patches/liborbispkg-chunk-sha-size.patch`, applied by
`overlays/liborbispkg-playgo-chunk-sha.nix`. Unpatched, `pkg_build` sizes the PlayGo chunk hash
table before counting the entry table and the hash table itself into the 512 KiB body alignment,
so a package whose body ends just past a boundary fails with "Playgo Chunk hash file was not
allocated enough space" (LibOrbisPkg issues #64 and #88; a 39 GB game hit it on 2026-10-11). The
patch sizes the table by iterating until it stops growing.

`fixtures/playgo-trigger.nix` runs `pst fpkg` on a synthetic dump (the param.sfo in
`fixtures/playgo-trigger/`, a 64 KiB `eboot.bin` and a `pic1.png` of 0x7A500 bytes, both zeros).
Measured on 2026-10-26 with pkgtool 0.3-unstable-2025-11-13, every `pic1.png` from 0x7A400 to
0x7A600 bytes fails unpatched and builds patched; 0x7A500 is the middle. The flake check builds it
with the patched pkgtool. The packaging standard's scheduled heal builds it with the stock nixpkgs
pkgtool and removes the overlay once that succeeds; if the patch stops applying, the package build
fails instead.
