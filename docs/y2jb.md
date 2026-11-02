# Y2JB

Y2JB starts the same jailbreak as the WebKit Autoloader (the Relapse kernel exploit, then
elfldr and Payload Manager with its autoload list) from the PS5 YouTube app instead of the
browser; reports through October 2026 call it steadier on 13.x. Both entries can stay
installed; use one per boot.

## The pieces

- The YouTube app `PPSA01650`, an official Sony-signed package; on 13.x only Sony-signed
  packages install, so a modified one is refused. itsPLK's README names version 01.009.253 for
  13.40 to 13.60; Y2JB's code also accepts 01.000.030, which was used on 13.40 and 13.60. One
  01.000.030 package checked here: `UP4381-PPSA01650_00-YOUTUBESIEA00000`, 101,515,264 bytes,
  sha256 `eaf0ba5c1063586ccbf76a5b7fbdfeaed45991176460baad87222ab6bf06bb80`.
- `download0.dat` in `/user/download/PPSA01650/`, YouTube's data image that carries the
  exploit. pst takes it from notmaj0r/Y2JB's newest release, the `download0-pldmgr.zip` build
  that starts Payload Manager; it shows no splash and was reported on 2026-11-02 to jailbreak
  almost at once, where itsPLK's autoloader took 10 to 15 seconds. The release `Relapse`
  (2026-10-27) zip holds only `download0.dat`, sha256
  `17399decc65515de1f456102a931edf2943fc5c19d8827572e3cf215a33c36da`. YouTube writes into the
  image while it runs, so the console's copy stops matching that digest after the first start.

## pst y2jb

`pst y2jb` does what its options say, and refuses to run with none:

- `--install` downloads the newest release's `download0-pldmgr.zip`, checks it against GitHub's
  sha256, refuses unless it holds only `download0.dat`, backs up the console's current
  `download0.dat` to `$PST_STATE/backups/y2jb/<time>/`, then uploads the new one under a
  temporary name and renames it into place. It refuses while a game or app runs, because
  `download0.dat` is YouTube's mounted data while it runs.
- `--pkg <YouTube package>`, with `--install`, first installs a missing YouTube: it stages the
  package in `/data/pkg`, checks it is `PPSA01650`, installs it through the Web File Manager,
  waits until `/user/app/PPSA01650/app.pkg` has the package's size, and deletes the staged copy.
  Deleting the YouTube tile on the console deletes `download0.dat` with it, so this sets
  everything up again.
- `--icon [png]` puts a 512x512 PNG on the tile's `/user/appmeta/PPSA01650/icon0.png`;
  without a file it takes `$PST_STATE/y2jb-icon.png`. notmaj0r's build never touches the icon,
  so it stays until the console rewrites the tile's metadata.
- `--rename` renames the app to "Y2JB" wherever the console shows its name (below).

The console can rewrite the tile's metadata and put YouTube's own icon and name back; this was
seen once on 13.40, with no cause found. `pst y2jb --icon --rename` puts both back.

## Renaming the app

An app's name is kept in seven places: `tbl_contentinfo` (`titleName` and `TITLE`, `TITLE_01`
in `AppInfoJson`), `tbl_conceptmetadata` (`conceptName` and the `concept_name` fields of
`ConceptInfoJson`, with their `size`), and the per-user `tbl_iconinfo_<id>` and
`tbl_concepticoninfo_<id>` in `app.db`; `TITLE`, `TITLE_01` in `appinfo.db`
(`/system_data/priv/mms/`); and `titleName` in the two `param.json` copies under
`/user/appmeta/PPSA01650` and `/system_data/priv/appmeta/PPSA01650`.

`--rename` copies both databases to the PC and refuses unless they hold exactly one row for the
app and every JSON blob it would rewrite comes back byte for byte (the console writes `/` as
`\/`). It edits only those values, runs `PRAGMA integrity_check`, keeps the originals in
`$PST_STATE/backups/y2jb/<time>/`, uploads each file under a temporary name and renames it into
place, and refuses while a game or app runs. A damaged database can delete installed games and
saves, which is why every one of those steps is there.

The home screen groups the titles of one Sony concept on one tile. A PS4 YouTube folder app
(`CUSA01015`) lands in YouTube's concept, so it sits on the same tile. The tile's name and icon
come from the app named in the concept's `metaDataPath`; the rename changes the concept only
when that is `PPSA01650`, and other titles keep their own names. To undo a rename, upload the
backup's `app.db` and `appinfo.db` to `/system_data/priv/mms/` and its two `param.json` files to
their folders with nothing running, then restart.

## Using it

Start YouTube only on a fresh boot. Before the jailbreak nothing answers DNS on 127.0.0.1 (see
[console-setup.md](console-setup.md)), so the app reaches neither youtube.com nor PSN; once
nanoDNS runs, youtube.com resolves, and YouTube opened then can replace `download0.dat` and undo
Y2JB (`pst y2jb --install` puts it back). With PSN blocked the app is never updated; Gezine's
`appinfo.db` edit that pins the version is not needed, and a damaged database can delete
installed games and saves. If YouTube asks to sign in, the account is not activated; fake
activation can break the saves of an account that is already activated.
