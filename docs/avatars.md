# Profile avatars

The PS5 shows a user's avatar from `/system_data/priv/cache/profile/0x<USERID>/`:
`avatar440.dds`, `avatar260.dds`, `avatar128.dds` and `avatar64.dds` (DXT5), the same again as
`picture<size>.dds`, `avatar.png` and `picture.png` at 440x440, and `online.json` (`firstName`,
`lastName`, `isOfficiallyVerified` as the string `"true"`). That is the set notmaj0r/ProsperoMgr
and koolaidxk1d/Hotswap write. A user on a built-in avatar has only `version.json` there. No PSN
connection is needed.

## pst avatar

`pst avatar <picture>` writes that set. The picture is a file on the PC or a console path under
`/data/`. One with a single plain colour in all four corners, like a logo, is trimmed to its
drawing, scaled so the drawing's corners stay inside the round frame the console draws (88% of
the width), and centred on that colour; any other picture is cut to its centred square.
`--fill` skips the trimming, for a picture that is already a finished avatar. The files already
in the folder are copied to `$PST_STATE/backups/avatars/<user>/<time>/` first, and each file is
uploaded under a temporary name and renamed into place. The user is picked automatically when
the console has one; `--user` names it otherwise. On 2026-10-14 on 13.40 an avatar set this way
showed at once, without a restart. To undo, put the backup's files back.

## Choosing on the console

No app or payload that picks an avatar on the console worked on 13.40 when searched
(2026-10-14): Lapy's Avatar Changer reads `.xavatar` files from `/data/AVATARS/` but is a
package documented for 3.xx to 5.xx, and ProsperoMgr takes its picture as a browser upload.

`pst avatar-pack <pack> <pictures or folders>` writes each picture's full file set into
`/data/avatars/<pack>/<name>/` (staged as `<name>.part` and renamed when complete; a name
already there is skipped). On the PS5, open the Web File Manager tile, go into an avatar's
folder (it previews `avatar.png`), select every file, Copy, go to
`/system_data/priv/cache/profile/0x<USERID>/` and Paste over the files there. On 2026-10-14 on
13.40, copying a pack folder in this way showed at once. Pack folders carry an empty
`firstName` in `online.json`; `pst avatar` writes the user's name.

Lapy's `.xavatar` "online" sets hold the same eleven files in DXT1 and an `online.json` that also
carries `avatarUrl`, `pictureUrl` and `trophySummary`; ProsperoMgr writes only the three keys
`pst` writes. Use pictures you made or have the right to use.
