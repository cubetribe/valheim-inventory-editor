#!/usr/bin/env python3
"""Valheim inventory editor for character save files (.fch).

Supported save format: player data v34, inventory v110.

Commands:
  list                         show the inventory
  add    ITEM AMOUNT           add items (tops up stacks first, then free slots)
  set    ITEM TOTAL            bring the total of an item to exactly TOTAL
  remove ITEM AMOUNT|all       remove items
  dupe   X Y [COPIES]          copy the item in slot (X,Y) into free slots

ITEM is a prefab name (Iron, FineWood, Coins) or an English/German display
name from references/items.tsv ("Core wood", "Eisen").

Options:
  --char NAME       character name (default: the only one found)
  --file PATH       a specific .fch file instead of auto-detection
  --out PATH        write the result there instead of replacing the file (testing)
  --dry-run         show the result, write nothing
  --stack-max N     max stack size if the item is not listed in items.tsv
  --backup-dir DIR  where backups go (default: ~/valheim-inventory-backups
                    or the VALHEIM_INV_BACKUP_DIR environment variable)
  --grid WxH        inventory size (default 8x4)

Writes only while Valheim is not running. Before replacing a save it creates a
backup, and afterwards it re-reads and verifies the written file.
"""
import argparse
import datetime
import glob
import hashlib
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEMS_TSV = HERE.parent / "references" / "items.tsv"
DEFAULT_BACKUP_DIR = os.environ.get("VALHEIM_INV_BACKUP_DIR",
                                    str(Path.home() / "valheim-inventory-backups"))

PLAYER_VERSION = 34
INVENTORY_VERSION = 110
F_EQUIPPED, F_QUALITY, F_STACK, F_CRAFTER = 0x02, 0x04, 0x08, 0x20
PLAIN_FLAGS = 0x49  # a picked-up, non-crafted stack (as observed for Iron)

STEAM_DIRS = [os.environ.get("STEAM_DIR", ""), "C:/Program Files (x86)/Steam",
              "~/.steam/steam", "~/.local/share/Steam"]
CHAR_DIRS = [os.path.expanduser(f"{s}/userdata/*/892970/remote/characters") for s in STEAM_DIRS if s] + [
    os.path.expanduser("~/AppData/LocalLow/IronGate/Valheim/characters_local"),
    os.path.expanduser("~/.config/unity3d/IronGate/Valheim/characters_local"),
]


def stable_hash(s):
    """Valheim's string.GetStableHashCode()."""
    def i32(x):
        return ((x + 2**31) % 2**32) - 2**31
    a = b = 5381
    i = 0
    while i < len(s):
        a = i32(((a << 5) + a) ^ ord(s[i]))
        if i == len(s) - 1:
            break
        b = i32(((b << 5) + b) ^ ord(s[i + 1]))
        i += 2
    return i32(a + b * 1566083941)


def load_item_table():
    by_hash, by_name = {}, {}
    if ITEMS_TSV.exists():
        for line in ITEMS_TSV.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cols = [c.replace("#ok", "").strip() for c in (line.split("\t") + ["", "", ""])[:4]]
            prefab, stack, name_en, name_de = cols
            entry = dict(prefab=prefab, stack=int(stack) if stack else None, name=name_en)
            by_hash[stable_hash(prefab)] = entry
            for key in (prefab, name_en, name_de):
                if key:
                    by_name.setdefault(key.lower(), entry)
    return by_hash, by_name


ITEMS_BY_HASH, ITEMS_BY_NAME = load_item_table()


class Reader:
    def __init__(self, b, pos=0):
        self.b, self.pos = b, pos

    def take(self, n):
        v = self.b[self.pos:self.pos + n]
        if len(v) != n:
            raise ValueError(f"unexpected end of data at {self.pos}")
        self.pos += n
        return v

    def u8(self):
        return self.take(1)[0]

    def i16(self):
        return struct.unpack("<h", self.take(2))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def i64(self):
        return struct.unpack("<q", self.take(8))[0]

    def f32(self):
        return struct.unpack("<f", self.take(4))[0]

    def string(self):
        n, shift = 0, 0
        while True:
            byte = self.u8()
            n |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                break
        return self.take(n).decode("utf-8")


