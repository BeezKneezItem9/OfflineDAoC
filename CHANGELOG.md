# Changelog

The newest version is first. For the full detail of every earlier update, see
[docs/history/CHANGELOG-0.3-to-0.32b.md](docs/history/CHANGELOG-0.3-to-0.32b.md).

## Coming in 0.34 / 0.34b (not released yet)

**These fixes are not in the 0.33 or 0.33b download.** They are finished and in the source code
here on GitHub, and they will ship in the next full download, **0.34 / 0.34b**. More changes will
be added to this list before then. The 0.33 and 0.33b downloads stay exactly as they are.

**Companion bots**
- Pets keep one target when the party fights several enemies. They finish their spells, heals
  included, instead of restarting them, and they still step in when an enemy attacks their owner.
- Pet heals go to the most injured ally, companion bots in the group included, instead of the
  first injured ally found.
- Ranged companions (Enchanter, Wizard and the other casters) walk up to a distant target that you
  or your pet are fighting instead of standing still, and their own pets join the fight.
- Melee companions and melee gamebots no longer rubberband while running at their target. Every
  AI tick they dropped their chase order, so the attack code stopped them and started them again
  about twice a second.
- Bots and pets with more than one damage-over-time spell use all of them when they stack. They
  used to skip a second one whenever the target already had any damage over time on it.
- Companion bots and gamebots no longer wear gear built on another realm's model. 256 items in
  the database are marked for one realm but use another realm's model: 77 Albion, 130 Midgard and
  49 Hibernia. For example, the Midgard "woven pointed steeple" wizard hats use the Hibernia hat,
  which has no Valkyn or Troll shape, so it didn't fit a Valkyn's head. Bots now skip those items
  when choosing gear. The items are still there for players. A companion that is already summoned
  keeps its gear until you summon it again.

**Gamebots**
- Nine hungry shriller (Caillte Garran) and Cliffs of Moher spawns that sit next to aggressive
  monsters 15 or more levels higher are no longer used as bot camps or pull targets. The
  monsters are still there for players, and every other spawn of the same monster is still a
  normal bot goal.
- To make up for that, Cliffs of Moher gets four more bantam spectres and two more koalinth
  sentinels next to the safe ones, spread out on open ground away from trees, rocks and
  high-level monsters. Bots now have five bantam spectres and four Moher sentinels to grind. To
  add them to an existing 0.33 install now, run
  `tools/claude-version/add_moher_spectre_sentinel_spawns.py --apply` with the game closed.
- Gamebots no longer hunt the 13 wiggle worms in Bog of Cullen. The worms are level 0, but most
  monsters in that zone are level 40 or higher, so level 1 bots walked across Hibernia into it
  for almost no experience and often died on the way. The worms are still there for players.
- The Shrouded Isles neutral towns are always open to bots. Mantid (Krrzck), lammia (Cryptos
  Mythicos) and iarn dwarf (The Remnants) town residents near their faction's stable masters never
  attack bots, and bots never attack them, so bots can ride the wyvern, dragonfly and gryphon
  routes. Players still need reputation.
- A gamebot's pet now casts its group buffs on the bot and the bot's party. The Sluaghbinder's
  zombie priest used to recast its 20-minute Grave Renewal on itself forever and never follow its
  bot, because the buff only ever reached the pet.
- Bot progress is saved more evenly. With thousands of bots, saves for loot and gear changes took
  every save slot, so bots whose bags rarely changed (healers, full backpacks) could go about two
  hours without being saved. Routine saves now always get part of every batch, at the same total
  write rate, so every bot stays within a few minutes of its saved state.
- Tank bots, gamebots and companions alike, now use instant taunts (the Paladin, Friar and
  Sluaghbinder taunts). The bots only looked for taunts with a cast time, so these were never
  used. A tank bot taunts a monster that attacks someone in its group.
- A gamebot leaves a camp after three pulls in a row never reach their target. Bots used to stand
  still for over an hour retrying monsters they could not reach (bear cubs across water, corpse
  flickers on a ledge). Such a camp is also benched for other bots for a while.
- A solo gamebot whose camp turned grey after a level-up picks a camp for its new level. It used
  to keep killing grey monsters for no experience until the 15-minute stuck rescue moved it.
- Outdoor camps are chosen in proportion to how many monsters they have (up to six), instead of
  every spot being equally likely. Midgard bots had spent most of their time at one- or two-spawn
  spots, where kills are about a quarter slower.
