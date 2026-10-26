import argparse
import datetime
import ftplib
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
import zipfile
import zlib

from PIL import Image, ImageChops

MIRROR = "https://itsplk.github.io/ps5-payloads-mirror/payloads.json"
GITHUB_API = "https://api.github.com/repos/"
PM_PORT = 8084
DUMPER_PORT = 8081
GARLIC_PORT = 8082
FILE_MANAGER_PORT = 8888
SHSRV_PORT = 2323
FTP_PORT = 2121
IGB_MAGIC_OFFSET = 0x28
PS4_PKG_DIR = "/data/pkg"
FSELF_PAID = 0x3100000000000002
FSELF_PTYPE_FAKE = 1
ELF_TYPES = (0x2, 0xFE00, 0xFE10, 0xFE18)
SELF_SEGMENT_TYPES = (0x1, 0x61000010, 0x61000000, 0x6FFFFF00)
PT_SCE_VERSION = 0x6FFFFF01
SELF_MAGIC = b"\x4f\x15\x3d\x1d"
FPKG_SKIP = {
    "sce_sys/.digests",
    "sce_sys/.entry_keys",
    "sce_sys/.image_key",
    "sce_sys/.unknown_0x21",
    "sce_sys/.general_digests",
    "sce_sys/.unknown_0xC0",
    "sce_sys/.metas",
    "sce_sys/.entry_names",
    "sce_sys/license.dat",
    "sce_sys/license.info",
    "sce_sys/selfinfo.dat",
    "sce_sys/imageinfo.dat",
    "sce_sys/target-deltainfo.dat",
    "sce_sys/origin-deltainfo.dat",
    "sce_sys/psreserved.dat",
    "sce_sys/playgo-chunk.dat",
    "sce_sys/playgo-chunk.sha",
    "sce_sys/playgo-manifest.xml",
    "sce_sys/pubtoolinfo.dat",
    "sce_sys/app/playgo-chunk.dat",
    "sce_sys/app/playgo-chunk.sha",
    "sce_sys/app/playgo-manifest.xml",
    "sce_sys/icon0.dds",
    "sce_sys/pic0.dds",
    "sce_sys/pic1.dds",
    "sce_discmap.plt",
    "sce_discmap_patch.plt",
}
FPKG_SKIP |= {path + ".encrypted" for path in FPKG_SKIP}
FPKG_SKIP |= {
    f"sce_sys/{name}_{index:02d}.dds"
    for name in ("icon0", "pic1")
    for index in range(31)
}
HOMEBREW = "/data/homebrew"
Y2JB_REPO = "itsPLK/ps5-y2jb-autoloader"
Y2JB_TITLE = "PPSA01650"
Y2JB_STATE_ICON = "y2jb-icon.png"
Y2JB_ICON_SIZE = (512, 512)
Y2JB_UPDATE = "/data/y2jb_update.zip"
Y2JB_DOWNLOAD0 = "/user/download/PPSA01650/download0.dat"
Y2JB_TILE_ICON = "/user/appmeta/PPSA01650/icon0.png"
Y2JB_APP_PKG = "/user/app/PPSA01650/app.pkg"
Y2JB_NAME = "Y2JB"
Y2JB_PARAMS = (
    "/user/appmeta/PPSA01650/param.json",
    "/system_data/priv/appmeta/PPSA01650/param.json",
)
APP_DATABASES = "/system_data/priv/mms"
USER_HOMES = "/system_data/priv/home"
PROFILE_CACHE = "/system_data/priv/cache/profile"
AVATAR_SIZES = (440, 260, 128, 64)
AVATAR_CIRCLE = 0.88
AVATAR_LIBRARY = "/data/avatars"
PICTURE_SUFFIXES = (".png", ".jpg", ".jpeg")
PKG_STAGING = "/data/pkg"
SEND_STAGING = "/data/pst-staging"
DUMPER_CONFIG = "/data/homebrew/ps5-app-dumper/config.ini"
SFO_LOCALES = (
    "ja-JP",
    "en-US",
    "fr-FR",
    "es-ES",
    "de-DE",
    "it-IT",
    "nl-NL",
    "pt-PT",
    "ru-RU",
    "ko-KR",
    "zh-Hant",
    "zh-Hans",
    "fi-FI",
    "sv-SE",
    "da-DK",
    "no-NO",
    "pl-PL",
    "pt-BR",
    "en-GB",
    "tr-TR",
    "es-419",
    "ar-AE",
    "fr-CA",
    "cs-CZ",
    "hu-HU",
    "el-GR",
    "ro-RO",
    "th-TH",
    "vi-VN",
    "id-ID",
)


class Fail(Exception):
    pass


def host():
    return address("PST_PS5", "the PS5")


def address(variable, console):
    value = os.environ.get(variable, "").strip()
    if not value:
        raise Fail(f"{variable} is not set; set it to {console}'s address")
    return value


def state_dir(*parts):
    root = os.environ.get("PST_STATE") or os.path.join(
        os.environ.get("XDG_STATE_HOME")
        or os.path.join(os.path.expanduser("~"), ".local", "state"),
        "pst",
    )
    if not os.path.isabs(root):
        raise Fail(
            f"the state folder {root!r} is not an absolute path; set PST_STATE or HOME"
        )
    return os.path.join(root, *parts)


def http(url, data=None, headers=None, timeout=30):
    headers = dict(headers or {})
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and url.startswith(GITHUB_API):
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        reset = error.headers.get("X-RateLimit-Reset")
        hint = ""
        if reset:
            hint = f"; GitHub limit resets at {datetime.datetime.fromtimestamp(int(reset)).strftime('%H:%M')}, or set GITHUB_TOKEN"
        raise Fail(f"{url}: HTTP {error.code:d} {error.reason}{hint}") from error
    except urllib.error.URLError as error:
        raise Fail(f"{url}: {error.reason}") from error


def http_json(url, **kwargs):
    return json.loads(http(url, **kwargs))


def ftp(address=None):
    connection = ftplib.FTP()
    connection.connect(address or host(), FTP_PORT, timeout=30)
    connection.login()
    return connection


def ftp_read(path):
    buffer = io.BytesIO()
    with ftp() as connection:
        connection.retrbinary("RETR " + path, buffer.write)
    return buffer.getvalue()


def ftp_dirs(path):
    with ftp() as connection:
        return sorted(
            posixpath.basename(name)
            for name, facts in connection.mlsd(path)
            if facts.get("type") == "dir"
        )


def ftp_size(path):
    with ftp() as connection:
        connection.voidcmd("TYPE I")
        try:
            return connection.size(path)
        except ftplib.error_perm as error:
            if not ftp_absent(error):
                raise
            return None


def ftp_absent(error):
    return str(error).startswith("550")


def ftp_exists(connection, remote):
    try:
        connection.size(remote)
    except ftplib.error_perm as error:
        if not ftp_absent(error):
            raise
        return False
    return True


def ftp_makedirs(connection, path):
    current = ""
    for part in path.strip("/").split("/"):
        current += "/" + part
        try:
            connection.cwd(current)
        except ftplib.error_perm as error:
            if not ftp_absent(error):
                raise
            connection.mkd(current)


def ftp_store(connection, remote, source, expected):
    try:
        connection.storbinary("STOR " + remote, source, blocksize=1 << 20)
        size = connection.size(remote)
    except (OSError, ftplib.Error) as error:
        raise Fail(
            f"upload of {remote} failed ({error}); {ftp_remove_partial(connection, remote)}"
        ) from error
    if size != expected:
        raise Fail(
            f"size mismatch after upload: {remote} has {size} bytes, not {expected:d}; {ftp_remove_partial(connection, remote)}"
        )


def ftp_put(remote, data):
    with ftp() as connection:
        connection.voidcmd("TYPE I")
        ftp_makedirs(connection, posixpath.dirname(remote))
        ftp_store(connection, remote, io.BytesIO(data), len(data))


def ftp_replace(remote, data):
    staged = remote + ".pst-new"
    ftp_put(staged, data)
    with ftp() as connection:
        try:
            connection.rename(staged, remote)
        except (OSError, ftplib.Error) as error:
            raise Fail(
                f"could not swap {remote} into place ({error}); {ftp_remove_partial(connection, staged)}"
            ) from error


def ftp_remove_partial(connection, remote):
    try:
        connection.delete(remote)
    except (OSError, ftplib.Error) as error:
        return f"could not delete the partial {remote} ({error})"
    return "deleted the partial " + remote


def ftp_remove_dir_if_empty(connection, path):
    if not [
        name
        for name in connection.nlst(path)
        if posixpath.basename(name) not in (".", "..")
    ]:
        connection.rmd(path)


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def write_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as output:
        output.write(data)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pm(path, **kwargs):
    return http_json(f"http://{host()}:{PM_PORT:d}{path}", **kwargs)


def load_payload(folder):
    paths = [path for path in pm("/list_payloads")["payloads"] if f"/{folder}/" in path]
    if len(paths) != 1:
        raise Fail(f"expected one {folder} payload, found {len(paths):d}")
    http(f"http://{host()}:{PM_PORT:d}/loadpayload:{paths[0]}")
    return paths[0]


def game_running():
    return any(
        item["name"] == "eboot.bin" for item in pm("/processes_list")["processes"]
    )


def dumper(path, **kwargs):
    return http_json(f"http://{host()}:{DUMPER_PORT:d}{path}", **kwargs)


def answers(request, path):
    try:
        request(path, timeout=5)
    except Fail:
        return False
    return True


def start_payload(folder, running, name, port):
    if running():
        return
    load_payload(folder)
    for _attempt in range(30):
        time.sleep(1)
        if running():
            return
    raise Fail(f"{name} did not answer on port {port:d}")


def dumper_running():
    return answers(dumper, "/api/status")


def dumper_token():
    config = ftp_read(DUMPER_CONFIG).decode("utf-8")
    match = re.search(r"^access_token\s*=\s*([0-9a-f]+)\s*$", config, re.M)
    if not match:
        raise Fail("no access_token in " + DUMPER_CONFIG)
    return match.group(1)


def garlic_url(path):
    return f"http://{host()}:{GARLIC_PORT:d}{path}"


def garlic(path, **kwargs):
    return http_json(garlic_url(path), **kwargs)


def garlic_running():
    return answers(garlic, "/api/users")


def file_manager(path, **kwargs):
    return http_json(f"http://{host()}:{FILE_MANAGER_PORT:d}{path}", **kwargs)


def file_manager_running():
    return answers(file_manager, "/api/tasks")


def shsrv_banner():
    connection = socket.create_connection((host(), SHSRV_PORT), timeout=8)
    data = b""
    try:
        while b"Type 'help'" not in data:
            chunk = connection.recv(4096)
            if not chunk:
                break
            data += chunk
    except TimeoutError:
        raise Fail("shsrv sent no complete banner within 8 s") from None
    finally:
        connection.close()
    return data.decode("utf-8", "replace")


def shsrv_running():
    try:
        socket.create_connection((host(), SHSRV_PORT), timeout=3).close()
    except OSError:
        return False
    return True


def stop_shsrv():
    pids = [
        item["pid"]
        for item in pm("/processes_list")["processes"]
        if item["name"] == "shsrv.elf"
    ]
    if len(pids) != 1:
        raise Fail(f"expected one shsrv.elf process, found {len(pids):d}")
    reply = pm(f"/process_kill?pid={pids[0]:d}")
    if not reply.get("ok"):
        raise Fail(f"Payload Manager could not stop shsrv: {reply!r}")


def mirror_entries():
    return {entry["name"]: entry for entry in http_json(MIRROR)}


def newest_release(repo, releases):
    published = [
        release
        for release in releases
        if not release.get("draft") and release.get("published_at")
    ]
    if not published:
        raise Fail("no published releases for " + repo)
    return max(published, key=lambda release: release["published_at"])


def github_latest(repo):
    return newest_release(repo, http_json(GITHUB_API + repo + "/releases?per_page=20"))


def repo_of(url):
    match = re.match(r"https://github\.com/([^/]+/[^/]+)", url or "")
    return match.group(1) if match else ""


def pick_asset(entry, release):
    direct = entry.get("source_direct", "")
    match = re.search(r"/releases/download/([^/]+)/([^/]+)$", direct)
    binaries = [
        asset for asset in release["assets"] if asset["name"].endswith((".elf", ".bin"))
    ]
    if match:
        old_tag, old_name = match.groups()
        wanted = old_name.replace(old_tag, "")
        for asset in binaries:
            if asset["name"].replace(release["tag_name"], "") == wanted:
                return asset
    if len(binaries) == 1:
        return binaries[0]
    names = ", ".join(asset["name"] for asset in release["assets"])
    raise Fail("cannot pick the payload file among: " + names)


