# Console setup

How the PS5 side `pst` works with is set up, with the facts measured on a CFI-1116A at 13.40.

## Payloads

What each payload in Payload Manager is for. `pst payloads` compares each installed one with its
developer's newest GitHub release; `pst payload-update <name>` installs that release after
checking GitHub's sha256.

| Payload | Starts at boot | Needed for |
|---|---|---|
| elfldr, Payload Manager | started by the WebKit Autoloader or Y2JB | loading every other payload; the API on 8084 |
| nanoDNS | yes, first | DNS on 127.0.0.1 with ad blocking, PSN and system updates blocked |
| kstuff-lite | yes | running fake-signed games and apps |
| ShadowMountPlus | yes | registering and mounting games and apps from `/data/homebrew`, USB and exFAT images |
| ftpsrv | yes | FTP on 2121, which every upload uses |
| websrv | yes | the Browser tile's start page on 8080, and websrv homebrew |
| PS5 App Dumper | no, `pst dumper` | dumping games and fake-signing folders (`pst fself`) |
| Garlic SaveMgr | no, started by the `save-` commands | decrypting and re-encrypting saves; web UI and API on 8082 |
| klogsrv | no | system log on 3232 for diagnosing crashes |
| shsrv | no, `pst temps` | a root shell on 2323, read only for its banner |

etaHEN and kstuff must not run for a PS5 Linux boot (see [ps5-linux.md](ps5-linux.md)).

## DNS

`dns/nanodns.ini` is a config for the nanoDNS payload, put on the console at
`/data/nanodns/nanodns.ini`. It forwards to AdGuard DNS (ad blocking) with Quad9 as the last
fallback, as plain DNS, and answers PlayStation Network domains with 0.0.0.0, keeping drakmor's
default exceptions. nanoDNS listens on 127.0.0.1; with the PS5's network DNS set to 127.0.0.1
the console has no DNS until nanoDNS runs, which keeps it off PSN before a jailbreak.

## Browser start page

`browser/index.html` is an address box with links for the PS5's built-in browser, kept on the
console at `/data/pst/browser/index.html` and served by websrv on 8080. `browser/tile/` is a
media-app tile (`FAKE00002`) whose `param.json` opens that page; it is uploaded over FTP to
`/data/homebrew/FAKE00002` (`pst send` takes only `PPSA` and `CUSA` title IDs). Its `eboot.bin`
is an empty placeholder because ShadowMountPlus
only registers folders that have one. websrv recreates its own "Homebrew Launcher" tile at start
unless `/user/app/FAKE00000/param.json` exists, so an empty `{}` file there keeps that tile
deleted.

## Temperatures and clocks

`pst temps` gives the SoC and CPU temperature and the CPU clock. The kernel log (ShadowMountPlus
`kernel-log`) has a `[SceSystemStateMgr]` table, printed on every power-mode change, with the
clock of each CPU core, the GPU clock (`GFX`), two more clocks (`F` and `U`, lower at idle),
`FAN` and `BAPM`. Measured on 2026-10-09 on a cleaned CFI-1116A at 13.40:

| State | SoC | CPU | CPU clock | GPU clock |
|---|---|---|---|---|
| Home screen | 37 C | 41 C | 4 cores 800, 4 cores 3200 MHz | 900 MHz |
| A game, steady after 3 minutes | 50 to 52 C | 64 to 67 C | 3200 MHz on all cores | 2230 MHz |

2230 MHz is Sony's published GPU maximum. The stock fan target is 91 C (drakmor's `fan_target`
README), so lowering it only adds fan noise. No homebrew on 13.x raises clocks or lowers
voltage; the boost to 3.5 GHz CPU and 2.23 GHz GPU exists under PS5 Linux.

## Recomp Store

The Recomp Store (`PPSA92000`, elripalda/RecompStore) installs and updates native PS5 ports of
recompiled games; it hosts no game data, and each port takes the game's files from a disc image,
ROM or data you own. Ports land in `/data/homebrew/<TITLEID>`, its state in `/data/recompstore`.
Its release `PPSA92000.zip`, checked against GitHub's sha256, unzipped and sent with `pst send`,
installs it; it updates itself from GitHub after that. It needs kstuff, ShadowMountPlus 1.7 beta
5 or newer, an ELF loader on `127.0.0.1:9021`, and recompstore.com and GitHub reachable. Its
README's `nc <PS5> 9021 < RecompStore-Installer.elf` cannot reach itsPLK's elfldr, which accepts
connections from the console itself only.

## Playden

leolobato/playden-ps5 plays Windows games from your own Steam library through prospero-win, a
Wine port: a native app (`FAKE77031`) plus a runtime kit in `/data/playden/kits/`. Read on
2026-10-14: v0.2.0 was an early alpha tested only on 13.60; the app and the kit move together
(0.2.0 accepts only kit H r8); it has no self-update; it stores the Steam sign-in token
unencrypted on the console, readable by anyone on the network through the login-less FTP; a bug
could overwrite Steam Cloud saves; a running game gets elevated rights.