- Camps where several solo bots keep dying for few kills are skipped by solo bots for a few
  hours (3 hours, doubling to 24 on repeats). Deaths on the way to a camp count against it, so
  bots stop being sent along the deadliest routes. This adds no work while bots move.
- A pet summoned at the very edge of the map now appears on top of its owner. The game places a
  new pet a few steps in front of its owner, and when that spot was off the map the summon
  crashed and the server removed the caster from the world. One Necromancer gamebot standing at
  the edge of Avalon Isle was logged back in and thrown out again about every 20 seconds, so the
  launcher showed one bot short (5,999 of 6,000). Players summoning there are covered too.
- RvR groups now pick as leader the bot closest to its realm's border keep (Castle Sauvage,
  Svasud Faste or Druim Ligen) instead of a random one. Random leaders were often solo roamers deep
  in an enemy realm's frontier who could not get back to the keep within the 20-minute gathering
  window, so about one RvR group in nine fell apart. The three realms take turns forming groups.
  PvE groups are unchanged.
- Epic dungeon raids (Galladoria, Tuscaran and the others):
  - A raid bot stuck on a ledge or a separate piece of floor inside the dungeon rejoins the raid
    at its current position after three failed tries from the same spot. It used to retry every
    30 seconds for the whole four-hour raid.
  - Bots fighting anywhere inside their raid's dungeon are no longer pulled out to town by the
    15-minute stuck rescue. Long boss fights where bots stand still looked like being stuck.
- A bot stuck in a small trapped spot (for example by the Druim Ligen stable master) no longer
  resets its stuck count by inching forward a little. Some bots looped there 80 times; now the
  existing safe move-out happens after three failures.
- Bots no longer try to pull flying monsters hovering far over their heads, such as the griffon
  gliders over Gripklosa, which they could never reach. Flyers close to the ground still count, and
  a high flyer that attacks a bot is still fought.
- An automatic level-50 raid that has waited 75 minutes with at least 180 of its 200 bots now goes
  in, instead of failing at 90 minutes for being a few short (Caer Sidi missed by 4 and 14). Raids
  started by a player are unchanged.
- When a nearby healer bot does not revive a dead group member, the server log now says why
  (out of power, casting, under attack, no line of sight or the cast refused), at most once a
  minute per bot. This only adds a log line; it does not change what the healers do.
- Siege bots no longer freeze on the way to an enemy keep. Bots walked toward the keep in one
  very long leg and some stood still for 15 minutes, so no siege engine was ever placed (77
  Hibernian siege bots froze in one evening). They now walk long routes in shorter checked legs,
  plan again from where they stand if they stop moving for a minute, and set that siege job aside
  for a couple of minutes after three freezes at the same spot.
- Bots bouncing between two spots in a keep courtyard (Nottmoor) are now recognised as trapped
  and moved out by the existing safe move-out.
- Dragon raids (Golestandt, Gjalpinulva and Cuuldurach):
  - A dragon fighting on the ground counts as landed wherever it is, so the whole raid joins in.
    Most of the raid used to wait for a landing when the fight drifted away from the lair.
  - A dragon whose flight stalls flies home and lands, and a landing that gets stuck is finished,
    so a dragon can no longer stay in the air for the rest of the raid. Throws and teleports stay
    off, as before.
- Epic dungeon raids set aside a target nobody has damaged for five minutes and try it again
  later, and skip monsters flying out of reach, instead of holding in place. Final bosses are never
  set aside. The server log now says why a raid is holding.
- Paladins and Bards stop their chant and song upkeep while a groupmate in range waits for their
  resurrection, so their resurrection spell is no longer refused for another spell already queued.
- Summoner's Hall is no longer handed to bots as a dungeon goal. It can only be reached through
  other dungeons, and only 1 of 268 attempts ever got there. The monsters stay for players.
- Shaman bots, gamebots and companions alike, now fight as hybrids instead of standing at spell
  range. They cast their bolt and nuke when the 20-second recasts are ready, keep their damage
  over time and disease on the target, and fight in melee in between. A ready nuke or an expired
  damage over time stops the melee for the cast, and they still stop to heal. A Shaman being hit
  stays in melee, since the cast would be interrupted.
- Shamans no longer root the monster being killed, since the first hit breaks the root. Solo
  Shamans never root in PvE; in a group, a Shaman roots an add that is still running at the party
  while the group fights something else. Roots in PvP are unchanged.
