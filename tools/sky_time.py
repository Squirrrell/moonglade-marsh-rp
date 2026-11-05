"""
Evaluates the vanilla overworld day timeline at a given tick.

Reads data/minecraft/dimension_type/overworld.json (base attribute values) and
data/minecraft/timeline/day.json (keyframed tracks) and returns the final
visual attribute values for that time of day. These values are then locked
with Catharsis environment modifiers, so the sky looks like that time
regardless of the server clock.
"""
import json
import os

VISUAL = [
    "minecraft:visual/sun_angle", "minecraft:visual/moon_angle", "minecraft:visual/star_angle",
    "minecraft:visual/star_brightness", "minecraft:visual/sky_color", "minecraft:visual/fog_color",
    "minecraft:visual/cloud_color", "minecraft:visual/sky_light_color",
    "minecraft:visual/sky_light_factor", "minecraft:visual/sunrise_sunset_color",
]


def parse_color(v):
    """-> (argb tuple, has_alpha)"""
    if isinstance(v, int):
        v &= 0xFFFFFFFF
        return ((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255), True
    h = v.lstrip("#")
    if len(h) == 6:
        return (255, int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)), False
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)), True


def fmt_color(c, alpha):
    a, r, g, b = (max(0, min(255, round(x))) for x in c)
    return f"#{a:02x}{r:02x}{g:02x}{b:02x}" if alpha else f"#{r:02x}{g:02x}{b:02x}"


def is_color(v):
    return isinstance(v, str) and v.startswith("#") or (isinstance(v, int) and not isinstance(v, bool))


def bezier(t, x1, y1, x2, y2):
    def bx(s):
        return 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3

    def by(s):
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if bx(mid) < t:
            lo = mid
        else:
            hi = mid
    return by((lo + hi) / 2)


def sample(track, period, tick):
    kfs = [(k["ticks"], k["value"]) for k in track["keyframes"]]
    prev = [k for k in kfs if k[0] <= tick]
    nxt = [k for k in kfs if k[0] > tick]
    p = prev[-1] if prev else (kfs[-1][0] - period, kfs[-1][1])
    n = nxt[0] if nxt else (kfs[0][0] + period, kfs[0][1])
    ease = track.get("ease", "linear")
    if p[0] == n[0] or ease == "constant":
        return p[1]
    t = (tick - p[0]) / (n[0] - p[0])
    if isinstance(ease, dict) and "cubic_bezier" in ease:
        t = bezier(t, *ease["cubic_bezier"])
    a, b = p[1], n[1]
    if isinstance(a, bool):
        return a
    if is_color(a):
        ca, al = parse_color(a)
        cb, _ = parse_color(b)
        return ("color", tuple(x + (y - x) * t for x, y in zip(ca, cb)), al)
    if isinstance(a, (int, float)):
        return a + (b - a) * t
    return a


def apply(base, value, modifier):
    if value is None:
        return base
    if base is None or modifier in (None, "override"):
        return value
    if isinstance(base, tuple):  # colours
        _, cb, al = base
        _, cv, _ = value
        if modifier == "multiply":
            return ("color", tuple(x * y / 255 for x, y in zip(cb, cv)), al)
        return value
    if modifier == "multiply":
        return base * value
    if modifier == "maximum":
        return max(base, value)
    return value


def evaluate(vanilla_dir, tick):
    data = os.path.join(vanilla_dir, "data", "minecraft")
    with open(os.path.join(data, "dimension_type", "overworld.json"), encoding="utf-8") as f:
        base_attrs = json.load(f)["attributes"]
    with open(os.path.join(data, "timeline", "day.json"), encoding="utf-8") as f:
        day = json.load(f)
    out = {}
    for attr in VISUAL:
        base = base_attrs.get(attr)
        if is_color(base):
            c, al = parse_color(base)
            base = ("color", c, al)
        track = day["tracks"].get(attr)
        val = None
        if track:
            val = sample(track, day["period_ticks"], tick)
            if is_color(val):
                c, al = parse_color(val)
                val = ("color", c, al)
        v = apply(base, val, track.get("modifier") if track else None)
        if isinstance(v, tuple):
            v = fmt_color(v[1], v[2])
        elif isinstance(v, float):
            v = round(v % 360.0 if attr.endswith("_angle") else v, 4)
        if v is not None:
            out[attr] = v
    return out


if __name__ == "__main__":
    import sys
    for t in map(int, sys.argv[2:]):
        print(t, json.dumps(evaluate(sys.argv[1], t)))
