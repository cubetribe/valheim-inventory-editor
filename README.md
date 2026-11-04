# 🪓 Valheim Inventory Editor: a Claude Code skill for Valheim save files (.fch)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill%20%26%20Plugin-d97757)](https://claude.com/claude-code)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Valheim](https://img.shields.io/badge/Valheim-save%20format%20v34%2Fv110-2f4f4f)](#limits)

> *"Odin sees everything. He just doesn't read save files."*

**Valheim Inventory Editor** is an open-source **Valheim save editor** packaged as a [Claude Code](https://claude.com/claude-code) skill and plugin. Tell Claude *"give my viking 200 iron"* and it edits your **Valheim character file (.fch)**: it adds items, resources, coins and arrows, sets exact amounts, removes junk and duplicates gear. No console, no `devcommands`, no BepInEx mod, no hex editor. Every change comes with an automatic backup and a byte-exact verification.

It works with **Steam Cloud saves**, local characters, **dedicated servers** and multiplayer worlds (your inventory lives on your PC), on **Windows**, plus **Linux and Steam Deck** paths.

---

## Why?

You spent 14 hours in the Swamp. Three Blobs poisoned you, a Draugr shot you with your own bow, and a Troll used you as a golf ball. Final haul: **3 iron**.

You've earned this. This skill brings you the rest.

## ✨ Features

| You say | Claude does |
|---|---|
| "Show me my inventory" | `list`: every slot with amount, quality, durability and crafter |
| "Give me 200 iron" | `add Iron 200`: tops up existing stacks and splits the rest into proper stacks |
| "I want exactly 50 fine wood" | `set FineWood 50` |
| "Get rid of the fire arrows" | `remove ArrowFire all` |
| "Copy that helmet" | `dupe 7 3`: an exact copy, unequipped |
| "MORE GOLD!" | `add Coins 3000`: Haldor approves |

- 🗣️ **Understands item names in English and German** ("Core wood", "Kernholz", `RoundLog`), mapped to Valheim prefab IDs via a built-in item list
- 📦 **Respects max stack sizes**: 200 iron becomes 7 stacks of up to 30, not one 200-stack that the game would silently cut to 30
- 💾 **Automatic backup** before every write
- ✅ **Verified writes**: recomputes the SHA-512 checksum and re-reads the file before replacing the original
- 🛑 **Refuses to write while Valheim is running**, because the game would overwrite the change
- 🧭 **Finds your character automatically** (Steam Cloud and `characters_local`)

## 🚀 Quick start

You need [Claude Code](https://claude.com/claude-code), Python 3.8+ and Valheim on PC.

**Install as a plugin** (inside Claude Code):

```
/plugin marketplace add cubetribe/valheim-inventory-editor
/plugin install valheim-inventory@valheim-inventory-editor
```

**Or install manually:** copy `skills/valheim-inventory` to `~/.claude/skills/` (Windows: `%USERPROFILE%\.claude\skills\`).

Then **quit Valheim completely** (the main menu doesn't count) and just ask:

```
Give my character Ragnar 100 iron and 50 fine wood.
```

## 💬 What it looks like

> **You:** I need 200 iron, the smelter hates me.
>
> **Claude:** Valheim is still running, so this is **not applied yet**. Dry run: Iron 3 → 203 in 7 stacks. Quit the game completely and I'll write it.
>
> **You:** closed.
>
> **Claude:** **Applied.** Backup created, file verified. Start Valheim, and mind your carry weight, Jarl.

## 🛡️ The safety belt

Save files are sacred. So:

1. **Backup first**, every time: `~/valheim-inventory-backups/backup_<name>_<date>_<time>`
2. **No writes while Valheim runs.** Otherwise the game overwrites your shiny new iron on its next save.
3. **Checksum recomputed and verified.** The new file is fully re-read before it replaces the original.
4. **Unknown save format? Abort.** After a game update the script would rather refuse than turn your viking into a Greydwarf.
5. **"It didn't work"?** The skill checks the file and the game log before re-applying, so nothing gets doubled.

## ⚙️ How it works

Valheim keeps each character in a `.fch` file: a length-prefixed data block followed by a SHA-512 hash. Inside it sits the player data block with the inventory. In the current format (inventory v110) every item is stored compactly as durability, slot, flags, optional quality/stack/crafter, and the **StableHash** of its prefab name (`Iron`, `Coins`, …).

The bundled Python script parses exactly that, edits only the inventory section, and leaves everything else byte-identical: map, skills, recipes and stats. The full byte layout is documented in [`references/format.md`](skills/valheim-inventory/references/format.md), along with how to re-check it after a game update.

## ❓ FAQ

**How do I add items to my Valheim inventory without the console or cheats?**
Install this skill, quit Valheim and ask Claude for the items. It edits your character save directly, so you need no `devcommands`, no admin rights and no mods.

**Where are Valheim character save files located?**
Steam Cloud (Windows): `C:\Program Files (x86)\Steam\userdata\<SteamID>\892970\remote\characters\<name>.fch`. Local characters: `%USERPROFILE%\AppData\LocalLow\IronGate\Valheim\characters_local\`. On Linux/Steam Deck: `~/.local/share/Steam/userdata/<SteamID>/892970/remote/characters/`. The skill finds them on its own.

**Does it work on dedicated servers and in multiplayer?**
Yes. Valheim stores the character, including the inventory, on your own PC. Exception: servers running mods that store characters server-side (e.g. ServerCharacters).

**Will it corrupt my save?**
It is built not to: backup first, checksum recomputed, result verified, and an abort on anything unknown. Backups are still like armor, though. You only notice how much you need them when the Troll is already swinging.

**I changed my inventory but the items are missing in game.**
Either Valheim was still running and overwrote the file, or Steam Cloud restored the old version. On a cloud conflict, choose the **local files**.

**Can I spawn new weapons or armor?**
Not from thin air, because durability and quality have to match. You can duplicate gear that is already in your inventory with `dupe`.

**Does it work on Steam Deck / Linux?**
The Linux and Steam Deck save paths are built in. It has been tested on Windows so far, and reports from Deck vikings are welcome.

**Will it still work after the next Valheim update?**
As long as the save format stays the same, yes. If Iron Gate changes the format, the script stops safely, and [`format.md`](skills/valheim-inventory/references/format.md) explains how to adapt it.

**Is this a mod? Do I need BepInEx?**
No. The game files are never touched; only your character save is edited.

## ⚖️ Fair play

- **Your own world:** go wild, you are the Jarl.
- **Your friends' server:** ask first. Whoever secretly carries 4,000 coins buys the next round of mead.
- **Carry weight:** 4,000 coins weigh about 400. Odin has a sense of humor, your carry weight doesn't.

## <a id="limits"></a>Limits

- Built for save format **player data v34 / inventory v110** (November 2026).
- Default inventory 8×4. For mods with bigger backpacks use `--grid 8x5`.
- No brand-new weapons or armor, but `dupe` copies existing ones.
- Items with extra data are left alone (the script aborts instead of guessing).

## 🤝 Contributing

Item names and max stack sizes live in [`items.tsv`](skills/valheim-inventory/references/items.tsv). Missing an item? Add a line (prefab, stack, English, German). Prefab names are confirmed automatically by hash when they show up in a real save. Pull requests for new save format versions are very welcome.

## Disclaimer

Unofficial fan project, not affiliated with or endorsed by Iron Gate AB or Coffee Stain Publishing. Valheim is a trademark of its respective owners. Use at your own risk.

## License

[MIT](LICENSE). Built by [cubetribe](https://github.com/cubetribe) with Claude Code while the smelter was running 🔥