- [PLAY.md](docs/PLAY.md) now recommends bot populations (500, 1000, 1500 or 2000 per realm)
  and explains the name-generation ceiling of about 18,800 bots.

**Gamebots and companions: parry, block and evade**
- Gamebots and companion bots now parry, block and evade like players. The combat code treated
  them as ordinary monsters, which use a fixed chance from their template (normally none), so
  their class abilities, Parry and Shields training, dexterity, quickness and shields did nothing.
- They now use the same formulas and rules as players:
  - **Parry** needs the Parry specialization (or a parry buff) and a melee weapon, never a bow.
  - **Evade** needs the class's Evade ability, which comes with level like a player's, or an evade
    buff. It works from the front, or from every side with Advanced or Enhanced Evade.
  - **Block** needs the Shield ability, a real shield and a one-handed weapon. It is scaled by the
    shield's quality and condition, and the shield's size limits how many attackers it can block.
- The player-versus-player caps (50% parry, 50% evade) apply whenever both sides are players or
  bots.
- Bots, tanks and evade classes especially, are noticeably harder to kill.

**Bounty Masters: normal, hard and very hard bounties**
- The Bounty Master now offers three kinds of leveling bounty:
  - a **normal bounty**, with monsters at your level as before;
  - a **hard bounty**, with monsters about 4 levels above you;
  - a **very hard bounty**, with monsters about 8 levels above you.
- Every difficulty needs the same number of kills: 5 below level 20, 10 in your 20s, 15 in your
  30s and 20 in your 40s. It used to climb from 5 to 50.
- Rewards by difficulty:

  | Difficulty | XP | Class items (1-3) |
  |---|---|---|
  | Normal | 2 bulbs | 1 level above you |
  | Hard | 4 bulbs | 3 levels above you |
  | Very Hard | 8 bulbs | 5 levels above you |

  A bulb is a tenth of a level at the level you took the bounty. Gear never goes above level 51.
- Rerolling still halves the XP. On a hard or very hard bounty, a reroll keeps that difficulty or
  picks an easier one, and pays half of the one you end up with. For example, a very hard bounty
  rerolled to normal pays 1 bulb.
- How hard and very hard targets are picked:
  - Only monsters with at least two spawns are used.
  - A level with fewer than eight different monsters also uses monsters one, then two levels
    lower, but never drops below 2 levels above you for hard, or 6 for very hard.
  - Monsters go up to level 57. The great foes stay level-50 bounties only.
- On hard and very hard, a same-named monster elsewhere in your realm only counts if it is at most
  one level below the marked one.
- Level-50 great-foe bounties are unchanged.
- **Bounties carried over from 0.33:** an unfinished 0.33 bounty brought over with the progress
  import becomes a normal bounty with the new kill count when you log in. Your kills so far are
  kept, so it may be ready to turn in right away. The Bounty Master also offers **[update bounty]**
  once, free, to swap it for a new bounty at any difficulty.

**Sluaghbinder (0.34b only)**
- The Cairn armor buffs say "You are surrounded by an unholy aura." instead of a holy aura, and
  the Cairn strength buffs say "You are filled with the power of the cairn!" instead of the
  strength of Thor and the gods.
- Dullahan's Bulwark taunts cost power (2, 6, 10, 14 and 18 by rank) and share one 15-second
  recast across every rank. They used to be free with a 4-second recast per rank.
