# 3D board assets

This directory is the libGDX board's independent art source. Runtime never reads
terrain or water from the 2D board's images directory. The Java build stages this
directory with the game's data. Blender is an authoring dependency only.

## Scenery folders

Scenery meshes live in topic folders under `scenery/`, with kebab-case names:

| Folder | Contents |
|---|---|
| `roofs/` | rooftop objects: bevel, ledge, roof grille, chimney stack, skylight, glass roof and dome, landing beacons |
| `parks/` | bench, picnic table, garden bed, pillar, hex plaza, fountain, plaza variants, formal gardens, grandstand |
| `pools/` | sport pools (deck, main and wading basins), rectangular, round and freeform pools; a pond is a pool in pond colours |
| `vehicles/` | the car (its paint is a colour slot), parking barrier, parking shelters |
| `construction/` | crawler crane, bulldozer, concrete debris, excavation site, concrete pipe |
| `farm/` | one mesh per animal and pose: cow, pig, horse, bison, hen and rooster; coats are colour slots |
| `seaport/` | container rows and gantry cranes by row axis (`n-s`, `ne-sw`, `nw-se`, `e-w`), crane tips |
| `maglev/` | route marker (the only rail mesh), station platform, city and colony vehicles, the city gangway coupler; `train.png` and `colony-train.png` are the stamps' thumbnails |
| `military/` | orbital gun, fortification |
| `rubble/` | rubble by structure type, and the cleared paths through it |
| `geysers/` | dormant and erupting water geysers, magma geyser |

No mesh sits at a legacy key. A legacy key is `scenery/<tileset image path
without extension>`; it resolves only through `scenery/layouts.json`, so that
file is the complete legacy-to-mesh mapping. A key that used to be one GLB is a
one-row entry at the origin on its renamed mesh. Every mesh stands on Z=0 and
every row has Z=0. Two kinds of mesh stand above Z=0 by design: a seaport crane
tip hangs from the gantry boom, so its mesh keeps the boom height and its grabber
is 10.28 px up, and the maglev vehicles ride the route's beam (their suspension shoes
1.3 px up, the coupler's shoe links 2.3 px; see Maglev). Blueprint IDs are the new mesh
paths; stamps still name legacy keys.
Decal rows (`decal/...`) name painted decals, not meshes (see Decals): each
car-park key `fluff/cars_*` places standard car-park decals, and its car rows
carry `"seat"`. The conversion (`BoardSceneryLayouts.convert`, run wherever a
legacy board is loaded) makes the lane a real `road:1` with the lane's exits on a
car park on plain ground without a road. The rows stand beside that road; the
conversion folds them back to back where no road is drawn.
A row may carry `"stretch": [x, y, z]`, positive factors on the mesh's own axes
before its turn (the narrow glass roof is `roofs/glass-roof-wide` stretched to
29/36 of its width), and `"colours": ["#rrggbb", null, ...]`, replacements for the
mesh's colour slots in slot order (null keeps a slot's own colour).

### Colour slots

A mesh may mark up to four colour slots: each vertex carries its slot in the
attribute `_COLOUR_SLOT` (0 none), and the file's extras `mmColourSlots` list each
slot's name, its default colour and preset colours (the colours of the family's
former meshes). A row's or a placed object's colour replaces a slot's default: each
channel keeps its ratio to the default in linear light, so shaded parts of a slot
stay shaded (`tools/glb_geometry.py` `recolour`; the runtime's `RigidGlb.recolour`
applies the same rule). A slot's base vertices hold its default exactly, to the
8-bit step, so a replacement reproduces itself exactly there. The colour families
are one mesh each:

| Mesh (`scenery/...`) | Slots | Former meshes (now colours) |
|---|---|---|
| `vehicles/car` | Paint | 19 `car-<paint>` (red is the default) |
| `farm/hen` | Plumage | 6 hens (white is the default) |
| `farm/rooster` | Plumage, Wings | 3 roosters (red) |
| `farm/horse` | Coat, Mane and tail, Muzzle | chestnut, dun, sorrel |
| `farm/horse-relaxed` | Coat, Mane and tail, Muzzle | bay, grey (resting) |
| `farm/cow` | Patches | brown, black patches |
| `farm/pig` | Skin, Spots | pink spotted (default), pink, brown spotted |
| `farm/bison` | Coat | dark, light |
| `pools/*` | Wall, Coping, Deck, Water | `parks/pond-1`, `-2`, `-4` are `pools/freeform`, `sport-2`, `sport-4` in the 'Pond' colours |

