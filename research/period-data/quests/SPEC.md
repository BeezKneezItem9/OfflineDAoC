# Classic quest spec (goal 10)

One JSON object per quest in `specs/<realm>.jsonl`, written from the Allakhazam walkthrough. The generator
turns specs into DataQuest rows (one row per class when rewards differ by class), spawns missing NPCs and
monsters, creates reward/quest items, and attaches the ClassicQuestMarkers step hook (yellow map marker on
the giver / turn-in NPC, red on the current step's location, dungeons included).

```json
{
  "src": "A113",                         // Allakhazam realm letter + quest id
  "name": "Abolishment of Sacrifice",
  "realm": "Albion",
  "level": 15, "max": 50,
  "classes": ["Paladin", "Cleric"],      // [] = all
  "requires": ["List of Denial"],        // quest names (DataQuest QuestDependency)
  "era": "classic" | "si",
  "giver": {"name": "Trainer", "zone": "Camelot", "trainer": ["Paladin", "Cleric"]},
  "offer": "short offer text in the period voice",
  "steps": [
    {"do": "talk",    "npc": "Belef",   "zone": "Black Mtns. South", "loc": [20360, 40475], "text": "journal text"},
    {"do": "talk",    "npc": "<any guard>", "zone": "Black Mtns. South", "loc": [36400, 18000]},
    {"do": "kill",    "npc": "Sacrificer Harish", "zone": "Black Mtns. South", "loc": [42350, 385], "count": 1,
                      "spawn": {"level": 17, "like": "filidh"}},     // spawn when missing; "like" = model/template donor
    {"do": "kill",    "npc": "Shade of Harish", "spawn_on_death_of": "Sacrificer Harish"},
    {"do": "deliver", "npc": "Belef", "item_from_giver": "Humberton Tithe"},
    {"do": "deliver", "npc": "Trainer", "item": "Humberton Tithe", "finish": true}
  ],
  "collect": {"item": "Giant Dragonfly Wing", "from": "giant dragonfly", "count": 2, "chance": 50},
  "whisper": "abeo decido animus exspecto terra",
  "rewards": {"coin": "7s", "xp": "auto",
              "items": {"Paladin": ["Faithbound Shield"], "Cleric": ["Redoubled Leggings"]}},
  "notes": "anything the generator must not guess"
}
```

Rules
- Locations are zone-local (loc=x,y from the walkthrough); the generator adds the zone offsets and snaps to
  the navmesh. Prefer the original (pre-1.75) location when a walkthrough notes a later move.
- `xp: "auto"` = period quest scale for the quest level (walkthroughs rarely give numbers); a number when
  the walkthrough gives one.
- Quest items (tithes, letters, wings) are created as plain quest items; reward equipment comes from the
  item pages (stats) collected in pass 2.
- Uncertain details go in `notes`; never invented.
