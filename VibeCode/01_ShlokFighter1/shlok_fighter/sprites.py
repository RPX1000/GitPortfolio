"""Fighter art: cartoon figures with cel shading, bold outlines, expressive faces and
outfits that suit each character. Everything is drawn at double resolution and shrunk
back down, so the edges stay smooth at any window size.

A fighter's state drives the look: its pose (charge, throw, raise, spin, dash), its mood
(calm, grit, shout, hurt) and its blink. Presentation attributes set by moves and the
game (pose, aura, alpha, silhouette) are read with getattr so simple stand-ins work too."""

import math
from types import SimpleNamespace

import pygame

from .config import OUTLINE, SKIN, WHITE, ATTACKS, FLOOR_Y
from .drawing import Canvas, shade, tint, grow, soft_glow

HEAD_R = 19
CANVAS_W, CANVAS_H, CANVAS_TOP = 200, 230, 190
SILHOUETTE = (34, 22, 46)
LIGHT = (0.55, 0.83)    # the light travels from the top-left: bottom-right surfaces are in shade

# Per-character colours and details. "accent" is the signature trim colour.
LOOKS = {
    "headband": {"pants": (46, 44, 64), "shoe": (30, 28, 38), "sole": (240, 240, 246), "accent": (210, 40, 50)},
    "spiky": {"pants": (34, 34, 44), "shoe": (26, 24, 32), "sole": (150, 150, 160), "accent": (250, 250, 250)},
    "slick": {"pants": (30, 64, 44), "shoe": (22, 20, 24), "sole": (30, 28, 32), "accent": (176, 40, 52)},
    "dapper": {"pants": (34, 30, 40), "shoe": (22, 18, 22), "sole": (70, 62, 70), "accent": (236, 186, 70),
               "skin": (160, 108, 72)},
    "straw": {"pants": (60, 96, 170), "shoe": (112, 76, 44), "sole": (70, 46, 28), "accent": (60, 96, 170)},
    "gold": {"pants": (40, 36, 46), "shoe": (60, 56, 64), "sole": (250, 210, 60), "accent": (255, 215, 60)},
    "hood": {"pants": (34, 20, 48), "shoe": (26, 18, 34), "sole": (60, 40, 80), "accent": (200, 120, 255)},
    "gray": {"pants": (70, 74, 90), "shoe": (20, 20, 24), "sole": (50, 50, 56), "accent": (240, 240, 246)},
}

# Hair shapes, in units of head radius, mirrored by facing direction.
SPIKY = [(-1.05, 0.1), (-1.3, -0.6), (-1.0, -0.5), (-1.1, -1.2), (-0.6, -0.8), (-0.4, -1.6),
         (0.0, -1.0), (0.3, -1.7), (0.6, -0.9), (1.0, -1.3), (0.95, -0.4), (1.15, 0.0),
         (0.6, -0.1), (0.0, -0.2), (-0.6, 0.0)]
SLICK = [(-1.05, 0.05), (-1.1, -0.7), (-0.4, -1.15), (0.5, -1.1), (1.0, -0.6),
         (0.95, -0.1), (0.4, -0.6), (-0.2, -0.35), (-0.8, -0.1)]
GRAY = [(-1.05, 0.0), (-1.1, -0.8), (-0.3, -1.2), (0.8, -1.1), (1.05, -0.4),
        (0.7, -0.45), (0.2, -0.7), (-0.4, -0.45), (-0.9, -0.1)]
HOOD = [(-1.4, 0.4), (-1.35, -0.9), (-0.6, -1.5), (0.6, -1.5), (1.2, -0.9),
        (1.25, 0.4), (0.6, 0.9), (-0.6, 0.9)]
QUIFF = [(-1.1, 0.1), (-1.2, -0.6), (-0.9, -1.1), (-0.3, -1.55), (0.3, -1.9), (0.85, -1.6),
         (1.1, -1.0), (1.0, -0.55), (0.4, -0.8), (-0.1, -0.7), (-0.6, -0.5), (-1.0, -0.2)]

_shadow_img = None


def actor(info, x, facing=1, feet=FLOOR_Y, **overrides):
    """A lightweight stand-in for a Fighter, used by the title screen, portraits and clones."""
    a = SimpleNamespace(name=info["name"], color=info["color"], hair=info["hair"], look=info["look"],
                        eye=info.get("eye"), x=float(x), y=float(feet), facing=facing, crouching=False,
                        on_ground=True, flash=0, walk_t=0, vx=0.0, attack=None, attack_t=0, blocking=False,
                        hurt_t=0, windup=0, pose=None, aura=None, alpha=255, silhouette=False)
    for key, value in overrides.items():
        setattr(a, key, value)
    return a


