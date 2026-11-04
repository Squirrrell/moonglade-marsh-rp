"""
Checks a built pack for broken references.

Usage: python -I tools/validate_pack.py <pack_dir> <vanilla_assets_dir>

Verifies that every redirect virtual_state, every model referenced by a
virtual block state, and every texture referenced by a pack model exists
(either in the pack's base assets or in vanilla), that every overlay
directory exists, and that every config value used by an overlay is a
declared option value.
"""
import json
import os
import sys

pack, van = (os.path.abspath(a) for a in sys.argv[1:3])
errors = []


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def split(ref):
    ns, path = ref.split(":", 1) if ":" in ref else ("minecraft", ref)
    return ns, path


def exists(kind, ref, ext):
    ns, path = split(ref)
    rel = os.path.join("assets", ns, *kind.split("/"), *path.split("/")) + ext
    return os.path.exists(os.path.join(pack, rel)) or os.path.exists(os.path.join(van, rel))


def walk_models(obj, out):
    if isinstance(obj, dict):
        if "model" in obj and isinstance(obj["model"], str):
            out.add(obj["model"])
        for v in obj.values():
            walk_models(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_models(v, out)


def walk_redirects(obj, out):
    if isinstance(obj, dict):
        if obj.get("type") == "redirect":
            out.add(obj["virtual_state"])
        for v in obj.values():
            walk_redirects(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_redirects(v, out)


meta = load(os.path.join(pack, "pack.mcmeta"))
opts = {}
for tab in meta["catharsis:pack/v1"]["config"]:
    for o in tab["options"]:
        if "id" in o:
            opts[o["id"]] = {x["value"] for x in o.get("options", [])} or None


def check_cond(c, where):
    if c["condition"] == "catharsis:config":
        if c["id"] not in opts:
            errors.append(f"{where}: unknown option {c['id']}")
        elif "value" in c and c["value"] not in (opts[c["id"]] or set()):
            errors.append(f"{where}: bad value {c['value']} for {c['id']}")
    for k in ("value", "values"):
        v = c.get(k)
        if isinstance(v, dict):
            check_cond(v, where)
        elif isinstance(v, list):
            for x in v:
                check_cond(x, where)


for e in meta["fabric:overlays"]["entries"]:
    if not os.path.isdir(os.path.join(pack, e["directory"])):
        errors.append(f"missing overlay dir {e['directory']}")
    check_cond(e["condition"], e["directory"])

counts = {"replacements": 0, "states": 0, "models": 0}
for dp, _, fs in os.walk(pack):
    for f in fs:
        if not f.endswith(".json"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, pack).replace(os.sep, "/")
        try:
            data = load(p)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{rel}: invalid json {ex}")
            continue
        if "/catharsis/block_replacements/" in rel:
            counts["replacements"] += 1
            vs = set()
            walk_redirects(data, vs)
            for v in vs:
                if not exists("catharsis/virtual_block_states", v, ".json"):
                    errors.append(f"{rel}: missing virtual state {v}")
        elif "/catharsis/virtual_block_states/" in rel:
            counts["states"] += 1
            ms = set()
            walk_models(data, ms)
            for m in ms:
                if not exists("models", m, ".json"):
                    errors.append(f"{rel}: missing model {m}")
        elif "/models/" in rel:
            counts["models"] += 1
            for t in data.get("textures", {}).values():
                if not t.startswith("#") and not exists("textures", t, ".png"):
                    errors.append(f"{rel}: missing texture {t}")

print(counts, "overlays:", len(meta["fabric:overlays"]["entries"]))
print("\n".join(errors[:50]) if errors else "OK: no broken references")
sys.exit(1 if errors else 0)
