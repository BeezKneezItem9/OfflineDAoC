# Beez Online Bind Stone gateways

Implemented on `beez-upstream-integration`; no playable installation or client files are modified.

## Stock fallback and evidence

The old endpoint was a `GameNPC` with monster model 1923. The monster catalog resolves this to an invisible `CorpseLightNode` with effect set 90 (`teleporter_ground`), not an upright stone gateway.

Both endpoints now use `GameStaticItem` model **4319**: `objects.csv` row “Caledonia Portal” → `items.csv` NIF row **2334**, “Caledonia Portal” → `items/magprtl2.nif`. This is the ITEM namespace, not a monster model ID. The client catalog marks it Expansion Only 1; compatibility with an arbitrary unmodified Classic/SI client is not established. Use the packaged OfflineDAoC client for acceptance testing.

Asset investigation used the original upstream v0.35b release, not an installed playable directory. Download parts 001 and 003 were verified against the release download manifest; selected entries were read through ZIP CRC checking. The mesh SHA-256 matches the package manifest:

`magprtl2.nif`: `f4ab6b02ca355fc2ddc0ada5ceaafea3c07bc832a62405b2b400ba516bebc00b`.

The repository's read-only `nif4_geom.py` decoded three geometry blocks. Orthographic wireframes show a stone arch geometry; local vertices alone do not establish world transforms or exact in-game size. The mesh references `LTHENGE.tga`, `HENGE.TGA`, `prtlune.tga`; the release supplies corresponding DDS textures in `items/` (DDS takes precedence). It contains no `Ni*Controller` records. A swirling animated vortex is therefore **not implemented** by selecting this static mesh. PyFFI could not fully parse the legacy geometry; its output is not treated as a completed renderer verification.

Other candidates: static model 2603 is the existing Frontiers Portal Stone (`Portal_Stone_F`), a smaller standing stone rather than an arch; monster 1438 is an invisible node with `portaleffect_mon`; Labyrinth models require expansion 6. SI architectural gateways (`BAvTeleporter`, `NAegTeleport`, `hibteleport`) are zone fixtures, not verified server-spawnable model IDs.

## Server behavior

The gateway is a transient, named static world object. The client object-interaction handler dispatches interaction to server-side `Interact`; it does not require an NPC. No database save method is called. Both endpoints have the same model and retain the original positions, headings and opposite destinations.

Owner-only checks, range (256 units), current-region checks, existing player-state restrictions, zone/keep/RvR/instance restrictions, bind-change invalidation and the ten-minute lifetime remain in force. Lifetime still starts at recall initiation, including the wait for region loading. Recall `/use2` replaces the previous pair. Disconnect, death and rebinding retain their existing cleanup hooks.

Interaction additionally requires both linked endpoints to be active and the object to belong to the current pair. The periodic callback removes the pair when either endpoint disappears. Partial spawn failures and exceptions clear the pair; disposal attempts deletion of both endpoints even if the first deletion throws. A delayed arrival still has the existing sixty-second limit. There are no schema changes, configuration additions, launcher changes or deployment-workflow changes.

## Exact custom gateway requirements

The concept image is an art reference, not a 3D asset. Matching it requires:

1. A modeled and UV-mapped arch, pillars, runes and crystals, exported to the client's supported legacy NetImmerse format with tested transforms, ground origin, scale, bounds and selection behavior.
2. Private DDS textures with full mipmaps and appropriate alpha/emissive materials for stone, cyan runes, crystals and the vortex.
3. A client-supported animated vortex (tested NIF controllers or a separately cataloged effect/animation). A still texture cannot satisfy the swirling animation requirement. Any separate effect must follow both endpoints and be deleted with them.
4. Verified unused private catalog IDs, chosen only after scanning the intended client's catalogs and database model references. No custom IDs are allocated here. Preserve stock rows/assets and catalog terminators, line endings, expansion fields and order.
5. A reproducible client package/install step with source hashes, backup manifest and rollback, distributed to every participating client. Verify both supported client editions and any release assembly changes before publishing. No binary patch is presumed necessary or safe.

## Required in-game acceptance

Automated tests do not establish client visibility, targetability, distance rendering, selection bounds or appearance. No server was started for this task. The fallback is a server implementation candidate, **not yet a client-verified successful gateway**.

- Recall with `/use2`: confirm two upright, named arches appear on suitable ground and can be targeted and activated.
- Travel expedition → bind → expedition repeatedly; verify destination coordinates and headings and usable selection after zoning.
- Confirm a stranger cannot use either endpoint; verify movement/combat/mount/casting and restricted-zone checks still reject travel.
- Check visibility at distance, large-mesh placement near walls/slopes, collision and selection bounds, especially when spawning at the owner's exact location. No unverified positional offset was introduced.
- Replace the pair; test expiry at ten minutes, logout, death, rebinding, and disappearance of one endpoint. Confirm both old objects vanish without duplicates or saved database rows.
- Evaluate visual suitability on the actual Classic/SI-era client. If model 4319 is absent or unsuitable there, do not silently substitute a ground effect; supply and validate private art or choose another verified upright asset.

## Automated validation

Release GameServer compilation succeeds with 0 errors and 584 existing warnings. The focused Beez Online fixture passes 43 tests. The full server suite passes 2,786 tests, an increase of one from the post-upstream baseline (2,785): the new gateway-pair test covers authorization from both endpoints, rejection of the remote endpoint, shared model selection, and cleanup when an endpoint is inactive. The suite reports 61 additional unexecuted cases, unchanged from the integration baseline. The existing owner-only, no-database-write, arrival/expiry/death and restricted-location tests also pass. These tests use world-object fixtures; they do not prove client targeting or completed network zoning.

Existing package advisory and compiler warnings remain; no dependency was changed. Windows launcher code is unaffected.
