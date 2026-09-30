# How to download and play

You don't need Git, programming knowledge or an AI tool to play.

## Before you start

**What you need:**
- A 64-bit Windows 10 or 11 PC whose CPU supports **AVX2**. Most CPUs from 2014 onward do.
- 16 GB RAM is recommended; 8 GB may work but is untested.
- About **30 GB of free disk space**: 6 GB of downloads, 12 GB for the game, and room for saves.

**Turn on the Windows .NET Framework 3.5 feature.** The old game's connector needs it, even
though the game bundles its own modern .NET.
1. Open the Start menu and type **Turn Windows features on or off**, then open it.
2. Tick **.NET Framework 3.5 (includes .NET 2.0 and 3.0)**.
3. Click **OK** and let Windows download and install it.
4. Restart the PC if Windows asks.

If the game window never appears after ENTER REALM, this feature is the usual cause.

## 1. Pick an edition

| Edition | Choose it if… |
|---|---|
| **0.33b** | You want the custom Hibernian **Sluaghbinder** class, for you and the bots. |
| **0.33** | You want only the original Classic + Shrouded Isles classes. |

Both are the same game otherwise. If you're unsure, pick 0.33b. The Sluaghbinder is just one more
Hibernian choice, and you don't have to play it.

## 2. Download

1. Make a new, empty folder, for example `C:\Games\OfflineDAoC`.
2. From your edition's release page, download both of these files into that folder:
   - [v0.33b](https://github.com/shadowofze/OfflineDAoC/releases/tag/v0.33b):
     `DOWNLOAD-AND-PLAY-v0.33b.cmd` and `Get-OfflineDAoC.ps1`
   - [v0.33](https://github.com/shadowofze/OfflineDAoC/releases/tag/v0.33):
     `DOWNLOAD-AND-PLAY-v0.33.cmd` and `Get-OfflineDAoC.ps1`
3. Double-click the `.cmd` file. If Windows asks whether to run it, choose **Run anyway**.

The helper:
1. downloads the game in parts, about 6 GB in total
2. checks each part against its published fingerprint (SHA-256)
3. unpacks the game into a new folder next to the helper (`playable-v0.33b` or `playable-v0.33`)

It never overwrites an existing game and never starts anything by itself. If a download is
interrupted, run the helper again: finished parts are kept and only the missing ones are fetched.

## 3. Play

1. Open the new `playable-…` folder and double-click **START OFFLINE DAOC.cmd**.
2. In the launcher, click **START SERVER** and wait until it shows **RUNNING**. The first start
   takes longer.
3. Click **ENTER REALM**. The first time, your own local account is created automatically.
4. Create your character and play.
5. When you're done, quit the game, then click **STOP SERVER** in the launcher and wait for it to
   finish saving.

### Bots

A new install starts with an empty world:
1. Each realm's card in the launcher (**ALBION**, **MIDGARD**, **HIBERNIA**) has buttons to create
   level 1 or level 50 gamebots, 1, 10 or 100 at a time.
2. New bots log in gradually and then play on their own.

The launcher's bot goals settings choose how much bots solo, group or go to RvR at each level
range. You can recruit companion bots in game.

Handy in-game commands are listed in [QUICK-COMMANDS.md](QUICK-COMMANDS.md). The complete list is
in `ALL SERVER COMMANDS.txt`.

## Moving from an older version

Your old game keeps working and isn't changed. To bring your progress (account, characters, items,
money, houses and bots) into 0.33, follow [TRANSFER-PROGRESS.md](TRANSFER-PROGRESS.md).
In short:
1. Stop both games.
2. Run **IMPORT PROGRESS FROM OLD OFFLINE DAOC.cmd** in the new folder.
3. Pick your old folder.

## Troubleshooting

| Problem | Try this |
|---|---|
| The helper says the destination already exists | Delete or rename the old `playable-…` folder, or run the helper from a different empty folder. Existing games are never overwritten. |
| A part fails its check | Run the helper again; it downloads only what's missing or broken. |
| ENTER REALM stays greyed out | Wait until the launcher shows RUNNING. The first start can take a few minutes. |
| The game window doesn't appear | Turn on the .NET Framework 3.5 feature (see above), then try again. |
| "Port 10300 is in use" or the server won't start | Another Offline DAoC server is running. Stop it first; only one can run at a time. |
| Windows SmartScreen blocks a file | Choose **More info → Run anyway**. The files are unsigned community builds. |

## Older versions

v0.3, v0.31, v0.31b, v0.32 and v0.32b are still on the
[Releases page](https://github.com/shadowofze/OfflineDAoC/releases). Their helpers are in the
repository's [older-versions](../older-versions/) folder.
