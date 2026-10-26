# Console services, ports and endpoints

What `pst` talks to on a jailbroken PS5, so a new command starts from here. The port numbers
in `pst.py` (`PM_PORT`, `DUMPER_PORT`, `GARLIC_PORT`, `FILE_MANAGER_PORT`, `SHSRV_PORT`,
`FTP_PORT`) are the code's source; this table follows them.

| Service | Port | Login | Started by |
|---|---|---|---|
| Payload Manager (itsPLK) | 8084 | none | the WebKit Autoloader or Y2JB |
| ftpsrv (drakmor) | 2121 | anonymous | the autoload list |
| PS5 App Dumper | 8081 | token in its `config.ini` | `pst dumper`, `pst status` reads it when running |
| Garlic SaveMgr | 8082 | none | the `save-` commands |
| ps5-web-file-manager | 8888 | none | `pst y2jb --pkg` |
| shsrv | 2323 | none | `pst temps`; `pst temps --stop` ends it |
| websrv | 8080 | none | the autoload list |
| ShadowMountPlus | 10101 | none | the autoload list |
| elfldr (itsPLK build) | 9021 | none | the autoloaders; accepts connections from the console itself only |
| GoldHEN FTP (PS4) | 2121 | anonymous | GoldHEN |

## Payload Manager, port 8084

- `/version`, `/get_config`, `/sources_list`, `/list_payloads` (with a `meta` map per file)
- `/processes_list`, `/process_kill?pid=`
- `/loadpayload:<path>` starts a payload from its folder under `/data/pldmgr/payloads/`
- `/manage:upload?filename=` with the ELF as the POST body installs a payload

## PS5 App Dumper, port 8081

- `/api/status` answers while it runs
- `/api/library` lists the installed titles, `/api/devices` the storage targets
- `/api/dumps/fself` (form fields `mount`, `dir`, `folder`, `token`) fake-signs a folder in place

## Garlic SaveMgr, port 8082

- `/api/users`, `/api/saves`
- `/api/mount?idx=`, `/api/unmount`
- `/api/download_file?name=`, `/api/upload_file?name=` with the bytes as the POST body

A save is decrypted and re-encrypted for the console's own account, so a pushed file needs no
re-signing. The game must be closed while its save is mounted.

## ps5-web-file-manager, port 8888

- `/api/pkg-info?path=` reads a package's content ID, title ID and version
- `POST /api/install-pkg` with the form field `paths` (one path per line) installs a package
  from internal storage; the reply carries `task_ids`
- `/api/tasks` lists running tasks; a finished task is dropped from the list

## ShadowMountPlus, port 10101

JSON POST bodies, documented in its `docs/api.md`: `games/info`, `games/mount`,
`games/unmount`, `games/delete` (with `"confirm": true`, then `games/storage/status` until
`completed`), `games/uninstall`, `scan`, `storage`. Only one `.ffpfsc` container mounts at a
time; a second answers status 16, "Device busy". If a new folder in `/data/homebrew` is not
registered, ShadowMountPlus is paused by a title it still counts as running; restarting the
payload rescans.

## shsrv, port 2323

Its connection banner carries the model, the system software version, the SoC and CPU
temperatures and the CPU clock, which `pst temps` reads. It is a root shell with no login.

## FTP, port 2121

Full read and write access to the filesystem. `pst` stages every upload under a temporary
name or folder, checks the size and renames it into place, so a dropped connection never
leaves a half-written file where the console reads it.