- Cairn Ward (Dullahan's Bulwark 20), an armor buff the core Cairn Oath line already outclassed,
  is replaced by a parry buff with its own icon: Barrow Deflection (+4% parry at 20), Barrow
  Riposte (+6% at 32) and Barrow Wardblade (+8% at 44). It lets the Sluaghbinder parry without
  the Parry specialization, and it works for Sluaghbinder bots too.
- To add these to an existing 0.33b install now, run
  `tools/pet-art/install_bulwark_update.py install` with the game, launcher and server closed. It
  previews the changes if run without `install`, and it can be rolled back.
- Sluaghbinder spells cost power only. They also took 5 endurance each; styles still cost
  endurance. This applies to players, gamebots and companions.
- Every Sluaghbinder life drain (the five Abhartach's Bane Vitality drains, Guardian Lifesteal
  and Dullahan's Blood Tithe) plays the naburite drinker's drain animation.
- The five Abhartach's Bane Vitality drains share one 4-second recast. Each rank used to have
  its own, so all five could be fired back to back.
- Bane-specced Sluaghbinder bots use both their Abhartach's Rot and Abhartach's Bane damage over
  time, which stack, and the Dullahan pet's Grave Rot stacks with both.
- The Abhartach's Bane damage over time (Withering through Final Rot) plays a plague spore cloud,
  so it looks different from the baseline Abhartach's Rot. Cosmetic only.
- To add the drain, Grave Rot and Bane cloud changes to an existing 0.33b install now, run
  `tools/claude-version/install_bane_drain_update.py install` with the game, launcher and server
  closed. It previews the changes if run without `install`, and it can be rolled back.
- The Cairn strength buffs, the Sluaghbinder's own (Cairn Vigor, Fortitude and Oath) and the
  ones it casts on its pets, show a green hand glow and a green rune emblem on the ground instead
  of the blue Midgard Thane and Bonedancer animations they borrowed. Thanes and Bonedancers still
  look blue. Cosmetic only. To add this to an existing 0.33b install now, run
  `tools/pet-art/install_cairn_green_buff.py install` with the game, launcher and server closed.
  It previews the changes if run without `install`, and it can be rolled back.
- The zombie priest is now the **ghastly healer**: a floating ghost on the badh's skeleton, with
  its own casting animation and a dagger instead of a staff. It has its own reshaped mesh (a
  longer ragged ghost tail, gaunter waist, longer hair, a broken circlet and claw-like fingers),
  a corpse-pale grave-shroud skin and a ghostly wailing voice instead of a dwarf-female one. World
  badh monsters are unchanged.
  - Its summon spell is now "Raise Ghastly Healer", and its "Priest's Mending" is now "Ghastly
    Mending".
  - Its stats, spells and healing AI are unchanged.
  - It needs a server built from this source, because the 0.33b server only knows the
    healer as "zombie priest" (the installer checks this). With such a server, close the
    game, launcher and server, then run:
    - `tools/claude-version/install_ghastly_healer.py install` (name, spells, robes);
    - `tools/pet-art/build_ghastly_healer.py`;
    - `tools/pet-art/install_ghastly_healer_art.py install` (the private model).

    Each previews without `install` and can be rolled back.

**Animist bots (gamebots and companions)**
- Animists use their shrooms by what they do, the way the class was played, instead of picking
  the highest-level shroom spell at random:
  - The permanent shroom and one damage shroom open the fight.
  - Each resist Vent is kept up once (both in a group, one solo). Vents never count against
    damage shrooms, and no duplicate Vents are planted.
  - Then the highest-rank damage shroom is added for as long as the monsters still need it, so
    a weak monster gets one or two and a tough one or a pack gets many more.
  - The old limit of three temporary shrooms and the extra 6.5-second wait are gone. The bot
    keeps 20% power in reserve, and the server's normal shroom limits still apply.
- Every spec plays to its strengths:
  - Verdant uses its taunting permanent shroom with Briar bursts and Ligneous ablatives.
  - Creeping adds a Spore in group fights where someone is being hit in melee.
  - Every spec heals its permanent shroom.
  - Between fights, a permanent shroom of the wrong kind or an outgrown rank is replaced.
- Animists stand inside shroom range (850) instead of nuke range (1,500) and plant every
  shroom, the permanent one included, beside themselves instead of next to the enemy. If the
  monster moves out of reach they walk up first instead of planting.
- Damage shrooms stop at two in crowded camps, and bursts and Spores wait until no other
  monster would be hit, so shrooms pull fewer extra monsters.
- Companion Animists keep planting while you move around during a fight.

**Charm pets**
- The charm creature menu (Sorcerer, Minstrel, Mentalist and Hunter) tags every choice with how it
  fights: **Caster** (casts an attack spell from range), **Archer** (shoots a bow) or **Melee**.
  The few creatures whose spells or gear are rolled at random show both, for example "Archer or
  Melee".
- Creatures that cannot move are no longer offered as charm pets, to players or to gamebots: the
  Darkness Falls clinging soul, the gurite and siabra lookouts, and the target and training dummies.
  They used to sit where they were summoned and never follow or chase. They are unchanged in the
  world.

**Shrouded Isles reputation**
- New repeatable reputation quest in each realm, from a faction emissary:
  - Hibernia: **Kzzirrak** `<Krrzck Emissary>`, a mantid beside Zrrazk inside Necht.
  - Albion: **Ysslith** `<Cryptos Mythicos Emissary>`, a lammia beside Vilmalin at Caer Diogel.
  - Midgard: **Hrodvar Deepvow** `<The Remnants Emissary>`, an iarn dwarf beside Korlis in Hagall.
- Kill 10 of a common enemy of that faction, chosen near your level without going over and never
  above level 45. A red dot marks the hunting ground on that zone's map, and the journal tracks
  your kills.
- Each turn-in gives +10 reputation with the faction. As with bounties, you can reroll for a
  different target, and that hunt then gives +5. The hunted monsters' own faction likes you 10
  less, but only if it already attacked on sight; friendly factions are never touched.
- Reputation runs from -100 to +100, and everyone starts at -100. The faction's stable masters
  serve you from -50, and its town guards stop attacking on sight above -75.
- The emissaries say which stable masters check reputation: Zrrazk, Dalniver and Calvine in
  Hibernia; Nimea and Callisa in Albion; Minerva in Midgard. Korlis and Vilmalin serve everyone
  of their realm.
- A faction stable master that turns you away now tells you your reputation, the -50 you need,
  and which emissary to see.
- Bounty quests never send you after monsters whose death would cost reputation with one of these
  three factions or their allies. For example, Hibernian bounties no longer pick mantids or ashen
  treants.

**World**
- The Cliffs of Moher phaeghoul that spawned inside a dead tree now spawns in open ground nearby.
  To apply this to an existing 0.33 install now, run
  `tools/claude-version/fix_moher_phaeghoul_tree.py --apply` with the game closed.
- Leptus in Domnann is always level 6. Its template randomly rolled level 6 or level 51, which put
  a roaming level 51 monster among the starter creatures.
- The level 6-7 venomous spore seeds in Cothrom Gorge are removed. They sat inside the level
  42-55 venomous spore field and drew low-level bots across the Shrouded Isles to die there. The
  level 48-55 venomous spores are unchanged. To apply the Leptus and spore seed changes to an
  existing 0.33 install now, run `tools/claude-version/fix_cothrom_seeds_and_leptus.py --apply`
  with the game closed.
- The Celtic scale helm and the five other helmets on the same mesh (for example Animalbound
  Osnadur Tha Coif) are visible again with extension 2. They used to hide the whole head.
- The Norse leather cap (for example the rawhide starklaedar cap) and the ten other helmets on the
  same mesh are visible with extension 2. The cap was invisible on a Shaman companion.
- The tendrils in Aegir's Landing, and the chokers, shacklers and the Throttler in Dales of Devwy,
  are no longer invisible.
  - They use the game's invisible model, so they used to show only a floating name.
  - Like the stranglers next to them, they now show a Tangling Vines effect. Their stats, levels
    and loot are unchanged.
  - Also like the stranglers, they are no longer offered as bounty, reputation-hunt or charm
    targets.
  - To add this to an existing 0.33 install now, run
    `tools/claude-version/vine_monsters_strangler_effect.py --apply` with the game, launcher and
    server closed. It previews the change if run without `--apply`, and `--undo` puts the
    monsters back.
- The Realm Exchange NPCs in Jordheim and Camelot have moved:
  - Jordheim's (for example Brynhild; each install picks the names) is back on the small ledge by
    the Name Registrar. It had ended up in the narrow hallway by the vault keeper, where bots
    traded with it through a wall.
  - Camelot's (for example Adalyn) now stands in the open courtyard in front of the benches,
    instead of on the crowded vault-keeper platform.
  - Each has a guard on either side, as before. The Tir na Nog exchange is unchanged.
- Bots pick a trading spot with a clear line to the Realm Exchange NPC, so they no longer trade
  through a pillar or wall. If there is no such spot, they choose one the old way. Both new spots
  were checked on the real city maps from every gate, and the nearby merchants stay reachable.
- New installs get the new spots automatically. To move them in an existing 0.33 install now,
  run `tools/claude-version/move_realm_exchange_npcs.py --apply` with the game, launcher and
  server closed. It previews the change if run without `--apply`, and `--undo` puts them back.
- The fire trap in Amminus Pilus's hall in the Catacombs of Cardova (Pilus'Fury, the smoke that
  burns anyone standing on the hot spots) no longer breaks when it burns a gamebot Necromancer's
  pet. It expected every Necromancer pet to belong to a player, crashed on a bot's pet, and the
  server removed the trap until Amminus Pilus respawned, so the hall often had no trap at all. It
  burns the same spots for the same damage as before.

## 0.33 / 0.33b "Claude Takeover" — 2026-09-30

The full notes are in [docs/RELEASE-0.33.md](docs/RELEASE-0.33.md). In short:

**Download and setup**
- One complete download, about 5 GB in checked parts, with two editions:
  - **0.33b** includes the Sluaghbinder.
  - **0.33** has the classic class list only.
- Every install gets its own account on the first ENTER REALM, an empty world for its own bots,
  default launcher settings and its own client settings profile.
- The .NET runtime is bundled. Only the Windows .NET Framework 3.5 feature is still needed.
- A new progress transfer tool moves an account, characters, items, money, houses and bots from
  v0.3 through v0.32b and the "new class test" builds.

**Bots**
- Much less lag with thousands of bots: faster database access, fewer repeated route searches,
  and heavy scans moved off the main game loop.
- Stuck pulls are retried closer, then abandoned, for every class. Stuck casts are cleared.
- Resting casters and archers walk up to far or wandering targets.
- Archers that stall at close range switch to melee briefly.
- Bots never mesmerize their own kill target.
- Savages can use claws in their main hand, and they cast their health-costing buffs only at the
  target.
- Level 0 creatures are real targets. New bots use starter camps near home with checked routes.
- The stuck-bot watchdog counts earned XP as progress.
- Groups:
  - They prefer 8 bots but can form with 5–7, and smaller groups pick easier targets.
  - Bots waiting for a group grind outdoors.
- Darkness Falls: solo bots need level 25 and blue-or-easier targets, and groups inside stay
  inside.
- Nearly full bags are emptied at natural task breaks, never mid-grind.
- Camps that several bots can't route to are benched for a while.

**Sluaghbinder (0.33b)**
- New or refreshed art for the sturdy zombie, zombie magician, zombie priest, walking dead, zombie
  guardian and Dullahan.
- The zombie magician has a void blast attack, its own casting gestures and fixed melee
  animations. Its robe is lower-res with muted markings, and its shoulder spikes are folded in.
- The zombie priest heals party members and pets properly, for both player and bot owners.
- Pet health is rebalanced; damage is unchanged.
- Cairn armor buffs show a black and blood-red shield instead of the holy halo.
- Summons cast in 10 seconds (was 20) and show green hand glows.
- Every Sluaghbinder buff shows its own tooltip.
- The zombie guardian carries a unique rusted mace and tower shield.

**Everyone**
- The Necromancer's level 20 Necroservant carries a unique blackened bone hammer and grave shield.
- Faces show under every variant of the Hibernian "Helm 3" helmets, 15 models.

## 0.32 / 0.32b "Darkness Falls Beta" — 2026-09-25 to 2026-09-28

- **Darkness Falls opened** to all three realms. Bots grind its ordinary camps on staged,
  floor-aware routes and use their own realm's exits. Raid AI and the hardest encounters were not
  included.
- **Maintenance updates fixed:**
  - bot travel, groups, meetups and recovery
  - dungeon goals and Savage outdoor pulls
  - backpack selling
  - the display of the model 840 scale coif
  - the classic-side Shrouded Isles portal visuals
- **Bounty Masters** stopped repeating the last hunted monster.
- **0.32b** added the optional Sluaghbinder on top of 0.32, as a separate copy.

## 0.31 / 0.31b — 2026-09-20 to 2026-09-26

- **0.31 maintenance fixed:**
  - pet scaling
  - companion spell power and healing
  - the Isle of Glass dragonfly camp and similar route traps
  - Bonedancer helper upkeep
  - a world-loop freeze
- **Later additions:**
  - repeatable Bounty Masters in Cotswold, Mularn and Mag Mell
  - Bard combat and companion song fixes
  - a Shannon Estuary beach-rat camp
  - shared bot progression and route repairs
- **0.31b** introduced the optional Hibernian **Sluaghbinder** class:
  - its Acolyte-to-level-5 promotion
  - three core and three trainable lines
  - seven pets
  - Muirenn, the trainer in Tir na Nog
  - five chained epic quests
  - full companion and gamebot support

## 0.3 — 2026-09-15

The first public single-player release: Classic + Shrouded Isles on 1.65 rules, with autonomous
gamebots, recruitable companion bots, raids, realm events, a launcher, navigation meshes and
development tools.
