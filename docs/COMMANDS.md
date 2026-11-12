# Commands

Every `pst` command. The environment variables they read are in the [README](../README.md), and
[CONTRIBUTING.md](../CONTRIBUTING.md) sorts the commands by what they touch: offline, reading a
console, starting a payload, writing a console, deleting local data.

| Command | Does |
|---|---|
| `pst status` | Running payloads, autoload list, installed payloads, games, storage |
| `pst payloads` | Each installed payload against its developer's newest GitHub release |
| `pst payload-update <name>` | Installs the developer's newest release after checking GitHub's sha256; Payload Manager updates its own repository's payloads |
| `pst snapshot [--dir D]` | Records console state and developer versions to `$PST_STATE/inventory/<date>.json`, or to `D/<date>.json` |
| `pst dumper` | Starts the App Dumper |
| `pst temps [--watch N] [--count N] [--stop]` | SoC and CPU temperature and CPU clock from shsrv's banner; `--stop` ends shsrv |
| `pst prep <dump>` | Writes `sce_sys/param.json` for a PS4 dump from its `param.sfo` |
| `pst casecheck <dump>` | Lists files the game names with different capitals than the dump has |
| `pst send <dump> [--fself]` | Uploads a dump to `/data/homebrew/<TITLEID>` through a staging folder, sizes checked; `--fself` then fake-signs it with the App Dumper |
| `pst fself <TITLEID>` | Fake-signs a game already in `/data/homebrew` |
| `pst fpkg <dump>... [--plan] [--dir D] [--send [PS4]] [--remove-dump]` | Builds PS4 fake packages from ItemzFlow dumps of base games |
| `pst y2jb [--install [--pkg PKG]] [--icon [PNG]] [--rename]` | Installs notmaj0r's newest Y2JB, sha256 checked, puts our icon on its tile, renames it; see [y2jb.md](y2jb.md) |
| `pst avatar <picture> [--user HEX] [--fill]` | Sets a picture as a user's profile avatar |
| `pst avatar-pack <pack> <picture or folder>... [--fill]` | Stores pictures as ready avatars in `/data/avatars/<pack>/` |
| `pst save-list` | Every game save on the console, by title and slot |
| `pst save-pull <TITLEID> <slot> [--dir D]` | Copies a save, encrypted and decrypted, with a sha256 manifest |
| `pst save-push <dir> <TITLEID> <slot> [--dir D]` | Backs the save up, writes the files in `<dir>` into it and reads them back |
| `pst save-inspect <file>` | Names a save file's format and byte order and lists its field and class names |
| `pst save-convert <in> <out> --to le\|be` | Rewrites an Alchemy IGB or Toys for Bob save in the other byte order |
| `pst save-checksum <file>...` | Names the checksum in a save's last 4 bytes |
| `pst itt-merge <ps5 file> <out> [--source F] [--unlock-all]` | Builds an It Takes Two PS5 save from another platform's progress |

Where each group of commands is explained:

- `status`, `payloads`, `payload-update`, `temps`: [console-setup.md](console-setup.md)
- `prep`, `casecheck`, `send`, `fself`: [game-folders.md](game-folders.md)
- `fpkg`: [fpkg.md](fpkg.md)
- the `save-` commands and `itt-merge`: [saves.md](saves.md)
- `y2jb`: [y2jb.md](y2jb.md)
- `avatar`, `avatar-pack`: [avatars.md](avatars.md)
