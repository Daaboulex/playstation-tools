import hashlib
import io
import json
import os
import posixpath
import socket
import sqlite3
import struct
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
import zipfile
import zlib

from PIL import Image, ImageChops

import pst


def sfo(entries):
    keys = b"".join(key.encode() + b"\x00" for key, _, _ in entries)
    index, data, key_off = b"", b"", 0
    for key, fmt, value in entries:
        index += struct.pack("<HHIII", key_off, fmt, len(value), len(value), len(data))
        key_off += len(key) + 1
        data += value
    key_table = 20 + len(index)
    header = b"\x00PSF" + struct.pack(
        "<IIII", 0x101, key_table, key_table + len(keys), len(entries)
    )
    return header + index + keys + data


def synthetic_elf(elf_type):
    segments = [
        (0x1, 0x5, bytes(range(256)) * 0x41),
        (0x1, 0x6, b"\x11" * 0x30),
        (0x2, 0x6, b"\x22" * 0x10),
        (0x61000000, 0x4, b"\x33" * 0x4001),
        (0x1, 0x6, b""),
        (0x6FFFFF00, 0x4, b"\x44" * 0x21),
        (0x6FFFFF01, 0x4, b"\x55" * 0x13),
    ]
    phoff = 0x40
    offset = phoff + 0x38 * len(segments)
    phdrs, body = b"", b""
    for kind, flags, data in segments:
        phdrs += struct.pack(
            "<2I6Q",
            kind,
            flags,
            offset + len(body),
            0x400000 + len(body),
            0,
            len(data),
            len(data) + 8,
            0x4000,
        )
        body += data + b"\x00" * 3
    ident = b"\x7fELF" + bytes([2, 1, 1, 9, 0]) + b"\x00" * 6 + b"\x00"
    header = ident + struct.pack(
        "<2HI3QI6H",
        elf_type,
        0x3E,
        1,
        0x401000,
        phoff,
        0x1234,
        0,
        0x40,
        0x38,
        len(segments),
        0x40,
        5,
        4,
    )
    return header + phdrs + body


def expect_fail(function, *args):
    try:
        function(*args)
    except pst.Fail:
        return
    raise AssertionError("expected Fail from " + function.__name__)


