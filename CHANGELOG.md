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