class Item:
    """One inventory entry kept as raw bytes; fields are read/written by offset."""

    def __init__(self, raw):
        self.raw = bytearray(raw)

    @property
    def flags(self):
        return self.raw[8]

    @property
    def x(self):
        return self.raw[5]

    @property
    def y(self):
        return self.raw[6]

    @property
    def hash(self):
        return struct.unpack("<i", self.raw[-4:])[0]

    @property
    def durability(self):
        return struct.unpack("<i", self.raw[1:5])[0] / 100

    @property
    def quality(self):
        return struct.unpack("<h", self.raw[9:11])[0] if self.flags & F_QUALITY else 1

    def _stack_at(self):
        return 9 + (2 if self.flags & F_QUALITY else 0)

    @property
    def stack(self):
        k = self._stack_at()
        return struct.unpack("<h", self.raw[k:k + 2])[0] if self.flags & F_STACK else 1

    @stack.setter
    def stack(self, n):
        k = self._stack_at()
        if not self.flags & F_STACK:
            if n == 1:
                return
            self.raw[8] |= F_STACK
            self.raw[k:k] = b"\0\0"
        self.raw[k:k + 2] = struct.pack("<h", n)

    @property
    def crafter(self):
        if not self.flags & F_CRAFTER:
            return None
        r = Reader(bytes(self.raw), self._stack_at() + (2 if self.flags & F_STACK else 0) + 8)
        return r.string()

    def moved(self, x, y):
        c = Item(self.raw)
        c.raw[5], c.raw[6] = x, y
        c.raw[8] &= ~F_EQUIPPED & 0xFF
        return c

    @staticmethod
    def plain(prefab_hash, x, y, n):
        raw = bytes([0]) + struct.pack("<i", 10000) + bytes([x, y, 0, PLAIN_FLAGS])
        return Item(raw + struct.pack("<h", n) + struct.pack("<i", prefab_hash))

    def name(self):
        e = ITEMS_BY_HASH.get(self.hash)
        return e["prefab"] if e else f"?{self.hash & 0xFFFFFFFF:08x}"


class Profile:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        r = Reader(raw)
        self.data = r.take(r.i32())
        stored = r.take(r.i32())
        if r.pos != len(raw):
            raise ValueError("unexpected bytes after the checksum")
        if hashlib.sha512(self.data).digest() != stored:
            raise ValueError("checksum mismatch, the file looks damaged")
        hits = [o for o in range(5, len(self.data))
                if self.data[o - 5] == 1
                and struct.unpack("<i", self.data[o - 4:o])[0] == len(self.data) - o]
        if len(hits) != 1:
            raise ValueError("could not locate the player data block")
        self.blob_at = hits[0]
        blob = self.data[self.blob_at:]
        r = Reader(blob)
        ver = r.i32()
        if ver != PLAYER_VERSION:
            raise ValueError(f"player data version {ver}, expected {PLAYER_VERSION}; "
                             "the game was probably updated, see references/format.md")
        r.f32(); r.f32(); r.f32(); r.f32()  # max HP, HP, max stamina, time since death
        r.string(); r.f32()                  # guardian power, cooldown
        inv_ver = r.i32()
        if inv_ver != INVENTORY_VERSION:
            raise ValueError(f"inventory version {inv_ver}, expected {INVENTORY_VERSION}; "
                             "the game was probably updated, see references/format.md")
        self.count_at = r.pos
        count = r.u8()
        self.items = []
        for _ in range(count):
            start = r.pos
            if r.u8() != 0:
                raise ValueError(f"unexpected lead byte for item at {start}")
            r.take(4 + 3)
            flags = r.u8()
            if flags & F_QUALITY:
                r.i16()
            if flags & F_STACK:
                r.i16()
            if flags & F_CRAFTER:
                r.i64(); r.string()
            if flags & ~(0x01 | F_EQUIPPED | F_QUALITY | F_STACK | 0x10 | F_CRAFTER | 0x40) & 0xFF:
                raise ValueError(f"unknown item flags {flags:#04x}, see references/format.md")
            if flags & 0x10:
                raise ValueError("item with extra data (flag 0x10) is not supported yet")
            r.i32()
            self.items.append(Item(blob[start:r.pos]))
        self.inv_end = r.pos
        # Next: one 0 byte, then the known recipes (int32 count + "$..." strings)
        tail = Reader(blob, self.inv_end + 1)
        if blob[self.inv_end] != 0 or tail.i32() <= 0 or not tail.string().startswith("$"):
            raise ValueError("data after the inventory does not look like the recipe list")
        if self.rebuild(self.items) != self.data:
            raise ValueError("self-test failed: rebuilding does not reproduce the same bytes")

    def rebuild(self, items):
        blob = self.data[self.blob_at:]
        new_blob = (blob[:self.count_at] + bytes([len(items)])
                    + b"".join(bytes(i.raw) for i in items) + blob[self.inv_end:])
        return self.data[:self.blob_at - 4] + struct.pack("<i", len(new_blob)) + new_blob