def _mid(a, b, dx=0.0, dy=0.0):
    return ((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy)


def _phase(f):
    fn = getattr(f, "phase", None)
    return fn() if callable(fn) else None


def fighter_pose(f, cx, feet):
    """Works out where every joint sits for the current state of a fighter."""
    d = f.facing
    crouch = f.crouching and f.on_ground
    air = not f.on_ground
    bob = 0.0 if (crouch or air) else math.sin(f.walk_t * 0.08) * 1.2
    lean = -d * 6.0 if getattr(f, "hurt_t", 0) > 0 else 0.0
    if crouch:
        hip_y, neck_y, head_y = feet - 36, feet - 72, feet - 94
    else:
        hip_y, neck_y, head_y = feet - 62 + bob, feet - 100 + bob, feet - 124 + bob
    nx = cx + lean
    hip = (cx, hip_y)
    sh = (nx, neck_y + 6)
    attack = getattr(f, "attack", None)
    pose = getattr(f, "pose", None)
    if pose is None and getattr(f, "throw_t", 0) > 0:
        pose = "throw"
    if pose is None and getattr(f, "windup", 0) > 0 and attack is None:
        pose = "charge"
    if pose is None and getattr(f, "dash_t", 0) > 0:
        pose = "dash"
    if pose is None and getattr(f, "snare_t", 0) > 0:
        pose = "snared"

    # how far a strike has reached: winds up in startup, fully out while active, retracts in recovery
    ext = 0.0
    if attack:
        spec = ATTACKS[attack]
        reach_end = spec["startup"] + spec["active"]
        if f.attack_t < spec["startup"]:
            ext = 0.25 * f.attack_t / max(1, spec["startup"])
        elif f.attack_t < reach_end:
            ext = 1.0
        else:
            ext = max(0.0, 1.0 - (f.attack_t - reach_end) / max(1, spec["recovery"]))

    swing = 0.0
    if (f.on_ground and abs(f.vx) > 0.5 and not attack and not f.blocking and not crouch
            and pose is None):
        swing = math.sin(f.walk_t * 0.25) * 11

    if crouch:
        foot_f, foot_b = (cx + d * 22, feet), (cx - d * 16, feet)
        knee_f, knee_b = (cx + d * 30, hip_y + 16), (cx - d * 22, hip_y + 18)
    elif air:
        foot_f, foot_b = (cx + d * 16, feet - 18), (cx - d * 8, feet - 8)
        knee_f, knee_b = (cx + d * 15, hip_y + 14), (cx - d * 6, hip_y + 16)
    else:
        foot_f, foot_b = (cx + d * 8 + swing, feet), (cx - d * 8 - swing, feet)
        knee_f, knee_b = _mid(hip, foot_f, d * 3), _mid(hip, foot_b, d * 3)
    if attack == "kick" or attack == "air_kick":
        foot_f = (cx + d * (8 + 60 * ext), feet - 10 - 52 * ext)
        knee_f = _mid(hip, foot_f, 0, 4)
        foot_b = (cx - d * 8, feet)
        knee_b = _mid(hip, foot_b, d * 3)
    elif attack == "sweep":
        foot_f = (cx + d * (14 + 46 * ext), feet - 4 - 6 * ext)
        knee_f = _mid(hip, foot_f, 0, 2)
        foot_b = (cx - d * 14, feet)
        knee_b = _mid(hip, foot_b, d * 3)
    if attack == "dive_kick":
        foot_f, foot_b = (cx + d * 30, feet - 12), (cx - d * 12, feet - 30)
        knee_f, knee_b = _mid(hip, foot_f, d * 4, 0), _mid(hip, foot_b, -d * 2, 0)
    if pose == "spin" and not attack:
        foot_f, foot_b = (cx + d * 42, feet - 36), (cx - d * 10, feet)
        knee_f, knee_b = _mid(hip, foot_f, 0, 6), _mid(hip, foot_b, d * 3)
    if pose == "dash":
        foot_f, foot_b = (cx + d * 20, feet - 6), (cx - d * 16, feet)
        knee_f, knee_b = _mid(hip, foot_f, d * 4, 0), _mid(hip, foot_b, -d * 2, 0)

    if getattr(f, "blocking", False):
        hand_f, hand_b = (nx + d * 22, head_y + 4), (nx + d * 12, head_y + 20)
    elif attack == "uppercut":   # the fist rises up from the hip
        hand_f = (nx + d * (16 + 16 * ext), head_y + 30 - 58 * ext)
        hand_b = (nx - d * 6, head_y + 22)
    elif attack == "dash_punch":  # a long, low lunge
        hand_f = (sh[0] + d * (40 + 22 * ext), sh[1] + 4)
        hand_b = (nx - d * 8, neck_y + 22)
    elif attack == "dive_kick":   # arms out for balance while falling
        hand_f, hand_b = (nx + d * 24, neck_y + 4), (nx - d * 24, neck_y - 6)
    elif pose == "snared":        # struggling against the vines
        shake = math.sin(f.walk_t * 1.3) * 3
        hand_f, hand_b = (nx + d * 12 + shake, head_y + 16), (nx - d * 10 - shake, head_y + 14)
    elif attack in ("punch", "air_punch"):
        hand_f = (sh[0] + d * (24 + 34 * ext), sh[1] - 2)
        hand_b = (nx + d * 8, head_y + 16)
    elif attack == "low_punch":
        hand_f, hand_b = (nx + d * (20 + 30 * ext), neck_y + 40), (nx - d * 6, neck_y + 30)
    elif attack in ("kick", "air_kick", "sweep"):
        hand_f, hand_b = (nx + d * 26, neck_y + 14), (nx - d * 24, neck_y + 12)
    elif getattr(f, "hurt_t", 0) > 0:
        hand_f, hand_b = (nx - d * 30, neck_y - 2), (nx - d * 16, neck_y + 28)
    elif pose == "charge":
        hand_f, hand_b = (nx + d * 12, neck_y + 22), (nx - d * 8, neck_y + 26)
    elif pose == "throw":
        hand_f, hand_b = (nx + d * 46, neck_y + 4), (nx - d * 2, neck_y + 24)
    elif pose == "raise":
        hand_f, hand_b = (nx + d * 10, head_y - 30), (nx - d * 10, head_y - 30)
    elif pose == "spin":
        hand_f, hand_b = (nx + d * 34, neck_y + 10), (nx - d * 34, neck_y + 10)
    elif pose == "dash":
        hand_f, hand_b = (nx + d * 30, neck_y + 14), (nx - d * 22, neck_y + 30)
    elif air:
        hand_f, hand_b = (nx + d * 12, neck_y - 14), (nx - d * 12, neck_y - 4)
    elif crouch:
        hand_f, hand_b = (nx + d * 18, neck_y + 20), (nx - d * 6, neck_y + 22)
    else:
        hand_f = (nx + d * 18 - swing * 0.5, hip_y - 6)
        hand_b = (nx - d * 14 + swing * 0.5, hip_y - 4)

    return {
        "hip": hip, "neck": (nx, neck_y), "head": (nx, head_y), "sh": sh,
        "hand_f": hand_f, "hand_b": hand_b,
        "elbow_f": _mid(sh, hand_f, 0, 6), "elbow_b": _mid(sh, hand_b, 0, 6),
        "knee_f": knee_f, "knee_b": knee_b, "foot_f": foot_f, "foot_b": foot_b,
    }


# ----- shapes ----------------------------------------------------------------

def _shade_normal(dx, dy):
    """The unit normal of a segment that points into its shadow side."""
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    if nx * LIGHT[0] + ny * LIGHT[1] < 0:
        nx, ny = -nx, -ny
    return nx, ny


def _tapered(c, a, b, wa, wb, col, caps=True):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length
    c.polygon([(a[0] + px * wa / 2, a[1] + py * wa / 2), (b[0] + px * wb / 2, b[1] + py * wb / 2),
               (b[0] - px * wb / 2, b[1] - py * wb / 2), (a[0] - px * wa / 2, a[1] - py * wa / 2)], col)
    if caps:
        c.circle(a, wa / 2, col)
        c.circle(b, wb / 2, col)


def _limb(c, a, b, wa, wb, col):
    """A tapered limb with an outline."""
    _tapered(c, a, b, wa + 4, wb + 4, OUTLINE)
    _tapered(c, a, b, wa, wb, col)


def _cel(c, a, b, wa, wb, col):
    """A limb in cel style: a shadow band on the side away from the light and a highlight on the lit side."""
    _limb(c, a, b, wa, wb, col)
    sx, sy = _shade_normal(b[0] - a[0], b[1] - a[1])
    off = min(wa, wb) * 0.26
    _tapered(c, (a[0] + sx * off, a[1] + sy * off), (b[0] + sx * off, b[1] + sy * off),
             wa * 0.5, wb * 0.5, shade(col, 0.68), caps=False)
    _tapered(c, (a[0] - sx * off, a[1] - sy * off), (b[0] - sx * off, b[1] - sy * off),
             wa * 0.2, wb * 0.2, tint(col, 0.24), caps=False)


def _fist(c, p, skin, skin_dk):
    c.circle(p, 8.6, OUTLINE)
    c.circle(p, 7.0, skin)
    c.circle((p[0] + 2.0, p[1] + 2.4), 4.2, skin_dk)


def _shoe(c, p, d, shoe, sole, sil):
    x, y = p
    body = (x - 10 + d * 2, y - 8, 22, 10)
    c.ellipse((body[0] - 1.5, body[1] - 1.5, body[2] + 3, body[3] + 3), OUTLINE)
    c.ellipse(body, shoe)
    if not sil:
        c.line((x - 8, y + 1.4), (x + 9, y + 1.4), 2.4, sole)
        c.line((x - 3 + d * 2, y - 6), (x + 2 + d * 2, y - 5), 1.2, tint(shoe, 0.35))


def _rel_poly(c, rel, hx, hy, d, r, color):
    pts = [(hx + dx * r * d, hy + dy * r) for dx, dy in rel]
    c.polygon(grow(pts, 1.6), OUTLINE)
    c.polygon(pts, color)


# ----- face and mood -----------------------------------------------------------

def _mood(f):
    if getattr(f, "hurt_t", 0) > 0 or getattr(f, "down_t", 0) > 0:
        return "hurt"
    if getattr(f, "snare_t", 0) > 0:
        return "grit"
    if getattr(f, "blocking", False) or getattr(f, "block_t", 0) > 0:
        return "grit"
    if f.attack and _phase(f) == "active":
        return "shout"
    if getattr(f, "throw_t", 0) > 0 or f.pose == "throw":
        return "shout"
    if getattr(f, "windup", 0) > 0 or f.pose == "charge" or (f.attack and _phase(f) == "startup"):
        return "focus"
    return "calm"


def _face(c, f, hx, hy, d, mood, eye_col, sil):
    if sil:
        return
    ex, ey = hx + d * 6.0, hy - 3.0
    blink = mood == "calm" and (f.walk_t % 210) < 5
    if mood in ("grit", "focus"):
        c.line((ex - 4.5, ey - 8.6), (ex + 4.2, ey - 5.6), 2.4, OUTLINE)
    elif mood == "hurt":
        c.line((ex - 4.5, ey - 6.0), (ex + 4.0, ey - 8.6), 2.0, OUTLINE)
    elif mood == "shout":
        c.line((ex - 4.5, ey - 9.2), (ex + 4.5, ey - 9.2), 2.2, OUTLINE)
    else:
        c.line((ex - 4.5, ey - 7.2), (ex + 4.2, ey - 7.6), 2.0, OUTLINE)

    if mood == "hurt":
        c.line((ex - 3, ey - 3), (ex + 3, ey + 3), 1.7, OUTLINE)
        c.line((ex - 3, ey + 3), (ex + 3, ey - 3), 1.7, OUTLINE)
    elif blink:
        c.line((ex - 4, ey + 0.6), (ex + 4, ey + 0.6), 2.0, OUTLINE)
    elif f.look == "hood":
        c.circle((ex, ey), 4.8, (90, 16, 30))
        c.circle((ex, ey), 3.2, eye_col)
        c.circle((ex + d * 0.8, ey), 1.5, (255, 232, 232))
    else:
        c.circle((ex, ey), 5.0, OUTLINE)
        c.circle((ex, ey), 4.3, WHITE)
        c.circle((ex + d * 0.9, ey + 0.3), 2.9, eye_col)
        c.circle((ex + d * 1.1, ey + 0.4), 1.4, (14, 12, 18))
        c.circle((ex + d * 0.2 - 1.0, ey - 1.2), 0.9, WHITE)
        tilt = 0.9 if mood in ("grit", "focus") else 0.0
        c.line((ex - 4.2, ey - 1.6 + tilt), (ex + 4.2, ey - 1.6 - tilt), 1.6, OUTLINE)

    mx, my = hx + d * 4.0, hy + 9.0
    if mood == "shout":
        c.ellipse((mx - 1, my - 2.5, 9, 6.5), (74, 22, 32))
        c.line((mx + 0.5, my + 0.6), (mx + 6, my + 0.6), 1.2, WHITE)
    elif mood == "hurt":
        c.circle((mx + d * 2.5, my + 0.5), 2.2, OUTLINE)
    elif mood in ("grit", "focus"):
        c.line((mx - 1, my), (mx + 6.5, my - 0.5), 2.0, OUTLINE)
    else:
        c.line((mx - 1, my - 0.5), (mx + 3.5, my + 0.5), 1.6, OUTLINE)
        c.line((mx + 3.5, my + 0.5), (mx + 6.5, my - 0.8), 1.6, OUTLINE)


# ----- hair and head ---------------------------------------------------------

def _hair(c, look, hx, hy, d, pal, f):
    r = HEAD_R
    if look in ("spiky", "gold", "headband"):
        _rel_poly(c, SPIKY, hx, hy, d, r, pal.hair)
        c.line((hx + d * 0.2 * r, hy - 1.25 * r), (hx + d * 0.9 * r, hy - 0.55 * r), 1.8, tint(pal.hair, 0.38))
        c.line((hx - d * 0.6 * r, hy - 0.9 * r), (hx - d * 0.1 * r, hy - 1.35 * r), 1.4, tint(pal.hair, 0.3))
        if look == "spiky":  # Korean David's red-tipped spikes
            for tip in ((0.3, -1.7), (1.0, -1.3), (-1.0, -0.5)):
                c.circle((hx + d * tip[0] * r, hy + tip[1] * r), 2.6, (220, 60, 60))
    elif look == "slick":
        _rel_poly(c, SLICK, hx, hy, d, r, pal.hair)
        c.line((hx - d * 0.5 * r, hy - 0.8 * r), (hx + d * 0.7 * r, hy - 0.95 * r), 1.8, tint(pal.hair, 0.35))
    elif look == "gray":
        _rel_poly(c, GRAY, hx, hy, d, r, pal.hair)
        c.line((hx - d * 0.6 * r, hy - 0.9 * r), (hx + d * 0.6 * r, hy - 1.1 * r), 2.0, WHITE)
        c.line((hx + d * 0.1 * r, hy - 0.4 * r), (hx + d * 0.8 * r, hy - 0.8 * r), 1.4, tint(pal.hair, 0.5))
    elif look == "hood":
        _rel_poly(c, HOOD, hx, hy, d, r, shade(pal.shirt, 0.85))
        c.line((hx - d * 1.1 * r, hy + 0.2 * r), (hx - d * 0.2 * r, hy - 1.3 * r), 1.6, pal.accent)
    elif look == "dapper":  # Ronak: a swept-back quiff with a sheen
        _rel_poly(c, QUIFF, hx, hy, d, r, pal.hair)
        c.line((hx - d * 0.2 * r, hy - 1.6 * r), (hx + d * 0.7 * r, hy - 1.25 * r), 1.8, tint(pal.hair, 0.4))
        c.line((hx - d * 0.9 * r, hy - 0.7 * r), (hx - d * 0.5 * r, hy - 1.1 * r), 1.2, tint(pal.hair, 0.25))
    elif look == "straw":
        straw = (234, 206, 128)
        rect = (hx - r - 13, hy - r + 1, 2 * r + 26, 9)
        c.ellipse((rect[0] - 1.5, rect[1] - 1.5, rect[2] + 3, rect[3] + 3), OUTLINE)
        c.ellipse(rect, straw)
        c.ellipse((rect[0] + 4, rect[1] + 1, rect[2] - 8, 3), tint(straw, 0.3))
        crown = [(hx - r + 3, hy - r + 2), (hx - r + 3, hy - r - 10),
                 (hx + r - 3, hy - r - 10), (hx + r - 3, hy - r + 2)]
        c.polygon(grow(crown, 1.4), OUTLINE)
        c.polygon(crown, straw)
        c.line((hx - r + 3, hy - r - 2), (hx + r - 3, hy - r - 2), 3, (176, 42, 42))


def _headband(c, hx, hy, d, accent, f):
    flutter = math.sin(f.walk_t * 0.2) * 2
    c.line((hx - d * (HEAD_R - 2), hy - 8), (hx + d * (HEAD_R - 1), hy - 8), 4.2, accent)
    c.polygon([(hx - d * (HEAD_R - 2), hy - 9), (hx - d * (HEAD_R + 13), hy - 6 + flutter),
               (hx - d * (HEAD_R + 10), hy - 14 + flutter)], accent)
    c.polygon([(hx - d * (HEAD_R - 2), hy - 7), (hx - d * (HEAD_R + 11), hy - 2 + flutter),
               (hx - d * (HEAD_R + 8), hy - 8 + flutter)], shade(accent, 0.7))


def _beard(c, hx, hy, d, color):
    """A short, neat beard along the jaw, with a trimmed moustache under the nose."""
    outer = [(hx + math.cos(math.radians(a)) * 18.5, hy + math.sin(math.radians(a)) * 18.5)
             for a in range(10, 171, 20)]
    inner = [(hx + math.cos(math.radians(a)) * 13.0 + d * 2.5, hy + math.sin(math.radians(a)) * 13.0 + 1.0)
             for a in range(170, 9, -20)]
    c.polygon(outer + inner, color)
    c.line((hx + d * 0.5, hy + 5.8), (hx + d * 9.5, hy + 5.8), 2.6, color)


# ----- outfits -----------------------------------------------------------------

def _outfit(c, look, pal, nx, neck_y, hip_x, hip_y, d, f):
    if look == "headband":  # Shlok: a hoodie with drawstrings, a zip and a patch
        c.polygon([(nx - 8, neck_y + 4), (nx + 8, neck_y + 4), (nx + 6, neck_y + 12), (nx - 6, neck_y + 12)],
                  pal.shirt_dk)
        c.line((nx - 2, neck_y + 11), (nx - 3, neck_y + 23), 1.4, pal.shirt_lt)
        c.line((nx + 2, neck_y + 11), (nx + 1.5, neck_y + 23), 1.4, pal.shirt_lt)
        c.line((nx, neck_y + 12), (hip_x, hip_y + 5), 1.2, shade(pal.shirt_dk, 0.8))
        c.polygon([(hip_x - 9, hip_y - 6), (hip_x + 9, hip_y - 6), (hip_x + 9, hip_y + 1), (hip_x - 9, hip_y + 1)],
                  pal.shirt_dk)
        c.circle((nx - 8, neck_y + 20), 2.6, pal.accent)
    elif look == "spiky":  # Korean David: a red bomber with a white V collar and a zip
        c.polygon([(nx - 7, neck_y + 4), (nx + 7, neck_y + 4), (nx, neck_y + 17)], pal.skin)
        c.line((nx, neck_y + 16), (hip_x, hip_y + 5), 1.4, shade(pal.shirt_dk, 0.8))
        c.line((nx - 12, neck_y + 26), (nx + 12, neck_y + 26), 3.0, pal.shirt_lt)
    elif look in ("slick", "gray"):  # the suits: white collar, lapels, a tie and a pocket square
        tie = pal.accent if look == "slick" else (46, 46, 60)
        c.line((nx - 7, neck_y + 5), (hip_x - 9, hip_y + 2), 2.2, pal.shirt_dk)
        c.line((nx + 7, neck_y + 5), (hip_x + 9, hip_y + 2), 2.2, pal.shirt_dk)
        c.polygon([(nx - 7, neck_y + 4), (nx + 7, neck_y + 4), (nx, neck_y + 16)], (240, 240, 246))
        c.polygon([(nx - 2.5, neck_y + 8), (nx + 2.5, neck_y + 8), (nx + 4, neck_y + 26),
                   (nx, neck_y + 31), (nx - 4, neck_y + 26)], tie)
        c.polygon([(nx - 12, neck_y + 14), (nx - 7, neck_y + 13), (nx - 9, neck_y + 19)], (246, 246, 250))
    elif look == "dapper":  # Ronak: a bandhgala with gold trim, a white collar and a silk pocket square
        gold = (236, 186, 70)
        c.polygon([(nx - 6, neck_y + 1), (nx + 6, neck_y + 1), (nx + 5, neck_y + 9), (nx - 5, neck_y + 9)], gold)
        c.polygon([(nx - 3.5, neck_y + 2), (nx + 3.5, neck_y + 2), (nx, neck_y + 8)], (246, 246, 250))
        c.line((nx, neck_y + 9), (hip_x, hip_y + 4), 1.6, shade(gold, 0.85))
        for k in range(4):
            c.circle((nx, neck_y + 14 + k * 6.5), 1.9, gold)
        c.polygon([(nx - 13, neck_y + 14), (nx - 6, neck_y + 12), (nx - 5, neck_y + 19), (nx - 12, neck_y + 20)], gold)
        c.line((nx - 11, neck_y + 16.5), (nx - 6.5, neck_y + 15.5), 1.0, shade(gold, 0.7))
        c.line((hip_x - 13, hip_y + 5), (hip_x + 13, hip_y + 5), 1.4, gold)
    elif look == "straw":  # Rogelio: a red check shirt under blue overalls with brass buckles
        plaid = (170, 40, 40)
        for k in (-8, 0, 8):
            c.line((nx + k, neck_y + 4), (hip_x + k * 0.8, hip_y + 4), 1.2, plaid)
        c.line((nx - 14, neck_y + 22), (nx + 14, neck_y + 22), 1.2, plaid)
        bib = (60, 96, 170)
        c.line((nx - 9, neck_y + 4), (nx - 9, neck_y + 14), 3.5, bib)
        c.line((nx + 9, neck_y + 4), (nx + 9, neck_y + 14), 3.5, bib)
        c.polygon([(nx - 9, neck_y + 14), (nx + 9, neck_y + 14), (hip_x + 13, hip_y + 6), (hip_x - 13, hip_y + 6)],
                  bib)
        c.circle((nx - 9, neck_y + 13), 1.7, (226, 186, 76))
        c.circle((nx + 9, neck_y + 13), 1.7, (226, 186, 76))
        c.polygon([(nx - 4, neck_y + 22), (nx + 4, neck_y + 22), (nx + 4, neck_y + 28), (nx - 4, neck_y + 28)],
                  shade(bib, 0.8))
    elif look == "gold":  # The Nak: a black belt and a gold chain
        c.polygon([(hip_x - 13, hip_y - 2), (hip_x + 13, hip_y - 2), (hip_x + 13, hip_y + 3),
                   (hip_x - 13, hip_y + 3)], (30, 28, 34))
        for k in range(4):
            t = k / 3.0
            x = nx - 9 + 18 * t
            y = neck_y + 6 + math.sin(t * math.pi) * 6
            c.circle((x, y), 2.0, (255, 220, 80))
    elif look == "hood":  # Evil Shlok: a dark robe with a glowing sigil
        glow = pal.accent
        c.line((nx - 6, neck_y + 14), (nx + 6, neck_y + 22), 1.6, glow)
        c.line((nx + 6, neck_y + 14), (nx - 6, neck_y + 22), 1.6, glow)
        c.line((nx, neck_y + 12), (nx, neck_y + 30), 1.2, shade(glow, 0.7))


def _arm(c, sh, elbow, hand, pal, look, d, f, sil):
    """A sleeved arm with a fist. Watches, wrist wraps and sleeve stripes follow the look."""
    _cel(c, sh, elbow, 11, 9, pal.shirt)
    _cel(c, elbow, hand, 9, 8, pal.skin)
    if not sil:
        if look == "spiky":
            m = _mid(sh, elbow, 0, 0)
            c.line((m[0] - 2, m[1] - 3), (m[0] + 2, m[1] + 3), 2.2, WHITE)
        if look == "headband":
            w = (elbow[0] + (hand[0] - elbow[0]) * 0.72, elbow[1] + (hand[1] - elbow[1]) * 0.72)
            c.line((w[0] - 4, w[1] - 3), (w[0] + 4, w[1] + 3), 3.0, pal.accent)
        if look == "slick":
            w = (elbow[0] + (hand[0] - elbow[0]) * 0.8, elbow[1] + (hand[1] - elbow[1]) * 0.8)
            c.circle(w, 3.0, (240, 200, 90))
            c.circle(w, 1.3, (120, 90, 30))
        if look == "dapper":
            cuff = (elbow[0] + (hand[0] - elbow[0]) * 0.9, elbow[1] + (hand[1] - elbow[1]) * 0.9)
            watch = (elbow[0] + (hand[0] - elbow[0]) * 0.78, elbow[1] + (hand[1] - elbow[1]) * 0.78)
            c.line((cuff[0] - 3.5, cuff[1] - 3.5), (cuff[0] + 3.5, cuff[1] + 3.5), 2.2, (246, 246, 250))
            c.circle(watch, 2.8, (236, 186, 70))
            c.circle(watch, 1.1, (120, 90, 30))
    _fist(c, hand, pal.skin, pal.skin_dk)


def _leg(c, hip, knee, foot, pal, look, d, f, sil):
    _cel(c, hip, knee, 16, 13, pal.pants)
    _cel(c, knee, foot, 13, 10, pal.pants)
    _shoe(c, foot, d, pal.shoe, pal.sole, sil)


def _lightning(c, nx, neck_y, f):
    """The Nak's crackling aura: short jagged bolts that flicker."""
    phase = (f.walk_t // 3) % 4
    for k in range(3):
        a = k * 2.1 + phase * 0.7
        x0, y0 = nx + math.cos(a) * 34, neck_y + math.sin(a) * 26
        pts = [(x0, y0), (x0 + math.cos(a + 1.0) * 6, y0 + 4), (x0 - 2, y0 + 8), (x0 + 5, y0 + 13)]
        for p, q in zip(pts, pts[1:]):
            c.line(p, q, 1.5, (255, 240, 120))


# ----- figure ------------------------------------------------------------------

def _palette(f, sil, flash):
    style = LOOKS.get(f.look, LOOKS["spiky"])
    if sil:
        sc = sil if isinstance(sil, tuple) else SILHOUETTE
        return SimpleNamespace(shirt=sc, shirt_dk=sc, shirt_lt=sc, skin=sc, skin_dk=sc, pants=sc,
                               pants_dk=sc, shoe=sc, sole=sc, accent=sc, hair=sc, eye=sc)
    shirt = tint(f.color, flash * 0.8)
    skin = tint(style.get("skin", SKIN), flash * 0.8)
    pants = tint(style["pants"], flash * 0.6)
    return SimpleNamespace(
        shirt=shirt, shirt_dk=shade(shirt, 0.68), shirt_lt=tint(shirt, 0.22),
        skin=skin, skin_dk=shade(skin, 0.8), pants=pants, pants_dk=shade(pants, 0.7),
        shoe=style["shoe"], sole=style["sole"], accent=style["accent"],
        hair=tint(f.hair, flash * 0.5), eye=f.eye or (50, 40, 36))


def _draw_figure(c, f, cx, feet):
    P = fighter_pose(f, cx, feet)
    d = f.facing
    look = f.look
    sil = getattr(f, "silhouette", False)
    flash = f.flash / 6.0 if f.flash else 0.0
    pal = _palette(f, sil, flash)
    hx, hy = P["head"]
    nx, neck_y = P["neck"]
    hip_x, hip_y = P["hip"]
    sh = P["sh"]
    mood = _mood(f)

    if look == "hood" and not sil:  # a cloak that billows behind
        flutter = math.sin(f.walk_t * 0.15) * 5
        cape = [(nx - 15, neck_y + 4), (nx + 15, neck_y + 4), (hip_x + 14, feet + 2),
                (hip_x - d * 26 - flutter, feet + 2)]
        c.polygon(grow(cape, 2), OUTLINE)
        c.polygon(cape, shade(f.color, 0.6))
        c.polygon([(hip_x - d * 26 - flutter, feet + 2), (hip_x - d * 18 - flutter, feet - 8),
                   (hip_x - d * 12 - flutter, feet + 2), (hip_x - d * 6 - flutter, feet - 6),
                   (hip_x - d * 1 - flutter, feet + 2)], shade(f.color, 0.45))

    _leg(c, P["hip"], P["knee_b"], P["foot_b"], pal, look, d, f, sil)
    _arm(c, sh, P["elbow_b"], P["hand_b"], pal, look, d, f, sil)

    _cel(c, (hx, hy + 14), (nx, neck_y + 4), 10, 9, pal.skin_dk)

    torso = [(nx - 15, neck_y + 4), (nx + 15, neck_y + 4), (hip_x + 13, hip_y + 6), (hip_x - 13, hip_y + 6)]
    c.polygon(grow(torso, 2.2), OUTLINE)
    c.polygon(torso, pal.shirt)
    if not sil:
        c.polygon([(nx + 6, neck_y + 4), (nx + 15, neck_y + 4), (hip_x + 13, hip_y + 6), (hip_x + 3, hip_y + 6)],
                  pal.shirt_dk)
        c.line((nx - 11, neck_y + 9), (hip_x - 9, hip_y + 1), 2.2, pal.shirt_lt)
    c.polygon([(hip_x - 13, hip_y - 2), (hip_x + 13, hip_y - 2), (hip_x + 13, hip_y + 6), (hip_x - 13, hip_y + 6)],
              pal.pants)
    if not sil:
        _outfit(c, look, pal, nx, neck_y, hip_x, hip_y, d, f)
        if look == "gold":
            _lightning(c, nx, neck_y, f)

    c.circle((hx, hy), HEAD_R + 2.2, OUTLINE)
    if sil:
        c.circle((hx, hy), HEAD_R, pal.skin)
    else:
        c.circle((hx + 1.6, hy + 2.2), HEAD_R, pal.skin_dk)
        c.circle((hx - 0.4, hy - 0.6), HEAD_R - 0.6, pal.skin)
        c.circle((hx - d * 4, hy + 3), 4.2, pal.skin_dk)
    _hair(c, look, hx, hy, d, pal, f)
    if look == "headband" and not sil:
        _headband(c, hx, hy, d, pal.accent, f)
    if not sil and look != "hood":
        nose = [(hx + d * (HEAD_R - 2), hy - 1.5), (hx + d * (HEAD_R + 4.5), hy + 3), (hx + d * (HEAD_R - 2), hy + 4.5)]
        c.polygon(grow(nose, 1.2), OUTLINE)
        c.polygon(nose, pal.skin)
    if look == "dapper" and not sil:
        _beard(c, hx, hy, d, pal.hair)
    _face(c, f, hx, hy, d, mood, pal.eye, sil)

    _leg(c, P["hip"], P["knee_f"], P["foot_f"], pal, look, d, f, sil)
    _arm(c, sh, P["elbow_f"], P["hand_f"], pal, look, d, f, sil)


def draw_shadow(dest, cx, strength=1.0):
    global _shadow_img
    if _shadow_img is None:
        _shadow_img = pygame.Surface((110, 26), pygame.SRCALPHA)
        pygame.draw.ellipse(_shadow_img, (0, 0, 0, 120), _shadow_img.get_rect())
    _shadow_img.set_alpha(int(255 * max(0.2, min(1.0, strength))))
    dest.blit(_shadow_img, (int(cx) - 55, FLOOR_Y - 13))


def draw_fighter(dest, f, cx=None, feet=None, angle=0, alpha=None):
    """Draws a fighter (or actor) onto dest. angle rotates the figure (KO, knockdown);
    alpha overrides the fighter's own transparency (used for afterimages)."""
    cx = f.x if cx is None else cx
    feet = f.y if feet is None else feet
    if alpha is None:
        alpha = getattr(f, "alpha", 255)
    if alpha <= 0:
        return
    aura = getattr(f, "aura", None)
    if aura and not angle:
        color, strength = aura
        s = max(0.0, min(1.0, strength))
        soft_glow(dest, (int(cx), int(feet) - 70), 60 + int(50 * s) // 10 * 10, color,
                  20 + int(140 * s) // 20 * 20)
    elif f.look == "gold" and not angle:
        soft_glow(dest, (int(cx), int(feet) - 70), 90, (255, 220, 60), 46)
    x0 = cx - CANVAS_W / 2
    y0 = feet - CANVAS_TOP
    c = Canvas(x0, y0, CANVAS_W, CANVAS_H, ss=2)
    _draw_figure(c, f, cx, feet)
    img = c.image()
    if angle:
        img = pygame.transform.rotate(img, angle)
        pos = img.get_rect(center=(int(cx), int(y0 + CANVAS_H / 2)))
    else:
        pos = (int(round(x0)), int(round(y0)))
    if alpha < 255:
        img.set_alpha(alpha)
    dest.blit(img, pos)


def _full_canvas(info):
    """The character drawn once at 1x, on a canvas whose origin is (0, 10)."""
    a = actor(info, 100, 1, feet=200)
    c = Canvas(0, 200 - CANVAS_TOP, 200, CANVAS_H, ss=3)
    _draw_figure(c, a, 100, 200)
    return c.image()


def portrait(info, scale=1.0):
    """A full-body image of a character, cropped to the figure, for the story and dialogue screens."""
    img = _full_canvas(info).subsurface(pygame.Rect(34, 14, 132, 214)).copy()
    if scale != 1.0:
        img = pygame.transform.smoothscale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
    return img


def bust(info, size=64):
    """A head-and-shoulders crop for the HUD."""
    crop = _full_canvas(info).subsurface(pygame.Rect(66, 30, 68, 68)).copy()
    return pygame.transform.smoothscale(crop, (size, size))
