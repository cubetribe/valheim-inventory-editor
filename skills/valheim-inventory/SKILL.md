---
name: valheim-inventory
description: Valheim inventory and character save editor. Edits a Valheim character's inventory directly in the save file (.fch). It can show the inventory, add resources and items (iron, wood, arrows, coins, mead …), set an exact total, remove items and duplicate gear, with an automatic backup and verification every time. Use this skill whenever the user wants to get, add, spawn, give, cheat in, increase or remove items, materials or gold in Valheim, or change their Valheim character, even if they never say "inventory" or "skill". Also for German requests such as "gib mir 200 Eisen".
---

# Valheim inventory editor

Valheim stores a character's inventory in the character save (`<name>.fch`) on the player's own PC, even when playing on a dedicated server. Edit that file correctly and the items are there on the next login. The script `scripts/valheim_inv.py` in this skill's folder does it byte-exact: it recomputes the SHA-512 checksum, backs up first, and re-reads the result to verify it.

Run it as `python "${CLAUDE_SKILL_DIR}/scripts/valheim_inv.py" <command>` (use `python3` on Linux/macOS).

## Where things are

- Character files are found automatically: Steam Cloud (`Steam/userdata/<id>/892970/remote/characters/`, Windows and Linux) and local characters (`characters_local`). With several characters pass `--char NAME`. For unusual locations pass `--file PATH` or set `STEAM_DIR`.
- Backups go to `~/valheim-inventory-backups/backup_<name>_<YYYY-MM-DD>_<HHMM>`. Override with `--backup-dir` or `VALHEIM_INV_BACKUP_DIR`.
- Item names (prefab, English, German) and max stack sizes: `references/items.tsv`
- Save format, and what to do after a game update: `references/format.md`

## Workflow

1. **Pin down the request.** Which item, how many, and should the amount be *added* (`add`) or is it the *total* (`set`)? The script accepts prefab names (`Iron`) as well as English or German names from `references/items.tsv` ("Core wood", "Eisen"). If an item is not listed, look up its exact prefab name and max stack size on the Valheim wiki ("Item IDs" page) or ask the user. A misspelled prefab name makes the item silently vanish when the game loads.

2. **Valheim must be fully closed, not just sitting in the main menu or lobby.** The game keeps the character in memory and overwrites the file on its next save. Check yourself (Windows: `tasklist /FI "IMAGENAME eq valheim.exe"`, Linux: `pgrep -i valheim`); the script refuses to write while the game runs anyway.
   If it is still running you may prepare the change with `--dry-run`, but then say unmistakably: **"Not applied yet."** Otherwise the player checks in game, finds nothing and assumes it failed.

3. **Look at the inventory:** `list`. It shows used and free slots. The inventory has 8×4 = 32 slots; row y=0 is the hotbar.

4. **Dry run:** run the change with `--dry-run` and tell the user the resulting amount.

5. **Apply:** run the same command without `--dry-run`. Look for "Backup: …" and "Written and verified: …" in the output. Only then is the change done.

6. **Tell the user:**
   - **"Applied."** They can start Valheim now, but not while you are still writing.
   - If Steam reports a cloud conflict, choose the **local files**, otherwise Steam brings the old version back.
   - Mention weight for large amounts: metal bars weigh 1 each, coins 0.1 each, base carry weight is 300.

## When the user says "it didn't work"

Don't blindly repeat `add`, that would double the amount. Check first:

1. `list` shows whether the items are in the file.
2. Compare timestamps: when was the .fch last written, and when did Valheim last start? The game log `Player.log` in `…/IronGate/Valheim/` begins with the start time. The most common cause is that the player looked before the change was applied, or the game was still running while writing and overwrote it later.
3. If the change really is missing, re-apply it with `set` and the desired **total**. `set` can be repeated without double counting.

## Commands

| Goal | Command |
|---|---|
| Show inventory | `list` |
| Add 200 iron | `add Iron 200` |
| Have exactly 50 wood | `set Wood 50` |
| Remove 20 iron | `remove Iron 20` |
| Remove all fire arrows | `remove ArrowFire all` |
| Copy the item in slot (3,0) twice | `dupe 3 0 2` |

Options: `--char NAME`, `--dry-run` (write nothing), `--stack-max N` (if the stack size is not in items.tsv), `--file PATH` (a specific file, e.g. a backup copy for testing), `--out PATH` (write the result elsewhere, without backup or game check, for testing only), `--grid 8x5` (if a mod enlarges the inventory), `--backup-dir DIR`.

`add` first tops up existing stacks to the max, then fills free slots from the bottom row up. A single stack above the max would be cut down by the game on load, so the script always splits amounts into proper stacks.

## Limits and what to do

- **Not enough free slots:** the script aborts before writing anything. Ask the user to put things in a chest, or add less.
- **Brand-new gear (weapons, armor) from nothing:** not supported, because durability and quality have to match the item. If the piece is already in the inventory, use `dupe`, which copies it exactly (unequipped).
- **Items with extra data** (flag 0x10) or unknown flags: the script aborts with a message. Don't edit the file by hand; study the format first (see `references/format.md`).
- **"player data version …" or "inventory version …" errors:** a game update changed the format. Read `references/format.md` and verify the new layout on a backup copy before changing the script. Never force it.
- **Unknown names in `list`** (e.g. `?d657b039`): an item that is not in items.tsv. It stays untouched. If you know its prefab name, add it to items.tsv; the hash confirms it automatically.
- **Server mods that store characters server-side** (e.g. "ServerCharacters"): the server overwrites the local file and this skill has no effect.

## Undo

Quit Valheim and copy the `<name>.fch` from the matching backup folder back into the characters folder. If Steam reports a conflict afterwards, choose the local files here too.
