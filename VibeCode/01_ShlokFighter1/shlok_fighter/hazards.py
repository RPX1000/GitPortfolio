"""Stage hazards: lava geysers, falling money, gusts, a tractor, shockwaves, mirror
fireballs and falling rubble.

Hazards never change health directly. They queue hits in `pending`, and the game resolves
them with the same hit rules as a punch, so a hazard flinches, knocks back and shows
damage on whichever fighter it catches. A boss standing on its own stage is immune: the
hazard skips it until the boss is stunned. `threat_at` tells the AI where a hazard is about
to land so it can react."""

import math
import random

import pygame

from .config import WIDTH, FLOOR_Y
from .drawing import lerp, soft_glow, text, shade
from .projectiles import Projectile

ORANGE = (255, 120, 40)


def draw_tractor(surf, x, rot):
    """Draws the tractor at x. Shared with the boss's Tractor Charge."""
    x = int(x)
    body = (60, 165, 70)
    pygame.draw.rect(surf, (16, 12, 20), (x - 84, FLOOR_Y - 74, 168, 44), border_radius=10)
    pygame.draw.rect(surf, body, (x - 80, FLOOR_Y - 70, 160, 40), border_radius=9)
    pygame.draw.rect(surf, shade(body, 0.7), (x - 80, FLOOR_Y - 40, 160, 10), border_radius=4)
    pygame.draw.rect(surf, (16, 12, 20), (x + 8, FLOOR_Y - 116, 60, 48), border_radius=6)
    pygame.draw.rect(surf, (220, 60, 50), (x + 12, FLOOR_Y - 112, 52, 40), border_radius=5)
    pygame.draw.rect(surf, (170, 220, 255), (x + 18, FLOOR_Y - 106, 30, 18), border_radius=3)
    pygame.draw.rect(surf, (90, 90, 96), (x - 42, FLOOR_Y - 100, 7, 30))
    for wx, wy, r in ((x - 44, FLOOR_Y - 22, 28), (x + 46, FLOOR_Y - 14, 20)):
        pygame.draw.circle(surf, (16, 12, 20), (wx, wy), r + 2)
        pygame.draw.circle(surf, (38, 38, 42), (wx, wy), r)
        pygame.draw.circle(surf, (230, 200, 60), (wx, wy), r // 2)
        for k in range(3):
            a = rot + k * math.pi * 2 / 3
            pygame.draw.line(surf, (200, 180, 60), (wx, wy),
                             (wx + math.cos(a) * r * 0.6, wy + math.sin(a) * r * 0.6), 2)


class Hazard:
    def __init__(self, kind):
        self.kind = kind
        self.t = 0
        self.items = []
        self.pending = []   # (target, damage, knock, direction, hitstun, sound)

    def take_hits(self):
        hits, self.pending = self.pending, []
        return hits

    def threat_at(self, x):
        """Returns (kind, hazard_x) if something is about to land on a grounded fighter at x,
        where kind is "move" (step out of the way) or "jump" (leap over it). Otherwise None."""
        k = self.kind
        if k == "lava":
            for it in self.items:
                if abs(x - it["x"]) < 62:
                    return ("move", it["x"])
        elif k == "money":
            for it in self.items:
                if abs(x - it["x"]) < 44:
                    return ("move", it["x"])
        elif k == "tractor":
            for it in self.items:
                if abs(x - it["x"]) < 120:
                    return ("jump", it["x"])
        elif k == "shockwave":
            for it in self.items:
                if abs(x - it["x"]) < 44:
                    return ("jump", it["x"])
        elif k == "rubble":
            for it in self.items:
                if it["t"] < 40 and abs(x - it["x"]) < 60:
                    return ("move", it["x"])
        return None

    def update(self, fighters, projectiles, fx):
        """Advances the hazard one frame. Returns the sounds to play as (name, volume)."""
        fighters = [f for f in fighters if not f.stage_immune()]
        self.t += 1
        t = self.t
        kind = self.kind
        sounds = []

        if kind == "lava":
            if t % 150 == 0:
                self.items.append({"x": random.randint(90, WIDTH - 90), "t": 0})
            for it in self.items:
                it["t"] += 1
                if it["t"] == 50:
                    sounds.append(("boom", 0.35))
                if 50 <= it["t"] < 90 and random.random() < 0.5:
                    fx.add(it["x"] + random.uniform(-45, 45), FLOOR_Y, random.uniform(-0.6, 0.6),
                           random.uniform(-6, -3), 50, (255, 170, 60), 3, gravity=0.18)
                if it["t"] >= 50:
                    for f in fighters:
                        if f.alive and f.on_ground and abs(f.x - it["x"]) < 55:
                            if t % 18 == 0:
                                self.pending.append((f, 2, 0, 1 if f.x >= it["x"] else -1, 8, ""))
                            if random.random() < 0.3:
                                fx.add(f.x + random.uniform(-16, 16), FLOOR_Y - 4, random.uniform(-0.4, 0.4),
                                       random.uniform(-2.2, -0.9), 26, (255, 150, 60), 3)
            self.items = [it for it in self.items if it["t"] < 90]

        elif kind == "money":
            if t % 55 == 0:
                self.items.append({"x": random.randint(60, WIDTH - 60), "y": -20.0, "vy": 0.0})
            keep = []
            for it in self.items:
                it["vy"] += 0.35
                it["y"] += it["vy"]
                bag = pygame.Rect(int(it["x"]) - 12, int(it["y"]) - 22, 24, 22)
                victim = next((f for f in fighters if f.alive and bag.colliderect(f.hurtbox())), None)
                if victim:
                    self.pending.append((victim, 6, 3, 1 if victim.x >= it["x"] else -1, 12, "coin"))
                    fx.burst(it["x"], it["y"] - 10, (240, 210, 90), 10, speed=4, life=24, size=3)
                elif it["y"] < FLOOR_Y + 30:
                    keep.append(it)
            self.items = keep

        elif kind == "wind":
            if t % 240 == 0:
                self.items = [{"dir": random.choice((-1, 1)), "t": 0}]
                sounds.append(("whoosh", 0.5))
            for it in self.items:
                it["t"] += 1
                for f in fighters:
                    if f.alive and not f.attack and f.hurt_t == 0:
                        f.x += 0.9 * it["dir"]
                if it["t"] % 3 == 0:
                    fx.add(random.randint(0, WIDTH), random.randint(60, FLOOR_Y - 40), it["dir"] * 6.0,
                           random.uniform(-0.4, 0.4), 40, (210, 230, 255), 2)
            self.items = [it for it in self.items if it["t"] < 120]

        elif kind == "tractor":
            if t % 360 == 0:
                going_right = random.random() < 0.5
                x = -90.0 if going_right else WIDTH + 90.0
                self.items.append({"x": x, "v": 5.0 if going_right else -5.0})
            for it in self.items:
                it["x"] += it["v"]
                if t % 5 == 0:
                    fx.add(it["x"] + (-80 if it["v"] > 0 else 80), FLOOR_Y - 96,
                           -it["v"] * 0.1, -1.1, 40, (150, 150, 150), 5, gravity=-0.02)
                for f in fighters:
                    if f.alive and f.on_ground and abs(f.x - it["x"]) < 100 and t % 10 == 0:
                        self.pending.append((f, 3, 6, 1 if f.x >= it["x"] else -1, 10, "thud"))
            self.items = [it for it in self.items if -150 < it["x"] < WIDTH + 150]

        elif kind == "shockwave":
            if t % 200 == 0:
                fx.shake = max(fx.shake, 8)
                sounds.append(("boom", 0.5))
                for d in (-1, 1):
                    self.items.append({"x": WIDTH / 2, "dir": d, "hit": set()})
            for it in self.items:
                it["x"] += it["dir"] * 7
                if t % 3 == 0:
                    fx.add(it["x"], FLOOR_Y - 4, random.uniform(-0.5, 0.5), -1.5, 20,
                           (200, 180, 140), 4, gravity=0.05)
                for f in fighters:
                    if f.alive and f.on_ground and id(f) not in it["hit"] and abs(f.x - it["x"]) < 20:
                        it["hit"].add(id(f))
                        self.pending.append((f, 10, 6, 1 if f.x >= it["x"] else -1, 14, "thud"))
            self.items = [it for it in self.items if -40 < it["x"] < WIDTH + 40]

        elif kind == "mirror":
            if t % 120 == 0:
                from_left = random.random() < 0.5
                x = -20 if from_left else WIDTH + 20
                direction = 1 if from_left else -1
                projectiles.append(Projectile(x, FLOOR_Y - 60, direction * 9.0, 0.0, owner=None, damage=6.0,
                                              knock=4.0, kind="fireball", radius=14, life=300,
                                              color=(150, 90, 255)))
                sounds.append(("fire", 0.4))

        elif kind == "rubble":
            if t % 90 == 0:
                jitter = [random.randint(-6, 6) for _ in range(6)]
                self.items.append({"x": random.randint(80, WIDTH - 80), "t": 0, "jitter": jitter})
            for it in self.items:
                it["t"] += 1
                if it["t"] == 40:
                    fx.shake = max(fx.shake, 10)
                    fx.burst(it["x"], FLOOR_Y - 4, (170, 160, 150), 16, speed=5, life=30, size=5,
                             gravity=0.3, upward=2)
                    sounds.append(("boom", 0.6))
                    for f in fighters:
                        if f.alive and f.on_ground and abs(f.x - it["x"]) < 40:
                            self.pending.append((f, 12, 5, 1 if f.x >= it["x"] else -1, 14, "boom"))
            self.items = [it for it in self.items if it["t"] < 60]
        return sounds

    def draw(self, surf, font):
        kind = self.kind
        if kind == "lava":
            for it in self.items:
                x = int(it["x"])
                if it["t"] < 50:
                    pulse = 0.5 + 0.5 * math.sin(it["t"] * 0.5)
                    col = lerp((120, 40, 10), (255, 200, 60), pulse)
                    pygame.draw.polygon(surf, col, [(x - 60, FLOOR_Y + 8), (x + 60, FLOOR_Y + 8),
                                                    (x + 45, FLOOR_Y - 2), (x - 45, FLOOR_Y - 2)])
                else:
                    soft_glow(surf, (x, FLOOR_Y - 30), 96, ORANGE, 90)
                    for i, (w, col) in enumerate([(110, (200, 40, 10)), (84, (255, 110, 20)),
                                                  (58, (255, 190, 60)), (30, (255, 245, 200))]):
                        pygame.draw.rect(surf, col, (x - w // 2, FLOOR_Y - 94 + i * 2, w, 94 - i * 2),
                                         border_radius=10)

        elif kind == "money":
            for it in self.items:
                x, y = int(it["x"]), int(it["y"])
                pygame.draw.ellipse(surf, (16, 12, 20), (x - 15, y - 25, 30, 28))
                pygame.draw.ellipse(surf, (70, 175, 90), (x - 13, y - 23, 26, 24))
                pygame.draw.polygon(surf, (70, 175, 90),
                                    [(x - 5, y - 23), (x + 5, y - 23), (x + 2, y - 31), (x - 2, y - 31)])
                pygame.draw.ellipse(surf, (120, 220, 150), (x - 9, y - 16, 6, 9))
                text(surf, "$", font, (240, 230, 120), (x, y - 11), anchor="center", shadow=False)

        elif kind == "wind":
            for it in self.items:
                for i in range(16):
                    x = (it["t"] * 12 + i * 70) % WIDTH
                    y = 80 + (i * 37) % 360
                    pygame.draw.line(surf, (210, 230, 255), (x, y), (x + it["dir"] * 40, y + 6), 2)

        elif kind == "tractor":
            for it in self.items:
                draw_tractor(surf, it["x"], it["x"] * 0.25)

        elif kind == "shockwave":
            for it in self.items:
                x = int(it["x"])
                soft_glow(surf, (x, FLOOR_Y - 22), 46, (255, 220, 80), 100)
                pygame.draw.rect(surf, (255, 220, 80), (x - 7, FLOOR_Y - 46, 14, 46), border_radius=6)
                pygame.draw.rect(surf, (255, 255, 255), (x - 2, FLOOR_Y - 44, 4, 40))

        elif kind == "rubble":
            for it in self.items:
                x = int(it["x"])
                if it["t"] < 40:
                    grow = 0.6 + 0.4 * (it["t"] / 40)
                    pygame.draw.ellipse(surf, (20, 20, 24), (x - 40 * grow, FLOOR_Y - 6, 80 * grow, 14))
                else:
                    j = it["jitter"]
                    pts = [(x - 30, FLOOR_Y), (x - 22 + j[0], FLOOR_Y - 28), (x - 4 + j[1], FLOOR_Y - 40),
                           (x + 18 + j[2], FLOOR_Y - 34), (x + 30 + j[3], FLOOR_Y - 12), (x + 26, FLOOR_Y)]
                    pygame.draw.polygon(surf, (16, 12, 20), pts)
                    pygame.draw.polygon(surf, (168, 158, 146), [(px + (1 if i % 2 else -1), py + 1)
                                                                  for i, (px, py) in enumerate(pts)])
