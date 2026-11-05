"""
Builds the "Custom Moonglade Marsh" Catharsis resource pack.

Usage:
    python -I tools/build_pack.py <vanilla_assets_dir> [output_dir]

<vanilla_assets_dir> must contain assets/minecraft/{blockstates,models,textures}
extracted from the 26.2 client jar (vanilla textures are recoloured, not shipped
as-is).

Everything is scoped with Catharsis conditions:
  * island-wide changes only apply on Galatea (locraw mode "foraging_2",
    which skyblock-api names "Moonglade Marsh")
  * tree changes only apply inside Catharsis' built-in repo areas
    catharsis:galatea/fig and catharsis:galatea/mangrove
so the pack never touches any other island.
"""
import json
import os
import shutil
import sys
import time
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sky_time import evaluate as evaluate_sky  # noqa: E402

PACK_ID = "moonglade_marsh"
NS = "moonglade_marsh"            # shared virtual states / models / textures
NS_FIG = "moonglade_marsh_fig"    # block replacements for fig trees
NS_MANG = "moonglade_marsh_mangrove"  # block replacements for mangrove trees
NS_GROUND = "moonglade_marsh_ground"  # block replacements for island-wide ground/foliage
ISLAND = "foraging_2"
# Padded copies of Catharsis' repo areas catharsis:galatea/{fig,mangrove}.
# The repo boxes are tight and cut through canopies/branches at their edges.
AREA_FIG = f"{NS}:fig_trees"
AREA_MANG = f"{NS}:mangrove_trees"
AREA_PAD = (4, 3, 4)  # horizontal, down, up
# Leaf blocks that belong to one tree type. These are recoloured island-wide
# (no area check), so whole canopies change even outside the area boxes.
FIG_LEAF_TYPES = {"azalea_leaves", "flowering_azalea_leaves"}
MANG_LEAF_TYPES = {"mangrove_leaves"}
REPO_AREAS = os.path.join(os.environ.get("APPDATA", ""), ".minecraft", "catharsis-repo-cache", "areas", "galatea")
VERSION = "1.1.0"
PACK_NAME = ("§cC§bu§as§dt§6o§2m §2Moonglade Marsh §fv"
             + ".".join(VERSION.split(".")[:2]))

# --------------------------------------------------------------------------- data

WOODS = [  # value, label, chat colour
    ("oak", "Oak", "gold"),
    ("birch", "Birch", "white"),
    ("spruce", "Spruce", "dark_red"),
    ("dark_oak", "Dark Oak", "dark_gray"),
    ("jungle", "Jungle", "yellow"),
    ("acacia", "Acacia", "gold"),
    ("mangrove", "Mangrove", "dark_red"),
    ("warped", "Warped", "dark_aqua"),
    ("crimson", "Crimson", "red"),
    ("pale_oak", "Pale Oak", "gray"),
    ("cherry", "Cherry", "light_purple"),
]


def wood_blocks(w):
    """log, wood, stripped log, stripped wood block ids for a wood type."""
    if w in ("warped", "crimson"):
        return (f"{w}_stem", f"{w}_hyphae", f"stripped_{w}_stem", f"stripped_{w}_hyphae")
    return (f"{w}_log", f"{w}_wood", f"stripped_{w}_log", f"stripped_{w}_wood")


COLORS = [  # value, label, chat colour, tint rgb
    ("red", "Red", "red", (205, 52, 46)),
    ("orange", "Orange", "gold", (232, 128, 34)),
    ("yellow", "Yellow", "yellow", (236, 200, 40)),
    ("lime", "Lime", "green", (128, 208, 56)),
    ("green", "Green", "dark_green", (62, 150, 58)),
    ("teal", "Swamp Teal", "dark_aqua", (38, 150, 130)),
    ("light_blue", "Light Blue", "aqua", (104, 182, 232)),
    ("blue", "Blue", "blue", (58, 92, 206)),
    ("pink", "Pink", "light_purple", (240, 124, 176)),
    ("purple", "Purple", "dark_purple", (144, 72, 196)),
    ("white", "White", "white", (236, 236, 236)),
    ("grey", "Grey", "gray", (132, 132, 132)),
    ("black", "Black", "dark_gray", (58, 58, 64)),
]

