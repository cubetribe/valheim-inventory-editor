# Valheim character save format (.fch): player data v34, inventory v110

Reverse-engineered from a real save (November 2026). Confirmed by a matching SHA-512 checksum, prefab hashes that resolve to real item names, and a rebuild that reproduces the original file byte for byte.

## Envelope

```
int32  len(data)
bytes  data
int32  64
bytes  SHA-512(data)
```

After any change the checksum has to be recomputed, otherwise the game rejects the file.

## data

The header (stats, worlds with map data, name, ID, …) is left untouched. The player data block is the last field:

```
bool   true
int32  len(blob)
bytes  blob          # runs exactly to the end of data
```

The script looks for the single position where `01` + int32 equals the remaining length. If the block grows, that int32 must be updated.

## blob (player data v34)

```
int32  34              version
float  max HP, HP, max stamina, time since death
string guardian power  (7-bit length prefix + UTF-8, e.g. "GP_TheElder")
float  guardian power cooldown
--- inventory ---
int32  110             inventory version
u8     item count      (can also be read as int16, see below)
items  ...
u8     0
int32  known recipe count, then "$item_…" / "$piece_…" strings  (copied unchanged)
...
```

## Item (inventory v110)

```
u8     0
int32  durability × 100        (materials: 10000)
u8     x                       (0–7)
u8     y                       (0–3, 0 = hotbar)
u8     0
u8     flags
[int16 quality]                if flags & 0x04 (omitted for quality 1)
[int16 stack]                  if flags & 0x08 (omitted for stack 1)
[int64 crafter ID + string crafter name]   if flags & 0x20
int32  StableHash(prefab name)
```

Observed flags: 0x01 and 0x40 are always set, 0x02 = equipped, 0x04 = quality follows, 0x08 = stack follows, 0x20 = crafter follows. 0x10 was never observed and is probably extra data; the script refuses such items. A picked-up material stack has flags 0x49.

The zero bytes at the start of each item and after the last item can also be read as "int16 count + items ending in 0". Both readings produce the same bytes when appending at the end with fewer than 256 items.

StableHash is Valheim's `GetStableHashCode` (`stable_hash` in `valheim_inv.py`).

## After a game update

If the script reports a different version:

1. Make a fresh backup of the .fch and only work on copies.
2. Dump the start of the blob as hex and compare it with the layout above.
3. Compute `stable_hash` for known items (e.g. `Iron`, `Hammer`) and search for them in the blob. The distances between hits reveal the new item layout.
4. Raise the version check in the script only once a rebuild of the unmodified file is byte-identical.