Every vertex whose colour differs between a family's coats belongs to the slot
that reproduces it for every coat; `tools/extract_herd_animals.py` assigns them
from `tools/farm-coats.json` (slot names and each coat's colours) and reports the
largest error per family (at most 3.9/255, the resting horse's head), and
`verify_legacy_decode.py` compares the recoloured rows with the base's meshes
vertex by vertex (see below). The car's paint and the pool slots are marked by
`tools/build_scenery_assets.py` (`CAR_SLOTS`, `POOL_SLOTS`), which writes each car
and pond row's colours.

`tools/build_scenery_assets.py` names its output with `SHARED` (shared
components) and `NAMES` (meshes that legacy images bake); it never writes a GLB
at a legacy key. The animal meshes are not generated: their pose source was never
in the repository. `tools/extract_herd_animals.py` split them out of the herd
meshes of commit `0d5b47e5d0` by undoing each animal's placement from
`tools/farm-herds.json`, and checks that animals with one name share geometry and
colour (26 coats and poses from 11 herds). Coats that differ only in colour share
one mesh with colour slots (`tools/farm-coats.json`, see Colour slots), so 12
animal meshes remain. The generator writes the herd keys' rows from the same tables,
each with its coat's colours.

### Old to new

| New mesh (`scenery/...`) | Old file or ID (`scenery/...`) | Legacy key decodes to it |
|---|---|---|
| `construction/concrete-pipe` | `components/concrete-pipe` | - |
| `construction/bulldozer`, `construction/debris-3` | `fluff/construction3` | yes, two rows |
| `construction/crawler-crane`, `construction/debris-1` | `fluff/construction1` | yes, two rows |
| `construction/site-excavation` | `fluff/construction2` | yes, one row |
| `farm/<animal>` (12 meshes; coats are colours) | `fluff/bison1`, `cattle1`-`3`, `chickens1`-`3`, `horses1`-`2`, `pigs1`-`2` | yes, one row per animal (`tools/farm-herds.json`) |
| `geysers/magma` | `saxarba/misc/geyser_magma` | yes, one row |
| `geysers/water-dormant` | `saxarba/misc/geyser_water_off` | yes, one row |
| `geysers/water-erupting` | `saxarba/misc/geyser_water_on` | yes, one row |
| `maglev/cab` | `components/maglev-cab` | - |
| `maglev/coupler` | `components/maglev-coupler` | - |
| `maglev/platform` | `components/maglev-platform` | - |
| `maglev/route` | `components/maglev-route` | - |
| `maglev/train` | `components/maglev-train` | layout ID of the train stamp, not a mesh |
| `maglev/wagon` | `components/maglev-wagon` | - |
| `military/fortification` | `saxarba/misc/fortified` | yes, one row |
| `military/orbital-gun` | `UlyssesSprites/orbitalguns/OrbitalGunE` | yes, one row |
| `parks/bench` | `components/bench` | - |
| `parks/formal-garden-hex` | `saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-01` | yes, one row |
| `parks/formal-garden-round` | `saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-02` | yes, one row |
| `parks/formal-garden-star` | `saxarba/SMV_Fluff/FluffSystem-07-Garden-03-Landscape-1-04` | yes, one row |
| `parks/garden-bed` | `components/garden-bed` | - |
| `parks/grandstand` | `components/grandstand` | - |
| `parks/picnic-table` | `components/picnic-table` | - |
| `parks/pillar` | `components/pillar` | - |
| `parks/plaza-flowers` | `fluff/square6` | yes, one row |
| `parks/plaza-flowers-pillars` | `fluff/square5` | yes, one row |
| `parks/plaza`, `parks/fountain` | `components/hex-plaza` | - |
| `parks/plaza-hedge` | `fluff/square3` | yes, one row |
| `parks/plaza-pillars` | `fluff/square2` | yes, one row |
| `parks/plaza-pond` | `fluff/square4` | yes, one row |
| `pools/freeform` in pond colours | `components/lake-freeform-01` | - |
| `pools/sport-2` in pond colours | `components/lake-freeform-02` | - |
| `pools/sport-4` in pond colours | `components/lake-freeform-04` | - |
| `pools/freeform` | `components/pool-garden-freeform` | - |
| `pools/rectangular` | `components/pool` | - |
| `pools/rectangular-no-deck` | `components/pool-rectangular-no-deck` | - |
| `pools/round-no-deck` | `components/pool-round-no-deck` | - |
| `pools/sport-1-deck` | `components/pool-sport-01-deck` | - |
| `pools/sport-1-main` | `components/pool-sport-01-main` | - |
| `pools/sport-1-wading` | `components/pool-sport-01-wading` | - |
| `pools/sport-2` | `components/pool-sport-02` | - |
| `pools/sport-3-deck` | `components/pool-sport-03-deck` | - |
| `pools/sport-3-main` | `components/pool-sport-03-main` | - |
| `pools/sport-3-wading` | `components/pool-sport-03-wading` | - |
| `pools/sport-4` | `components/pool-sport-04` | - |
| `pools/sport-5` | `components/pool-sport-05` | - |
| `roofs/bevel` | `components/bevel` | - |
| `roofs/glass-dome` | `saxarba/SMV_Fluff/FluffSystem-01-Building-07-GlassRoof-3-01` | yes, one row |
| `roofs/glass-roof-wide`, stretched to 29/36 of its width | `roofs/glass-roof-narrow`, `saxarba/SMV_Fluff/FluffSystem-01-Building-07-GlassRoof-1-01` | yes, one row with stretch |
| `roofs/glass-roof-wide` | `saxarba/SMV_Fluff/FluffSystem-01-Building-07-GlassRoof-2-01` | yes, one row |
| `roofs/landing-beacon-hex` | `fluff/beacon1` | yes, one row |
| `roofs/landing-beacon-round` | `fluff/beacon2` | yes, one row |
| `roofs/ledge` | `components/ledge` | - |
| `roofs/skylight` | `components/skylight` | - |
| `roofs/grille`, `roofs/chimney-stack` | `components/roof-vent` | - |
| `rubble/hardened` | `saxarba/misc/rubble_hardened` | yes, one row |
| `rubble/hardened-path` | `saxarba/rubble_hardened_path` | yes, one row |
| `rubble/heavy` | `saxarba/misc/rubble_heavy` | yes, one row |
| `rubble/heavy-path` | `saxarba/rubble_heavy_path` | yes, one row |
| `rubble/light` | `saxarba/misc/rubble_light` | yes, one row |
| `rubble/light-path` | `saxarba/rubble_light_path` | yes, one row |
| `rubble/medium` | `saxarba/misc/rubble_medium` | yes, one row |
| `rubble/medium-path` | `saxarba/rubble_medium_path` | yes, one row |
| `rubble/wall` | `saxarba/misc/rubble_wall` | yes, one row |
| `rubble/wall-path` | `saxarba/rubble_wall_path` | yes, one row |
| `seaport/containers-e-w-01` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-01` | yes, one row |
| `seaport/containers-e-w-02` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-02` | yes, one row |
| `seaport/containers-e-w-03` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-03` | yes, one row |
| `seaport/containers-e-w-04` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-04` | yes, one row |
| `seaport/containers-e-w-05` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-05` | yes, one row |
| `seaport/containers-e-w-06` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-06` | yes, one row |
| `seaport/containers-e-w-07` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-4-07` | yes, one row |
| `seaport/containers-n-s-01` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-01` | yes, one row |
| `seaport/containers-n-s-02` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-02` | yes, one row |
| `seaport/containers-n-s-03` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-03` | yes, one row |
| `seaport/containers-n-s-04` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-04` | yes, one row |
| `seaport/containers-n-s-05` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-05` | yes, one row |
| `seaport/containers-n-s-06` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-06` | yes, one row |
| `seaport/containers-n-s-07` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-1-07` | yes, one row |
| `seaport/containers-ne-sw-01` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-01` | yes, one row |
| `seaport/containers-ne-sw-02` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-02` | yes, one row |
| `seaport/containers-ne-sw-03` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-03` | yes, one row |
| `seaport/containers-ne-sw-04` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-04` | yes, one row |
| `seaport/containers-ne-sw-05` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-05` | yes, one row |
| `seaport/containers-ne-sw-06` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-06` | yes, one row |
| `seaport/containers-ne-sw-07` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-2-07` | yes, one row |
| `seaport/containers-nw-se-01` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-01` | yes, one row |
| `seaport/containers-nw-se-02` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-02` | yes, one row |
| `seaport/containers-nw-se-03` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-03` | yes, one row |
| `seaport/containers-nw-se-04` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-04` | yes, one row |
| `seaport/containers-nw-se-05` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-05` | yes, one row |
| `seaport/containers-nw-se-06` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-06` | yes, one row |
| `seaport/containers-nw-se-07` | `saxarba/SMV_Seaport/SeaportSystem-01-Container-01-20Footer-3-07` | yes, one row |
| `seaport/crane-tip-01` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-01` | yes, one row |
| `seaport/crane-tip-02` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-02` | yes, one row |
| `seaport/crane-tip-02`, turned -59.49, 180 and 120.51 degrees | `seaport/crane-tip-03`, `-05`, `-06`, `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-03`, `-05`, `-06` | yes, one row each |
| `seaport/crane-tip-01`, turned 180 degrees | `seaport/crane-tip-04`, `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-04` | yes, one row |
| `seaport/gantry-crane-e-w-01` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-01` | yes, one row |
| `seaport/gantry-crane-e-w-02` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-02` | yes, one row |
| `seaport/gantry-crane-e-w-03` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-03` | yes, one row |
| `seaport/gantry-crane-e-w-04` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-04` | yes, one row |
| `seaport/gantry-crane-e-w-05` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-05` | yes, one row |
| `seaport/gantry-crane-e-w-06` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-06` | yes, one row |
| `seaport/gantry-crane-e-w-07` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-07` | yes, one row |
| `seaport/gantry-crane-e-w-08` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-08` | yes, one row |
| `seaport/gantry-crane-e-w-09` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-09` | yes, one row |
| `seaport/gantry-crane-e-w-10` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-10` | yes, one row |
| `seaport/gantry-crane-e-w-11` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-11` | yes, one row |
| `seaport/gantry-crane-e-w-12` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-4-12` | yes, one row |
| `seaport/gantry-crane-n-s-01` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-01` | yes, one row |
| `seaport/gantry-crane-n-s-02` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-02` | yes, one row |
| `seaport/gantry-crane-n-s-03` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-03` | yes, one row |
| `seaport/gantry-crane-n-s-04` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-04` | yes, one row |
| `seaport/gantry-crane-n-s-05` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-05` | yes, one row |
| `seaport/gantry-crane-n-s-06` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-06` | yes, one row |
| `seaport/gantry-crane-n-s-07` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-07` | yes, one row |
| `seaport/gantry-crane-n-s-08` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-08` | yes, one row |
| `seaport/gantry-crane-n-s-09` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-09` | yes, one row |
| `seaport/gantry-crane-n-s-10` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-10` | yes, one row |
| `seaport/gantry-crane-n-s-11` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-11` | yes, one row |
| `seaport/gantry-crane-n-s-12` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-1-12` | yes, one row |
| `seaport/gantry-crane-ne-sw-01` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-01` | yes, one row |
| `seaport/gantry-crane-ne-sw-02` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-02` | yes, one row |
| `seaport/gantry-crane-ne-sw-03` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-03` | yes, one row |
| `seaport/gantry-crane-ne-sw-04` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-04` | yes, one row |
| `seaport/gantry-crane-ne-sw-05` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-05` | yes, one row |
| `seaport/gantry-crane-ne-sw-06` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-06` | yes, one row |
| `seaport/gantry-crane-ne-sw-07` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-07` | yes, one row |
| `seaport/gantry-crane-ne-sw-08` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-08` | yes, one row |
| `seaport/gantry-crane-ne-sw-09` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-09` | yes, one row |
| `seaport/gantry-crane-ne-sw-10` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-10` | yes, one row |
| `seaport/gantry-crane-ne-sw-11` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-11` | yes, one row |
| `seaport/gantry-crane-ne-sw-12` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-2-12` | yes, one row |
| `seaport/gantry-crane-nw-se-01` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-01` | yes, one row |
| `seaport/gantry-crane-nw-se-02` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-02` | yes, one row |
| `seaport/gantry-crane-nw-se-03` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-03` | yes, one row |
| `seaport/gantry-crane-nw-se-04` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-04` | yes, one row |
| `seaport/gantry-crane-nw-se-05` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-05` | yes, one row |
| `seaport/gantry-crane-nw-se-06` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-06` | yes, one row |
| `seaport/gantry-crane-nw-se-07` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-07` | yes, one row |
| `seaport/gantry-crane-nw-se-08` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-08` | yes, one row |
| `seaport/gantry-crane-nw-se-09` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-09` | yes, one row |
| `seaport/gantry-crane-nw-se-10` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-10` | yes, one row |
| `seaport/gantry-crane-nw-se-11` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-11` | yes, one row |
| `seaport/gantry-crane-nw-se-12` | `saxarba/SMV_Seaport/SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-3-12` | yes, one row |
| `vehicles/car` (paint as a colour) | `components/car-<paint>` (19 paints) | - |
| `vehicles/parking-barrier` | `components/parking-barrier` | - |
| `vehicles/parking-shelter` | `components/shelter` | - |
| `vehicles/parking-shelter-no-floor` | `components/shelter-no-floor` | - |

## Maglev

The twelve `scenery/fluff/maglev*` keys decode through `scenery/layouts.json`
to a route marker row and the artwork's pieces: platform, passenger wagons,
driver cab, coupler and parked road cars (`scenery/vehicles/`). The marker row
(`scenery/maglev/route`) carries the route's sides as `connections`
(N=1, NE=2, SE=4, S=8, SW=16, NW=32): 9 for N/S, 18 for NE/SW and 36 for NW/SE.
The client draws the rail from the stored sides. Facts measured on the 84x72 sprites (`MAGLEV` in
`tools/build_scenery_assets.py`):

| Keys | Route | Platform | Train piece | Parked cars |
|---|---|---|---|---|
| `track1`-`3` | N/S, NE/SW, NW/SE | - | - | 0 |
| `station1`-`3` | N/S, NE/SW, NW/SE | W, NW, NE | - | 4, 2, 0 |
| `train1`-`3` | N/S | -, W, - | cab hex (nose N), middle, tail | 2, 4, 1 |
| `train4`-`6` | NE/SW | -, NW, - | cab hex (nose SW), middle, tail | 0, 3, 1 |

A three-hex train is a cab hex, a middle hex and a tail hex: maglevtrain1-3 from
north to south, maglevtrain4-6 from south-west to north-east (every shipped
maglevtrain4 has a maglevtrain5 to its north-east, every maglevtrain6 one to its
south-west). No baked composite and no second rail mesh remain.

The pieces ride the client's generated guideway (a concrete beam 4 px wide to Z 2.4 and a steel guide rail
1.4 px wide to Z 4): each has its origin on the beam's centre line at the marker's level, the track along Y and
the nose at +Y, and carries its ride height, so every row has Z=0. A body hovers 0.4 px over the guide rail
(underside at Z 4.4); a black suspension shoe near each end bridges the rail and wraps the beam's sides 0.4 px
off the concrete, down to Z 1.3, clear of the maglev pier cap. Every vehicle is 30 px long over its ends, so two
cars and their 4 px gap fill a hex as the legacy rows place them (y -17 and +17). Two families, each car with
Body and Trim colour slots (the car's colour convention: every livery colour is a preset of both):

- City ("Civitas", Body cream, Trim teal, a fixed orange stripe): `cab` (control car with a wraparound
  windscreen and destination sign), `wagon` (passenger car), `service-car`, `city-freight` (two boxes on a
  flat), and `coupler`, their gangway with the bars that link the two cars' shoes.
- Colony ("Vector", Body navy, Trim cream, amber lamps): `colony-cab` (armoured wedge nose), `colony-cargo`,
  `colony-tanker`, `colony-containers` and `colony-heavy` (a construction walker strapped to a flatbed). Each
  carries its own drawbars, so no coupler row is needed.

`platform` is a raised station deck at the cars' floor (Z 5.2) with edge lights, stairs at both ends and a
lens-shaped canopy on Y columns; it is symmetric across the track, so it serves either side, and its edge lights,
canopy fascia and pylon signs are a Trim slot. The stamps (`scenery/layouts.json`): `scenery/maglev/train`
("City maglev": a wagon, a cab and their coupler, the legacy pair) and `scenery/maglev/colony-train` ("Colony
maglev": cab, cargo car, tanker and heavy transport at 34 px); `train.png` and `colony-train.png` are their
thumbnails. Placed objects draw only their near mesh (LOD0), so each piece is one mesh of 140 to 740 triangles.
A platform on a fixed-level (elevated) route floats at the route's level; it has no supports of its own.

`tools/build_scenery_assets.py` (with the `fluff/maglev` argument) writes the route marker mesh and the twelve
legacy maglev layouts, whose rows name the pieces; `blender --background --factory-startup --python
tools/build_maglev_assets.py`, from the data repository root, writes the pieces, both stamps' rows and their
thumbnails, and checks that no vehicle enters the beam or reaches the pier cap. The Java
`BoardSceneryMaglevTest` checks the decoded rows against the sprite facts above, the palette and the import of
two shipped boards.

## Rail pieces

The rail track (ballast, sleepers, rails) is generated by the client's route builder, shared with the maglev
beam. The pieces that never bend are GLBs under `scenery/rail/`, at real scale (2.8 px per metre): the
`buffer-stop` at dead ends, the level-crossing `crossing-signal` and the rolling stock of three families:
- Frontier Rail, armoured military-industrial (olive Body, orange Trim): `locomotive` (armoured freight
  locomotive, 56 px), `coach` (armoured transit coach, 62), `box-car` (cargo wagon, 46), `tank-car` (tanker, 42),
  `ore-hopper` (40) and `heavy-flatbed` (48, with a power unit as its load);
- the Express, a high-speed passenger train (white Body, blue Trim): `express-power-car` (64, nose tip included)
  and `express-car` (62);
- Ironline, colony mining freight (oxide red Body, cream Trim): `colony-locomotive` (56), `container-wagon` (46,
  two of the seaport's containers at real scale), `heavy-hopper` (42), `insulated-tanker` (42) and
  `equipment-carrier` (48, with an excavator chained down).

The track's rail top lies 1.4 px above its carrier plane (ballast top 0.6, sleepers 0.3, rails 0.5; gauge 4.2).
Every rail piece has its origin on the track centre line at rail-top height, the track along Y: a piece placed
1.4 px above the carrier plane rides the rails. Locomotive and power car noses and the buffer stop's buffers face
+Y; the signal faces +Y from its footing's base. Vehicles are measured over their coupler faces (a power car over
its nose tip) and carry their own couplers, so coupled vehicles stand half their lengths apart and need no coupler
piece. Each vehicle has two colour slots, Body and Trim, in the parked car's convention (`mmColourSlots`), with the
same twelve livery presets; warning stripes, lamps, glass, ore and running gear are fixed colours. Placed objects
draw only a GLB's level 0, so every vehicle is one mesh of about 650 to 1,150 triangles. Three stamps, each in its
family's default livery with the lead nose at +Y: `scenery/rail/train` ("Freight train": locomotive, cargo wagon,
tanker, heavy flatbed), `scenery/rail/express-train` (power car, two cars, the second power car turned 180 degrees)
and `scenery/rail/colony-train` (colony locomotive, heavy hopper, insulated tanker, equipment carrier), with
`train.png`, `express-train.png` and `colony-train.png` as thumbnails.
`blender --background --factory-startup --python tools/build_rail_assets.py` writes the fourteen GLBs, the
stamps' rows and the thumbnails; the crossing signal is a palette object of `tools/build_scenery_assets.py`.

The 64 legacy rail keys `scenery/hq_fluff/rail00`-`rail63` (FLUFF 10:0-63) decode to one route marker row,
`scenery/rail/route`, whose `connections` is the token value: the sprite's side mask. The client builds the track
from those sides. `rail00` has no sides; the conversion takes them from its neighbours, and an isolated one places
nothing. The six level crossings `rail_road01`-`06` (FLUFF 10:64-69) add three things: the marker on the rail's
axis, the `decal/rail/level-crossing` panel turned to the two axes, and four crossing signals. Each signal stands
beside the road, 10 px from its centre line and 8.5 px from the track's, and faces the road traffic that comes
towards it. `RAIL_CROSSINGS` in `tools/build_scenery_assets.py` holds the measured axes, and the `hq_fluff/rail`
argument rebuilds these keys.

How the client uses them (MegaMek `docs/3d-board-editor.md`, rails): a hex lays only gentle pieces, straights
between opposite sides and 60-degree arcs between sides two apart. A side without a gentle partner (two adjacent
sides, or the middle of three) ends in a short stub, and every dead end and stub gets a `buffer-stop`, placed by the
route builder and never stored. A legacy sprite always draws its sides' default pieces; the editor stores other
pieces only for the 18 side masks with a choice (`tracks`). A rail marker lies on the ground (`surface ground/top`)
and follows it and its ramps as a road does, or on a bridge deck (`bridge/deck`), whose drawn top it rides; a
vehicle row stands on the rail top. The Rail and Maglev routes are two palette choices in Transport.

## Legacy scenery decode

`scenery/layouts.json` is the decode table for legacy scenery keys: one row per
real object, placed on one canonical mesh. Rotated or baked duplicates are not
shipped. Bevel, ledge, roof grille, chimney stack, skylight, garden bed, pillar,
picnic table, hex plaza, fountain, crawler crane, bulldozer and concrete debris
are canonical components, recentred on their XY bounds and grounded at Z=0. A
legacy stack sprite is a grille and a chimney stack, square1 a plaza, a fountain
and trees, and construction sites 1 and 3 a vehicle and its debris. The fountain's
outer wall reaches the ground: the plaza hides that 0.9 px plinth, bare ground
shows it. Their rows use the same
angles and offsets that baked the old variants. GlassRoof-1-01..04 and
GlassRoof-2-02..04 are rows on the wide glass roof (the 1-0n rows stretch it to the
narrow roof's width), crane tips 03-06 rows on tips 01 and 02, OrbitalGun
N/S/W rows on the orbital gun and Landscape 1-03 rows on the round formal garden. The sport pool decks are separate components, so no
row names its own key. Rows carry no `kind`: `tree-broad` is the only tree.
Maglev decodes to a route marker and its pieces (see Maglev). Herds decode to one row per animal;
each seaport key stays one baked mesh.

The conversion takes every legacy art token (FLUFF and GROUND_FLUFF below the server values 2000+,
ROAD_FLUFF, WATER_FLUFF, BLDG_FLUFF), so a `.board2` holds none. A token becomes objects (these rows, or a legacy
decal id of `decals/decals.json`: runway, landing pads, letters, courts, rails), a hex design that draws exactly
its art (the blueprint variant whose `selectors` equal the token: `ground/blend/*` transitions at strength
exits/6, `road/rounded`, `road/horizontal`, `woods/orchard`, `rough/obstacles`, `rough/felled-trees`, the 55
`building/legacy-art-N` building art designs, or the asset variant of the building model chosen beside the art),
or nothing (the transparent wildcard `saxarba/misc/blank.png`, `bldg_fluff:0`, quay art the fitted quay wall
replaces). Elevator plates and the cleared-rubble gravel stay rows of their rule terrain (below).

The generator owns both the meshes and the rows. Rebuild every generated family
from the data repository root with
`blender --background --factory-startup --python tools/build_scenery_assets.py --
fluff/skylight GlassRoof fluff/ledge fluff/stack fluff/bevel fluff/construction
fluff/cars fluff/square fluff/pillars fluff/garden fluff/pool fluff/suburb
fluff/beacon fluff/heli fluff/maglev hq_fluff/rail SMV_Seaport road_trees SMV_Fluff/ orbitalguns rubble
fortified geyser fluff/bison fluff/cattle fluff/chickens fluff/horses fluff/pigs`,
then `tools/build_maglev_assets.py` for the maglev pieces, stamps and thumbnails, `tools/build_rail_assets.py` for the
rail pieces (see Rail pieces), and
`python tools/build_board_decals.py` for the decals and the car-park decal rows and seats
(the scenery build writes the car-park keys without them). The arguments select
image names, as `build(only)` does. The herd rows need the animal meshes of
`tools/extract_herd_animals.py`. The heli pads (`fluff/heli1`-`3`) decode to their landing lights
(`roofs/landing-light`, rows only) and the pad decal that `tools/build_board_decals.py` adds. Each build also
writes the palette objects (bench, rectangular pool, landing light, crossing signal; `-- --palette` writes
only them), and overwrites `tools/board-scenery-compositions.blend` and
`tools/board-models/scenery/model-inventory.json` with the selected families. The build and
`tools/verify_scenery_assets.py` read the sprite measurements that `python tools/prepare_scenery_layouts.py`
writes to `tools/board-models/scenery/layouts.json`.

`python tools/verify_legacy_decode.py` checks the rows against the baked GLBs of
commit `0d5b47e5d0`, the last commit that has them at their legacy keys. A
replaced key must match its old GLB after grounding, because that runtime
grounded a whole legacy SCENERY mesh but placed rows as authored. A key that
already had rows must match its old composition, trees included; the maglev keys
are re-authored from their sprites (see Maglev) and skip that comparison, as do the keys whose art the base
only painted (rails, heli pads, elevator plates, the cleared-rubble gravel), which have no 3D reference. Every tileset
key that resolved to 3D at the base must still resolve through layouts.json, on
existing meshes; the rail route marker has none, because the client generates its track. Every mesh reached by a decodable tileset token (`fluff` below
2000, `road_fluff:3`, `road:2`) must be grounded and have a
blueprint entry, and the rows of decoded keys must have Z=0. No layout may
z-fight: within one mesh, and between the rows of a layout, no two upward faces
that face the same way and are shaded differently may lie within 0.1 px of each
other where their outlines overlap. No two meshes that rows, palette props or
the scatter kit reach may be copies (the same vertex radii about Z, heights,
colours and materials): a rotated or mirrored copy is a row on the other mesh.
That check does not catch stretched or regenerated near-copies, which need a
scan with fitted transforms. Decals (see Decals) must have their image by path
convention and every image an entry; palette decals and legacy ids must name
existing decals; every ground-symbol, landing-pad, letter, runway and court tile must decode to a decal, and
every elevator plate and the cleared-rubble gravel to a decal row; each set must have its centre
and six directions once; each one-hex variant must match its emblem at its decode
transform (blurred mean difference at most 8/255, coverage overlap at least
0.75); and every car of a car-park key must have its own slot on one of the
key's decal rows. A row's `colours` must be one to four `#rrggbb` values or null,
no more than its mesh's colour slots, and a key whose rows recolour a shared mesh
must reproduce the base's colours vertex by vertex within 5/255 (see Colour
slots). Deliberate geometry changes since the base
are listed as Fixed. Residuals are symmetric Hausdorff distances between vertex
sets, in model px:

| Family | Keys | Rows | Canonical meshes | Reference | Mesh residual (px) | Tree residual |
|---|---:|---:|---|---|---:|---:|
| 01-Building-07-GlassRoof-# | 9 | 9 | glass-dome, glass-roof-wide | baked GLB | 2.7e-01 | 0.0e+00 |
| 02-Sport-03-SwimmingPool-# | 5 | 19 | sport-1-deck, sport-1-main, sport-1-wading, sport-2, sport-3-deck, sport-3-main, sport-3-wading, sport-4, sport-5 | old rows | 7.5e-01 | 1.6e+00 |
| 07-Garden-01-Tree-# | 5 | 13 | - | old rows | 0.0e+00 | 0.0e+00 |
| 07-Garden-02-Table-# | 5 | 97 | picnic-table | old rows | 2.2e-06 | 0.0e+00 |
| 07-Garden-03-Landscape-# | 4 | 4 | formal-garden-hex, formal-garden-round, formal-garden-star | baked GLB | 0.0e+00 | 0.0e+00 |
| 07-Garden-04-Lake-# | 5 | 11 | freeform, sport-2, sport-4 | old rows | 0.0e+00 | 0.0e+00 |
| OrbitalGun# | 4 | 4 | orbital-gun | baked GLB | 2.0e-01 | 0.0e+00 |
| SeaportSystem-01-Container-01-20Footer-# | 28 | 28 | 28 meshes (containers-e-w-01 ...) | baked GLB | 0.0e+00 | 0.0e+00 |
| SeaportSystem-02-ShipToShoreGantryCrane-01-20Footer-# | 48 | 48 | 48 meshes (gantry-crane-e-w-01 ...) | baked GLB | 0.0e+00 | 0.0e+00 |
| SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-# | 6 | 6 | crane-tip-01, crane-tip-02 | baked GLB | 1.0e+01 | 0.0e+00 |
| beacon# | 2 | 2 | landing-beacon-hex, landing-beacon-round | baked GLB | 0.0e+00 | 0.0e+00 |
| bevel# | 6 | 6 | bevel | baked GLB | 3.6e-06 | 0.0e+00 |
| bison# | 1 | 2 | bison | baked GLB | 1.7e-06 | 0.0e+00 |
| cars_# | 8 | 79 | car, parking-barrier, parking-shelter | old rows | 0.0e+00 | 0.0e+00 |
| cars_2b | 1 | 8 | car, parking-shelter | old rows | 0.0e+00 | 0.0e+00 |
| cars_3b | 1 | 9 | car, parking-barrier | old rows | 0.0e+00 | 0.0e+00 |
| cattle# | 3 | 7 | cow, cow-grazing, cow-resting | baked GLB | 2.0e-06 | 0.0e+00 |
| chickens# | 3 | 9 | hen, rooster | baked GLB | 2.3e-06 | 0.0e+00 |
| construction# | 3 | 5 | bulldozer, crawler-crane, debris-1, debris-3, site-excavation | baked GLB | 5.0e-02 | 0.0e+00 |
| fortified | 1 | 1 | fortification | baked GLB | 0.0e+00 | 0.0e+00 |
| garden# | 6 | 36 | garden-bed | old rows | 8.3e-07 | 0.0e+00 |
| geyser_magma | 1 | 1 | magma | baked GLB | 2.2e-01 | 0.0e+00 |
| geyser_water_off | 1 | 1 | water-dormant | baked GLB | 0.0e+00 | 0.0e+00 |
| geyser_water_on | 1 | 1 | water-erupting | baked GLB | 0.0e+00 | 0.0e+00 |
| horses# | 2 | 7 | horse, horse-black-running, horse-brown-running, horse-relaxed | baked GLB | 2.4e-06 | 0.0e+00 |
| ledge# | 6 | 6 | ledge | baked GLB | 3.4e-06 | 0.0e+00 |
| pigs# | 2 | 8 | pig, pig-brown-resting | baked GLB | 2.2e-06 | 0.0e+00 |
| pillars# | 6 | 36 | pillar | baked GLB | 2.0e-06 | 0.0e+00 |
| pool# | 1 | 2 | freeform | old rows | 0.0e+00 | 0.0e+00 |
| road_trees# | 64 | 336 | - | old rows | 0.0e+00 | 0.0e+00 |
| rubble_hardened | 1 | 1 | hardened | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_hardened_path | 1 | 1 | hardened-path | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_heavy | 1 | 1 | heavy | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_heavy_path | 1 | 1 | heavy-path | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_light | 1 | 1 | light | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_light_path | 1 | 1 | light-path | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_medium | 1 | 1 | medium | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_medium_path | 1 | 1 | medium-path | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_wall | 1 | 1 | wall | baked GLB | 0.0e+00 | 0.0e+00 |
| rubble_wall_path | 1 | 1 | wall-path | baked GLB | 0.0e+00 | 0.0e+00 |
| skylight# | 6 | 6 | skylight | baked GLB | 3.2e-06 | 0.0e+00 |
| square# | 6 | 13 | fountain, plaza, plaza-flowers, plaza-flowers-pillars, plaza-hedge, plaza-pillars, plaza-pond | baked GLB, old rows | 9.0e-01 | 0.0e+00 |
| stack# | 6 | 12 | chimney-stack, grille | baked GLB | 2.1e-06 | 0.0e+00 |
| suburb# | 3 | 23 | car, concrete-pipe, grandstand, parking-shelter-no-floor, picnic-table, rectangular-no-deck, round-no-deck | old rows | 7.8e-07 | 0.0e+00 |

- 281 tileset keys resolved to 3D at the base; all resolve through layouts.json, and every row names an existing mesh.
- `bevel1` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `bevel2` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `bevel3` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `bevel4` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `bevel5` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `bevel6` (now `scenery/roofs/bevel`) stood 1 px off Z=0; the mesh is re-grounded.
- `FluffSystem-01-Building-07-GlassRoof-3-01` (now `scenery/roofs/glass-dome`) stood -7.4 px off Z=0; the mesh is re-grounded.
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-01` (now `scenery/seaport/crane-tip-01`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-02` (now `scenery/seaport/crane-tip-02`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-03` (now `scenery/seaport/crane-tip-02`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-04` (now `scenery/seaport/crane-tip-01`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-05` (now `scenery/seaport/crane-tip-02`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-06` (now `scenery/seaport/crane-tip-02`) stood 10.3 px off Z=0; it keeps that height (see Fixed).
- 141 meshes reached by decodable tileset tokens: all grounded within 0.01 px and present in the blueprint.
- Every row has Z=0.
- Decals: 22 in `decals/decals.json`, each with its image by path convention; 170 legacy decal ids decode to them.
- Emblems: 13 full emblems; all 169 ground-symbol tiles decode (13 sets of 7 pieces, 78 one-hex variants). The variants match their emblem at the decode transform: blurred mean |difference| at most 5.5/255 (the -04 variants at most 4.4), coverage overlap at least 0.77.
- Car parks: 10 legacy car-park keys place 20 standard decal rows and seat all 72 cars in distinct slots (only the conversion places them; no 3D view draws the legacy sprite).
- 4 keys stretch a row (01-Building-07-GlassRoof-#).
- Colours: 25 keys recolour a shared mesh; 25 keep the base's vertex order and match its colours, by family within 07-Garden-04-Lake-# 0.6, bison# 2.6, cars_# 0.5, cars_2b 0.5, cars_3b 0.4, cattle# 0.4, chickens# 2.9, horses# 3.9, pigs# 1.1, suburb# 0.5 (of 255).
- Copy check: 256 meshes reached by rows, palette props and the scatter kit; accepted `water-dormant`: GpuGeysers takes the eruption from the asset name (water-erupting).
- Coplanar check (upward faces within 0.1 px, outlines overlapping by more than 0.01 px, different shading): 56 multi-row layouts and every row mesh, no z-fighting.
- Accepted: 12 sliver pairs in 5 terrain-owned rubble meshes (rebar and beam flanges crossing slabs at shallow angles).
- Accepted: `FluffSystem-02-Sport-03-SwimmingPool-1-03` trees lowered by 1.6 px to Z=0.
- Fixed: `OrbitalGunE` differs by 0.2 px: vent slats raised clear of the plinth top they z-fought with.
- Fixed: `OrbitalGunN` differs by 0.2 px: vent slats raised clear of the plinth top they z-fought with.
- Fixed: `OrbitalGunS` differs by 0.2 px: vent slats raised clear of the plinth top they z-fought with.
- Fixed: `OrbitalGunW` differs by 0.2 px: vent slats raised clear of the plinth top they z-fought with.
- Fixed: `construction1` differs by 0.05 px: the debris is its own object, grounded: it floated 0.05 px.
- Fixed: `construction3` differs by 0.05 px: the debris is its own object, grounded: it floated 0.05 px.
- Fixed: `square1` differs by 0.9 px: the fountain is its own object; its outer wall reaches the ground, hidden by the plaza.
- Fixed: `FluffSystem-01-Building-07-GlassRoof-1-01` differs by 0.273 px: the narrow glass roof is the wide one stretched to 29 px; its side curbs and ridge bar are 20% thinner.
- Fixed: `FluffSystem-01-Building-07-GlassRoof-1-02` differs by 0.273 px: the narrow glass roof is the wide one stretched to 29 px; its side curbs and ridge bar are 20% thinner.
- Fixed: `FluffSystem-01-Building-07-GlassRoof-1-03` differs by 0.273 px: the narrow glass roof is the wide one stretched to 29 px; its side curbs and ridge bar are 20% thinner.
- Fixed: `FluffSystem-01-Building-07-GlassRoof-1-04` differs by 0.273 px: the narrow glass roof is the wide one stretched to 29 px; its side curbs and ridge bar are 20% thinner.
- Fixed: `FluffSystem-02-Sport-03-SwimmingPool-1-03` differs by 0.751 px: two overlapping pool islands, whose coplanar tops z-fought, are merged into one.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-01` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-02` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-03` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-04` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-05` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `SeaportSystem-02-ShipToShoreGantryCrane-03-CraneTip-1-06` differs by 10.3 px: tips keep their boom height; grounding them broke the boom at the hex edge.
- Fixed: `geyser_magma` differs by 0.215 px: lava fissures lifted from 0.035 to 0.25 px above the rock they z-fought with.
- Accepted: 1 `car*` meshes stand 0.0494 px up, as authored.
- Accepted: 2 `crane-tip-*` meshes stand 10.3 px up, as authored.
- Accepted: 1 `wagon*` meshes stand 3.5 px up, as authored.
- Accepted: 1 `cab*` meshes stand 3.5 px up, as authored.
- Accepted: 1 `coupler*` meshes stand 4 px up, as authored.

Tolerance is 0.001 px for meshes and trees and 0.01 px for grounding. The pool
trees are the only accepted tree difference: tree meshes are shared species
assets, so a pool-island tree cannot keep its 1.6 px model height. The rubble
meshes are terrain-owned and never placed by import or the editor; their thin
rebar and beam flanges cross slabs at shallow angles, and those slivers are
accepted by the coplanar check.

## Decals

A decal id `decal/<group>/<name>` is the image `decals/<group>/<name>.png`; no
catalog is needed to find it. Images are straight RGBA with north (+y) at the
top; transparent texels carry the colour of the nearest ink so filtering and
mipmaps do not darken edges. `tools/build_board_decals.py` writes every image and
`decals/decals.json`, and also the car-park rows of `scenery/layouts.json`:

| Folder | Decals | Source |
|---|---|---|
| `emblems/` | `red-cross`, `capellan-confederation`, `draconis-combine`, `federated-suns`, `free-worlds-league`, `lyran-commonwealth`, `terran-hegemony`, `magistracy-of-canopus`, `outworlds-alliance`, `rim-worlds-republic`, `taurian-concordat`, `star-league`, `comstar` | the seven pieces of the Saxarba 7-hex set stitched at their hex offsets: 144 x 144 px, 1 image px per model px, identical to the unused `-Medium` images |
| `car-park/` | `straight-4`, `-8`, `-12`; `parallel-3`, `-6`; `diagonal-3`, `-6`, `-9` | painted: 8 image px per model px |
| `damage/` | `rubble-light-path`, `cleared-rubble-gravel` | copies of `images/hexes/saxarba/rubble_light_path.png` and `cleared_rubble_gravel.png` (84 x 72) |
| `runway/` | `centreline` (6 x 64), `threshold` (64 x 28), `number-36`, `-06`, `-12`, `-18`, `-24`, `-30`, each also with `l`, `c`, `r` (56 x 72) | redrawn from the legacy runway geometry at 8 image px per model px; designations in Noto Sans Regular (`data/fonts`, OFL); white paint at 95 % |
| `landing-pads/` | `vtol-`, `medic-`, `aero-`, `aero-lit-` each `concrete` and `asphalt` (72 x 72); `dropship-`, `dropship-ring-` each `concrete` and `asphalt` (144 x 144); `heli-pad` (60 x 60) | one-hex pads cut 1:1 from the -01 sprites; DropShip pads stitched from their 7 pieces as the emblems; the heli pad redrawn flat |
| `lettering/` | `letter-a` ... `letter-z`, `digit-0` ... `digit-9` (40 x 40) | the upright black sprite's shape, 4x bicubic, blurred and re-sharpened, white: the object's paint colour (`size` entry `"colour": "#ffffff"`) multiplies it |
| `sport/` | `tennis-court-green`, `-blue` (33 x 63); `basketball-court-green`, `-blue` (39 x 71) | redrawn at 8 image px per model px, 0.75 px lines |
| `elevator/` | `level-minus-10` ... `level-minus-1`, `level-0` ... `level-10` (84 x 72) | copies of `images/hexes/saxarba/misc/elevator_<n>.png`; rows of the elevator's rule terrain, not palette decals |
| `rail/` | `level-crossing` (16 x 27) | redrawn: two 15 px strips (road and rail) at 60 degrees, concrete, yellow dashed edges; placed by the level-crossing rows |

The 2D tileset's ground-symbol pieces and their copies under `tileset/` stay for
the 2D board, which draws a converted board's kept tokens, and for the conversion,
which matches the `tileset/` copy; only the palette moved here.

`decals/decals.json`:

```json
{
  "format": "megamek-board-decals", "version": 1,
  "decals": {
    "decal/emblems/red-cross": {"size": [144, 144]},
    "decal/car-park/straight-4": {"size": [22.5, 9.25],
      "slots": [{"position": [-8.25, -0.075], "heading": 0}, ...]}
  },
  "legacy": {
    "decal/saxarba/SMV_GroundSymbols/FluffSystem-05-Symbol-01-RedCross-1-04":
      {"decal": "decal/emblems/red-cross", "scale": 0.5, "rotation": 0},
    "decal/saxarba/SMV_GroundSymbols/FluffSystem-05-Symbol-01-RedCross-1-10":
      {"decal": "decal/emblems/red-cross", "set": true},
    "decal/saxarba/SMV_GroundSymbols/FluffSystem-05-Symbol-01-RedCross-1-12":
      {"decal": "decal/emblems/red-cross", "set": true, "direction": 2},
    "decal/saxarba/rubble_light_path": {"decal": "decal/damage/rubble-light-path"}
  }
}
```

- `size`: the decal's footprint at scale 1, model px (a hex is 84 x 72), centred on
  the object's position. Image px differ per group; only `size` sets the footprint.
- `slots` (car parks only): parking places in the decal's frame, model px from its
  centre, +y toward the back of the bays (the bay centres); `heading` is the car's rotation in
  degrees (CCW, 0 = the car's front to +y, as object rotations). The slots fit
  the car mesh at its car-park scale 0.8 (3.84 x 7.36 px) with at least 0.33 px to
  every bay line.
- `legacy`: old decal ids, which are also the legacy tileset images
  (`decal/` + the tileset image path without extension; `.board2` files saved
  before this change use them). `scale` (default 1) and `rotation` (default 0,
  CCW degrees) are the new decal's transform at the old object's position.
  `"set": true` marks a piece of a ground symbol's 7-hex set: import places ONE
  decal at scale 1 and rotation 0 on the set's centre hex, which is the piece's
  own hex for the centre piece (no `direction`) and its neighbour in direction
  `(direction + 3) % 6` otherwise (`direction` is the piece's hex direction from
  the centre: 0 N, 1 NE, 2 SE, 3 S, 4 SW, 5 NW). A set with
  pieces missing on the board paints exactly its present pieces: each gets the
  set's decal on the set centre, clipped to its own hex, one group per set; a set
  cut by the board edge still gets its full emblem at the inferred centre. The
  landing pads' DropShip sets follow the same rule. A legacy row may carry a
  paint `colour` (`"#000000"` on the black letters), which the converted decal
  object stores as its colour. The one-hex variants
  -01/-04 are upright, -02/-05 turned -30 deg and -03/-06 +30 deg; their scales
  were fitted to the legacy tiles (small 0.204-0.326, large 0.346-0.503 per emblem).

Car parks: each standard decal is only its row of bays (straight: 5.5 x 9 px
bays; parallel: 9.8 x 5 px; diagonal: 60 deg to the row, 5.5 px wide and 10.8 px
long along the car), open on its bottom (road) edge: the dividers reach that edge,
and the back line and the two end dividers lie on the other three edges, so no
asphalt shows beyond them and two rows laid back to back touch line to line.
Unmarked asphalt with white bay lines, no aisle, no road markings, fully opaque.
Two sides are the same decal twice, the second turned 180 deg, one on each side
of the road. In `scenery/layouts.json` each legacy key `fluff/cars_*` (1-8, 2b,
3b) has one decal row per side of its lane that has cars, beside the lane's road:
its road-side edge 7.3 px from the lane's centre line (`ROAD_EDGE`: the road's
7.5 px half width less half its 0.45 px asphalt fade, so the decal hides the
road's gray verge and leaves its carriageway clear), the smallest standard of the
cars' layout (across the lane: straight; along it: parallel) with room for that
side's cars. No legacy car park is diagonal. Where no road is drawn (no lane, as
2b/3b; a roof, deck, industrial top, fuel tank, ice or liquid; a road level the
renderer does not draw), the conversion folds the same rows back to back on
the line through the hex centre, turned and mirrored, their closed sides touching.
Each car row carries `"seat": [n, slot]`: the conversion places that car on
`slots[slot]` of the key's n-th decal row (the decal row's transform, mirror
included, applied to the slot; the car keeps its asset, colour and scale). Cars
keep the order they had along the lane; beside the road they move up to 22.0 px
(mean 3.7-12.5 px per key) from their legacy spots, back to back up to 23.0 px
(mean 8.7-13.4 px). Seats and decal rows exist only for the conversion.

## Editor palette, import and stamps

The rows serve one reader, the conversion (`BoardSceneryLayouts.convert`, 
wherever a legacy `.board` is loaded (a game's sheets on the server, old
saves, map previews, the editor) it turns a key's rows into separate placed
objects once, with the rows of one key in one group. Stamps in
`data/board-editor/blueprint.json` name a key in their `layout` field and place
its rows the same way; `{exits}` in a stamp's layout becomes the painted hex's
road exits. Beside them, the 3D board draws the rows of the terrain-owned keys
directly: geysers, rubble 1-6, fortified and the cleared-rubble paths (FLUFF
2001-2005), and the elevator plates (`saxarba/misc/elevator_<n>`,
following the elevator's level) and the cleared-rubble gravel (GROUND_FLUFF 2000),
whose decal rows become decals of their hex that are never stored or picked. The
conversion never takes them, and they change during play. So
editing a row changes future conversions, stamps and the terrain-owned keys'
drawing, but never objects already on a converted board or saved in a `.board2`.

Palette rules, checked by `BoardSceneryDecodeDataTest`:

- A visible entry is one real object a user places, or a stamp: 226 props.
- A mesh that only imported objects use is `palette: false` and keeps its
  label (sport-pool parts, plaza ornaments, the second debris pile, the rooster
  and the other animal poses: one visible animal per species). Coats and paints
  are colours, not entries. An entry may place another `model` in `colours`: the
  three ponds are pools in the pond colours. The five `-snow` trees that keep their
  own GLB are `palette: false` too: a tree takes its winter form on a snow surface,
  and its Snow toggle keeps it bare.
- No visible ID is a layouts key. Transport shows the two routes, Maglev and Rail, the crossing signal and the
  roadside-trees stamp (and the level crossing among the decals). Maglev and wagons (28) shows the station
  platform, the city and colony maglev cars, the thirteen rail vehicles and five train stamps: City maglev,
  Colony maglev, Freight train, Express train and Colony train (see Maglev and Rail pieces); the city gangway
  coupler is `palette: false`. Airfield shows the landing light.
- Rotated or baked duplicates are not shipped; terrain-owned scenery (rubble,
  geysers, fortifications) has no prop entry, though its GLBs stay.
- Every decode row's mesh has a blueprint entry, so imported objects have a
  readable name.
- Decals: 102 visible entries, all from `decals/`: the 13 full emblems
  ("Emblems"), the 8 standard car parks ("Car park, straight 12", ... in
  "Ground details"), the light rubble path ("Damage and debris"), the 26 runway
  markings and 13 landing pads ("Airfield"), 36 letters and digits ("Lettering"),
  4 courts ("Sport and pools") and the level crossing ("Transport"). The
  emblem pieces and one-hex variants have no entry; they only decode
  (`decals/decals.json` `legacy`). The elevator plates and the cleared-rubble
  gravel have none either: they belong to their rule terrain.
- Designs: `rough/felled-trees` ("Felled trees", Designs) and the 55
  `building/legacy-art-N` variants ("Legacy building art N", 100: "Legacy roof
  outline"; group "Legacy building art"), each with the `selectors` of the
  legacy token it stands for.

The 78 seaport pieces are
visible in the Seaport group (container yards, gantry cranes and the straight and
diagonal boom tips, which the other four tip directions turn), one baked mesh each, with live 3D previews; import
places each seaport key as one object and gives a hex whose art covered woods
the `woods/no-trees` vegetation design. Imported and placed trees store their
bare species; the renderer draws the `-snow` form on a snow surface unless the
object is marked `"bare": true`.

For 19 species the `-snow` form is a material variant of the bare GLB, not a file:
the six `orchard-*`, `pine`, `pine-broad`, `pine-slender`, `pine-layered`,
`tree-broad`, `birch`, `willow-broad`, `tree-layered`, `birch-spreading`,
`birch-young`, `tree-slender`, `tree` and `birch-tall`. Their materials' extras
`mmVariants.snow` give the snow canopy material and textures, a linear factor on
the crown's vertex colours (the snow cards drop the species' pigment) and the
winter impostor's texture and card colours; `manifest.json` points their `-snow`
entry at the bare file (`"variant": "snow"`). The runtime builds the winter form
from it (`RigidGlb.source`). `pine-tall`, `tree-dead`, `willow`, `tree-forked` and
`foliage-snow` keep their own winter GLB: the duplicate scan found their snow
geometry or bark different. `python tools/merge_snow_trees.py merge` folds a
rebuilt `<species>-snow.glb` into its bare GLB (and removes it); `split` writes it
out again for the Blender tree tools, which read and write the winter GLBs. Ten
pairs share the bare geometry exactly; the nine regenerated ones (from
`tree-broad` on) take the bare geometry, 0.15-0.61 px from their own.

## Rock and scatter meshes

- `rocks/block-N.glb` and `rocks/boulder-N.glb` (N = 0..7) are sixteen independently
  editable rock variants. Each contains three root nodes named `block-N-lod0`,
  `block-N-lod1`, `block-N-lod2` (or `boulder-N-lod0`, etc.). The library has 48
  meshes and 1,572 triangles. Rough terrain, rims, slopes and cliffs share these files.
- `rocks/outcrop-N.glb` (N = 0..7) are bedrock formations used by zero-gravity
  rough and dry natural rough on exposed ridges, in the same layout (`outcrop-N-lod0` to `-lod2`; 92, 44
  and 22 triangles). Unlike the other rocks they are generated: rebuild them with
  `blender -b --factory-startup --python tools/build_outcrop_assets.py`.
- `scatter/` contains 25 independently editable GLBs: `stone-block-N.glb` and
  `stone-boulder-N.glb` (N = 0..7, eight triangles each, open base), `bush-N.glb`
  (N = 0..7, shrub masses, 660 triangles dry and 792 green) and `grass.glb` (six
  triangles). The small scatter plant is the first bush of its biome (`bush-0`
  dry, `bush-4` green).
  Each file contains only its `<shape>-lod0` root mesh (for example, `grass-lod0`)
  and that mesh's vertices.
  The complete scatter kit has 5,942 triangles. Grass and bushes have explicit
  back faces; green and dry grass share geometry.

For terrain rocks, LOD0 is the most detailed version. LOD1 and LOD2 are optional;
the loader resolves missing levels once as LOD2 -> LOD1 -> LOD0, sharing the
existing mesh. LOD0 is required. Fallback stays within one shape and file,
so a scatter stone can never select a larger terrain rock. Scatter uses only
LOD0 and does not load additional levels. Terrain's first two sampling bands use
rock LOD0; subsequent bands use rock LOD1 and LOD2, preserving the established
screen-size thresholds.

These files are the editable mesh source, baked from the original Java shapes.
Import/export one file in Blender as uncompressed GLB, preserving names, triangle
budgets and flat normals. Each shape is a root node. After Y-up to Z-up import,
rocks have their base at zero and a largest horizontal extent of one. There
are no textures or embedded animation clips. Their material is named `geometry`;
the renderer chooses colors and terrain shading. The importer restores shared
corners for CPU ground sampling. Placement, picking and batching share the meshes;
no rock or scatter geometry is generated in-game.

## Contents and editing

- `tileset/saxarba.tileset`: the forced 3D tileset, with all recursive includes
  and referenced images, including references outside the Saxarba subdirectory.
  The 7,295 files are independent copies. Edit these without affecting 2D.
- `buildings/`: 3,295 structure models with roofs derived from the exact selected
  tile image. Simplified outlines retain diagonal walls, curves, disconnected
  parts and courtyards; no runtime pixel extrusion or generic substitutions.
- `building-manifest.json`: each structure's source, facade family, wall tint,
  outline, vertex and triangle counts. The largest has 499 triangles. Fuel tanks
  and industrial structures use their selected Saxarba artwork too; generic
  cylinder/factory substitutes have been removed.
- `field.glb` and foliage GLB files. Counts and the imported Blender source
  names are in `manifest.json`. Bridge spans are generated at runtime;
  reusable terminal and pier kits remain GLBs.
- Each tree GLB contains `-lod0`, `-lod1`, and `-lod2` groups, with budgets
  of 480, 240 and 96 triangles including explicit back faces. Sixteen leafy
  variants retain their authored trunks and crown envelopes but replace closed
  leaf shells with cutout branch clusters. Standard glTF `MASK` materials use
  a 0.5 alpha threshold in color, depth and shadow passes. Pine branch roots
  follow the authored curved trunk. Palms use curved, folded cutout fronds;
  cacti retain their stem silhouettes with smooth normals, mapped ribs and
  cutout flowers. Dead trees keep their existing near meshes and decimated or
  component-hull distant meshes. These runtime GLBs are the maintained tree
  meshes; the legacy low-poly source exports and their importer have been retired.
  A `-lod3` group holds the plant's impostor: two crossed vertical cards and a
  horizontal cap through the crown, 12 triangles with their backs, textured by
  `textures/foliage/impostors/<name>.png` (three 128 by 128 unlit renders of
  LOD0 from the front and the side, both 30 degrees above the plant, and from
  above: the game's raw albedo before lighting, the detail texel times the
  display-space vertex colour, with edge colours dilated for the cutout). Each
  card side's normal is the mean normal of the surfaces its render shows, so the
  cards take the light as the plant does. The cards' vertex colour carries how
  the plant takes the sun: red, the share of direct light its own leaves let
  through; green, the share of bark, cactus or snow the card shows. Shrubs and
  orchard trees carry the same level; `prepare_tree_lods.py -- impostors`
  refreshes it for all of them.
  The manifest records every level; screen-pixel thresholds live in Java's
  `TreeLod`, so no camera or game state is baked into these assets.
- Every plant's origin is the foot of its trunk, where the board places, grounds and
  clears roads for it; a leaning crown (bent palm, willow) overhangs to one side.
  The maintained GLBs keep that origin and their bark projection. Cactus skin
  wraps around each stem, following bent arms.
- `textures/foliage/*-cutout.png`: six shared 512 by 512 RGBA textures
  for broadleaf/conifer and their snow variants, palm fronds and cactus flowers. Near, medium and far crowns
  share these clamped images; impostors are baked from the same alpha-tested
  geometry. Source images, exact ImageGen prompts and reproduction instructions
  are in `tools/foliage-sources/README.md`. Bark textures remain shared.
- `textures/foliage/cactus-skin.png` and `cactus-skin-normal.png`: 512-square
  albedo and estimated shallow normal relief, shared by both cactus variants
  at all three mesh levels. Standard glTF `normalTexture` supplies the normal
  detail; the instanced foliage shader uses the existing dielectric light model
  for waxy skin. The normal-map tuning switch applies to these maps too.
- `textures/foliage/`: nine shared 64 by 64 detail albedos for broad leaves,
  pine needles, hanging willow leaves, palm fronds, ordinary bark, birch bark,
  ringed palm bark, ribbed cactus stems and snow. Source material boundaries keep snow caps separate
  from green foliage and preserve the birch's pale trunk and dark scars. Existing
  vertex colors tint the pale maps; dominant-axis UVs follow the tree's original
  proportions. Snow variants use their own authored geometry. Texture generation
  prompts are recorded in `tools/board-foliage-texture-prompts.json`; the cactus
  old cactus map is procedural (`tools/build_cactus_texture.py`, CC0-1.0).
  These small legacy leaf/cactus maps remain available to original authoring
  models; converted runtime plants use the cutouts and skin maps above.
- `orchard-*.glb`: six fruit-tree forms and their snow variants reuse the shared
  branch-cutout baker. Their authored branch and apple counts stay intact at
  each level; leaf cards use the remaining budget (480/240/84/12 triangles per
  tree). Bark and fruit retain their orchard atlases. Rebuild with
  `tools/build_orchard_assets.py`, then `tools/prepare_tree_lods.py -- impostors`.
- `textures/foliage/marsh-sedge.png`: the editable 1254 by 1254 RGBA sedge/cattail
  cutout for marsh vegetation. The renderer filters it to one shared 512 by 512
  texture with mipmaps; all three plant LODs use this same image. Ground peat,
  moss and pools are shaded separately using the existing sculpt earth maps.
- `textures/buildings/`: 128 by 128 runtime facade maps. Light buildings retain
  windows; medium uses concrete, hard reinforced concrete, and heavy armored
  panels. Fortresses/gun emplacements use massive sci-fi walls, hangars use
  large shutter bays, fuel tanks use metal courses, and industry uses service
  panels/vents. Sealed structures and dropships use closed armored panels.
  Source names select the family; opaque roof colors tint each model's walls.
  Ordinary facade courses repeat once per four stories. Hangar doors and
  fortress buttresses span the full height instead of stacking per story.
  Eight light-building windows span 128 world units; other families have fewer,
  larger structural bays at that width.
- `textures/terrain/`: 128 by 128 runtime concrete, dirt, rock and sand maps,
  repeating once per 96 world units. Both texture directories have a
  `full-resolution/` subdirectory containing the untouched editable originals.
  Models and materials reference only the small runtime versions. Rebuild those
  after editing originals with `tools/prepare_board_textures.py`.
- `textures/sculpt/`: the sculpted terrain's 512 by 512 materials (ground,
  debris, wall and mantle maps for every surface family): `NAME.png` is sRGB albedo
  with normalized height in alpha, `NAME-normal.png` a tangent normal (U right, V
  down) with ambient occlusion in alpha, and `manifest.json` the metres each repeat
  spans. `tools/build_terrain_materials.py` builds the original procedural set
  (CC0-1.0). Afterward,
  `tools/prepare_terrain_contact.py` bakes the authored ground, soil, stone and
  scree sources into those same slots; `--check` verifies pixels and metadata.
  ImageGen sources and exact prompts are in `tools/terrain-contact-sources/`;
  their height/normal relief is an artistic estimate, not a measured scan. See
  `tools/terrain-realism/README.md` for the stone sources and visual references.
  The former `outcrop-*` formations are replaced by the shared GLB rock kit below.
- `textures/cliffs/`: the vertical hex sides' 1024 by 1024 color, tangent normal,
  and packed height/roughness/occlusion maps for rock, sandstone, soil, concrete
  and snow. These retain full mip resolution and use the board's dedicated
  parallax material shader. Missing sets fall back to `textures/terrain/`.
  Rebuild with `tools/prepare_cliff_materials.py`; `--check` verifies all baked
  pixels. Sources and generation prompts live in `tools/cliff-sources/` and
  `tools/cliff-texture-prompts.json`. Optional grayscale `NAME-height.png` sources
  supply authored geometry; otherwise height is an artistic approximation from
  source luminance. No baking or height estimation runs in the game. These maps
  are separate from top tiles, upper rims, buildings and water beds.
- `textures/bed.png`: a 128 by 128 silt, sand and pebble riverbed albedo;
  water reflections and animation remain in the separate water surface.
- `textures/*-rim.png`: six 128 by 128 pale material-detail maps for grass,
  dirt, sand, rock, concrete and snow. Runtime tints them from the selected
  Saxarba ground artwork, preserving each theme's palette. An irregular mesh
  edge fades into the geology; fixed world-scale UVs crop the texture on short
  walls instead of stretching it to fit. Model rebuilds preserve these maps.
- Liquid artwork comes from this directory's own `tileset/saxarba/anim_water_N.gif`,
  `theme_mars/water_anim_mars_N.gif`, `theme_volcano/water_anim_volcano_N.gif`,
  `base/base_magma_anim_N.gif`, and `water/rapids_anim.gif` / `water/torrent_anim.gif`.
  The latter paths are relative to `tileset/saxarba/`. All are independent copies
  of the original 32-frame, 3.2-second animations. `tools/copy_board_tileset.py`
  includes these runtime-selected images even when the static tileset omits them.
  `GpuWaterShader.USE_PROCEDURAL_WATER` selects shader-generated water patterns
  and palettes matched to this artwork, using the renderer's shared noise field.
  Set it to `false` and rebuild for the authored water GIFs. Both paths share
  wave/rain normals, lighting, reflection, downstream currents and waterfall foam/spray.
  Magma retains its original artwork. `GpuLiquidShader.USE_SHADER_ANIMATION`
  interpolates the original GIF frames; set it to `false` for discrete frame timing.
  In the GIF path, transparent foam is composed onto the water image. Hazardous
  liquid shares the water material with a green tint in both paths.
  The renderer constructs curved banks and actual depth; the static
  `Structured_Water` art is a shoreline reference, not a baked replacement.
  Two nonadjacent water openings form a continuous channel. Elevation drops
  use vertically scrolling, animated water on the waterfall face.
- Exposed top edges reuse the single south-facing `08` patches under
  `tileset/High_Incline/`, oriented per edge. Edit these to change cliff-top
  detail without affecting 2D. The renderer avoids mixing their baked lighting
  with the brighter north-facing variants and leaves road approaches open.
  `normals/High_Incline/` supplies their matching normal maps. Runtime rotates
  these directions with the edge, combines color and normals with the ground
  before lighting, and caches the resulting paired atlas material. The source
  images remain separate. Riverbanks keep the undecorated ground artwork.

Edit roof art under `tileset/`, then rebuild the derived roof texture and mesh.
Opaque source roof pixels and their UV locations are unchanged by the export;
RGB is extended only outside the roof mask to prevent filtering fringes.
Each `buildings/<name>.png` is an exact copy of the original tile artwork,
including transparency and shadows, for inspection beside `<name>.glb`.
The processed RGB roof texture is embedded in the GLB; its offline input is
under `tools/board-models/roofs`. Edit the facade originals under
`textures/buildings/full-resolution/` to change windows/walls. Edit
`tools/building-footprints.json` between preparation
and export to author a silhouette manually.

Models are indexed GLB with positions, flat normals, vertex colors and UVs.
The importer converts glTF Y-up and linear colors back to the board convention.
In the runtime representation Z is up; X/Y use the 84 by 72 pixel hex dimensions.
Plants preserve their original proportions at local height 30. Buildings,
including tanks and industrial structures, stand at Z=0 with their roof at
Z=18: one default board level, visible at useful proportions in ordinary GLB
viewers. Placement fits their actual bounds to the game's feature height;
interior floors/columns share the shell's coordinates and placement. Wall UVs
and facade repetition remain independent of these authored coordinates.
Crops retain their legacy height-one convention. Bridge decks, kerbs and trusses
are generated and cached at runtime by `BoardBridgeMesh` and `BoardBridgeTruss`.
Their outlines follow the shared road footprint and the actual railway routes
on the deck. Kerbs and trusses follow the outside of the joined deck and leave
connected exits open. Five- and six-way road junctions retain their roundabout
islands; railway junctions have clear centres. No per-pattern span GLBs are used.
The runtime places each span at the bridge elevation plus the road surface
clearance. Board scale applies uniformly; terrain-level height affects only
elevation, never slab thickness or rail height.
The deck uses shared road asphalt and the road's normal/surface maps, lighting
and world-space texture phase. Sides and underside use shared repeating concrete.

Two concrete kits complete the deck; each is a set of root meshes named `<part>-lod0`/`-lod1`, outside
`manifest.json`. `bridge-terminal.glb` is the bank end block. `bridges/bridge-pier.glb` is the hammerhead
pier that stands under a deck joint, on the edge two bridge hexes share, never at a hex centre (56 triangles
at LOD0, 40 at LOD1). Its origin is the edge midpoint; X runs along the edge (across the deck), Y along the
deck. Three parts keep the pier undistorted at any height: `bridge-pier-cap` (17 by 9, Z=0 at the deck
underside, top 0.75 up inside the slab, tapered soffit at Z=-6), `bridge-pier-shaft` (11 by 8 with chamfered
corners, unit height Z=0..1, no end faces; stretched between footing and cap) and `bridge-pier-footing`
(16 by 13, Z=0 at the floor, a 1-unit lip, buried 6). The runtime (`BoardBridgeFooting`) places one pier under
each joint of a bridge whose Pillars toggle is on: each of the two hexes builds the half on its own side of the
edge, cut at the kit's mirror plane and closed by its section there, so the pier must stay mirror-symmetric in X
and Y and each part convex. `bridges/maglev-pier.glb` is the same kit for the elevated maglev's pillars, from the
same generator (`python tools/build_bridge_pier.py --profile maglev`), with parts named `maglev-pier-*`: cap 6 by
4 under the 4 wide beam (soffit at Z=-2.5), shaft 3.2 square, footing 7 by 7 (a 0.6 lip, buried 4). The same
runtime code places it: one pier on each shared edge of two hexes of a maglev route whose Pillars toggle is on (the
marker's `"pillars": true`, set for the whole connected route), from below the floor up to the beam's underside, and
none where the beam is less than a level up or a road, ground rail or bridge deck crosses the edge beneath.

Bridge spans need no asset bake. Rebuild the retained detail kits in mm-data with
`python tools/build_bridge_terminal.py` or `python tools/build_bridge_pier.py`;
add `--profile maglev` for the maglev pier. Add `--check` to validate a shipped
kit without changing it. The main board-asset builder also rebuilds the bridge
terminal and pier kits.

Textures and meshes are shared;
translucency changes instance materials, not the assets. Snow trees have their
own snow materials, as variants of the bare tree where it shares their shape.
Rough terrain places the shared GLB rock templates in its terrain mesh.
Ground image normal maps remain a separate surface detail. `normals/` mirrors ground image paths
under `tileset/`, appending `.png` to the complete source name (including its
original extension and any crop). `normal-manifest.json` records dimensions,
strength and source pixel hashes. Runtime selects each map through the chosen
albedo image and composites both in the same order, then packs aligned atlases.
No height estimation or normal-map generation runs in the game. Missing maps
for custom art fall back to flat shading until they are prepared.

`tools/prepare_board_normals.py` smooths alpha-weighted image brightness and
bakes constant normals over alternating 4-pixel triangles. Painted brightness
is only an approximation to height; baked highlights can also produce relief.
Rubble/rough use the strongest relief, rocky themes are next, and grass, dirt,
sand, snow, mud/swamp, tundra, fields and ice use gentler detail. Pavement and
paved roads receive neutral maps, including their opaque coverage over grass.
South-edge cliff-top patches use restrained relief at strength 3. Their alpha
masks control both color and normal coverage; reoriented normal mapping retains
the base relief under the rim. These derived maps retain the same limitation as
other painted sources: authored height/normal maps would give more accurate
relief. Missing custom rim normals preserve the base normal map.
F9 opens Tuning, where the Normal maps checkbox switches this shading live.
It starts enabled, and Defaults re-enables it; switching needs no atlas,
geometry or shadow rebuild.
Animated water keeps its separate rendering. These maps affect ground lighting
and bank slopes, not silhouettes, picking, movement or cast-shadow geometry.

## Rebuild

Run from the mm-data root (Python requires Pillow and NumPy):

```text
python tools/copy_board_tileset.py
python tools/build_terrain_materials.py
python tools/prepare_terrain_contact.py
python tools/prepare_terrain_contact.py --check
python tools/prepare_board_textures.py
python tools/prepare_cliff_materials.py
python tools/prepare_cliff_materials.py --check
python tools/test_cliff_materials.py
python tools/prepare_board_normals.py
python tools/prepare_board_normals.py --check
python tools/test_board_normals.py
python tools/prepare_building_footprints.py
blender --background tools/board-assets.blend --python tools/build_saxarba_buildings.py
blender --background tools/board-assets.blend --python tools/build_board_assets.py
python tools/validate_board_assets.py
```

The copy step copies missing files only; it preserves local 3D artwork edits.
It repairs two pre-existing fungus image-path typos in the copy only.
Preparation follows actual building, fuel-tank and industrial entries in the
independent include tree. Family selection lives in `facade_family` in the
preparation script; it recognizes named fortress/hangar/sealed families before
ordinary construction strength, including reinforced SMV structures.
Blender uses constrained triangulation for the simplified roof outlines,
exports runtime files, and saves editable object libraries at
`tools/saxarba-buildings.blend` and `tools/board-assets.blend`.
Use Blender's Append command to load their objects. The source scripts create
their own scenes and do not replace the user's open scene.

`build_board_assets.py` rebuilds bridges and crops while preserving the other
manifest entries. It no longer imports or regenerates the legacy low-poly trees.
Edit the maintained tree GLBs directly. To refresh their impostors, run
`python tools/merge_snow_trees.py split`, then
`blender --background --factory-startup --python tools/prepare_tree_lods.py -- impostors`,
then `python tools/merge_snow_trees.py merge`. The bake preserves the three mesh
levels, owns a temporary Blender scene and preserves the active scene. Its shared
branch-card helpers remain available to the shrub, orchard and volcanic generators.

Validation checks all 3,319 base models and 66 tree detail meshes, their budgets and texture dependencies, structure
roof winding, unchanged opaque roof pixels, facade assignments, small runtime
texture dimensions, preserved source resolution, and independent copied files.
Native Java integration tests additionally check transparency, lighting,
water animation and representative model loading.

## Provenance

Roof/terrain/water art comes from the existing MegaMek data tileset; its license
headers and original paths are retained. The repository license remains at
`../../../LICENSE`.

Trees are simplified derivatives of Quaternius's **Ultimate Nature
Pack (June 2019)**: `CommonTree_1/2/4`, `CommonTree_Dead_2`, `PineTree_1/2/3`,
`BirchTree_2`, `Willow_2`, their corresponding snow models, `PalmTree_1/2`,
`Cactus_2` and `CactusFlowers_2`. The supplied CC0 notice is preserved
in `QUATERNIUS-LICENSE.txt`.

Bridge models are baked from the shared road outlines; crop models are authored with the Blender script.
Dirt, sandstone, rock, concrete and windowed facade albedos were generated with
the built-in image_gen tool; exact prompts are in
`../../../tools/board-texture-prompts.json`. The seven contextual facade prompts
are in `../../../tools/building-texture-prompts.json`; these also used built-in
image_gen. Bed and rim art also use built-in image_gen; their prompts and
references are in `../../../tools/board-rim-texture-prompts.json`. Only the
128 by 128 runtime maps are shipped. The rim maps are pale detail albedos;
their final theme colors come from the hex artwork, and geometry supplies
their uneven lower silhouette.

## Plant GLB packaging

Each of the 22 plant variants has one GLB, for example `pine.glb`, containing
identity groups `pine-lod0`, `pine-lod1`, `pine-lod2` and the impostor `pine-lod3`. Their authored geometry,
UVs and material roles are preserved. The runtime chooses one level and resolves
missing optional levels toward LOD0 once while loading. Foliage PNGs remain
external under `textures/foliage`, shared by all variants and levels.
All levels have natural proportions and a base at zero, including when inspected
in an ordinary GLB viewer. Export and LOD preparation never flatten the height.
LOD coverage checks compare the shipped near mesh with its coarser levels.

## Building GLBs and textures

All 3,295 Saxarba buildings now use one GLB each, with an identity
`<building>-lod0` group. Each embeds its dedicated roof PNG without changing
the image bytes, and uses a relative URI for one of eight shared facade PNGs.
Roof and wall are separate material groups, not two layers over the same mesh.
Runtime wall materials still scale vertical UVs with building height; `shell`
materials retain full-height UVs. Roof samplers clamp; facade samplers repeat.

`RigidGlb` supports embedded PNG/JPEG diffuse images and local image references.
`ModelTextures` caches images with their sampler state, releases native pixels
after upload, retains encoded bytes for context restoration and gives texture
disposal to the owning asset library. Unit and plant models use the same path.
Only the roof belongs inside each building package; the facade stays shared.
Each building keeps `<building>.png` beside `<building>.glb`: a byte-for-byte
copy of its original tileset image, retaining alpha and shadows. This is for
inspection and is not a runtime texture dependency. The processed roof PNG
stays embedded, with no loose `*-roof.png` under deployed buildings. The
footprint tool copies the original sibling and prepares the filtering-safe
RGB roof under `tools/board-models/roofs`; the exporter embeds that prepared
image. Validation checks the original sibling against its source and the
embedded roof against the source's opaque pixels. There is no measured
runtime performance gain claimed from embedding.

`field.glb` also contains a single LOD0 group. No G3DJ remains
under deployed `data/` or authoring/reference `tools/`. The 475 former tool
meshes also use GLB, including seven empty squad references. Before the runtime
bridge migration, all 4,056 deployed GLBs passed Khronos validation with zero
errors. The obsolete span files have since been removed.

See the glTF image specification:
https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#images