def release_asset(release, name):
    for asset in release["assets"]:
        if asset["name"] == name:
            return asset
    raise Fail(f"release {release['tag_name']} has no {name}")


def verified_download(asset):
    digest = asset.get("digest") or ""
    if not digest.startswith("sha256:"):
        raise Fail(f"{asset['name']} has no GitHub sha256 digest; refusing")
    data = http(asset["browser_download_url"], timeout=900)
    if hashlib.sha256(data).hexdigest() != digest[len("sha256:") :]:
        raise Fail("checksum mismatch for " + asset["name"])
    return data


def installed_payloads():
    listing = pm("/list_payloads")
    mirror = mirror_entries()
    result = []
    for path in listing["payloads"]:
        filename = posixpath.basename(path)
        meta = listing.get("meta", {}).get(filename, {})
        name = meta.get("display_name") or ""
        if not name or name.endswith((".elf", ".bin")):
            name = posixpath.basename(posixpath.dirname(path))
        stem = posixpath.splitext(filename)[0]
        version = meta.get("version") or stem[len(name) + 1 :]
        source = repo_of(meta.get("source")) or repo_of(
            mirror.get(name, {}).get("source")
        )
        result.append(
            {
                "name": name,
                "file": filename,
                "version": version,
                "source": "https://github.com/" + source if source else "",
            }
        )
    return result


def collect_status():
    report = {
        "host": host(),
        "pm_version": http(f"http://{host()}:{PM_PORT:d}/version").decode().strip(),
        "config": pm("/get_config"),
        "sources": pm("/sources_list")["sources"],
        "daemons": sorted(
            item["name"]
            for item in pm("/processes_list")["processes"]
            if item["is_daemon"]
        ),
        "payloads": installed_payloads(),
        "homebrew": [name for name in ftp_dirs(HOMEBREW) if name != "ps5-app-dumper"],
        "library": None,
        "storage": [],
    }
    if dumper_running():
        report["library"] = dumper("/api/library")["titles"]
        report["storage"] = dumper("/api/devices")["targets"]
    return report


def cmd_status(_args):
    report = collect_status()
    print(f"Payload Manager {report['pm_version']} on {host()}")
    print("autoload: " + report["config"].get("AUTOLOAD_LIST", ""))
    print("running: " + ", ".join(report["daemons"]))
    print("payloads:")
    for item in report["payloads"]:
        print(f"  {item['name']!s:<30} {item['file']}")
    print(f"games in {HOMEBREW}: {', '.join(report['homebrew'])}")
    if report["library"] is None:
        print("App Dumper not running; start it with: pst dumper")
        return
    for title in report["library"]:
        print(
            f"  {title['titleId']} {title['title']!s:<30} {title.get('mountedFrom', '')}"
        )
    for target in report["storage"]:
        print(
            f"storage {target['mount']!s:<10} free {target['freeBytes'] / 1000000000.0:6.1f} GB of {target['totalBytes'] / 1000000000.0:6.1f} GB"
        )


def payload_current(installed, tag):
    return bool(installed) and installed.lstrip("v") == tag.lstrip("v")


def cmd_payloads(_args):
    for item in installed_payloads():
        repo = repo_of(item["source"])
        if not repo:
            print(f"{item['name']!s:<30} {item['version']!s:<16} source unknown")
            continue
        latest = github_latest(repo)
        mark = (
            "current"
            if payload_current(item["version"], latest["tag_name"])
            else "UPDATE"
        )
        print(
            f"{item['name']!s:<30} {item['version'] or '?'!s:<16} latest {latest['tag_name']!s:<16} {mark}{(' (pre-release)' if latest['prerelease'] else '')}"
        )


def cmd_payload_update(args):
    entry = mirror_entries().get(args.name)
    if not entry:
        raise Fail(f"unknown payload {args.name!r}; see: pst payloads")
    repo = repo_of(entry.get("source"))
    release = github_latest(repo)
    asset = pick_asset(entry, release)
    data = verified_download(asset)
    extension = posixpath.splitext(asset["name"])[1]
    filename = f"{args.name}_{release['tag_name']}{extension}"
    query = urllib.parse.urlencode({"filename": filename})
    reply = http(
        f"http://{host()}:{PM_PORT:d}/manage:upload?{query}",
        data=data,
        headers={"Content-Type": "application/octet-stream"},
    )
    if reply.strip() != b"OK":
        raise Fail(f"upload refused: {reply!r}")
    print(
        f"installed {filename} ({repo}, sha256 verified){(' pre-release' if release['prerelease'] else '')}"
    )


def cmd_snapshot(args):
    report = collect_status()
    report["latest"] = {}
    for item in report["payloads"]:
        repo = repo_of(item["source"])
        if repo:
            release = github_latest(repo)
            report["latest"][item["name"]] = {
                "repo": "https://github.com/" + repo,
                "tag": release["tag_name"],
                "prerelease": release["prerelease"],
                "published": release["published_at"],
            }
    today = datetime.date.today().isoformat()
    folder = args.dir or state_dir("inventory")
    path = os.path.join(folder, today + ".json")
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print("wrote " + path)


def cmd_dumper(_args):
    if dumper_running():
        print("App Dumper already running")
        return
    print("App Dumper started: " + load_payload("ps5-app-dumper"))


