# Game folders on the PS5

These procedures are for games you own, dumped from your own discs or installs, on consoles you
own.

## Installing a dumped game

1. Dump the game with ItemzFlow on a PS4 or the App Dumper on a PS5 to a USB drive.
2. Plug the drive into the PC.
3. A PS4 dump: `pst prep <dump>` writes `sce_sys/param.json` from its `param.sfo`. PS5 dumps
   already carry `param.json`.
4. `pst send <dump> --fself`. It uploads into `/data/pst-staging/<TITLEID>`, checks every
   file's size, renames the folder to `/data/homebrew/<TITLEID>`, and fake-signs it with the
   App Dumper. ShadowMountPlus registers it from there.

## PS4 app packages

A PS4 homebrew package becomes a PS5 folder app in three steps: extract it with
`orbis-pkg-util extract <app.pkg> -o <folder>` (github.com/videobitva/orbis), `pst prep
<folder>`, `pst send <folder>`. Its executables are already signed, so no `--fself`.
LibOrbisPkg's `pkgtool` cannot read these packages ("inode 0 is corrupt").

## Games that need case-insensitive storage

PS5 internal storage (`/data`) is case-sensitive; PS4 storage and exFAT are not. A dump whose
game opens mixed-case names that the dump stores in lowercase crashes on `/data` with
CE-108255-1 (seen with CUSA05158: `CollectibleTrackerIcons.pak` stored as
`collectibletrackericons.pak`). `pst casecheck <dump>` finds these before install. Such a game
runs from exFAT USB, or from an exFAT image in `/data/homebrew` that ShadowMountPlus mounts.

Building the image needs a real mount, so the `sudo` lines are yours to run:

1. `truncate -s <size> <ID>.exfat` with the dump size plus 64 KB per file plus 512 MB, then
   `mkfs.exfat -c 64K -L <ID> <ID>.exfat` (from exfatprogs)
2. `sudo mount -o loop,uid=$(id -u),gid=$(id -g) <ID>.exfat mnt`
3. `cp -r <dump>/. mnt/`
4. `sync && sudo umount mnt`, then `fsck.exfat -n <ID>.exfat` must list every file
5. Upload as `/data/homebrew/<ID>.exfat.part`, check the size, then rename to `.exfat`.

ShadowMountPlus also scans the top level of USB drives, so a second copy of the same title ID
anywhere it scans makes it ignore the image as a duplicate.

## Compressed games

Game Compressor (the keieksof fork, v1.1.3-smp17) packs a game folder into `<TITLEID>.ffpfsc`,
an exFAT image inside a compressed PFS file that ShadowMountPlus mounts. Measured on
2026-10-09 on a CFI-1116A at 13.40, the cost outweighed the space:

- Its read-speed test through `/system_ex/app/<ID>` gave 118 MB/s and about 35 MB/s for two
  compressed games, against 871 and 880 MB/s for two games as folders. ShadowMountPlus's README
  puts compressed containers at 150 to 250 MB/s and warns that streaming games may stutter.
- Game data that is already compressed barely shrank (16.0 GB to 15.3 GB). A game of 35,254
  small files went from 3.44 GB to 1.21 GB, mostly from packing them into one image.
- Only one `.ffpfsc` game mounts at a time.
- Its `deletePolicy=after` removes a folder before the hash check, and its API on 5910 has no
  login.

The size on the PS5's game information page is the console's stored value (`#_size` in
`/system_data/priv/mms/appinfo.db`), not what the game takes on disk.