def write_fch(path, data):
    digest = hashlib.sha512(data).digest()
    with open(path, "wb") as f:
        f.write(struct.pack("<i", len(data)) + data + struct.pack("<i", len(digest)) + digest)


def find_character(char):
    files = []
    for pattern in CHAR_DIRS:
        files += glob.glob(os.path.join(pattern, "*.fch"))
    files = sorted({os.path.realpath(f) for f in files if "_backup_" not in os.path.basename(f)})
    if char:
        files = [f for f in files if Path(f).stem.lower() == char.lower()]
    if len(files) != 1:
        names = ", ".join(sorted(Path(f).stem for f in files)) or "none"
        raise SystemExit(f"Character file is ambiguous (found: {names}). Use --char or --file.")
    return files[0]


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq valheim.exe", "/NH"],
                             capture_output=True, text=True, errors="replace").stdout
    except FileNotFoundError:
        out = subprocess.run(["ps", "-A"], capture_output=True, text=True).stdout
    return "valheim" in out.lower()


def resolve_item(name, profile):
    e = ITEMS_BY_NAME.get(name.lower())
    if e:
        return e["prefab"], stable_hash(e["prefab"]), e["stack"]
    h = stable_hash(name)
    if not any(i.hash == h for i in profile.items):
        print(f"Warning: '{name}' is neither in items.tsv nor in the inventory. Check the "
              "prefab name; a wrong one makes the item vanish when the game loads.")
    return name, h, None


def free_slots(items, w, h):
    used = {(i.x, i.y) for i in items}
    order = [(x, y) for y in list(range(h - 1, 0, -1)) + [0] for x in range(w)]  # hotbar last
    return [p for p in order if p not in used]


def op_add(items, prefab_hash, amount, stack_max, w, h):
    stacks = [i for i in items if i.hash == prefab_hash]
    if stack_max is None:
        raise SystemExit("Max stack size unknown, pass --stack-max N.")
    left = amount
    for it in stacks:
        add = min(stack_max - it.stack, left)
        if add > 0:
            it.stack = it.stack + add
            left -= add
    free = free_slots(items, w, h)
    while left:
        if not free:
            raise SystemExit(f"Not enough free slots: {left} do not fit into the inventory.")
        x, y = free.pop(0)
        n = min(stack_max, left)
        if stacks:
            new = stacks[0].moved(x, y)
            new.stack = n
        else:
            new = Item.plain(prefab_hash, x, y, n)
        items.append(new)
        left -= n


def op_remove(items, prefab_hash, amount):
    stacks = sorted((i for i in items if i.hash == prefab_hash), key=lambda i: i.stack)
    total = sum(i.stack for i in stacks)
    if amount is None:
        amount = total
    if amount > total:
        raise SystemExit(f"Only {total} present, cannot remove {amount}.")
    left = amount
    for it in stacks:
        if not left:
            break
        take = min(it.stack, left)
        if take == it.stack:
            items.remove(it)
        else:
            it.stack = it.stack - take
        left -= take