def parse_temps(text):
    patterns = {
        "soc": r"SoC temp:\s+(-?\d+)",
        "cpu": r"CPU temp:\s+(-?\d+)",
        "freq": r"CPU freq:\s+(\d+) MHz",
        "model": r"Model:\s+(.+)",
        "firmware": r"S/W:\s+(\S+)",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            values[key] = match.group(1).strip()
    if "soc" not in values or "cpu" not in values:
        raise Fail("shsrv answered without temperatures")
    return values


def cmd_temps(args):
    if args.stop:
        stop_shsrv()
        print("shsrv stopped")
        return
    start_payload("shsrv", shsrv_running, "shsrv", SHSRV_PORT)
    for number in range(args.count):
        values = parse_temps(shsrv_banner())
        if number == 0:
            print(f"{values.get('model', '?')}, firmware {values.get('firmware', '?')}")
        print(
            f"{time.strftime('%H:%M:%S')} SoC {values['soc']} C, CPU {values['cpu']} C, CPU {values.get('freq', '?')} MHz"
        )
        if number + 1 < args.count:
            time.sleep(args.watch)


def parse_sfo(data):
    magic, _, keys, values, count = struct.unpack_from("<4sIIII", data, 0)
    if magic != b"\x00PSF":
        raise Fail("not a param.sfo: bad magic")
    result = {}
    for index in range(count):
        key_off, fmt, length, _, data_off = struct.unpack_from(
            "<HHIII", data, 20 + index * 16
        )
        start = keys + key_off
        key = data[start : data.index(b"\x00", start)].decode("ascii")
        raw = data[values + data_off : values + data_off + length]
        if fmt == 0x0404:
            result[key] = struct.unpack("<I", raw)[0]
        else:
            result[key] = raw.split(b"\x00", 1)[0].decode("utf-8")
    return result


def sfo_text(values, key):
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def param_json(values):
    title_id = sfo_text(values, "TITLE_ID")
    if not re.fullmatch(r"CUSA\d{5}", title_id):
        raise Fail(f"TITLE_ID is not a PS4 title id: {title_id!r}")
    order = ["TITLE", "TITLE_01"] + [f"TITLE_{i:02d}" for i in range(30)]
    names = [sfo_text(values, key) for key in [*order, "CONTENT_ID"]]
    title = next((name for name in names if name), title_id)
    localized = {
        locale: {"titleName": sfo_text(values, f"TITLE_{index:02d}")}
        for index, locale in enumerate(SFO_LOCALES)
        if sfo_text(values, f"TITLE_{index:02d}")
    }
    localized["en-US"] = {"titleName": sfo_text(values, "TITLE_01") or title}
    localized["defaultLanguage"] = "en-US"
    payload = {
        "localizedParameters": localized,
        "titleId": title_id,
        "titleName": title,
    }
    for index in range(1, 5):
        value = values.get(f"USER_DEFINED_PARAM_{index:d}")
        if isinstance(value, int) and value:
            payload[f"userDefinedParam{index:d}"] = value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def cmd_prep(args):
    root = os.path.abspath(args.path)
    target = os.path.join(root, "sce_sys", "param.json")
    if os.path.exists(target):
        print("already has sce_sys/param.json: " + root)
        return
    sfo = os.path.join(root, "sce_sys", "param.sfo")
    if not os.path.isfile(sfo):
        raise Fail("no sce_sys/param.json or param.sfo in " + root)
    if not os.path.isfile(os.path.join(root, "eboot.bin")):
        raise Fail("no eboot.bin in " + root)
    with open(sfo, "rb") as source:
        text = param_json(parse_sfo(source.read()))
    with open(target, "x", encoding="utf-8") as output:
        output.write(text + "\n")
    print("wrote " + target)


APP_PATH = re.compile(rb"app0?:/([A-Za-z0-9_./-]+)")


def case_mismatches(root, eboot_bytes):
    present = {}
    for current, _dirs, files in os.walk(root):
        for name in files:
            relative = os.path.relpath(os.path.join(current, name), root)
            present.setdefault(relative.lower(), set()).add(relative)
    wanted = {m.group(1).decode() for m in APP_PATH.finditer(eboot_bytes)}
    return sorted(
        (path, sorted(present[path.lower()])[0])
        for path in wanted
        if path.lower() in present and path not in present[path.lower()]
    )


def cmd_casecheck(args):
    root = os.path.abspath(args.path)
    eboot = os.path.join(root, "eboot.bin")
    if not os.path.isfile(eboot):
        raise Fail("no eboot.bin in " + root)
    with open(eboot, "rb") as source:
        found = case_mismatches(root, source.read())
    if not found:
        print("ok: no file the game names differs only in case")
        return
    print("the game names these files with different case than the dump:")
    for wanted, actual in found:
        print(f"  {wanted}  (dump has {actual})")
    print(
        "internal PS5 storage is case-sensitive: run it from exFAT USB "
        "or an exFAT image (see README)"
    )


def title_id_of(root):
    with open(os.path.join(root, "sce_sys", "param.json"), encoding="utf-8") as source:
        title_id = json.load(source).get("titleId", "")
    if not re.fullmatch(r"(PPSA|CUSA)\d{5}", title_id):
        raise Fail(f"bad titleId in param.json: {title_id!r}")
    return title_id


def cmd_send(args):
    root = os.path.abspath(args.path)
    if not os.path.isfile(os.path.join(root, "sce_sys", "param.json")):
        raise Fail("no sce_sys/param.json; run: pst prep " + args.path)
    title_id = title_id_of(root)
    if title_id in ftp_dirs(HOMEBREW):
        raise Fail(f"{HOMEBREW}/{title_id} already exists on the console")
    remote_root = posixpath.join(HOMEBREW, title_id)
    staged_root = posixpath.join(SEND_STAGING, title_id)
    total = 0
    with ftp() as connection:
        connection.voidcmd("TYPE I")
        for current, dirs, files in os.walk(root):
            dirs.sort()
            relative = os.path.relpath(current, root)
            remote = (
                staged_root
                if relative == "."
                else posixpath.join(staged_root, *relative.split(os.sep))
            )
            ftp_makedirs(connection, remote)
            for name in sorted(files):
                local = os.path.join(current, name)
                size = os.path.getsize(local)
                with open(local, "rb") as source:
                    ftp_store(connection, posixpath.join(remote, name), source, size)
                total += size
        connection.rename(staged_root, remote_root)
        ftp_remove_dir_if_empty(connection, SEND_STAGING)
    print(
        f"sent {title_id} to {remote_root} ({total / 1000000000.0:.2f} GB, sizes verified)"
    )
    if args.fself:
        fself(title_id)


def fself(title_id):
    if not dumper_running():
        raise Fail("App Dumper not running; start it with: pst dumper")
    body = urllib.parse.urlencode(
        {
            "mount": "/data",
            "dir": "homebrew",
            "folder": title_id,
            "token": dumper_token(),
        }
    ).encode()
    reply = dumper("/api/dumps/fself", data=body, timeout=600)
    print(
        f"FSELF {title_id}: {reply.get('converted')} converted, {reply.get('skipped')} skipped"
    )


def cmd_fself(args):
    fself(args.title_id)


def align_up(value, step):
    return (value + step - 1) & ~(step - 1)


def fake_self(elf):
    if len(elf) < 0x40 or elf[:4] != b"\x7fELF":
        raise Fail("not an ELF")
    ident = struct.unpack_from("<4s5B6xB", elf, 0)
    header = list(struct.unpack_from("<2HI3QI6H", elf, 16))
    elf_type, machine, version = header[0:3]
    phoff, ehsize, phentsize, phnum, shentsize = (
        header[4],
        header[7],
        header[8],
        header[9],
        header[10],
    )
    if ident[1] != 2 or ident[2] != 1 or machine != 0x3E or version != 1:
        raise Fail("not a little-endian x86-64 ELF64")
    if elf_type not in ELF_TYPES:
        raise Fail(f"unsupported ELF type 0x{elf_type:X}")
    if phentsize != 0x38 or shentsize not in (0, 0x40):
        raise Fail("unsupported ELF header entry size")
    if phoff + phentsize * phnum > len(elf):
        raise Fail("program headers past the end of the file")
    phdrs = [
        struct.unpack_from("<2I6Q", elf, phoff + index * phentsize)
        for index in range(phnum)
    ]
    segments = [elf[phdr[2] : phdr[2] + phdr[5]] for phdr in phdrs]
    used = (*SELF_SEGMENT_TYPES, PT_SCE_VERSION)
    if any(
        len(data) != phdr[5]
        for data, phdr in zip(segments, phdrs, strict=True)
        if phdr[0] in used
    ):
        raise Fail("a segment runs past the end of the file")
    version_data = None
    for phdr, data in zip(phdrs, segments, strict=True):
        if phdr[0] == PT_SCE_VERSION:
            version_data = data
    kept = [index for index, phdr in enumerate(phdrs) if phdr[0] in SELF_SEGMENT_TYPES]
    count = 2 * len(kept)
    elf_headers = align_up(max(ehsize, phoff + phentsize * phnum), 16)
    header_size = 0x20 + 0x20 * count + elf_headers + 0x40 + 0x30
    meta_size = 0x50 * count + 0x50 + 0x100
    if header_size > 0xFFFF or meta_size > 0xFFFF:
        raise Fail("too many segments for a SELF header")
    entries, blobs = b"", []
    offset = header_size + meta_size
    for number, index in enumerate(kept):
        size = phdrs[index][5]
        digests = bytes(0x20 * (align_up(size, 0x4000) // 0x4000))
        entries += struct.pack(
            "<4Q",
            0x10004 | ((2 * number + 1) << 20),
            offset,
            len(digests),
            len(digests),
        )
        blobs.append((offset, digests))
        offset = align_up(offset + len(digests), 16)
        entries += struct.pack(
            "<4Q", 0x2804 | ((index & 0xFFFF) << 20), offset, size, size
        )
        blobs.append((offset, segments[index]))
        offset = align_up(offset + size, 16)
    out = bytearray()

    def put(position, data):
        if data:
            if position > len(out):
                out.extend(bytes(position - len(out)))
            out[position : position + len(data)] = data
        return position + len(data)

    cursor = put(
        0,
        b"".join(
            [
                struct.pack("<4s4B", SELF_MAGIC, 0, 1, 1, 0x12),
                struct.pack(
                    "<I2HQ2H4x", 0x101, header_size, meta_size, offset, count, 0x22
                ),
                entries,
            ]
        ),
    )
    header[11] = 0
    put(
        cursor,
        b"".join(
            [
                struct.pack(
                    "<4s5B6xB",
                    ident[0],
                    ident[1],
                    ident[2],
                    version,
                    ident[4],
                    ident[5],
                    ident[6],
                ),
                struct.pack("<2HI3QI6H", *header),
            ]
        ),
    )
    for index, phdr in enumerate(phdrs):
        put(cursor + phoff + index * phentsize, struct.pack("<2I6Q", *phdr))
    cursor = put(
        cursor + elf_headers,
        b"".join(
            [
                struct.pack(
                    "<4Q32s",
                    FSELF_PAID,
                    FSELF_PTYPE_FAKE,
                    0,
                    0,
                    hashlib.sha256(elf).digest(),
                ),
                struct.pack("<H14x19s13s", 3, b"", b""),
                bytes(0x50 * count),
                struct.pack("<48xI28x", 0x10000),
                bytes(0x100),
            ]
        ),
    )
    for position, data in blobs:
        cursor = put(position, data)
    if version_data is not None:
        put(cursor, version_data)
    return bytes(out)


def fpkg_skipped(relative):
    return any(
        [
            relative in FPKG_SKIP,
            relative == "sce_sys/about",
            relative.startswith("sce_sys/about/"),
            "/" not in relative and relative.endswith(".gp4"),
        ]
    )


def fpkg_plan(root):
    files, dirs, encrypted = [], [], []
    for current, subdirs, names in os.walk(root):
        subdirs.sort()
        base = os.path.relpath(current, root).replace(os.sep, "/")
        base = "" if base == "." else base + "/"
        subdirs[:] = [name for name in subdirs if not fpkg_skipped(base + name)]
        dirs.extend(base + name for name in subdirs)
        for name in sorted(names):
            relative = base + name
            if fpkg_skipped(relative):
                continue
            with open(os.path.join(current, name), "rb") as source:
                magic = source.read(4)
            if magic == SELF_MAGIC:
                encrypted.append(relative)
            files.append((relative, magic == b"\x7fELF"))
    named = [path for path, _ in files] + dirs
    unreadable = [path for path in named if not path.isascii()]
    if unreadable:
        raise Fail(
            f"pkgtool writes names as ASCII and would rename: {', '.join(unreadable[:5])}"
        )
    return files, dirs, encrypted


def gp4_xml(content_id, c_date, files, dirs):
    project = ElementTree.Element("psproject", fmt="gp4", version="1000")
    volume = ElementTree.SubElement(project, "volume")
    ElementTree.SubElement(volume, "volume_type").text = "pkg_ps4_app"
    ElementTree.SubElement(volume, "volume_id").text = "PS4VOLUME"
    ElementTree.SubElement(volume, "volume_ts").text = c_date + " 00:00:00"
    ElementTree.SubElement(
        volume,
        "package",
        content_id=content_id,
        passcode="0" * 32,
        storage_type="digital50",
        app_type="full",
        c_date=c_date,
    )
    chunk_info = ElementTree.SubElement(
        volume, "chunk_info", chunk_count="1", scenario_count="1"
    )
    chunks = ElementTree.SubElement(chunk_info, "chunks")
    ElementTree.SubElement(chunks, "chunk", id="0", layer_no="0", label="Chunk #0")
    scenarios = ElementTree.SubElement(chunk_info, "scenarios", default_id="0")
    ElementTree.SubElement(
        scenarios,
        "scenario",
        id="0",
        type="sp",
        initial_chunk_count="1",
        label="Scenario #0",
    ).text = "0"
    listing = ElementTree.SubElement(project, "files", img_no="0")
    for target, source in files:
        ElementTree.SubElement(listing, "file", targ_path=target, orig_path=source)
    rootdir = ElementTree.SubElement(project, "rootdir")
    nodes = {"": rootdir}
    for path in sorted(dirs):
        parent, _, name = path.rpartition("/")
        nodes[path] = ElementTree.SubElement(nodes[parent], "dir", targ_name=name)
    ElementTree.indent(project)
    return ElementTree.tostring(project, encoding="utf-8", xml_declaration=True)


def pubtool_date(values):
    match = re.search(
        r"(?:^|,)c_date=(\d{4})(\d{2})(\d{2})(?:,|$)", sfo_text(values, "PUBTOOLINFO")
    )
    if match:
        return "-".join(match.groups())
    return datetime.date.today().isoformat()


def fpkg_need(root, files, dirs):
    total = (len(dirs) + 1) * 0x10000
    for relative, is_elf in files:
        size = os.path.getsize(os.path.join(root, *relative.split("/")))
        if is_elf:
            size += size // 0x200 + 0x10000
            total += size
        total += align_up(size, 0x10000)
    return total + total // 50 + 0x8000000


def existing_parent(path):
    while not os.path.isdir(path):
        path = os.path.dirname(path)
    return path


def inside(path, root):
    current = os.path.realpath(existing_parent(path))
    while True:
        if os.path.samefile(current, root):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def fpkg_candidates(chosen, root):
    if chosen:
        return [os.path.abspath(chosen)]
    return [os.path.dirname(root), state_dir("fpkg")]


def fpkg_out_dir(chosen, root, need, reserved):
    report = []
    for candidate in fpkg_candidates(chosen, root):
        parent = existing_parent(candidate)
        device = os.stat(parent).st_dev
        free = shutil.disk_usage(parent).free - reserved.get(device, 0)
        if free >= need and os.access(parent, os.W_OK):
            reserved[device] = reserved.get(device, 0) + need
            return candidate
        report.append(f"{candidate}: {free / 1000000000.0:.1f} GB free")
    raise Fail(
        f"not enough space for {need / 1000000000.0:.1f} GB: {'; '.join(report)}"
    )


def ftp_send_pkg(address, local):
    remote = posixpath.join(PS4_PKG_DIR, os.path.basename(local))
    with ftp(address) as connection:
        connection.voidcmd("TYPE I")
        ftp_makedirs(connection, PS4_PKG_DIR)
        if ftp_exists(connection, remote):
            raise Fail(f"{remote} already exists on {address}")
        with open(local, "rb") as source:
            ftp_store(connection, remote, source, os.path.getsize(local))
    return remote


def fpkg_game(root):
    if os.path.exists(root + ".dumping"):
        raise Fail(f"{root}.dumping exists: ItemzFlow has not finished this dump")
    sfo_path = os.path.join(root, "sce_sys", "param.sfo")
    if not os.path.isfile(sfo_path):
        raise Fail("no sce_sys/param.sfo in " + root)
    if not os.path.isfile(os.path.join(root, "eboot.bin")):
        raise Fail("no eboot.bin in " + root)
    with open(sfo_path, "rb") as source:
        values = parse_sfo(source.read())
    content_id = sfo_text(values, "CONTENT_ID")
    if not re.fullmatch(r"[A-Z]{2}\d{4}-[A-Z]{4}\d{5}_00-[A-Z0-9]{16}", content_id):
        raise Fail(f"CONTENT_ID is not a PS4 content id: {content_id!r}")
    category = sfo_text(values, "CATEGORY")
    if category != "gd":
        raise Fail(
            f"CATEGORY is {category!r}, not a base game (gd); pass the base game dump, not its update"
        )
    files, dirs, encrypted = fpkg_plan(root)
    if encrypted:
        raise Fail(f"still encrypted (SELF), dump again: {', '.join(encrypted)}")
    return {
        "root": root,
        "values": values,
        "content_id": content_id,
        "title": sfo_text(values, "TITLE") or content_id,
        "files": files,
        "dirs": dirs,
        "need": fpkg_need(root, files, dirs),
    }


def fpkg_built(chosen, game):
    for candidate in fpkg_candidates(chosen, game["root"]):
        pkg = os.path.join(candidate, game["content_id"] + ".pkg")
        work = os.path.join(candidate, game["content_id"] + ".work")
        if os.path.exists(work):
            return (
                "partial",
                work + " exists: a build is running or "
                "failed; remove it and any .pkg beside it to rebuild",
            )
        if os.path.exists(pkg):
            return ("built", pkg)
    return None


def fpkg_queue(roots, chosen):
    reserved, rows = {}, []
    for root in roots:
        try:
            game = fpkg_game(root)
        except Fail as error:
            rows.append(
                {
                    "root": root,
                    "game": None,
                    "out": None,
                    "state": "invalid",
                    "note": str(error),
                }
            )
            continue
        found = fpkg_built(chosen, game)
        if found:
            state, detail = found
            rows.append(
                {
                    "root": root,
                    "game": game,
                    "out": detail if state == "built" else None,
                    "state": state,
                    "note": detail,
                }
            )
            continue
        try:
            out = fpkg_out_dir(chosen, root, game["need"], reserved)
        except Fail as error:
            rows.append(
                {
                    "root": root,
                    "game": game,
                    "out": None,
                    "state": "no-room",
                    "note": str(error),
                }
            )
            continue
        rows.append(
            {"root": root, "game": game, "out": out, "state": "queued", "note": ""}
        )
    return rows


def fpkg_table(rows):
    lines = []
    for row in rows:
        game = row["game"]
        lines.append(
            f"""{os.path.basename(row["root"])!s:<10} {(game["title"] if game else "?")[:34]!s:<34} {(f"{game['need'] / 1000000000.0:.1f}GB" if game else "-")!s:>7}  {row["state"]!s:<8} {row["out"] or row["note"]}"""
        )
    return lines


def cmd_fpkg(args):
    roots = [os.path.abspath(path) for path in args.paths]
    real = [os.path.realpath(path) for path in roots]
    if len(set(real)) != len(real):
        raise Fail("the same dump is named twice")
    tool = shutil.which("pkgtool")
    if not tool:
        raise Fail("pkgtool not on PATH; use the packaged pst or the dev shell")
    rows = fpkg_queue(roots, args.dir)
    print("\n".join(fpkg_table(rows)), flush=True)
    blocked = [row for row in rows if row["state"] in ("invalid", "no-room", "partial")]
    if args.plan:
        if blocked:
            raise Fail(
                f"{len(blocked):d} of {len(rows):d} dumps cannot be built as planned"
            )
        return
    results = []
    for row in rows:
        name = os.path.basename(row["root"])
        if row["state"] != "queued":
            results.append((name, row["state"], row["note"]))
            continue
        print(f"=== {name}: {row['game']['title']}", flush=True)
        try:
            results.append((name, "built", fpkg_build(row["game"], tool, args)))
        except Fail as error:
            print(f"pst: {name}: {error}", file=sys.stderr, flush=True)
            results.append((name, "failed", str(error)))
    print("summary:")
    for name, state, detail in results:
        print(f"  {name!s:<10} {state!s:<8} {detail.splitlines()[0]}")
    bad = [result for result in results if result[1] != "built"]
    if bad:
        raise Fail(f"{len(bad):d} of {len(results):d} dumps not built")


def fpkg_build(game, tool, args):
    root, content_id, values = game["root"], game["content_id"], game["values"]
    files, dirs = game["files"], game["dirs"]
    out_dir = fpkg_out_dir(args.dir, root, game["need"], {})
    if inside(out_dir, root):
        raise Fail(f"the output {out_dir} is inside the dump {root}")
    print(
        f"output {out_dir} (needs about {game['need'] / 1000000000.0:.1f} GB)",
        flush=True,
    )
    pkg = os.path.join(out_dir, content_id + ".pkg")
    work = os.path.join(out_dir, content_id + ".work")
    for path in (pkg, work):
        if os.path.exists(path):
            raise Fail(path + " already exists")
    os.makedirs(work)
    listing, signed = [], 0
    for relative, is_elf in files:
        source = os.path.join(root, *relative.split("/"))
        if is_elf:
            with open(source, "rb") as original:
                try:
                    data = fake_self(original.read())
                except Fail as error:
                    raise Fail(
                        f"{relative}: {error}; remove {work} before retrying"
                    ) from error
            source = os.path.join(work, "signed", *relative.split("/"))
            os.makedirs(os.path.dirname(source), exist_ok=True)
            with open(source, "wb") as output:
                output.write(data)
            signed += 1
        listing.append((relative, source))
    project = os.path.join(work, "project.gp4")
    with open(project, "wb") as output:
        output.write(gp4_xml(content_id, pubtool_date(values), listing, dirs))
    print(
        f"{content_id}: {len(listing):d} files, {signed:d} fake-signed; building {pkg}",
        flush=True,
    )
    if subprocess.run([tool, "pkg_build", project, out_dir]).returncode:
        raise Fail("pkgtool pkg_build failed; project kept in " + work)
    report = subprocess.run([tool, "pkg_validate", pkg], capture_output=True, text=True)
    errors = [line for line in report.stdout.splitlines() if line.startswith("[ERROR]")]
    if report.returncode or errors:
        raise Fail(
            f"pkg_validate failed for {pkg}:\n{'\n'.join(errors) or report.stdout + report.stderr}"
        )
    shutil.rmtree(work)
    print("built and validated " + pkg, flush=True)
    result = pkg
    if args.send is not None:
        target = args.send or address("PST_PS4", "the PS4")
        remote = ftp_send_pkg(target, pkg)
        os.remove(pkg)
        print(f"sent to {target}:{remote} (size verified), removed {pkg}")
        result = f"{target}:{remote}"
    if args.remove_dump:
        shutil.rmtree(root)
        if os.path.exists(root + ".complete"):
            os.remove(root + ".complete")
        print("removed the dump " + root)
    return result


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise Fail("not a PNG file")
    return struct.unpack(">II", data[16:24])


def checked_icon(icon):
    if png_size(icon) != Y2JB_ICON_SIZE:
        raise Fail(f"the icon must be a {Y2JB_ICON_SIZE[0]}x{Y2JB_ICON_SIZE[1]} PNG")
    return icon


def with_icon(update_zip, icon):
    checked_icon(icon)
    source = zipfile.ZipFile(io.BytesIO(update_zip))
    names = source.namelist()
    if "icon0.png" not in names or "update-info.txt" not in names:
        raise Fail(
            "y2jb_update.zip has no icon0.png or update-info.txt; "
            "its layout changed, refusing to edit it"
        )
    info = source.read("update-info.txt").decode("ascii")
    newline = "\r\n" if "\r\n" in info else "\n"
    lines = info.splitlines()
    rows = [
        index
        for index, line in enumerate(lines)
        if line.split("|")[0].strip().lstrip("/") == "icon0.png"
    ]
    if len(rows) != 1:
        raise Fail(f"update-info.txt lists icon0.png {len(rows):d} times, not once")
    lines[rows[0]] = f"icon0.png|{len(icon):d}"
    edited = newline.join(lines) + (newline if info.endswith(newline) else "")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            if item.filename == "icon0.png":
                data = icon
            elif item.filename == "update-info.txt":
                data = edited.encode("ascii")
            else:
                data = source.read(item)
            target.writestr(item, data)
    return output.getvalue()


def install_task_settled(task):
    if task.get("error") or task.get("state") in ("failed", "error", "cancelled"):
        raise Fail(f"package install failed: {task.get('state')} {task.get('error')}")
    return task.get("state") == "done"


def install_finished(tasks, ids, installed_size, package_size):
    listed = [task for task in tasks if task.get("id") in ids]
    states = [install_task_settled(task) for task in listed]
    return all(states) and installed_size == package_size


def install_youtube(local):
    with open(local, "rb") as source:
        package = source.read()
    remote = posixpath.join(PKG_STAGING, os.path.basename(local))
    ftp_put(remote, package)
    try:
        start_payload(
            "ps5-web-file-manager",
            file_manager_running,
            "the Web File Manager",
            FILE_MANAGER_PORT,
        )
        query = urllib.parse.urlencode({"path": remote})
        info = file_manager("/api/pkg-info?" + query)
        fields = {field["name"]: field["value"] for field in info.get("fields", [])}
        if not info.get("ok") or fields.get("titleId") != Y2JB_TITLE:
            raise Fail(f"{local} is not a YouTube {Y2JB_TITLE} package")
        reply = file_manager(
            "/api/install-pkg",
            data=urllib.parse.urlencode({"paths": remote}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not reply.get("ok"):
            raise Fail(f"install refused: {reply!r}")
        ids = set(reply.get("task_ids", []))
        for _attempt in range(300):
            if install_finished(
                file_manager("/api/tasks")["tasks"],
                ids,
                ftp_size(Y2JB_APP_PKG),
                len(package),
            ):
                break
            time.sleep(1)
        else:
            raise Fail("YouTube did not finish installing within 300 s")
    finally:
        with ftp() as connection:
            try:
                connection.delete(remote)
                ftp_remove_dir_if_empty(connection, PKG_STAGING)
            except (OSError, ftplib.Error) as error:
                print(
                    f"pst: could not clear the staged {remote} ({error})",
                    file=sys.stderr,
                )
    print(f"installed YouTube {fields.get('contentVersion')} from {local}")


def compact_json(text):
    value = json.loads(text)
    if dump_compact(value) != text:
        raise Fail(
            "a stored JSON blob is not compact with sorted keys; refusing to rewrite it"
        )
    return value


def dump_compact(value):
    return json.dumps(
        value, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    ).replace("/", "\\/")


def check_integrity(database, name):
    result = database.execute("pragma integrity_check").fetchall()
    if result != [("ok",)]:
        raise Fail(f"{name} failed its integrity check: {result!r}")


def retitle_app_db(path, title_id, new):
    database = sqlite3.connect(path)
    try:
        rows = database.execute(
            "select titleName, localConceptId, AppInfoJson from "
            "tbl_contentinfo where titleId = ?",
            (title_id,),
        ).fetchall()
        if len(rows) != 1:
            raise Fail(f"app.db has {len(rows):d} rows for {title_id}, not one")
        old, concept, app_info = rows[0]
        if old == new:
            return None
        info = compact_json(app_info)
        for key in info:
            if re.fullmatch(r"TITLE(_\d\d)?", key) and info[key] == old:
                info[key] = new
        database.execute(
            "update tbl_contentinfo set titleName = ?, AppInfoJson = ? "
            "where titleId = ?",
            (new, dump_compact(info), title_id),
        )
        concepts = database.execute(
            "select conceptName, ConceptInfoJson, metaDataPath from "
            "tbl_conceptmetadata where localConceptId = ?",
            (concept,),
        ).fetchall()
        if len(concepts) != 1:
            raise Fail(
                f"app.db has {len(concepts):d} concept rows for {title_id}, not one"
            )
        concept_name, concept_json, concept_meta = concepts[0]
        concept_ours = concept_meta == "/user/appmeta/" + title_id
        if concept_ours:
            concept_info = compact_json(concept_json)
            for field in concept_info["field_list"]:
                if (
                    re.fullmatch(r"concept_name(_\d\d)?", field["key"])
                    and field["data"] == old
                ):
                    field["data"] = new
                    field["size"] = len(new.encode("utf-8"))
            database.execute(
                "update tbl_conceptmetadata set conceptName = ?, "
                "ConceptInfoJson = ? where localConceptId = ?",
                (
                    new if concept_name == old else concept_name,
                    dump_compact(concept_info),
                    concept,
                ),
            )
        sharing = [
            other
            for (other,) in database.execute(
                "select titleId from tbl_contentinfo where localConceptId = ? "
                "and titleId != ?",
                (concept, title_id),
            ).fetchall()
        ]
        for (table,) in database.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall():
            if re.fullmatch(r"tbl_iconinfo_\d+", table):
                database.execute(
                    f'update "{table}" set titleName = ? where titleId = ? and titleName = ?',
                    (new, title_id, old),
                )
            elif re.fullmatch(r"tbl_concepticoninfo_\d+", table):
                if concept_ours:
                    database.execute(
                        f'update "{table}" set conceptName = ? where localConceptId = ? and conceptName = ?',
                        (new, concept, old),
                    )
                database.execute(
                    f'update "{table}" set primaryTitleName = ? where primaryTitleId = ? and primaryTitleName = ?',
                    (new, title_id, old),
                )
        database.commit()
        check_integrity(database, "app.db")
        return {"old": old, "tile": concept_ours, "sharing": sharing}
    finally:
        database.close()


def retitle_appinfo_db(path, title_id, old, new):
    database = sqlite3.connect(path)
    try:
        keys = [
            key
            for (key,) in database.execute(
                "select key from tbl_appinfo where titleId = ? and val = ?",
                (title_id, old),
            ).fetchall()
            if re.fullmatch(r"TITLE(_\d\d)?", key)
        ]
        if not keys:
            raise Fail(f"appinfo.db names no title {old!r} for {title_id}")
        for key in keys:
            database.execute(
                "update tbl_appinfo set val = ? where titleId = ? and key = ?",
                (new, title_id, key),
            )
        database.commit()
        check_integrity(database, "appinfo.db")
    finally:
        database.close()


def retitle_param(text, old, new):
    pattern = r'("titleName"\s*:\s*)' + re.escape(json.dumps(old))
    replacement = json.dumps(new)
    edited, count = re.subn(pattern, lambda match: match.group(1) + replacement, text)
    if not count:
        raise Fail(f"param.json names no title {old!r}")
    json.loads(edited)
    return edited


def rename_y2jb():
    with tempfile.TemporaryDirectory() as work:
        databases = {}
        for name in ("app.db", "appinfo.db"):
            databases[name] = ftp_read(posixpath.join(APP_DATABASES, name))
            with open(os.path.join(work, name), "wb") as target:
                target.write(databases[name])
        params = {remote: ftp_read(remote) for remote in Y2JB_PARAMS}
        renamed = retitle_app_db(os.path.join(work, "app.db"), Y2JB_TITLE, Y2JB_NAME)
        if renamed is None:
            print("the YouTube tile is already named " + Y2JB_NAME)
            return
        old = renamed["old"]
        if game_running():
            raise Fail(
                "close every game and app first; renaming rewrites "
                "the console's app databases"
            )
        retitle_appinfo_db(os.path.join(work, "appinfo.db"), Y2JB_TITLE, old, Y2JB_NAME)
        edited = {
            remote: retitle_param(data.decode("utf-8"), old, Y2JB_NAME).encode("utf-8")
            for remote, data in params.items()
        }
        backup = os.path.join(state_dir("backups", "y2jb"), stamp())
        os.makedirs(backup)
        for name, data in databases.items():
            write_file(os.path.join(backup, name), data)
        for remote, data in params.items():
            write_file(os.path.join(backup, remote.strip("/").replace("/", "_")), data)
        for remote, data in edited.items():
            ftp_replace(remote, data)
        for name in ("appinfo.db", "app.db"):
            with open(os.path.join(work, name), "rb") as source:
                ftp_replace(posixpath.join(APP_DATABASES, name), source.read())
    print(
        f"renamed {Y2JB_TITLE} from {old!r} to {Y2JB_NAME!r}; the originals are in {backup}; restart the PS5 for the name to show"
    )
    if not renamed["tile"]:
        print(
            "the home tile's name comes from another app in its concept, "
            "so it was left as it is"
        )
    if renamed["sharing"]:
        print(
            f"the home tile also holds {', '.join(renamed['sharing'])}, which keep their own names"
        )


def cmd_y2jb(args):
    if args.install and game_running():
        raise Fail(
            "close every game and app first; download0.dat is "
            "YouTube's mounted data while it runs"
        )
    installed = Y2JB_TITLE in ftp_dirs("/user/app")
    if args.pkg and (installed or not args.install):
        raise Fail("--pkg only installs a missing YouTube, with --install")
    if not installed:
        if not args.pkg:
            raise Fail(
                f"YouTube ({Y2JB_TITLE}) is not installed on the PS5; run: pst y2jb --install --pkg <YouTube package>"
            )
        install_youtube(args.pkg)
    icon_path = args.icon or state_dir(Y2JB_STATE_ICON)
    icon = None
    if args.icon or os.path.isfile(icon_path):
        with open(icon_path, "rb") as source:
            icon = checked_icon(source.read())
        ftp_put(Y2JB_TILE_ICON, icon)
        print(f"put {icon_path} on the YouTube tile ({Y2JB_TILE_ICON})")
    releases = http_json(GITHUB_API + Y2JB_REPO + "/releases?per_page=20")
    release = newest_release(
        Y2JB_REPO, [release for release in releases if not release.get("prerelease")]
    )
    update = verified_download(release_asset(release, "y2jb_update.zip"))
    if icon:
        update = with_icon(update, icon)
    if args.install:
        ftp_put(
            Y2JB_DOWNLOAD0, verified_download(release_asset(release, "download0.dat"))
        )
        print("sent download0.dat to " + Y2JB_DOWNLOAD0)
    ftp_put(Y2JB_UPDATE, update)
    print(
        f"sent {release['tag_name']} y2jb_update.zip{(' with ' + icon_path if icon else '')} to {Y2JB_UPDATE} (sha256 verified, sizes checked); it applies the next time YouTube starts"
    )
    if args.rename:
        rename_y2jb()


def avatar_master(image, fill=False):
    image = image.convert("RGBA")
    width, height = image.size
    corners = {
        image.getpixel(point)
        for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
    }
    side = AVATAR_SIZES[0]
    if len(corners) == 1 and not fill:
        background = corners.pop()
        plain = Image.new("RGBA", image.size, background)
        box = ImageChops.difference(image, plain).getbbox(alpha_only=False)
        if box is None:
            raise Fail("the picture is a single colour")
        content = image.crop(box)
        diagonal = (content.width**2 + content.height**2) ** 0.5
        scale = side * AVATAR_CIRCLE / diagonal
        content = content.resize(
            (
                max(1, round(content.width * scale)),
                max(1, round(content.height * scale)),
            ),
            Image.LANCZOS,
        )
        master = Image.new("RGBA", (side, side), background)
        master.paste(
            content,
            ((side - content.width) // 2, (side - content.height) // 2),
            content,
        )
        return master
    edge = min(width, height)
    left, top = (width - edge) // 2, (height - edge) // 2
    return image.crop((left, top, left + edge, top + edge)).resize(
        (side, side), Image.LANCZOS
    )


def encoded(image, **options):
    buffer = io.BytesIO()
    image.save(buffer, **options)
    return buffer.getvalue()


def avatar_files(image, name, fill=False):
    master = avatar_master(image, fill)
    files = {}
    for size in AVATAR_SIZES:
        scaled = (
            master
            if size == AVATAR_SIZES[0]
            else master.resize((size, size), Image.LANCZOS)
        )
        dds = encoded(scaled, format="DDS", pixel_format="DXT5")
        files[f"avatar{size:d}.dds"] = dds
        files[f"picture{size:d}.dds"] = dds
    png = encoded(master, format="PNG")
    files["avatar.png"] = png
    files["picture.png"] = png
    files["online.json"] = json.dumps(
        {"firstName": name, "lastName": "", "isOfficiallyVerified": "true"}
    ).encode("utf-8")
    return files


def console_user(wanted):
    users = [
        name for name in ftp_dirs(USER_HOMES) if re.fullmatch(r"[0-9a-f]{8}", name)
    ]
    if wanted:
        if wanted.lower() not in users:
            raise Fail(f"no user {wanted} on the PS5; users: {', '.join(users)}")
        return wanted.lower()
    if len(users) != 1:
        raise Fail(
            f"the PS5 has users {', '.join(users) or 'none'}; pick one with --user"
        )
    return users[0]


def open_picture(data, label):
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except OSError as error:
        raise Fail(f"{label} is not a picture Pillow can read ({error})") from error
    return image


def pack_pictures(paths):
    pictures = []
    for path in paths:
        if os.path.isdir(path):
            pictures += sorted(
                os.path.join(path, name)
                for name in os.listdir(path)
                if name.lower().endswith(PICTURE_SUFFIXES)
            )
        elif os.path.isfile(path):
            pictures.append(path)
        else:
            raise Fail(f"{path} is not a file or folder here")
    named = {}
    for picture in pictures:
        stem = re.sub(
            r"[^A-Za-z0-9_-]", "_", os.path.splitext(os.path.basename(picture))[0]
        )
        if stem in named:
            raise Fail(f"{named[stem]} and {picture} would both be named {stem}")
        named[stem] = picture
    if not named:
        raise Fail("no .png or .jpg pictures in " + ", ".join(paths))
    return sorted(named.items())


def cmd_avatar_pack(args):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.pack):
        raise Fail("a pack name is letters, digits, - and _ only")
    pictures = pack_pictures(args.paths)
    root = posixpath.join(AVATAR_LIBRARY, args.pack)
    added = 0
    with ftp() as connection:
        connection.voidcmd("TYPE I")
        ftp_makedirs(connection, root)
        present = {
            posixpath.basename(entry)
            for entry, facts in connection.mlsd(root)
            if facts.get("type") == "dir"
        }
        for stem, path in pictures:
            if stem in present:
                continue
            with open(path, "rb") as source:
                files = avatar_files(open_picture(source.read(), path), "", args.fill)
            staged = posixpath.join(root, stem + ".part")
            ftp_makedirs(connection, staged)
            for name in sorted(files):
                ftp_store(
                    connection,
                    posixpath.join(staged, name),
                    io.BytesIO(files[name]),
                    len(files[name]),
                )
            connection.rename(staged, posixpath.join(root, stem))
            added += 1
            if added % 50 == 0:
                print(f"{added:d} added so far")
    print(
        f"{args.pack}: {added:d} added, {len(pictures) - added:d} already there, in {root}; apply one with pst avatar {root}/<name>/avatar.png --fill, or on the PS5 copy its files into {PROFILE_CACHE}/0x<USERID>"
    )


def cmd_avatar(args):
    if os.path.isfile(args.image):
        with open(args.image, "rb") as source:
            data = source.read()
    elif args.image.startswith("/data/"):
        data = ftp_read(args.image)
    else:
        raise Fail(
            f"{args.image} is neither a file here nor a console path under /data/"
        )
    image = open_picture(data, args.image)
    user = console_user(args.user)
    name = ftp_read(f"/user/home/{user}/username.dat").split(b"\0")[0].decode("utf-8")
    folder = posixpath.join(PROFILE_CACHE, "0x" + user.upper())
    if "0x" + user.upper() not in ftp_dirs(PROFILE_CACHE):
        raise Fail(
            f"{folder} does not exist; restart the PS5 once so it creates the profile cache"
        )
    files = avatar_files(image, name, args.fill)
    backup = os.path.join(state_dir("backups", "avatars"), user, stamp())
    with ftp() as connection:
        present = [
            posixpath.basename(entry)
            for entry, facts in connection.mlsd(folder)
            if facts.get("type") == "file"
        ]
    for entry in present:
        write_file(os.path.join(backup, entry), ftp_read(posixpath.join(folder, entry)))
    for entry, payload in files.items():
        ftp_replace(posixpath.join(folder, entry), payload)
    print(
        f"set {args.image} as the avatar of {name} ({user}) in {folder}; the folder's {len(present):d} earlier files are in {backup}"
    )


def live_save(save):
    return not save.get("backup") and not save.get("usb")


def console_saves():
    return [
        save for save in garlic("/api/saves", timeout=60)["saves"] if live_save(save)
    ]


def find_save(title_id, slot):
    saves = garlic("/api/saves", timeout=60)["saves"]
    wanted = (title_id, "sdimg_" + slot)
    matches = [
        index
        for index, save in enumerate(saves)
        if (save.get("title_id"), save.get("save_name")) == wanted and live_save(save)
    ]
    if len(matches) != 1:
        raise Fail(f"{title_id} {slot}: {len(matches):d} saves match on the console")
    return matches[0], saves[matches[0]]


def mounted_files(entries):
    return sorted(entry["name"] for entry in entries if not entry["dir"])


def mount_save(index):
    reply = garlic(f"/api/mount?idx={index:d}", timeout=120)
    if reply.get("error"):
        raise Fail(f"Garlic mount failed: {reply['error']}")
    return reply


def unmount_save():
    reply = garlic("/api/unmount", timeout=60)
    if not reply.get("ok"):
        raise Fail(f"Garlic unmount failed: {reply!r}")


def download_mounted(name):
    url = garlic_url("/api/download_file?name=" + urllib.parse.quote(name))
    return http(url, timeout=300)


def encrypted_names(save, slot):
    image = posixpath.basename(save["path"])
    if save.get("type") == "ps4":
        return [image, slot + ".bin"]
    if save.get("type") == "ps5":
        return [image]
    raise Fail(f"unknown save type {save.get('type')!r} for {save['path']}")


def pull_save(title_id, slot, root):
    if game_running():
        raise Fail("a game is running; close it before touching saves")
    index, save = find_save(title_id, slot)
    target = os.path.join(root, title_id, slot, stamp())
    remote_dir = posixpath.dirname(save["path"])
    encrypted = {}
    for name in encrypted_names(save, slot):
        data = ftp_read(posixpath.join(remote_dir, name))
        write_file(os.path.join(target, "encrypted", name), data)
        encrypted[name] = sha256(data)
    reply = mount_save(index)
    files = {}
    try:
        for name in mounted_files(reply["files"]):
            data = download_mounted(name)
            write_file(os.path.join(target, "files", *name.split("/")), data)
            files[name] = sha256(data)
    finally:
        unmount_save()
    manifest = {
        "title_id": title_id,
        "title_name": save.get("title_name", ""),
        "slot": slot,
        "type": save.get("type", ""),
        "uid": save.get("uid", ""),
        "account_id": reply.get("account_id", ""),
        "remote": save["path"],
        "encrypted": encrypted,
        "files": files,
    }
    with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    return target, manifest


def cmd_save_list(_args):
    start_payload("garlic-savemgr", garlic_running, "Garlic SaveMgr", GARLIC_PORT)
    for save in console_saves():
        print(
            f"{save['title_id']!s:<10} {save['save_name'][len('sdimg_') :]!s:<26} {save.get('type', '')!s:<4} {save.get('title_name', '')}"
        )


def cmd_save_pull(args):
    start_payload("garlic-savemgr", garlic_running, "Garlic SaveMgr", GARLIC_PORT)
    target, manifest = pull_save(
        args.title_id, args.slot, args.dir or state_dir("saves")
    )
    print(
        f"pulled {args.title_id} {args.slot} ({len(manifest['files']):d} files, account {manifest['account_id']}) to {target}"
    )


def push_files(root):
    names = []
    for current, dirs, files in os.walk(root):
        dirs.sort()
        relative = os.path.relpath(current, root)
        parts = [] if relative == "." else relative.split(os.sep)
        if parts and parts[0] == "sce_sys":
            continue
        names.extend("/".join([*parts, name]) for name in sorted(files))
    return names


def cmd_save_push(args):
    root = os.path.abspath(args.path)
    names = push_files(root)
    if not names:
        raise Fail(f"no files to push in {args.path} (sce_sys is never pushed)")
    start_payload("garlic-savemgr", garlic_running, "Garlic SaveMgr", GARLIC_PORT)
    backup, manifest = pull_save(
        args.title_id, args.slot, args.dir or state_dir("saves")
    )
    unknown = [name for name in names if name not in manifest["files"]]
    if unknown:
        raise Fail("not in the save, refusing to add: " + ", ".join(unknown))
    local = {}
    for name in names:
        with open(os.path.join(root, *name.split("/")), "rb") as source:
            local[name] = source.read()
    index, _save = find_save(args.title_id, args.slot)
    mount_save(index)
    try:
        for name, data in local.items():
            reply = json.loads(
                http(
                    garlic_url("/api/upload_file?name=" + urllib.parse.quote(name)),
                    data=data,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=300,
                )
            )
            if not reply.get("ok"):
                raise Fail(f"upload of {name} refused: {reply!r}")
    finally:
        unmount_save()
    index, _save = find_save(args.title_id, args.slot)
    mount_save(index)
    try:
        wrong = [
            name
            for name, data in local.items()
            if sha256(download_mounted(name)) != sha256(data)
        ]
    finally:
        unmount_save()
    if wrong:
        raise Fail(f"read back differs for {', '.join(wrong)}; the backup is {backup}")
    summary = f"pushed {len(local):d} files into {args.title_id} {args.slot}, read back and verified"
    print(f"{summary}; backup in {backup}")


def fnv1a32(data):
    value = 0x811C9DC5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def tfb_order(data):
    if len(data) < 8 or len(data) % 4:
        return None
    digest = fnv1a32(data[:-4])
    for order in ("<", ">"):
        if struct.unpack(order + "I", data[-4:])[0] == digest:
            return order
    return None


def convert_tfb(data, order):
    source = tfb_order(data)
    if source is None:
        raise Fail("not a Toys for Bob save: its FNV-1a trailer does not match")
    words = f"{(len(data) - 4) // 4:d}I"
    body = struct.pack(order + words, *struct.unpack(source + words, data[:-4]))
    return body + struct.pack(order + "I", fnv1a32(body))


def save_format(data):
    magic = data[IGB_MAGIC_OFFSET : IGB_MAGIC_OFFSET + 4]
    if magic == b"\x00\x00\xfa\xda":
        return "igb", "big-endian (Wii U, PS3, Xbox 360)"
    if magic == b"\xda\xfa\x00\x00":
        return "igb", "little-endian (PS4, PS5, PC)"
    order = tfb_order(data)
    if order == ">":
        return "tfb", "big-endian (Wii U, PS3, Xbox 360), FNV-1a valid"
    if order == "<":
        return "tfb", "little-endian (PS4, PS5, PC), FNV-1a valid"
    return "unknown", ""


def printable_strings(data, minimum=4):
    return [
        match.group().decode("ascii")
        for match in re.finditer(rb"[\x20-\x7e]{%d,}(?=\x00)" % minimum, data)
    ]


def cmd_save_inspect(args):
    with open(args.path, "rb") as source:
        data = source.read()
    kind, detail = save_format(data)
    used = len(data.rstrip(b"\x00"))
    print(f"{args.path}: {kind} {detail}, {len(data):d} bytes, data ends at 0x{used:x}")
    if kind != "igb":
        print("first bytes: " + data[:32].hex(" "))
        return
    order = ">" if detail.startswith("big") else "<"
    words = struct.unpack_from(order + "12I", data, 0)
    print("header: " + " ".join(f"0x{word:x}" for word in words))
    names = printable_strings(data)
    fields = [name for name in names if re.fullmatch(r"[a-z][a-z0-9_]+", name)]
    classes = sorted(
        {name for name in names if re.fullmatch(r"C[A-Z]\w*SaveData\w*", name)}
    )
    print(f"strings: {len(names):d}")
    print("fields: " + ", ".join(fields))
    print("save classes: " + ", ".join(classes))


IGB_MAGIC = 0xFADA
IGB_VERSION = 12
IGB_FLAG_HAS_INFO = 0x8000
IGB_FLAG_SHARED_ENTRIES = 0x2000
IGB_FLAG_POOL_NAMES = 0x1000
IGB_FLAG_HASH_NAME_TABLE = 0x0400
IGB_KNOWN_FLAG_SETS = {
    IGB_FLAG_HAS_INFO | IGB_FLAG_SHARED_ENTRIES | IGB_FLAG_POOL_NAMES,
    IGB_FLAG_HAS_INFO
    | IGB_FLAG_SHARED_ENTRIES
    | IGB_FLAG_POOL_NAMES
    | IGB_FLAG_HASH_NAME_TABLE,
}
IGB_SUMMARY_BUFFER_COUNT = 3
IGB_SUMMARY_VALUE_TYPES = {0: "int", 1: "float"}
IGB_U32 = ("u32", 4)
IGB_U8 = ("raw", 1)
IGB_PAD3 = ("raw", 3)
IGB_FIELD_LAYOUTS = {
    "igObjectRefMetaField": (IGB_U32,),
    "igIntMetaField": (IGB_U32,),
    "igUnsignedIntMetaField": (IGB_U32,),
    "igEnumMetaField": (IGB_U32,),
    "igFloatMetaField": (IGB_U32,),
    "igTimeMetaField": (IGB_U32,),
    "igStringMetaField": (IGB_U32,),
    "igMemoryRefMetaField": (IGB_U32,),
    "igBoolMetaField": (IGB_U8, IGB_PAD3),
    "igCharMetaField": (IGB_U8, IGB_PAD3),
    "igVectorMetaField": (IGB_U32, IGB_U32),
    "igHandleMetaField": (IGB_U32, IGB_U32),
    "igBitFieldMetaField": (),
    "igVec3fMetaField": (("unproven", 12),),
    "igUnsignedLongMetaField": (("unproven", 8),),
}
IGB_ELEMENT_LAYOUTS = {
    "igObjectRefMetaField": (IGB_U32,),
    "igIntMetaField": (IGB_U32,),
    "igUnsignedIntMetaField": (IGB_U32,),
    "igStringMetaField": (IGB_U32,),
    "igFloatMetaField": (IGB_U32,),
    "igNameMetaField": (IGB_U32, IGB_U32),
    "igHandleMetaField": (IGB_U32, IGB_U32),
    "igCharMetaField": (IGB_U8,),
    "igBoolMetaField": (IGB_U8,),
}
IGB_OBJECT_DIR_ENTRY = "igObjectDirEntry"
IGB_MEMORY_DIR_ENTRY = "igMemoryDirEntry"
IGB_OBJECT_DIR_SHAPE = (
    ("igStringMetaField", 0),
    ("igIntMetaField", 4),
    ("igIntMetaField", 5),
)
IGB_MEMORY_DIR_SHAPE = (
    ("igStringMetaField", 0),
    ("igIntMetaField", 3),
    ("igIntMetaField", 6),
    ("igBoolMetaField", 7),
    ("igIntMetaField", 8),
    ("igIntMetaField", 9),
)
IGB_OBJECT_TYPE_SLOT = 4
IGB_MEMORY_COUNT_SLOT = 3
IGB_MEMORY_ELEMENT_TYPE_SLOT = 6


class IgbWalker:
    def __init__(self, data, endian):
        self.data = data
        self.endian = endian
        self.pos = 0
        self.spans = []

    def need(self, n, label):
        if n < 0 or self.pos + n > len(self.data):
            raise Fail(
                f"{label} at 0x{self.pos:x} needs {n:d} bytes, runs past the data (file size 0x{len(self.data):x})"
            )

    def emit(self, kind, n, label):
        self.need(n, label)
        self.spans.append((self.pos, n, kind, label))
        self.pos += n

    def u32(self, label):
        self.need(4, label)
        value = struct.unpack_from(self.endian + "I", self.data, self.pos)[0]
        self.emit("u32", 4, label)
        return value

    def i32(self, label):
        self.need(4, label)
        value = struct.unpack_from(self.endian + "i", self.data, self.pos)[0]
        self.emit("u32", 4, label)
        return value

    def u16(self, label):
        self.need(2, label)
        value = struct.unpack_from(self.endian + "H", self.data, self.pos)[0]
        self.emit("u16", 2, label)
        return value

    def raw(self, n, label):
        self.need(n, label)
        value = self.data[self.pos : self.pos + n]
        self.emit("raw", n, label)
        return value

    def le32(self, label):
        self.need(4, label)
        self.emit("le32", 4, label)

    def cstring(self, label, limit):
        end = self.data.find(b"\0", self.pos, limit)
        if end < 0:
            raise Fail(f"{label} at 0x{self.pos:x} has no NUL before 0x{limit:x}")
        return self.raw(end + 1 - self.pos, label)

    def expect_at(self, end, label):
        if self.pos != end:
            raise Fail(f"{label} ends at 0x{self.pos:x} but its size says 0x{end:x}")


def igb_name(raw_bytes):
    head = raw_bytes.split(b"\0", 1)[0]
    try:
        return head.decode("ascii", "strict")
    except UnicodeDecodeError:
        raise Fail(f"name {head[:40]!r} is not ASCII") from None


def igb_endian(data):
    if len(data) < 0x30:
        raise Fail(f"file is 0x{len(data):x} bytes, shorter than the 0x30-byte header")
    le = struct.unpack_from("<I", data, 0x28)[0]
    be = struct.unpack_from(">I", data, 0x28)[0]
    if le == IGB_MAGIC:
        return "<"
    if be == IGB_MAGIC:
        return ">"
    raise Fail("no 0xFADA magic at 0x28")


def igb_walk_fields(w, layout, mo_index, end, what):
    mo = layout["meta_objects"][mo_index]
    values = {}
    for type_index, slot, _declared in mo["fields"]:
        type_name = layout["meta_fields"][type_index]["name"]
        parts = IGB_FIELD_LAYOUTS.get(type_name)
        if parts is None:
            raise Fail(
                f"{what} {mo['name']}: field slot {slot:d} has type {type_name} with no known serialized size"
            )
        label = f"{what} {mo['name']} slot {slot:d} {type_name}"
        for kind, n in parts:
            if kind == "u32":
                values[slot] = w.u32(label)
            elif kind == "raw":
                w.raw(n, label)
            else:
                w.emit("unproven:" + type_name, n, label)
    w.expect_at(end, f"{what} {mo['name']}")
    return values


def igb_parse(data):
    endian = igb_endian(data)
    w = IgbWalker(data, endian)
    layout = {"endian": endian, "sections": [], "meta_fields": [], "meta_objects": []}

    def section(name, start, count=None):
        layout["sections"].append((name, start, w.pos - start, count))

    header = [w.u32(f"header[{i:d}]") for i in range(12)]
    section("header", 0, 12)
    layout["header"] = header
    version = header[11] & 0xFFFF
    flags = header[11] >> 16
    if version != IGB_VERSION:
        raise Fail(f"IGB version {version:d}, only {IGB_VERSION:d} is understood")
    if flags not in IGB_KNOWN_FLAG_SETS:
        raise Fail(f"flag set 0x{flags:04x} not seen in any proven input")
    layout["version"] = version
    layout["flags"] = flags
    (
        entry_size,
        entry_count,
        mo_size,
        mo_count,
        obj_size,
        obj_count,
        mem_size,
        mem_count,
        mf_size,
        mf_count,
    ) = header[:10]

    start = w.pos
    n_buffers = w.u32("summary buffer count")
    if n_buffers != IGB_SUMMARY_BUFFER_COUNT:
        raise Fail(
            f"summary block has {n_buffers:d} buffers, only {IGB_SUMMARY_BUFFER_COUNT:d} is understood"
        )
    desc_size = w.u32("summary descriptor buffer size")
    if desc_size % 12:
        raise Fail(
            f"summary descriptor buffer size {desc_size:d} is not a multiple of 12"
        )
    n_desc = desc_size // 12
    descriptors = []
    for i in range(n_desc):
        descriptors.append(
            (
                w.u32(f"summary desc {i:d} type"),
                w.u32(f"summary desc {i:d} name offset"),
                w.u32(f"summary desc {i:d} value offset"),
            )
        )
    names_size = w.u32("summary name buffer size")
    names = w.raw(names_size, "summary names")
    values_size = w.u32("summary value buffer size")
    if values_size != 4 * n_desc:
        raise Fail(
            f"summary value buffer is {values_size:d} bytes for {n_desc:d} descriptors"
        )
    summary = []
    for i, (vtype, name_off, value_off) in enumerate(descriptors):
        if vtype not in IGB_SUMMARY_VALUE_TYPES:
            raise Fail(
                f"summary descriptor {i:d} has value type {vtype:d}, only 0 and 1 are understood"
            )
        if value_off != 4 * i:
            raise Fail(
                f"summary descriptor {i:d} value offset {value_off:d}, expected {4 * i:d}"
            )
        if (
            name_off >= names_size
            or (name_off and names[name_off - 1] != 0)
            or names.find(b"\0", name_off) < 0
        ):
            raise Fail(
                f"summary descriptor {i:d} name offset {name_off:d} does not start a NUL-terminated name"
            )
        summary.append(
            (
                igb_name(names[name_off:]),
                IGB_SUMMARY_VALUE_TYPES[vtype],
                data[w.pos + value_off : w.pos + value_off + 4],
            )
        )
    for i in range(n_desc):
        w.le32(f"summary value {i:d} (always little-endian)")
    layout["summary"] = summary
    section("summary", start, n_desc)

    start = w.pos
    pool_size = w.u32("string pool size")
    pool_count = w.u32("string pool count")
    strings = []
    for i in range(pool_count):
        n = w.u32(f"string {i:d} length")
        s = w.raw(n, f"string {i:d}")
        if n and s[-1] != 0:
            raise Fail(f"string {i:d} at 0x{w.pos - n:x} is not NUL-terminated")
        strings.append(s)
    w.expect_at(start + pool_size, "string pool")
    layout["strings"] = strings
    section("string pool", start, pool_count)

    start = w.pos
    records = []
    for i in range(mf_count):
        rec_off = w.pos
        records.append(
            (
                rec_off,
                w.u32(f"meta-field {i:d} name length"),
                w.u32(f"meta-field {i:d} major"),
                w.u32(f"meta-field {i:d} minor"),
            )
        )
    for i, (rec_off, n, _major, _minor) in enumerate(records):
        name_off = w.pos
        raw_name = w.raw(n, f"meta-field {i:d} name")
        if b"\0" not in raw_name:
            raise Fail(f"meta-field {i:d} name at 0x{name_off:x} is not NUL-terminated")
        layout["meta_fields"].append(
            {
                "name": igb_name(raw_name),
                "record": rec_off,
                "name_at": name_off,
                "name_len": n,
            }
        )
    w.expect_at(start + mf_size, "meta-field buffer")
    section("meta-fields", start, mf_count)

    start = w.pos
    statics = []
    for i in range(mo_count):
        rec_off = w.pos
        statics.append(
            (
                rec_off,
                w.u32(f"meta-object {i:d} name length"),
                w.u32(f"meta-object {i:d} major"),
                w.u32(f"meta-object {i:d} minor"),
                w.u32(f"meta-object {i:d} field count"),
                w.i32(f"meta-object {i:d} parent"),
                w.u32(f"meta-object {i:d} slot count"),
            )
        )
    for i, (rec_off, n, _major, _minor, nf, parent, _slots) in enumerate(statics):
        name_off = w.pos
        raw_name = w.raw(n, f"meta-object {i:d} name")
        if b"\0" not in raw_name:
            raise Fail(
                f"meta-object {i:d} name at 0x{name_off:x} is not NUL-terminated"
            )
        if not (parent == -1 or 0 <= parent < mo_count):
            raise Fail(f"meta-object {i:d} parent {parent:d} out of range")
        fields_off = w.pos
        fields = []
        for j in range(nf):
            t = w.u16(f"meta-object {i:d} field {j:d} type")
            s = w.u16(f"meta-object {i:d} field {j:d} slot")
            z = w.u16(f"meta-object {i:d} field {j:d} size")
            if t >= mf_count:
                raise Fail(
                    f"meta-object {i:d} field {j:d} type index {t:d} out of range"
                )
            fields.append((t, s, z))
        layout["meta_objects"].append(
            {
                "name": igb_name(raw_name),
                "record": rec_off,
                "name_at": name_off,
                "name_len": n,
                "fields_at": fields_off,
                "fields": fields,
                "parent": parent,
            }
        )
    w.expect_at(start + mo_size, "meta-object buffer")
    section("meta-objects", start, mo_count)

    if flags & IGB_FLAG_HASH_NAME_TABLE:
        start = w.pos
        size = w.u32("hash-name table size")
        tables = w.u32("hash-name table count")
        if tables != 1:
            raise Fail(f"hash-name table count {tables:d}, only 1 is understood")
        n = w.u32("hash-name entry count")
        for i in range(n):
            w.u32(f"hash-name {i:d} hash")
        for i in range(n):
            w.cstring(f"hash-name {i:d} name", start + size)
        w.expect_at(start + size, "hash-name table")
        section("hash-name table", start, n)

    start = w.pos
    size = w.u32("memory pool name buffer size")
    pool_names_count = w.u32("memory pool name count")
    pool_names = [
        igb_name(w.cstring(f"memory pool name {i:d}", start + size))
        for i in range(pool_names_count)
    ]
    w.expect_at(start + size, "memory pool names")
    layout["pool_names"] = pool_names
    section("memory pool names", start, pool_names_count)

    start = w.pos
    size = w.u32("memory pool id table size")
    if size != 4 + 4 * pool_names_count:
        raise Fail(
            f"memory pool id table is {size:d} bytes for {pool_names_count:d} pool names"
        )
    for i in range(pool_names_count):
        w.u32(f"memory pool id {i:d}")
    section("memory pool ids", start, pool_names_count)

    mos = layout["meta_objects"]
    mfs = layout["meta_fields"]

    def shape(mo):
        return tuple((mfs[t]["name"], s) for t, s, _z in mo["fields"])

    start = w.pos
    entries = []
    for i in range(entry_count):
        e_start = w.pos
        etype = w.u32(f"entry {i:d} type")
        esize = w.u32(f"entry {i:d} size")
        if etype >= mo_count:
            raise Fail(f"entry {i:d} type {etype:d} out of range")
        ename = mos[etype]["name"]
        if ename == IGB_OBJECT_DIR_ENTRY:
            if shape(mos[etype]) != IGB_OBJECT_DIR_SHAPE:
                raise Fail(
                    f"igObjectDirEntry has an unseen field list {shape(mos[etype])!r}"
                )
        elif ename == IGB_MEMORY_DIR_ENTRY:
            if shape(mos[etype]) != IGB_MEMORY_DIR_SHAPE:
                raise Fail(
                    f"igMemoryDirEntry has an unseen field list {shape(mos[etype])!r}"
                )
        else:
            raise Fail(
                f"entry {i:d} is a {ename}, only {IGB_OBJECT_DIR_ENTRY} and {IGB_MEMORY_DIR_ENTRY} are understood"
            )
        values = igb_walk_fields(w, layout, etype, e_start + esize, f"entry {i:d}")
        entries.append((ename, values))
    w.expect_at(start + entry_size, "entry buffer")
    section("entries", start, entry_count)

    start = w.pos
    size = w.u32("index buffer size")
    count = w.u32("index count")
    if size != 8 + 2 * count:
        raise Fail(f"index buffer is {size:d} bytes for {count:d} u16 indices")
    if count != obj_count + mem_count:
        raise Fail(
            f"index count {count:d} is not objects {obj_count:d} + memory blocks {mem_count:d}"
        )
    index = []
    for i in range(count):
        v = w.u16(f"index {i:d}")
        if v >= entry_count:
            raise Fail(f"index {i:d} points at entry {v:d} of {entry_count:d}")
        index.append(v)
    section("index", start, count)

    start = w.pos
    info_list = w.u32("info list index")
    if info_list >= count:
        raise Fail(f"info list index {info_list:d} out of range")
    section("info list index", start, 1)

    start = w.pos
    n_obj = 0
    for i, e in enumerate(index):
        ename, entry_values = entries[e]
        if ename != IGB_OBJECT_DIR_ENTRY:
            continue
        o_start = w.pos
        otype = w.u32(f"object {i:d} type")
        osize = w.u32(f"object {i:d} size")
        if otype != entry_values[IGB_OBJECT_TYPE_SLOT]:
            raise Fail(
                f"object {i:d} type {otype:d} disagrees with its directory entry type {entry_values[IGB_OBJECT_TYPE_SLOT]:d}"
            )
        if otype >= mo_count:
            raise Fail(f"object {i:d} type {otype:d} out of range")
        igb_walk_fields(w, layout, otype, o_start + osize, f"object {i:d}")
        n_obj += 1
    if n_obj != obj_count:
        raise Fail(f"{n_obj:d} objects in the index, header says {obj_count:d}")
    w.expect_at(start + obj_size, "object buffer")
    section("objects", start, n_obj)

    start = w.pos
    n_mem = 0
    for i, e in enumerate(index):
        ename, entry_values = entries[e]
        if ename != IGB_MEMORY_DIR_ENTRY:
            continue
        n = entry_values[IGB_MEMORY_COUNT_SLOT]
        t = entry_values[IGB_MEMORY_ELEMENT_TYPE_SLOT]
        if t >= mf_count:
            raise Fail(f"memory block {i:d} element type {t:d} out of range")
        tname = mfs[t]["name"]
        parts = IGB_ELEMENT_LAYOUTS.get(tname)
        if parts is None:
            raise Fail(
                f"memory block {i:d} has element type {tname} with no known element size"
            )
        width = sum(z for _k, z in parts)
        w.need(n * width, f"memory block {i:d} ({n:d} x {tname})")
        label = f"memory block {i:d} {tname}"
        for _ in range(n):
            for kind, z in parts:
                if kind == "u32":
                    w.u32(label)
                else:
                    w.raw(z, label)
        pad = -(n * width) % 4
        if pad:
            w.raw(pad, f"memory block {i:d} padding")
        n_mem += 1
    if n_mem != mem_count:
        raise Fail(f"{n_mem:d} memory blocks in the index, header says {mem_count:d}")
    w.expect_at(start + mem_size, "memory buffer")
    section("memory", start, n_mem)

    layout["data_end"] = w.pos
    tail = data[w.pos :]
    nonzero = len(tail.rstrip(b"\0"))
    if nonzero == 0:
        layout["trailer"] = None
        w.emit("zero", len(tail), "zero padding")
    elif len(tail) >= 4 and not tail[:-4].strip(b"\0"):
        w.emit("zero", len(tail) - 4, "zero padding")
        layout["trailer"] = data[-4:]
        w.emit("trailer", 4, "4-byte trailer at end of file")
    else:
        raise Fail(
            f"non-zero bytes after the memory buffer at 0x{layout['data_end']:x}, first at 0x{layout['data_end'] + len(tail) - len(tail.lstrip(b'\x00')):x}"
        )
    layout["spans"] = w.spans
    return layout


def igb_accounted(layout, size):
    pos = 0
    for off, n, _kind, label in layout["spans"]:
        if off != pos:
            return f"gap or overlap at 0x{pos:x} before {label}"
        pos += n
    if pos != size:
        return f"spans end at 0x{pos:x}, file is 0x{size:x}"
    return None


def igb_convert(data, to):
    layout = igb_parse(data)
    target = "<" if to == "le" else ">"
    problem = igb_accounted(layout, len(data))
    if problem:
        raise Fail("structure does not tile the file: " + problem)
    if layout["endian"] == target:
        raise Fail(
            f"input is already {('little-endian' if target == '<' else 'big-endian')}"
        )
    out = bytearray(data)
    for off, n, kind, label in layout["spans"]:
        if kind in ("u32", "u16"):
            out[off : off + n] = data[off : off + n][::-1]
        elif kind in ("raw", "le32", "zero"):
            continue
        elif kind == "trailer":
            raise Fail(
                f"the file ends in a 4-byte trailer of unknown meaning ({data[off : off + 4].hex()}); its byte order cannot be decided"
            )
        else:
            raise Fail(
                f"{label} at 0x{off:x}: {kind.split(':', 1)[-1]} has a known size but no proven byte layout"
            )
    return bytes(out)


def igb_same_structure(first, second):
    keys = ("header", "strings", "pool_names", "summary")
    if any(first[key] != second[key] for key in keys):
        return False
    shape = [
        (item["name"], item["fields"], item["parent"]) for item in first["meta_objects"]
    ]
    other = [
        (item["name"], item["fields"], item["parent"])
        for item in second["meta_objects"]
    ]
    names = [item["name"] for item in first["meta_fields"]]
    return shape == other and names == [item["name"] for item in second["meta_fields"]]


def convert_save(data, to):
    kind, _detail = save_format(data)
    order = "<" if to == "le" else ">"
    if kind == "tfb":
        converted = convert_tfb(data, order)
        if tfb_order(converted) != order:
            raise Fail("converted file fails its own FNV-1a check")
        return kind, converted
    if kind == "igb":
        converted = igb_convert(data, to)
        layout = igb_parse(converted)
        if layout["endian"] != order or igb_accounted(layout, len(converted)):
            raise Fail(f"converted IGB file does not parse back in {to}")
        if not igb_same_structure(igb_parse(data), layout):
            raise Fail("converted IGB file decodes to a different structure")
        return kind, converted
    raise Fail("unknown save format; nothing converts it")


CRC32_POLYS = (
    0x04C11DB7,
    0x1EDC6F41,
    0x741B8CD7,
    0x32583499,
    0x814141AB,
    0x000000AF,
    0xA833982B,
)


def reflect_bits(value, width):
    result = 0
    for _bit in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def crc32_table(poly, reflected):
    table = []
    for byte in range(256):
        if reflected:
            crc = byte
            for _bit in range(8):
                crc = (crc >> 1) ^ reflect_bits(poly, 32) if crc & 1 else crc >> 1
        else:
            crc = byte << 24
            for _bit in range(8):
                crc = (
                    ((crc << 1) ^ poly) & 0xFFFFFFFF
                    if crc & 0x80000000
                    else (crc << 1) & 0xFFFFFFFF
                )
        table.append(crc)
    return table


def crc32_run(data, table, reflected, init):
    crc = init
    if reflected:
        for byte in data:
            crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
    else:
        for byte in data:
            crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ byte) & 0xFF]
    return crc


def fnv1_32(data):
    value = 0x811C9DC5
    for byte in data:
        value = ((value * 0x01000193) & 0xFFFFFFFF) ^ byte
    return value


def jenkins_one_at_a_time(data):
    value = 0
    for byte in data:
        value = (value + byte) & 0xFFFFFFFF
        value = (value + (value << 10)) & 0xFFFFFFFF
        value ^= value >> 6
    value = (value + (value << 3)) & 0xFFFFFFFF
    value ^= value >> 11
    return (value + (value << 15)) & 0xFFFFFFFF


def murmur3_32(data):
    value = 0
    for offset in range(0, len(data) & ~3, 4):
        k = (struct.unpack_from("<I", data, offset)[0] * 0xCC9E2D51) & 0xFFFFFFFF
        k = (((k << 15) | (k >> 17)) * 0x1B873593) & 0xFFFFFFFF
        value ^= k
        value = (((value << 13) | (value >> 19)) * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail = data[len(data) & ~3 :]
    if tail:
        k = (int.from_bytes(tail, "little") * 0xCC9E2D51) & 0xFFFFFFFF
        value ^= (((k << 15) | (k >> 17)) * 0x1B873593) & 0xFFFFFFFF
    value ^= len(data)
    value = ((value ^ (value >> 16)) * 0x85EBCA6B) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 0xC2B2AE35) & 0xFFFFFFFF
    return value ^ (value >> 16)


def word_sum(data, order):
    count = len(data) // 4
    return sum(struct.unpack_from(order + f"{count:d}I", data)) & 0xFFFFFFFF


def checksum_candidates(body):
    results = {
        "fnv1a32": fnv1a32(body),
        "fnv1_32": fnv1_32(body),
        "adler32": zlib.adler32(body) & 0xFFFFFFFF,
        "jenkins one-at-a-time": jenkins_one_at_a_time(body),
        "murmur3_32 seed 0": murmur3_32(body),
        "byte sum": sum(body) & 0xFFFFFFFF,
        "little-endian word sum": word_sum(body, "<"),
        "big-endian word sum": word_sum(body, ">"),
    }
    for poly in CRC32_POLYS:
        for reflected in (False, True):
            table = crc32_table(poly, reflected)
            for init in (0, 0xFFFFFFFF):
                raw = crc32_run(body, table, reflected, init)
                for xorout in (0, 0xFFFFFFFF):
                    name = f"crc32 poly {poly:08x} {('reflected' if reflected else 'msb-first')} init {init:08x} xorout {xorout:08x}"
                    results[name] = raw ^ xorout
    return results


def trailer_checksums(data):
    if len(data) < 8:
        return []
    stored = {
        "little-endian": struct.unpack("<I", data[-4:])[0],
        "big-endian": struct.unpack(">I", data[-4:])[0],
    }
    return sorted(
        f"{name}, stored {order}"
        for name, value in checksum_candidates(data[:-4]).items()
        for order, wanted in stored.items()
        if value == wanted
    )


def cmd_save_checksum(args):
    common = None
    for path in args.paths:
        with open(path, "rb") as source:
            matches = trailer_checksums(source.read())
        print(f"{path}: {'; '.join(matches) or 'no known checksum'}")
        common = set(matches) if common is None else common & set(matches)
    if len(args.paths) > 1:
        print(f"in every file: {'; '.join(sorted(common)) or 'none'}")
    if not common:
        raise Fail("no known checksum explains the last 4 bytes of every file")


ITT_ENDING = "/Game/Maps/Music/Ending/Music_Ending_BP##EndingIntro"
ITT_MINIGAMES = (
    "Whack-A-Cody",
    "The Nail Wheel",
    "Tug of War",
    "Plunger",
    "Tank Brothers",
    "Laser Tennis",
    "Low Gravity Room",
    "Baseball",
    "Throwing Hoops",
    "Rodeo",
    "Birdstar",
    "Bomb Run",
    "Horse Derby",
    "Snowball Warfare",
    "Shuffle Board",
    "Icicle Throwing",
    "Ice Race",
    "Larva Basket",
    "Garden Swing",
    "Snail Race",
    "Musical Chairs",
    "Track Runner",
    "Slotcars",
    "Chess",
    "Volleyball",
)
ITT_IDENTITY = ("EULA_Accepted", "UID")


def itt_block(name, items, last):
    lines = [f"\t{json.dumps(name)}:", "\t{"]
    for number, (key, value) in enumerate(items):
        comma = "," if number < len(items) - 1 else ""
        lines.append(f"\t\t{json.dumps(key)}: {json.dumps(value)}{comma}")
    lines.append("\t}" if last else "\t},")
    return lines


def itt_merge(ps5, other, unlock_all):
    if any(key not in ps5.get("Profile", {}) for key in ITT_IDENTITY):
        raise Fail("the PS5 save has no Profile identity; play until it saves")
    profile = {key: ps5["Profile"][key] for key in ITT_IDENTITY}
    cloud = ps5.get("CloudSettings", {})
    source = ps5["Profile"]
    if other is not None:
        source = other.get("Profile", other)
        cloud = other.get("CloudSettings", cloud)
    for key, value in source.items():
        if key not in ITT_IDENTITY:
            profile[key] = value
    if unlock_all:
        profile["FurthestUnlockedChapter"] = ITT_ENDING
        for name in ITT_MINIGAMES:
            profile["Minigame." + name] = "true"
    lines = ["{"]
    lines += itt_block("Profile", list(profile.items()), False)
    lines += itt_block("CloudSettings", list(cloud.items()), False)
    lines += itt_block(
        "LocalSettings", list(ps5.get("LocalSettings", {}).items()), True
    )
    text = "\n".join([*lines, "}"]) + "\n"
    if json.loads(text)["Profile"]["UID"] != ps5["Profile"]["UID"]:
        raise Fail("merge changed the PS5 profile identity")
    return text


def cmd_itt_merge(args):
    with open(args.ps5, encoding="utf-8") as source:
        ps5 = json.load(source)
    other = None
    if args.source:
        with open(args.source, encoding="utf-8-sig") as source:
            other = json.load(source)
    text = itt_merge(ps5, other, args.unlock_all)
    try:
        with open(args.target, "x", encoding="utf-8", newline="\n") as output:
            output.write(text)
    except FileExistsError:
        raise Fail(f"{args.target} already exists; refusing to overwrite it") from None
    profile = json.loads(text)["Profile"]
    print(
        f"wrote {args.target}: {len(profile):d} profile keys, furthest chapter {profile.get('FurthestUnlockedChapter', 'none')}"
    )


def cmd_save_convert(args):
    with open(args.source, "rb") as source:
        data = source.read()
    kind, converted = convert_save(data, args.to)
    try:
        with open(args.target, "xb") as output:
            output.write(converted)
    except FileExistsError:
        raise Fail(f"{args.target} already exists; refusing to overwrite it") from None
    print(f"converted {args.source} ({kind}) to {args.to}: {args.target}")


def main(argv):
    parser = argparse.ArgumentParser(prog="pst")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="what runs and what is installed")
    commands.add_parser("payloads", help="installed versus developer latest")
    update = commands.add_parser(
        "payload-update", help="install a developer's latest release"
    )
    update.add_argument("name")
    y2jb = commands.add_parser(
        "y2jb", help="send the newest Y2JB autoloader update with our icon"
    )
    y2jb.add_argument("--install", action="store_true")
    y2jb.add_argument("--pkg", metavar="YOUTUBE_PKG")
    y2jb.add_argument("--icon", metavar="PNG")
    y2jb.add_argument("--rename", action="store_true")
    avatar = commands.add_parser(
        "avatar", help="set a picture as a user's profile avatar"
    )
    avatar.add_argument("image")
    avatar.add_argument("--user", metavar="HEX")
    avatar.add_argument("--fill", action="store_true")
    avatar_pack = commands.add_parser(
        "avatar-pack", help="store pictures as ready avatars in /data/avatars"
    )
    avatar_pack.add_argument("pack")
    avatar_pack.add_argument("paths", nargs="+", metavar="path")
    avatar_pack.add_argument("--fill", action="store_true")
    prep = commands.add_parser("prep", help="write param.json for a PS4 dump")
    prep.add_argument("path")
    send = commands.add_parser("send", help="copy a dump to /data/homebrew")
    send.add_argument("path")
    send.add_argument("--fself", action="store_true")
    fpkg = commands.add_parser(
        "fpkg", help="build PS4 fake PKGs from ItemzFlow base dumps"
    )
    fpkg.add_argument("paths", nargs="+", metavar="path")
    fpkg.add_argument("--dir")
    fpkg.add_argument("--plan", action="store_true")
    fpkg.add_argument("--send", nargs="?", const="", metavar="PS4_IP")
    fpkg.add_argument("--remove-dump", action="store_true")
    sign = commands.add_parser("fself", help="fake-sign a game on the PS5")
    sign.add_argument("title_id")
    commands.add_parser("dumper", help="start the App Dumper")
    temps = commands.add_parser("temps", help="SoC and CPU temperature through shsrv")
    temps.add_argument("--watch", type=int, default=15)
    temps.add_argument("--count", type=int, default=1)
    temps.add_argument("--stop", action="store_true")
    commands.add_parser("save-list", help="saves on the console (Garlic)")
    pull = commands.add_parser("save-pull", help="copy a save, decrypted and encrypted")
    pull.add_argument("title_id")
    pull.add_argument("slot")
    pull.add_argument("--dir")
    push = commands.add_parser(
        "save-push", help="back up a save, then write files into it"
    )
    push.add_argument("path")
    push.add_argument("title_id")
    push.add_argument("slot")
    push.add_argument("--dir")
    inspect = commands.add_parser("save-inspect", help="name a save file's format")
    inspect.add_argument("path")
    convert = commands.add_parser(
        "save-convert", help="rewrite a save in another byte order"
    )
    convert.add_argument("source")
    convert.add_argument("target")
    convert.add_argument("--to", choices=("le", "be"), required=True)
    checksum = commands.add_parser(
        "save-checksum", help="find which checksum ends a save file"
    )
    checksum.add_argument("paths", nargs="+")
    merge = commands.add_parser(
        "itt-merge", help="build an It Takes Two PS5 save from another one"
    )
    merge.add_argument("ps5")
    merge.add_argument("target")
    merge.add_argument("--source")
    merge.add_argument("--unlock-all", action="store_true")
    case = commands.add_parser(
        "casecheck", help="find files the game names in other case"
    )
    case.add_argument("path")
    snapshot = commands.add_parser("snapshot", help="record console state")
    snapshot.add_argument("--dir")
    args = parser.parse_args(argv)
    handler = globals()["cmd_" + args.command.replace("-", "_")]
    try:
        handler(args)
    except (Fail, OSError, ftplib.Error) as error:
        print("pst: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
