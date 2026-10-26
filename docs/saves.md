# Saves

Saves are reached through Garlic SaveMgr ([console-apis.md](console-apis.md)), which decrypts
and re-encrypts them for the console's own account, so a pushed file needs no re-signing. A
game must be closed while its save is pulled or pushed.

- `pst save-pull <TITLEID> <slot>` copies a save to `$PST_STATE/saves/<TITLEID>/<slot>/<time>/`:
  the encrypted image and key, the decrypted files, and a manifest with each file's sha256.
- `pst save-push <dir> <TITLEID> <slot>` pulls a backup first, then writes the files in `<dir>`
  into the save, never `sce_sys` and never a file the save does not already have, and reads
  them back to check the hashes. To undo a push, push the backup's `files` folder back.

## Formats

**Skylanders SWAP Force and Imaginators** store `SYS-DATA.sav` in Alchemy's IGB format,
version 12, laid out in [igb-v12.md](igb-v12.md). PS4 and Switch files are little-endian, Wii U
files the same layout big-endian. The PS4 game reports a big-endian file as corrupt. On
2026-10-09 a Wii U SWAP Force slot, converted with `save-convert`, loaded on a PS4, and
with that completed slot present the game offered Nightmare for a new save. Wii U Imaginators
files do not convert: they hold field types (`igVec3f`, `igUnsignedLong`) and a 4-byte trailer
whose byte layout is not proven, so `save-convert` refuses them. A Switch Imaginators
`IMAGINATORS_OPTIONS.sav`, pushed unchanged as the Global Save (CUSA05158 savedata0), loaded
and offered Nightmare for a new game: Imaginators keeps that unlock in the profile save, not
in a story slot.

**Skylanders Trap Team** stores `Save_Header` and `Save_Slot_1` to `_4`: arrays of 32-bit words
in the console's own byte order, each file ending in an FNV-1a checksum of the bytes before it
(found with `save-checksum`). A converted empty Wii U slot is byte for byte the PS4 empty slot.
On 2026-10-09 a Wii U EU save, converted and pushed into CUSA00697 SAVEDATA00, loaded on a PS4
with Nightmare unlocked.

**It Takes Two** (PPSA02343) keeps everything in one JSON file, `ue4savegame.dpx.sav` in the
`ProfileData` save, in the same shape on the PS5 and the Switch (JKSV exports it as
`ProfileData`). Progress is in the `Profile` block: `FurthestUnlockedChapter` decides what
Chapter Select offers, `Minigame.<name>` entries unlock minigames, and `LastSaveChapter` and
`LastSaveProgressPoint` are where Continue resumes. The PC save Hazelight published,
`SaveData.Nuts` (kept by the Internet Archive), holds the same keys flat with the ending as the
furthest chapter; `itt-merge --unlock-all` carries those values. On 2026-10-09 a Switch save,
merged with `itt-merge --source <Switch ProfileData> --unlock-all` and pushed into PPSA02343
ProfileData, loaded on a PS5: Continue resumed at the Switch progress point and Chapter Select
offered every chapter.

## Checksums

`pst save-checksum <file>...` names the checksum in a save's last 4 bytes by trying CRC-32
variants, FNV-1 and FNV-1a, Adler-32, Jenkins one-at-a-time, MurmurHash3, byte and word sums, in
either byte order; given several files, it names the one that explains all of them.