def show(items, w, h):
    print(f"{'Slot':7} {'Item':40} {'Qty':>5}  Q  Dur.    Crafter")
    for it in sorted(items, key=lambda i: (i.y, i.x)):
        eq = " (equipped)" if it.flags & F_EQUIPPED else ""
        e = ITEMS_BY_HASH.get(it.hash)
        label = f"{it.name()}{' - ' + e['name'] if e and e['name'] else ''}"
        print(f"({it.x},{it.y})   {label:40.40} {it.stack:>5}  {it.quality}  {it.durability:6.1f}  {it.crafter or ''}{eq}")
    print(f"{len(items)} slots used, {w * h - len(items)} free.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "add", "set", "remove", "dupe"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--char")
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stack-max", type=int)
    ap.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    ap.add_argument("--grid", default="8x4")
    a = ap.parse_args()
    w, h = (int(v) for v in a.grid.lower().split("x"))

    path = a.file or find_character(a.char)
    prof = Profile(path)
    print(f"File: {path}")
    for it in prof.items:
        if it.x >= w or it.y >= h:
            raise SystemExit(f"Item at ({it.x},{it.y}) is outside {a.grid}, adjust --grid.")
    if a.cmd == "list":
        show(prof.items, w, h)
        return

    items = [Item(i.raw) for i in prof.items]
    if a.cmd == "dupe":
        x, y = int(a.args[0]), int(a.args[1])
        copies = int(a.args[2]) if len(a.args) > 2 else 1
        src = next((i for i in items if (i.x, i.y) == (x, y)), None)
        if not src:
            raise SystemExit(f"Slot ({x},{y}) is empty.")
        free = free_slots(items, w, h)
        if len(free) < copies:
            raise SystemExit(f"Only {len(free)} free slots.")
        items += [src.moved(*free[k]) for k in range(copies)]
        target = src.hash
    else:
        _, target, stack_max = resolve_item(a.args[0], prof)
        stack_max = a.stack_max or stack_max
        current = sum(i.stack for i in items if i.hash == target)
        if a.cmd == "add":
            op_add(items, target, int(a.args[1]), stack_max, w, h)
        elif a.cmd == "remove":
            op_remove(items, target, None if a.args[1] == "all" else int(a.args[1]))
        elif a.cmd == "set":
            want = int(a.args[1])
            if want > current:
                op_add(items, target, want - current, stack_max, w, h)
            elif want < current:
                op_remove(items, target, current - want)

    before = sum(i.stack for i in prof.items if i.hash == target)
    after = sum(i.stack for i in items if i.hash == target)
    new_data = prof.rebuild(items)
    print("\nNew inventory:")
    show(items, w, h)
    print(f"\nItem total: {before} -> {after}")
    if a.dry_run:
        print("Dry run: nothing written.")
        return

    if a.out:
        dest = a.out
    else:
        if game_running():
            raise SystemExit("Valheim is still running. Quit it completely, "
                             "otherwise the game overwrites the change on its next save.")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        bdir = Path(a.backup_dir) / f"backup_{Path(path).stem}_{stamp}"
        if bdir.exists():
            bdir = Path(f"{bdir}{datetime.datetime.now():%S}")
        bdir.mkdir(parents=True)
        for f in (path, path + ".old"):
            if os.path.exists(f):
                shutil.copy2(f, bdir)
        print(f"Backup: {bdir}")
        dest = path

    tmp = dest + ".tmp"
    write_fch(tmp, new_data)
    check = Profile(tmp)  # re-reads: checksum, format and byte-exact rebuild
    if check.data != new_data or [bytes(i.raw) for i in check.items] != [bytes(i.raw) for i in items]:
        os.remove(tmp)
        raise SystemExit("Verification of the new file failed, nothing replaced.")
    os.replace(tmp, dest)
    print(f"Written and verified: {dest}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as e:
        raise SystemExit(f"Error: {e}")