def main():
    game = sfo(
        [
            ("TITLE", 0x0204, b"Skylanders SWAP Force\x00"),
            ("TITLE_02", 0x0204, b"Skylanders SWAP Force FR\x00"),
            ("TITLE_ID", 0x0204, b"CUSA00024\x00"),
            ("USER_DEFINED_PARAM_1", 0x0404, struct.pack("<I", 7)),
            ("USER_DEFINED_PARAM_2", 0x0404, struct.pack("<I", 0)),
        ]
    )
    produced = json.loads(pst.param_json(pst.parse_sfo(game)))
    assert produced == {
        "localizedParameters": {
            "defaultLanguage": "en-US",
            "en-US": {"titleName": "Skylanders SWAP Force"},
            "fr-FR": {"titleName": "Skylanders SWAP Force FR"},
        },
        "titleId": "CUSA00024",
        "titleName": "Skylanders SWAP Force",
        "userDefinedParam1": 7,
    }, produced
    expect_fail(pst.parse_sfo, b"XXXX" + game[4:])
    ps5 = sfo([("TITLE_ID", 0x0204, b"PPSA00002\x00")])
    expect_fail(pst.param_json, pst.parse_sfo(ps5))

    entry = {
        "source_direct": "https://github.com/a/b/releases/download/"
        "v0.5.2/tool_v0.5.2.elf"
    }
    release = {
        "tag_name": "v0.6.0",
        "assets": [
            {"name": "tool_v0.6.0.elf"},
            {"name": "other_v0.6.0.elf"},
            {"name": "tool_v0.6.0.zip"},
        ],
    }
    assert pst.pick_asset(entry, release)["name"] == "tool_v0.6.0.elf"
    release["assets"] = [{"name": "a.elf"}, {"name": "b.elf"}]
    expect_fail(pst.pick_asset, entry, release)

    assert [
        pst.murmur3_32(data)
        for data in (
            b"",
            b"test",
            b"Hello, world!",
            b"abcdefghi",
            b"The quick brown fox jumps over the lazy dog",
        )
    ] == [0x00000000, 0xBA6BD213, 0xC0363E43, 0x421406F0, 0x2E4FF723]
    assert not pst.payload_current("1.7-beta5fix1", "1.7")
    assert pst.payload_current("1.7beta7", "1.7beta7")
    assert pst.payload_current("0.6.1", "v0.6.1")
    assert not pst.payload_current("", "v0.6.1")

    listed = [
        {"tag_name": "1.7beta5", "published_at": "2026-10-10T16:12:16Z"},
        {"tag_name": "1.7-beta5fix1", "published_at": "2026-10-10T18:36:33Z"},
        {"tag_name": "1.8", "draft": True, "published_at": None},
    ]
    assert pst.newest_release("a/b", listed)["tag_name"] == "1.7-beta5fix1"
    expect_fail(pst.newest_release, "a/b", listed[2:])

    def png(width, height, body):
        return (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", width, height)
            + body
        )

    def update_zip(info):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("icon0.png", png(512, 512, b"theirs"))
            archive.writestr(zipfile.ZipInfo("main.js"), b"abc")
            archive.writestr("update-info.txt", info)
        return buffer.getvalue()

    ours = png(512, 512, b"our icon, longer")
    edited = zipfile.ZipFile(
        io.BytesIO(pst.with_icon(update_zip("icon0.png|30\r\nmain.js|3\r\n"), ours))
    )
    assert edited.read("icon0.png") == ours
    assert edited.read("main.js") == b"abc"
    assert (
        edited.read("update-info.txt")
        == (f"icon0.png|{len(ours):d}\r\nmain.js|3\r\n").encode()
    )
    expect_fail(pst.with_icon, update_zip("icon0.png|30\n"), png(256, 256, b""))
    expect_fail(pst.with_icon, update_zip("main.js|3\n"), ours)
    expect_fail(pst.with_icon, update_zip("icon0.png|30\n/icon0.png|30\n"), ours)
    saved_env = {
        name: os.environ.pop(name, None)
        for name in ("PST_STATE", "XDG_STATE_HOME", "HOME")
    }
    os.environ["HOME"] = "/home/someone"
    assert pst.state_dir("saves") == "/home/someone/.local/state/pst/saves"
    os.environ["XDG_STATE_HOME"] = "/srv/state"
    assert pst.state_dir() == "/srv/state/pst"
    os.environ["PST_STATE"] = "relative/state"
    expect_fail(pst.state_dir)
    for name, value in saved_env.items():
        os.environ.pop(name, None)
        if value is not None:
            os.environ[name] = value
    os.environ.pop("PST_PS4", None)
    expect_fail(pst.address, "PST_PS4", "the PS4")
    assert pst.install_task_settled({"state": "done", "error": ""})
    assert not pst.install_task_settled({"state": "running", "error": ""})
    expect_fail(pst.install_task_settled, {"state": "done", "error": "x"})
    expect_fail(pst.install_task_settled, {"state": "failed", "error": ""})
    running = {"id": 1, "state": "running", "error": ""}
    assert pst.install_finished([], {1}, 100, 100)
    assert pst.install_finished([dict(running, id=2)], {1}, 100, 100)
    assert not pst.install_finished([running], {1}, 100, 100)
    assert not pst.install_finished([], {1}, None, 100)
    expect_fail(pst.install_finished, [dict(running, state="failed")], {1}, 100, 100)

    def app_db(path, concept_meta, app_info):
        database = sqlite3.connect(path)
        database.executescript(
            "create table tbl_contentinfo (titleId, titleName, "
            "localConceptId, AppInfoJson);"
            "create table tbl_conceptmetadata (localConceptId, conceptName, "
            "metaDataPath, ConceptInfoJson);"
            "create table tbl_iconinfo_0123456789 (titleId, titleName);"
            "create table tbl_concepticoninfo_0123456789 (localConceptId, "
            "conceptName, primaryTitleId, primaryTitleName);"
        )
        database.executemany(
            "insert into tbl_contentinfo values (?,?,?,?)",
            [
                ("PPSA01650", "YouTube", "c1", app_info),
                ("CUSA01015", "YouTube", "c1", '{"TITLE":"YouTube"}'),
            ],
        )
        concept = (
            '{"field_list":[{"data":"YouTube","key":"concept_name",'
            '"size":7,"type":2},{"data":"\\/user","key":"path",'
            '"size":5,"type":2}]}'
        )
        database.execute(
            "insert into tbl_conceptmetadata values (?,?,?,?)",
            ("c1", "YouTube", concept_meta, concept),
        )
        database.executemany(
            "insert into tbl_iconinfo_0123456789 values (?,?)",
            [("PPSA01650", "YouTube"), ("CUSA01015", "YouTube")],
        )
        database.execute(
            "insert into tbl_concepticoninfo_0123456789 values (?,?,?,?)",
            ("c1", "YouTube", "PPSA01650", "YouTube"),
        )
        database.commit()
        database.close()

    def dump(path):
        database = sqlite3.connect(path)
        rows = list(database.iterdump())
        database.close()
        return rows

    ours = '{"TITLE":"YouTube","TITLE_01":"YouTube","TITLE_ID":"PPSA01650"}'
    with tempfile.TemporaryDirectory() as work:
        shared = os.path.join(work, "shared.db")
        app_db(shared, "/user/appmeta/PPSA01650", ours)
        result = pst.retitle_app_db(shared, "PPSA01650", "Y2JB")
        assert result == {"old": "YouTube", "tile": True, "sharing": ["CUSA01015"]}, (
            result
        )
        rows = "\n".join(dump(shared))
        assert '"TITLE":"Y2JB","TITLE_01":"Y2JB","TITLE_ID":"PPSA01650"' in rows, rows
        assert (
            '{"data":"Y2JB","key":"concept_name","size":4,"type":2},'
            '{"data":"\\/user"' in rows
        ), rows
        assert (
            "VALUES('CUSA01015','YouTube','c1','{\"TITLE\":\"YouTube\"}')" in rows
            and "VALUES('CUSA01015','YouTube');" in rows
        ), rows
        assert "VALUES('c1','Y2JB','PPSA01650','Y2JB')" in rows, rows
        before = dump(shared)
        assert pst.retitle_app_db(shared, "PPSA01650", "Y2JB") is None
        assert dump(shared) == before

        foreign = os.path.join(work, "foreign.db")
        app_db(foreign, "/user/app/CUSA01015/sce_sys", ours)
        assert pst.retitle_app_db(foreign, "PPSA01650", "Y2JB")["tile"] is False
        rows = "\n".join(dump(foreign))
        assert "VALUES('c1','YouTube','/user/app/CUSA01015/sce_sys'" in rows
        assert "VALUES('c1','YouTube','PPSA01650','Y2JB')" in rows, rows

        loose = os.path.join(work, "loose.db")
        app_db(loose, "/user/appmeta/PPSA01650", '{"TITLE": "YouTube"}')
        expect_fail(pst.retitle_app_db, loose, "PPSA01650", "Y2JB")

        info = os.path.join(work, "appinfo.db")
        database = sqlite3.connect(info)
        database.execute("create table tbl_appinfo (titleId, key, val)")
        database.executemany(
            "insert into tbl_appinfo values (?,?,?)",
            [
                ("PPSA01650", "TITLE", "YouTube"),
                ("PPSA01650", "TITLE_ID", "PPSA01650"),
                ("PPSA01650", "_sort", "YouTube"),
                ("CUSA01015", "TITLE", "YouTube"),
            ],
        )
        database.commit()
        database.close()
        pst.retitle_appinfo_db(info, "PPSA01650", "YouTube", "Y2JB")
        assert [row for row in dump(info) if "INSERT" in row] == [
            "INSERT INTO \"tbl_appinfo\" VALUES('PPSA01650','TITLE','Y2JB');",
            "INSERT INTO \"tbl_appinfo\" VALUES('PPSA01650','TITLE_ID','PPSA01650');",
            "INSERT INTO \"tbl_appinfo\" VALUES('PPSA01650','_sort','YouTube');",
            "INSERT INTO \"tbl_appinfo\" VALUES('CUSA01015','TITLE','YouTube');",
        ], dump(info)
        expect_fail(pst.retitle_appinfo_db, info, "PPSA01650", "YouTube", "Y2JB")

    logo = Image.new("RGB", (300, 200), "white")
    logo.paste(Image.new("RGB", (60, 30), "red"), (20, 150))
    master = pst.avatar_master(logo)
    box = ImageChops.difference(
        master, Image.new("RGBA", master.size, (255, 255, 255, 255))
    ).getbbox(alpha_only=False)
    assert master.size == (440, 440) and master.getpixel((0, 0)) == (
        255,
        255,
        255,
        255,
    ), master.size
    assert abs((box[0] + box[2]) / 2 - 220) <= 1, box
    assert abs((box[1] + box[3]) / 2 - 220) <= 1, box
    assert ((box[2] - box[0]) ** 2 + (box[3] - box[1]) ** 2) ** 0.5 <= (
        440 * pst.AVATAR_CIRCLE + 2
    ), box
    photo = Image.new("RGB", (400, 200))
    photo.putdata([(x % 256, y, 0) for y in range(200) for x in range(400)])
    cropped = pst.avatar_master(photo)
    assert cropped.size == (440, 440)
    assert (
        cropped.getpixel((0, 220))[0]
        == pst.avatar_master(photo.crop((100, 0, 300, 200))).getpixel((0, 220))[0]
    )
    expect_fail(pst.avatar_master, Image.new("RGB", (50, 50), "white"))
    files = pst.avatar_files(logo, "Player")
    assert sorted(files) == sorted(
        ["avatar.png", "picture.png", "online.json"]
        + [
            f"{kind}{size:d}.dds"
            for kind in ("avatar", "picture")
            for size in (440, 260, 128, 64)
        ]
    ), sorted(files)
    for size in (440, 260, 128, 64):
        dds = files[f"avatar{size:d}.dds"]
        assert dds[:4] == b"DDS " and struct.unpack("<I", dds[4:8])[0] == 124
        assert struct.unpack("<II", dds[12:20]) == (size, size)
        assert dds[84:88] == b"DXT5", dds[84:88]
    assert Image.open(io.BytesIO(files["avatar.png"])).size == (440, 440)
    framed = Image.new("RGB", (240, 240), "blue")
    framed.paste(Image.new("RGB", (40, 40), "yellow"), (100, 100))
    kept = pst.avatar_master(framed, fill=True)
    assert kept.getpixel((5, 5)) == (0, 0, 255, 255)
    assert kept.getpixel((220, 220)) == (255, 255, 0, 255)
    assert kept.getpixel((150, 150)) == (0, 0, 255, 255)
    with tempfile.TemporaryDirectory() as work:
        for name in ("b.png", "a.jpg", "notes.txt"):
            open(os.path.join(work, name), "wb").close()
        assert [stem for stem, _ in pst.pack_pictures([work])] == ["a", "b"]
        os.mkdir(os.path.join(work, "x"))
        open(os.path.join(work, "x", "a b.png"), "wb").close()
        open(os.path.join(work, "x", "a_b.jpg"), "wb").close()
        expect_fail(pst.pack_pictures, [os.path.join(work, "x")])
        expect_fail(pst.pack_pictures, [os.path.join(work, "missing")])
    assert json.loads(files["online.json"]) == {
        "firstName": "Player",
        "lastName": "",
        "isOfficiallyVerified": "true",
    }

    param = (
        '{\n  "localizedParameters": {\n    "en-US": {\n'
        '      "titleName": "YouTube"\n    }\n  }\n}'
    )
    assert pst.retitle_param(param, "YouTube", "Y2JB") == param.replace(
        '"YouTube"', '"Y2JB"'
    )
    expect_fail(pst.retitle_param, param, "Netflix", "Y2JB")
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "archives"))
        for name in ("archives/toycollection.pak", "archives/same.pak"):
            open(os.path.join(root, name), "w").close()
        eboot = (
            b"\x00app:/archives/ToyCollection.pak\x00"
            b"app:/archives/same.pak\x00app:/archives/Missing.pak\x00"
        )
        assert pst.case_mismatches(root, eboot) == [
            ("archives/ToyCollection.pak", "archives/toycollection.pak")
        ]
    igb = bytearray(0x40)
    igb[0x28:0x2C] = b"\x00\x00\xfa\xda"
    assert pst.save_format(bytes(igb))[0] == "igb"
    assert pst.save_format(bytes(igb))[1].startswith("big-endian")
    igb[0x28:0x2C] = b"\xda\xfa\x00\x00"
    assert pst.save_format(bytes(igb))[1].startswith("little-endian")
    assert pst.fnv1a32(b"") == 0x811C9DC5
    assert pst.fnv1a32(b"a") == 0xE40C292C
    body = struct.pack(">4I", 0x66464F00, 0x00080000, 0, 0x00008000)
    wiiu = body + struct.pack(">I", pst.fnv1a32(body))
    assert pst.save_format(wiiu)[0] == "tfb"
    assert pst.tfb_order(wiiu) == ">"
    ps4 = pst.convert_tfb(wiiu, "<")
    assert ps4[:16] == struct.pack("<4I", 0x66464F00, 0x00080000, 0, 0x00008000)
    assert pst.tfb_order(ps4) == "<"
    assert pst.convert_tfb(ps4, ">") == wiiu
    expect_fail(pst.convert_tfb, wiiu[:5] + b"\x01" + wiiu[6:], "<")
    assert pst.save_format(bytes(64))[0] == "unknown"
    assert "fnv1a32, stored big-endian" in pst.trailer_checksums(wiiu)
    crc_body = b"abc" * 20
    crc_sample = crc_body + struct.pack("<I", zlib.crc32(crc_body))
    assert (
        "crc32 poly 04c11db7 reflected init ffffffff xorout ffffffff, "
        "stored little-endian"
    ) in pst.trailer_checksums(crc_sample)
    with open(os.path.join("fixtures", "swapforce-global-ps4.igb"), "rb") as source:
        ps4_igb = source.read()
    layout = pst.igb_parse(ps4_igb)
    assert layout["endian"] == "<"
    assert pst.igb_accounted(layout, len(ps4_igb)) is None
    kind, wiiu_igb = pst.convert_save(ps4_igb, "be")
    assert kind == "igb" and wiiu_igb != ps4_igb
    assert pst.save_format(wiiu_igb)[1].startswith("big-endian")
    assert pst.igb_same_structure(layout, pst.igb_parse(wiiu_igb))
    assert pst.convert_save(wiiu_igb, "le")[1] == ps4_igb
    expect_fail(pst.igb_convert, ps4_igb, "le")
    expect_fail(pst.igb_parse, ps4_igb[:-8])
    flagged = bytearray(ps4_igb)
    flagged[0x2E] ^= 0x01
    expect_fail(pst.igb_parse, bytes(flagged))
    ps5_itt = {
        "Profile": {
            "EULA_Accepted": "true",
            "UID": "AA",
            "FurthestUnlockedChapter": "start",
        },
        "CloudSettings": {},
        "LocalSettings": {"AudioChannelSetup": "Surround"},
    }
    switch_itt = {
        "Profile": {
            "EULA_Accepted": "true",
            "UID": "BB",
            "LastSaveChapter": "playroom",
            "ProfileFlag.Lantern": "True",
        },
        "CloudSettings": {"Subtitles": "On"},
        "LocalSettings": {"Gamma": "0.0"},
    }
    merged = json.loads(pst.itt_merge(ps5_itt, switch_itt, True))
    assert merged["Profile"]["UID"] == "AA"
    assert merged["Profile"]["ProfileFlag.Lantern"] == "True"
    assert merged["Profile"]["FurthestUnlockedChapter"] == pst.ITT_ENDING
    assert sum(key.startswith("Minigame.") for key in merged["Profile"]) == 25
    assert merged["CloudSettings"] == {"Subtitles": "On"}
    assert merged["LocalSettings"] == {"AudioChannelSetup": "Surround"}
    expect_fail(pst.itt_merge, {"Profile": {}}, None, True)
    banner = (
        "Welcome to shsrv.elf running on pid 100\nModel:          "
        "CFI-1000A 01Y\nS/W:               13.000.000\nSoC temp:"
        "               37 \xb0C\nCPU temp:               41 \xb0C\n"
        "CPU freq:            3200 MHz\n"
    )
    temps = pst.parse_temps(banner)
    assert (temps["soc"], temps["cpu"], temps["freq"]) == ("37", "41", "3200")
    assert temps["model"] == "CFI-1000A 01Y"
    expect_fail(pst.parse_temps, "Welcome to shsrv.elf\nCPU freq: 3200 MHz\n")
    ps4_save = {"type": "ps4", "path": "/user/home/u/savedata/C/sdimg_S01"}
    assert pst.encrypted_names(ps4_save, "S01") == ["sdimg_S01", "S01.bin"]
    ps5_save = {"type": "ps5", "path": "/user/home/u/savedata_prospero/P/sdimg_P"}
    assert pst.encrypted_names(ps5_save, "P") == ["sdimg_P"]
    expect_fail(pst.encrypted_names, {"type": "", "path": "/x/sdimg_Q"}, "Q")
    assert pst.printable_strings(
        b"\x57\x00save_version\x00ab\x00credits_watched\x00tail"
    ) == ["save_version", "credits_watched"]
    assert pst.mounted_files(
        [
            {"name": "sce_sys", "dir": True},
            {"name": "sce_sys/param.sfo", "dir": False},
            {"name": "SYS-DATA.sav", "dir": False},
        ]
    ) == ["SYS-DATA.sav", "sce_sys/param.sfo"]
    with tempfile.TemporaryDirectory() as root:
        for name in ("sce_sys/param.sfo", "SYS-DATA.sav", "sub/x.bin"):
            path = os.path.join(root, *name.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
        assert pst.push_files(root) == ["SYS-DATA.sav", "sub/x.bin"]
    for elf_type, digest in (
        (0xFE10, "d85f75cb8c78078d609f437c023314734424d1d02d54cb934d8308f69956e934"),
        (0xFE18, "e8a960ff6e90ed20cb63d8265bdc692d73f00fc1b2d754212f7cd1661bce31bb"),
    ):
        signed = pst.fake_self(synthetic_elf(elf_type))
        assert hashlib.sha256(signed).hexdigest() == digest, hex(elf_type)
    elf = synthetic_elf(0xFE10)
    expect_fail(pst.fake_self, b"\x4f\x15\x3d\x1d" + elf[4:])
    expect_fail(pst.fake_self, elf[:18] + b"\xb7\x00" + elf[20:])
    expect_fail(pst.fake_self, synthetic_elf(0x3))
    expect_fail(pst.fake_self, elf[:-20])
    dynamic = 0x40 + 2 * 0x38 + 8
    far = elf[:dynamic] + struct.pack("<Q", len(elf) + 0x1000) + elf[dynamic + 8 :]
    assert len(pst.fake_self(far)) == len(pst.fake_self(elf))
    with tempfile.TemporaryDirectory() as root:
        for name, data in (
            ("eboot.bin", elf),
            ("sce_module/libc.prx", elf),
            ("sce_sys/param.sfo", b"\x00PSF"),
            ("sce_sys/keystone", b"k"),
            ("sce_sys/license.dat", b"l"),
            ("sce_sys/icon0_03.dds", b"i"),
            ("sce_sys/about/right.sprx", b"\x4f\x15\x3d\x1d"),
            ("CUSA00001.gp4", b"<x/>"),
            ("data/a.pak", b"a"),
            ("empty/.keep", b""),
        ):
            path = os.path.join(root, *name.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as output:
                output.write(data)
        files, dirs, encrypted = pst.fpkg_plan(root)
        assert files == [
            ("eboot.bin", True),
            ("data/a.pak", False),
            ("empty/.keep", False),
            ("sce_module/libc.prx", True),
            ("sce_sys/keystone", False),
            ("sce_sys/param.sfo", False),
        ], files
        assert sorted(dirs) == ["data", "empty", "sce_module", "sce_sys"]
        assert encrypted == []
        os.makedirs(os.path.join(root, "game"))
        with open(os.path.join(root, "game", "x.sprx"), "wb") as output:
            output.write(b"\x4f\x15\x3d\x1d")
        assert pst.fpkg_plan(root)[2] == ["game/x.sprx"]
        need = pst.fpkg_need(root, files, dirs)
        signed = len(pst.fake_self(elf))
        floor = sum(
            [
                2 * signed,
                2 * pst.align_up(signed, 0x10000),
                3 * 0x10000,
                (len(dirs) + 1) * 0x10000,
            ]
        )
        assert need >= floor, (need, floor)
        many = pst.fpkg_need(root, files, dirs + [f"d{i:d}" for i in range(3000)])
        assert many - need >= 3000 * 0x10000, many - need
        outside = os.path.join(root, "out", "deeper")
        assert pst.existing_parent(outside) == root
        assert pst.fpkg_out_dir(outside, root, 1, {}) == outside
        expect_fail(pst.fpkg_out_dir, outside, root, 1 << 62, {})
        game = os.path.join(root, "data")
        assert pst.fpkg_out_dir(None, game, 1, {}) == root
        half = pst.shutil.disk_usage(root).free // 2 + 1
        reserved = {}
        assert pst.fpkg_out_dir(outside, root, half, reserved) == outside
        expect_fail(pst.fpkg_out_dir, outside, root, half, reserved)
        assert pst.fpkg_out_dir(outside, root, half, {}) == outside
        assert pst.inside(outside, game) is False
        assert pst.inside(os.path.join(game, "out"), game) is True
        alias = os.path.join(root, "alias")
        os.symlink(game, alias)
        assert pst.inside(os.path.join(alias, "out"), game) is True
        with open(os.path.join(game, "\u00e9t\u00e9.bin"), "wb"):
            pass
        expect_fail(pst.fpkg_plan, root)
    with tempfile.TemporaryDirectory() as drive:

        def dump(title_id, category, content):
            root = os.path.join(drive, title_id)
            for name, data in (
                ("eboot.bin", elf),
                (
                    "sce_sys/param.sfo",
                    sfo(
                        [
                            ("CATEGORY", 0x0204, category + b"\x00"),
                            ("CONTENT_ID", 0x0204, content + b"\x00"),
                            ("TITLE", 0x0204, b"Game " + title_id.encode() + b"\x00"),
                        ]
                    ),
                ),
            ):
                path = os.path.join(root, *name.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as output:
                    output.write(data)
            return root

        ready = dump("CUSA00001", b"gd", b"UP0001-CUSA00001_00-AAAAAAAAAAAAAAAA")
        running = dump("CUSA00002", b"gd", b"UP0001-CUSA00002_00-BBBBBBBBBBBBBBBB")
        open(running + ".dumping", "w").close()
        update = dump("CUSA00003", b"gp", b"UP0001-CUSA00003_00-CCCCCCCCCCCCCCCC")
        done = dump("CUSA00004", b"gd", b"UP0001-CUSA00004_00-DDDDDDDDDDDDDDDD")
        open(
            os.path.join(drive, "UP0001-CUSA00004_00-DDDDDDDDDDDDDDDD.pkg"), "w"
        ).close()
        crashed = dump("CUSA00005", b"gd", b"UP0001-CUSA00005_00-EEEEEEEEEEEEEEEE")
        for name in (
            "UP0001-CUSA00005_00-EEEEEEEEEEEEEEEE.pkg",
            "UP0001-CUSA00005_00-EEEEEEEEEEEEEEEE.work",
        ):
            os.makedirs(os.path.join(drive, name))
        rows = pst.fpkg_queue([ready, running, update, done, crashed], None)
        assert [row["state"] for row in rows] == [
            "queued",
            "invalid",
            "invalid",
            "built",
            "partial",
        ], rows
        assert rows[0]["out"] == drive
        assert "dumping" in rows[1]["note"] and "gp" in rows[2]["note"]
        table = pst.fpkg_table(rows)
        assert table[0].startswith("CUSA00001  Game CUSA00001"), table
        assert len(table) == 5
        expect_fail(
            pst.cmd_fpkg,
            pst.argparse.Namespace(
                paths=[ready, ready + "/"],
                dir=None,
                plan=True,
                send=None,
                remove_dump=False,
            ),
        )
    project = ElementTree.fromstring(
        pst.gp4_xml(
            "UP0001-CUSA00001_00-0000000000000000",
            "2026-10-11",
            [("eboot.bin", "/w/eboot.bin"), ("sce_sys/param.sfo", "/d/p.sfo")],
            ["sce_sys", "sce_sys/trophy", "data"],
        )
    )
    assert project.find("volume/volume_type").text == "pkg_ps4_app"
    assert project.find("volume/package").get("passcode") == "0" * 32
    assert [f.get("targ_path") for f in project.iter("file")] == [
        "eboot.bin",
        "sce_sys/param.sfo",
    ]
    assert [d.get("targ_name") for d in project.find("rootdir")] == ["data", "sce_sys"]
    assert (
        project.find("rootdir/dir[@targ_name='sce_sys']/dir").get("targ_name")
        == "trophy"
    )
    assert pst.pubtool_date({"PUBTOOLINFO": "c_date=20170324,c_time=1"}) == (
        "2017-03-24"
    )
    os.environ["PST_PS5"] = "127.0.0.1"
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()
    pst.DUMPER_PORT = pst.GARLIC_PORT = closed_port
    assert pst.dumper_running() is False
    assert pst.garlic_running() is False
    check_uploads()
    print("check: ok")
    return 0


class FakeFtp:
    def __init__(self, fail_on=None, short_on=None):
        self.files, self.dirs = {}, {"/", "/data", "/data/homebrew"}
        self.fail_on, self.short_on = fail_on, short_on

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def voidcmd(self, _command):
        return "200"

    def cwd(self, path):
        if path not in self.dirs:
            raise pst.ftplib.error_perm("550 no such directory")

    def mkd(self, path):
        self.dirs.add(path)

    def storbinary(self, command, source, blocksize):
        path = command[len("STOR ") :]
        if path == self.fail_on:
            raise OSError("connection reset")
        data = source.read()
        self.files[path] = data[:-1] if path == self.short_on else data

    def size(self, path):
        if path not in self.files:
            raise pst.ftplib.error_perm("550 no such file")
        return len(self.files[path])

    def delete(self, path):
        if path not in self.files:
            raise pst.ftplib.error_perm("550 no such file")
        del self.files[path]

    def rename(self, old, new):
        for table in (self.files, self.dirs):
            for name in [
                name for name in table if name == old or name.startswith(old + "/")
            ]:
                moved = new + name[len(old) :]
                if isinstance(table, dict):
                    table[moved] = table.pop(name)
                else:
                    table.discard(name)
                    table.add(moved)

    def nlst(self, path):
        return [
            name
            for name in list(self.files) + list(self.dirs)
            if posixpath.dirname(name) == path
        ]

    def rmd(self, path):
        self.dirs.discard(path)


def check_uploads():
    with tempfile.TemporaryDirectory() as work:
        dump = os.path.join(work, "dump")
        os.makedirs(os.path.join(dump, "sce_sys"))
        with open(os.path.join(dump, "sce_sys", "param.json"), "w") as out:
            json.dump({"titleId": "PPSA00001"}, out)
        with open(os.path.join(dump, "eboot.bin"), "wb") as out:
            out.write(b"\x7fELF" + bytes(60))
        args = pst.argparse.Namespace(path=dump, fself=False)
        pst.ftp_dirs = lambda path: []

        good = FakeFtp()
        pst.ftp = lambda address=None: good
        pst.cmd_send(args)
        assert good.files["/data/homebrew/PPSA00001/eboot.bin"][:4] == b"\x7fELF"
        assert not any(
            name.startswith(pst.SEND_STAGING)
            for name in list(good.files) + list(good.dirs)
        )

        broken = FakeFtp(fail_on="/data/pst-staging/PPSA00001/eboot.bin")
        pst.ftp = lambda address=None: broken
        expect_fail(pst.cmd_send, args)
        assert not any(
            name.startswith("/data/homebrew/PPSA00001")
            for name in list(broken.files) + list(broken.dirs)
        )

        short = FakeFtp(short_on="/data/pst-staging/PPSA00001/eboot.bin")
        pst.ftp = lambda address=None: short
        expect_fail(pst.cmd_send, args)
        assert "/data/pst-staging/PPSA00001/eboot.bin" not in short.files

        def refused(address=None):
            raise ConnectionRefusedError(111, "Connection refused")

        pst.ftp = refused
        assert pst.main(["send", dump]) == 1


if __name__ == "__main__":
    sys.exit(main())