# Every leaf block that could make up a fig / mangrove canopy. Only blocks
# inside the tree areas are affected, so covering extra types is harmless.
LEAVES = ["oak_leaves", "spruce_leaves", "birch_leaves", "jungle_leaves", "acacia_leaves",
          "dark_oak_leaves", "mangrove_leaves", "cherry_leaves", "azalea_leaves",
          "flowering_azalea_leaves", "pale_oak_leaves"]

GRASS_BLOCKS = ["grass_block", "vine"]                      # follow grass colour
FOLIAGE = ["short_grass", "tall_grass", "fern", "large_fern"]  # follow grass colour, can hide
LILY = ["lily_pad"]
# Other greenery that follows the grass colour when "Vegetation Follows Grass Color" is on.
VEGETATION = ["moss_block", "moss_carpet", "cave_vines", "cave_vines_plant", "azalea", "flowering_azalea",
              "big_dripleaf", "big_dripleaf_stem", "small_dripleaf", "seagrass", "tall_seagrass", "kelp",
              "kelp_plant", "sugar_cane", "mangrove_propagule", "sea_pickle", "sweet_berry_bush", "bush",
              "firefly_bush",
              "green_terracotta"]  # olive ground/path borders on the island
PATH = ["dirt_path"]  # the yellow walkways; recoloured by "Path Color"
# Bush / hedge leaves outside the tree areas also follow the grass colour.
OTHER_LEAVES = [l for l in LEAVES if l not in FIG_LEAF_TYPES | MANG_LEAF_TYPES]
# Catharsis tries replacement files in namespace order (vanilla resource stacks are a TreeMap),
# so this must sort after NS_FIG / NS_MANG for tree leaf colours to win inside tree areas.
NS_VEG = "moonglade_marsh_vegetation"
AREA_ISLAND = f"{NS}:island"  # always just Moonglade Marsh (unlike AREA_SKY)

AREA_SKY = f"{NS}:sky_scope"  # redefined by the "time_scope_all_skyblock" overlay
# Every SkyBlockIsland id known to skyblock-api 4.2.25 (as used by Catharsis beta.22).
ALL_SKYBLOCK_ISLANDS = [
    "dynamic", "hub", "dungeon_hub", "farming_1", "foraging_1", "mining_1", "mining_2", "mining_3",
    "crystal_hollows", "mineshaft", "combat_1", "combat_3", "crimson_isle", "garden", "fishing_1",
    "lotus_atoll", "foraging_2", "foraging_3", "safari", "rift", "dark_auction", "dungeon", "kuudra",
    "winter",
]
TIME_SCOPES = [  # value, label, colour, islands
    ("moonglade_marsh", "Moonglade Marsh Only", "dark_green", [ISLAND]),
    ("all_skyblock", "All of SkyBlock", "gold", ALL_SKYBLOCK_ISLANDS),
]
TIMES = [  # value, label, colour, overworld tick whose sky is locked in (None = server time)
    ("default", "Server Time", "gray", None),
    ("sunrise", "Sunrise", "gold", 23300),
    ("day", "Day", "yellow", 6000),
    ("sunset", "Sunset", "red", 12700),
    ("night", "Night", "dark_blue", 18000),
]

MUD = [  # value, label, colour, vanilla block used
    ("mud", "Mud", "dark_gray", None),
    ("packed_mud", "Packed Mud", "gold", "packed_mud"),
    ("mud_bricks", "Mud Bricks", "gold", "mud_bricks"),
    ("dirt", "Dirt", "gold", "dirt"),
    ("coarse_dirt", "Coarse Dirt", "gold", "coarse_dirt"),
    ("moss_block", "Moss", "green", "moss_block"),
    ("rooted_dirt", "Rooted Dirt", "gold", "rooted_dirt"),
]

