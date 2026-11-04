# Custom Moonglade Marsh (Catharsis pack)

A configurable recolour pack for Galatea / Moonglade Marsh in Hypixel SkyBlock (`/locraw` mode `foraging_2`). It requires the [Catharsis](https://modrinth.com/mod/catharsis) mod, version 1.0.0-beta.22 or newer.

## Options
Open the options in-game with `/catharsis config moonglade_marsh`.

| Section | Option | Applies to |
|---|---|---|
| Fig Trees | Wood Type (11 woods, default Spruce) | spruce and stripped spruce logs and wood in the fig tree areas |
| Fig Trees | Leaf Color (Default + 13 colours) | azalea and flowering azalea leaves anywhere on the island, plus other leaf types in the fig tree areas |
| Mangrove Trees | Wood Type (default Mangrove) | mangrove and stripped mangrove logs and wood in the mangrove tree areas |
| Mangrove Trees | Leaf Color | mangrove leaves anywhere on the island, plus other leaf types in the mangrove tree areas |
| Grass Color | Grass Color | grass blocks, short and tall grass, ferns, vines and lily pads |
| Marsh Clutter | Hide Grass & Ferns, Hide Lily Pads | anywhere on the island; hitboxes are unchanged |
| Ground | Mud Texture | mud blocks |

## How it is scoped
- Every replacement is wrapped in an `in_island: foraging_2` condition, so other islands are never affected.
- The tree areas (`moonglade_marsh:fig_trees` and `moonglade_marsh:mangrove_trees`) are Catharsis's built-in `catharsis:galatea/fig` and `catharsis:galatea/mangrove` boxes, widened by 4 blocks on each side, 3 below and 4 above. The original boxes cut through canopies.
- A replacement whose condition fails falls through to the next pack, so other Catharsis packs, such as Torrhus Canyon, keep working.

## Compatibility
The pack has been run on Minecraft 26.2. Catharsis beta.22 also exists for 26.1.x and 26.3, so it should work there, but that is untested.

## Install
Download the pack zip, put it in `.minecraft/resourcepacks`, and enable it.

## Building
The pack in `Moonglade Marsh/` is generated. To rebuild it:

```bash
python -I tools/build_pack.py <dir containing assets/minecraft extracted from the 26.2 client jar>
python -I tools/validate_pack.py "Moonglade Marsh" <same dir>
```

The build needs Python with Pillow. It reads the Galatea tree areas from your local Catharsis repo cache (`%APPDATA%/.minecraft/catharsis-repo-cache/areas/galatea`). The build writes the zip to the repository root; the zip is git-ignored.

## Credits
The textures are recoloured from vanilla Minecraft textures (© Mojang). This project is not affiliated with Hypixel, Mojang or the Catharsis authors.