# --------------------------------------------------------------------------- io helpers

VAN = None
OUT = None


def wjson(path, obj):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def vjson(kind, name):
    with open(os.path.join(VAN, "assets", "minecraft", kind, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def strip_ns(ref):
    ref = ref.split(":", 1)[1] if ":" in ref else ref
    return ref


def text(t, color, bold=False):
    d = {"text": t, "color": color}
    if bold:
        d["bold"] = True
    return d


def desc(t):
    return {"text": "", "extra": [{"text": t, "color": "gray", "italic": True}]}


def cfg(id_, value=None):
    c = {"condition": "catharsis:config", "pack": PACK_ID, "id": id_}
    if value is not None:
        c["value"] = value
    return c


def c_not(c):
    return {"condition": "fabric:not", "value": c}


def c_and(*cs):
    return {"condition": "fabric:and", "values": list(cs)}


def on_island(definition):
    return {"type": "conditional", "condition": {"type": "in_island", "island": ISLAND},
            "definition": definition}


def redirect(vs):
    return {"type": "redirect", "virtual_state": vs}


def in_area(area, vs):
    return on_island({"type": "per_area", "entries": {area: redirect(vs)}})


# --------------------------------------------------------------------------- models

def resolve_model(ref):
    """Flatten a vanilla block model: returns (textures, elements, ambientocclusion)."""
    textures, elements, ao = {}, None, None
    chain = []
    name = strip_ns(ref)
    while name:
        m = vjson("models", name)
        chain.append(m)
        name = strip_ns(m["parent"]) if "parent" in m else None
    for m in reversed(chain):  # root first, child overrides
        textures.update(m.get("textures", {}))
        if "elements" in m:
            elements = m["elements"]
        if "ambientocclusion" in m:
            ao = m["ambientocclusion"]

    def res(v, depth=0):
        while v.startswith("#") and depth < 16:
            v = textures.get(v[1:], v)
            depth += 1
        return v
    textures = {k: res(v) for k, v in textures.items()}
    return textures, json.loads(json.dumps(elements or [])), ao


def tinted_texture_keys(elements):
    keys = set()
    for e in elements:
        for face in e.get("faces", {}).values():
            if "tintindex" in face:
                keys.add(face["texture"].lstrip("#"))
    return keys


# --------------------------------------------------------------------------- textures

_tex_done = set()


def tint_image(src_name, rgb):
    im = Image.open(os.path.join(VAN, "assets", "minecraft", "textures", "block", src_name + ".png")).convert("RGBA")
    px = im.load()
    lum = []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a > 0:
                lum.append(0.299 * r + 0.587 * g + 0.114 * b)
    mean = (sum(lum) / len(lum)) if lum else 128.0
    out = Image.new("RGBA", im.size)
    op = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            l = (0.299 * r + 0.587 * g + 0.114 * b) / mean  # ~1.0 on average
            f = max(0.0, min(1.45, 0.92 * l))
            op[x, y] = tuple(max(0, min(255, int(c * f))) for c in rgb) + (a,)
    return out


def write_tinted(src_ref, color, rgb):
    """Write a recoloured copy of a vanilla block texture; returns its id."""
    src = strip_ns(src_ref).split("/", 1)[1]  # block/xxx -> xxx
    tid = f"{NS}:block/tint/{color}/{src}"
    if tid in _tex_done:
        return tid
    _tex_done.add(tid)
    path = os.path.join(OUT, "assets", NS, "textures", "block", "tint", color, src + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tint_image(src, rgb).save(path)
    meta = os.path.join(VAN, "assets", "minecraft", "textures", "block", src + ".png.mcmeta")
    if os.path.exists(meta):
        shutil.copyfile(meta, path + ".mcmeta")
    return tid


def write_grass_side(color, rgb):
    """Dirt side with the recoloured grass fringe baked in (no tint needed)."""
    tid = f"{NS}:block/tint/{color}/grass_block_side"
    if tid in _tex_done:
        return tid
    _tex_done.add(tid)
    tb = os.path.join(VAN, "assets", "minecraft", "textures", "block")
    side = Image.open(os.path.join(tb, "grass_block_side.png")).convert("RGBA")
    overlay = Image.open(os.path.join(tb, "grass_block_side_overlay.png")).convert("RGBA")
    ov = overlay.load()
    sp = side.load()
    for y in range(side.height):
        for x in range(side.width):
            r, g, b, a = ov[x, y]
            if a > 0:
                f = max(0.0, min(1.45, 0.92 * (r / 150.0)))
                sp[x, y] = tuple(max(0, min(255, int(c * f))) for c in rgb) + (255,)
    path = os.path.join(OUT, "assets", NS, "textures", "block", "tint", color, "grass_block_side.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    side.save(path)
    return tid


# --------------------------------------------------------------------------- virtual states

def tinted_virtual_state(block, color, rgb, tint_all=False):
    """Copy a vanilla blockstate, pointing every model at an untinted recoloured clone."""
    bs = vjson("blockstates", block)
    made = {}

    def model_for(ref):
        if ref in made:
            return made[ref]
        name = strip_ns(ref).split("/", 1)[1]
        mid = f"{NS}:block/tint/{color}/{name}"
        made[ref] = mid
        if name == "grass_block_snow":  # snowy grass keeps vanilla look
            made[ref] = ref
            return ref
        textures, elements, ao = resolve_model(ref)
        keys = set(textures) if tint_all else tinted_texture_keys(elements)
        tinted_values = {textures[k] for k in keys if k in textures}
        new_tex = {}
        for k, v in textures.items():
            if name == "grass_block" and k == "side":
                new_tex[k] = write_grass_side(color, rgb)
            elif v in tinted_values:
                new_tex[k] = write_tinted(v, color, rgb)
            else:
                new_tex[k] = v if ":" in v else "minecraft:" + v
        for e in elements:
            for face in e.get("faces", {}).values():
                face.pop("tintindex", None)
        if name == "grass_block":  # fringe is baked into the side texture
            elements = elements[:1]
        model = {"textures": new_tex, "elements": elements}
        if ao is not None:
            model = {"ambientocclusion": ao, **model}
        wjson(f"assets/{NS}/models/block/tint/{color}/{name}.json", model)
        return mid

    def remap(entry):
        if isinstance(entry, list):
            return [remap(e) for e in entry]
        e = dict(entry)
        e["model"] = model_for(e["model"])
        return e

    if "variants" in bs:
        out = {"variants": {k: remap(v) for k, v in bs["variants"].items()}}
    else:
        out = {"multipart": [{**p, "apply": remap(p["apply"])} for p in bs["multipart"]]}
    vs = f"{NS}:tint/{color}/{block}"
    wjson(f"assets/{NS}/catharsis/virtual_block_states/tint/{color}/{block}.json", out)
    return vs


def vanilla_virtual_state(block):
    vs = f"{NS}:vanilla/{block}"
    wjson(f"assets/{NS}/catharsis/virtual_block_states/vanilla/{block}.json", vjson("blockstates", block))
    return vs


# --------------------------------------------------------------------------- build

def build():
    os.makedirs(OUT, exist_ok=True)

    def retry(func, path, _exc):  # Windows: editors/indexers briefly lock files
        for _ in range(20):
            time.sleep(0.25)
            try:
                func(path)
                return
            except OSError:
                pass
        raise

    for entry in os.listdir(OUT):  # empty it (the folder itself may be in use)
        p = os.path.join(OUT, entry)
        if os.path.isdir(p):
            shutil.rmtree(p, onexc=retry)
        else:
            try:
                os.remove(p)
            except OSError as e:
                retry(os.remove, p, e)
    overlays = []

    # padded tree areas
    h, dn, up = AREA_PAD
    for src, area in (("fig", AREA_FIG), ("mangrove", AREA_MANG)):
        with open(os.path.join(REPO_AREAS, src + ".json"), encoding="utf-8") as f:
            repo = json.load(f)
        boxes = []
        for b in repo["boxes"]:
            mn = [int(v) for v in b["min"].split(":")]
            mx = [int(v) for v in b["max"].split(":")]
            boxes.append({"min": f"{mn[0] - h}:{mn[1] - dn}:{mn[2] - h}",
                          "max": f"{mx[0] + h}:{mx[1] + up}:{mx[2] + h}"})
        wjson(f"assets/{NS}/catharsis/areas/{area.split(':', 1)[1]}.json",
              {"_comment": f"catharsis:galatea/{src} padded by {AREA_PAD} (h, down, up)",
               "type": "multiple", "islands": ISLAND, "boxes": boxes})

    # shared invisible state
    wjson(f"assets/{NS}/models/block/invisible.json", {"elements": []})
    wjson(f"assets/{NS}/catharsis/virtual_block_states/invisible.json",
          {"variants": {"": {"model": f"{NS}:block/invisible"}}})
    invisible = f"{NS}:invisible"

    # wood virtual states (straight copies of vanilla blockstates)
    for w, _, _ in WOODS:
        for b in wood_blocks(w):
            vanilla_virtual_state(b)

    # ---- fig / mangrove wood
    for tree, ns, area, default, src_wood in (
            ("fig", NS_FIG, AREA_FIG, "spruce", "spruce"),
            ("mangrove", NS_MANG, AREA_MANG, "mangrove", "mangrove")):
        for w, _, _ in WOODS:
            if w == default:
                continue
            d = f"{tree}_wood_as_{w}"
            for src, dst in zip(wood_blocks(src_wood), wood_blocks(w)):
                wjson(f"{d}/assets/{ns}/catharsis/block_replacements/minecraft/{src}.json",
                      in_area(area, f"{NS}:vanilla/{dst}"))
            overlays.append({"directory": d, "condition": cfg(f"{tree}_wood_type", w)})

    # ---- fig / mangrove leaves
    for color, _, _, rgb in COLORS:
        for leaf in LEAVES:
            tinted_virtual_state(leaf, color, rgb, tint_all=True)
    for tree, ns, area, own, other in (("fig", NS_FIG, AREA_FIG, FIG_LEAF_TYPES, MANG_LEAF_TYPES),
                                       ("mangrove", NS_MANG, AREA_MANG, MANG_LEAF_TYPES, FIG_LEAF_TYPES)):
        for color, _, _, _ in COLORS:
            d = f"{tree}_leaves_{color}"
            for leaf in LEAVES:
                if leaf in other:
                    continue  # owned by the other tree type
                vs = f"{NS}:tint/{color}/{leaf}"
                rule = on_island(redirect(vs)) if leaf in own else in_area(area, vs)
                wjson(f"{d}/assets/{ns}/catharsis/block_replacements/minecraft/{leaf}.json", rule)
            overlays.append({"directory": d, "condition": cfg(f"{tree}_leaf_color", color)})

    # ---- island-wide grass colour
    for color, _, _, rgb in COLORS:
        for b in GRASS_BLOCKS + FOLIAGE + LILY:
            tinted_virtual_state(b, color, rgb)
        groups = (
            (f"grass_color_{color}", GRASS_BLOCKS, cfg("grass_color", color)),
            (f"foliage_color_{color}", FOLIAGE,
             c_and(cfg("grass_color", color), c_not(cfg("hide_foliage")))),
            (f"lily_pad_color_{color}", LILY,
             c_and(cfg("grass_color", color), c_not(cfg("hide_lily_pads")))),
        )
        for d, blocks, cond in groups:
            for b in blocks:
                wjson(f"{d}/assets/{NS_GROUND}/catharsis/block_replacements/minecraft/{b}.json",
                      on_island(redirect(f"{NS}:tint/{color}/{b}")))
            overlays.append({"directory": d, "condition": cond})

    # ---- vegetation + bush leaves follow the grass colour
    for leaf in OTHER_LEAVES:
        vanilla_virtual_state(leaf)
    for color, _, _, rgb in COLORS:
        d = f"vegetation_color_{color}"
        for b in VEGETATION:
            vs = tinted_virtual_state(b, color, rgb, tint_all=True)
            wjson(f"{d}/assets/{NS_VEG}/catharsis/block_replacements/minecraft/{b}.json",
                  on_island(redirect(vs)))
        for leaf in OTHER_LEAVES:
            # inside tree areas keep the vanilla leaf (tree colour rules sort first and win
            # when a tree colour is chosen); everywhere else use the grass colour
            wjson(f"{d}/assets/{NS_VEG}/catharsis/block_replacements/minecraft/{leaf}.json",
                  on_island({"type": "select",
                             "definitions": [{"type": "per_area", "entries": {
                                 AREA_FIG: redirect(f"{NS}:vanilla/{leaf}"),
                                 AREA_MANG: redirect(f"{NS}:vanilla/{leaf}")}}],
                             "fallback": redirect(f"{NS}:tint/{color}/{leaf}")}))
        overlays.append({"directory": d,
                         "condition": c_and(cfg("grass_color", color), cfg("vegetation_follows_grass"))})

    # ---- path colour
    for color, _, _, rgb in COLORS:
        d = f"path_color_{color}"
        for b in PATH:
            vs = tinted_virtual_state(b, color, rgb, tint_all=True)
            wjson(f"{d}/assets/{NS_GROUND}/catharsis/block_replacements/minecraft/{b}.json",
                  on_island(redirect(vs)))
        overlays.append({"directory": d, "condition": cfg("path_color", color)})

    # ---- water colour (biome effect)
    wjson(f"assets/{NS}/catharsis/areas/{AREA_ISLAND.split(':', 1)[1]}.json",
          {"type": "on_island", "islands": [ISLAND]})
    for color, _, _, rgb in COLORS:
        d = f"water_color_{color}"
        wjson(f"{d}/assets/{NS}/catharsis/environment_modifier/water_color.json", {
            "type": "biome_effect", "effect": "water_color",
            "condition": {"type": "in_area", "area": AREA_ISLAND},
            "provider": {"type": "override", "value": (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]},
        })
        overlays.append({"directory": d, "condition": cfg("water_color", color)})

    # ---- hide clutter
    for d, blocks, opt in (("hide_foliage", FOLIAGE, "hide_foliage"),
                           ("hide_lily_pads", LILY, "hide_lily_pads")):
        for b in blocks:
            wjson(f"{d}/assets/{NS_GROUND}/catharsis/block_replacements/minecraft/{b}.json",
                  on_island(redirect(invisible)))
        overlays.append({"directory": d, "condition": cfg(opt)})

    # ---- mud swap
    for v, _, _, block in MUD:
        if block is None:
            continue
        d = f"mud_as_{v}"
        vanilla_virtual_state(block)
        wjson(f"{d}/assets/{NS_GROUND}/catharsis/block_replacements/minecraft/mud.json",
              on_island(redirect(f"{NS}:vanilla/{block}")))
        overlays.append({"directory": d, "condition": cfg("mud_type", v)})

    # ---- time of day (client-side sky lock via Catharsis environment modifiers)
    sky_area_path = f"assets/{NS}/catharsis/areas/{AREA_SKY.split(':', 1)[1]}.json"
    for i, (v, _, _, islands) in enumerate(TIME_SCOPES):
        area = {"type": "on_island", "islands": islands}
        if i == 0:
            wjson(sky_area_path, area)  # default scope lives in the base pack
        else:
            d = f"time_scope_{v}"
            wjson(f"{d}/{sky_area_path}", area)
            overlays.append({"directory": d, "condition": cfg("time_scope", v)})
    for v, _, _, tick in TIMES:
        if tick is None:
            continue
        d = f"time_{v}"
        values = evaluate_sky(VAN, tick)
        wjson(f"{d}/assets/{NS}/catharsis/environment_modifier/time_of_day.json", {
            "type": "composite",
            "condition": {"type": "in_area", "area": AREA_SKY},
            "modifiers": [{"type": "environmental_attribute", "attribute": attr,
                           "provider": {"type": "override", "value": val}}
                          for attr, val in values.items()],
        })
        overlays.append({"directory": d, "condition": cfg("time_of_day", v)})

    # ---- pack.mcmeta
    def wood_dropdown(id_, default):
        return {"type": "dropdown", "id": id_, "title": "Wood Type",
                "description": desc("Changes the log, wood, stripped log and stripped wood blocks "
                                    "used by these trees. Only affects blocks inside the tree areas."),
                "options": [dict({"value": v, "text": text(l, c)}, **({"default": True} if v == default else {}))
                            for v, l, c in WOODS]}

    def color_dropdown(id_, title, what):
        opts = [{"value": "default", "text": text("Default", "gray"), "default": True}]
        opts += [{"value": v, "text": text(l, c)} for v, l, c, _ in COLORS]
        return {"type": "dropdown", "id": id_, "title": title, "description": desc(what), "options": opts}

    options = [
        {"type": "separator", "title": text("Fig Trees", "gold", True)},
        wood_dropdown("fig_wood_type", "spruce"),
        color_dropdown("fig_leaf_color", "Leaf Color", "Recolors the canopy of every fig tree."),
        {"type": "separator", "title": text("Mangrove Trees", "dark_red", True)},
        wood_dropdown("mangrove_wood_type", "mangrove"),
        color_dropdown("mangrove_leaf_color", "Leaf Color", "Recolors the canopy of every mangrove tree."),
        {"type": "separator", "title": text("Grass Color", "dark_green", True)},
        color_dropdown("grass_color", "Grass Color",
                       "Recolors grass blocks, grass, ferns, vines and lily pads across Moonglade Marsh."),
        {"type": "boolean", "id": "vegetation_follows_grass", "title": "Vegetation Follows Grass Color",
         "description": desc("Also recolors moss, cave vines, azalea bushes, dripleaf, seagrass, kelp, "
                             "sugar cane, propagules, olive ground blocks and hedge leaves outside the "
                             "trees, so the whole "
                             "marsh matches the grass color."),
         "default": True},
        color_dropdown("water_color", "Water Color", "Recolors water on Moonglade Marsh."),
        {"type": "separator", "title": text("Marsh Clutter", "dark_aqua", True)},
        {"type": "boolean", "id": "hide_foliage", "title": "Hide Grass & Ferns",
         "description": desc("Hides short grass, tall grass, ferns and large ferns so logs are easier to see."),
         "default": False},
        {"type": "boolean", "id": "hide_lily_pads", "title": "Hide Lily Pads",
         "description": desc("Makes lily pads invisible. Their hitbox still exists."), "default": False},
        {"type": "separator", "title": text("Time of Day", "aqua", True)},
        {"type": "dropdown", "id": "time_of_day", "title": "Sky",
         "description": desc("Locks the sky, sun, moon, stars and sky lighting to a time of day. "
                             "Client-side only; the server time and mob behaviour are unchanged."),
         "options": [dict({"value": v, "text": text(l, c)}, **({"default": True} if t is None else {}))
                     for v, l, c, t in TIMES]},
        {"type": "dropdown", "id": "time_scope", "title": "Sky Applies To",
         "description": desc("Where the chosen sky is used: only on Moonglade Marsh, or on every "
                             "SkyBlock island (hub, dungeons, Garden, Rift, ...)."),
         "options": [dict({"value": v, "text": text(l, c)}, **({"default": True} if i == 0 else {}))
                     for i, (v, l, c, _) in enumerate(TIME_SCOPES)]},
        {"type": "separator", "title": text("Ground", "gray", True)},
        color_dropdown("path_color", "Path Color", "Recolors the dirt paths that run across Moonglade Marsh."),
        {"type": "dropdown", "id": "mud_type", "title": "Mud Texture",
         "description": desc("Replaces mud blocks on the island."),
         "options": [dict({"value": v, "text": text(l, c)}, **({"default": True} if block is None else {}))
                     for v, l, c, block in MUD]},
    ]
    mcmeta = {
        "pack": {
            "description": "§7Recolors Moonglade Marsh.\n§4Requires: Catharsis",
            "min_format": [84, 0],
            "max_format": [2147483647, 0],
        },
        "catharsis:pack/v1": {
            "id": PACK_ID,
            "version": VERSION,
            "dependencies": {"catharsis": ">=1.0.0-beta.22"},
            "config": [{"type": "tab", "title": text("Customizable Options", "gold", True), "options": options}],
        },
        "fabric:overlays": {"entries": overlays},
    }
    wjson("pack.mcmeta", mcmeta)
    make_icon()
    return len(overlays)


# --------------------------------------------------------------------------- icon

def make_icon():
    S = 128
    img = Image.new("RGBA", (S, S))
    px = img.load()
    top, bot = (16, 22, 52), (34, 86, 92)
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(S):
            px[x, y] = c
    # crescent moon
    for y in range(S):
        for x in range(S):
            if (x - 92) ** 2 + (y - 28) ** 2 <= 15 ** 2 and (x - 99) ** 2 + (y - 23) ** 2 > 13 ** 2:
                px[x, y] = (238, 236, 206, 255)
    tb = os.path.join(VAN, "assets", "minecraft", "textures", "block")

    def tile(name, gx, gy, rgb=None):  # 12px tiles on a 128px canvas
        t = tint_image(name, rgb) if rgb else Image.open(os.path.join(tb, name + ".png")).convert("RGBA")
        img.alpha_composite(t.resize((12, 12), Image.NEAREST), (gx * 12 - 4, gy * 12 - 4))

    leaf_green, leaf_teal = (70, 160, 62), (40, 158, 134)
    # mangrove tree on the left: canopy, trunk, arching roots
    for gx, gy in ((2, 3), (3, 3), (4, 3), (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (2, 5), (3, 5), (4, 5)):
        tile("mangrove_leaves", gx, gy, leaf_green)
    for gy in (6, 7, 8):
        tile("mangrove_log", 3, gy)
    for gx, gy in ((2, 8), (4, 8), (1, 9), (5, 9)):
        tile("mangrove_log", gx, gy)
    # fig tree on the right: stripped spruce trunk, teal canopy
    for gx, gy in ((7, 5), (8, 5), (9, 5), (6, 6), (7, 6), (8, 6), (9, 6), (10, 6), (7, 7), (8, 7), (9, 7)):
        tile("oak_leaves", gx, gy, leaf_teal)
    for gy in (8, 9):
        tile("stripped_spruce_log", 8, gy)
    # marsh water line with lily pads
    for y in range(110, S):
        for x in range(S):
            r, g, b, a = px[x, y]
            px[x, y] = (int(r * 0.5 + 14), int(g * 0.5 + 58), int(b * 0.5 + 70), 255)
    for gx in (3, 7, 10):
        tile("lily_pad", gx, 10, leaf_green)
    img.save(os.path.join(OUT, "pack.png"))


def main():
    global VAN, OUT
    VAN = os.path.abspath(sys.argv[1])
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(root, "Moonglade Marsh")
    n = build()
    zpath = os.path.join(root, PACK_NAME + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(OUT):
            for f in sorted(fs):
                full = os.path.join(dp, f)
                z.write(full, os.path.relpath(full, OUT).replace(os.sep, "/"))
    count = sum(len(fs) for _, _, fs in os.walk(OUT))
    print(f"overlays={n} files={count} zip={zpath}")


if __name__ == "__main__":
    main()
