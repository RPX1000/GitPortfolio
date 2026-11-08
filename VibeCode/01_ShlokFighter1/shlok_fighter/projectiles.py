"""Projectiles: fireballs, the Lava Fist comet, boomerang wrenches, rolling hay bales, shock
waves, falling pillars, money bags, homing void orbs and a golden beam. Every kind moves and
collides the same way, and draws its own look."""

import math

import pygame

from .config import WIDTH, FLOOR_Y, OUTLINE, WHITE
from .drawing import lerp, soft_glow, text


def _pt(a):
    return int(a[0]), int(a[1])


class Projectile:
    def __init__(self, x, y, vx, vy=0.0, owner=None, damage=8.0, knock=5.0, kind="fireball",
                 radius=14, life=260, color=(255, 140, 60), gravity=0.0, pierce=False, returns_at=None,
                 homing=0.0, target=None, max_speed=None, ground=False):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.owner = owner
        self.damage = damage
        self.knock = knock
        self.kind = kind
        self.radius = radius
        self.life = life
        self.color = color
        self.gravity = gravity
        self.pierce = pierce          # may hit each target once per pass
        self.returns_at = returns_at  # frame at which a boomerang turns back to its owner
        self.homing = homing          # how strongly it steers toward `target`
        self.target = target
        self.max_speed = max_speed
        self.ground = ground          # lands (and disappears) when it reaches the floor
        self.age = 0
        self.hit_ids = set()
        self.dead = False
        self.landed = False
        self.returning = False

    def rect(self):
        r = self.radius
        return pygame.Rect(int(self.x - r), int(self.y - r), 2 * r, 2 * r)

    def update(self):
        self.age += 1
        if self.returns_at is not None and self.age == self.returns_at:
            self.returning = True
            self.hit_ids.clear()
        if self.returning and self.owner is not None:
            gap = self.owner.x - self.x
            self.vx = math.copysign(9.0, gap) if gap else 9.0
            if abs(gap) < 30:
                self.dead = True
                return
        if self.homing and self.target is not None and not self.returning:
            dx = self.target.x - self.x
            dy = (self.target.y - 70) - self.y
            d = math.hypot(dx, dy) or 1.0
            self.vx += dx / d * self.homing
            self.vy += dy / d * self.homing
            if self.max_speed:
                speed = math.hypot(self.vx, self.vy)
                if speed > self.max_speed:
                    self.vx *= self.max_speed / speed
                    self.vy *= self.max_speed / speed
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        if self.kind == "pillar" and self.y >= FLOOR_Y - 40:
            self.y = float(FLOOR_Y - 40)
            self.landed = True
            self.dead = True
            return
        if self.ground and self.gravity and self.y >= FLOOR_Y - self.radius:
            self.y = float(FLOOR_Y - self.radius)
            self.landed = True
            self.dead = True
            return
        if self.age >= self.life or (not self.returning and not (-90 < self.x < WIDTH + 90)):
            self.dead = True

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.kind == "lava_fist":
            self._comet(surf, x, y)
        elif self.kind == "wrench":
            self._wrench(surf, x, y)
        elif self.kind == "hay":
            self._hay(surf, x, y)
        elif self.kind == "shock":
            self._shock(surf, x, y)
        elif self.kind == "pillar":
            self._pillar(surf, x, y)
        elif self.kind == "bag":
            self._bag(surf, x, y)
        elif self.kind == "beam":
            self._beam(surf, x, y)
        elif self.kind == "orb":
            self._orb(surf, x, y)
        else:
            self._fireball(surf, x, y)

    def _fireball(self, surf, x, y):
        soft_glow(surf, (x, y), 30, self.color, 110)
        pygame.draw.circle(surf, lerp(self.color, WHITE, 0.5), (x, y), 12)
        pygame.draw.circle(surf, self.color, (x, y), 8)

    def _comet(self, surf, x, y):
        """The Lava Fist: a blazing comet with a ribbon of flame behind it."""
        soft_glow(surf, (x, y), 74, (255, 110, 30), 150)
        d = 1 if self.vx >= 0 else -1
        a = self.age
        for i in range(7):
            ph = a * 0.45 + i * 1.7
            length = 26 + 16 * math.sin(ph)
            bx = x - d * (self.radius * 0.6 + i * 10)
            by = y + math.sin(ph * 1.3) * (4 + i)
            tip = (bx - d * length, by + math.sin(ph) * 6)
            half = max(3.0, self.radius * 0.45 - i * 2)
            col = (255, 150 - i * 10, 40) if i < 4 else (255, 210, 90)
            pygame.draw.polygon(surf, col, [_pt((bx, by - half)), _pt(tip), _pt((bx, by + half))])
        for i in range(4):
            sx = x - d * (18 + i * 14) + math.sin(a * 0.9 + i * 2.3) * 8
            sy = y + math.cos(a * 0.7 + i * 1.9) * 16
            pygame.draw.circle(surf, (255, 230, 150), _pt((sx, sy)), 2)
        pygame.draw.circle(surf, (255, 120, 40), (x, y), self.radius + 6)
        pygame.draw.circle(surf, (255, 190, 90), (x, y), self.radius)
        pygame.draw.circle(surf, (255, 246, 210), (x, y), max(4, int(self.radius * 0.5)))

    def _wrench(self, surf, x, y):
        ang = self.age * 0.35
        cs, sn = math.cos(ang), math.sin(ang)
        a = (x - cs * 14, y - sn * 14)
        b = (x + cs * 14, y + sn * 14)
        steel = (196, 202, 214)
        pygame.draw.line(surf, OUTLINE, _pt(a), _pt(b), 9)
        pygame.draw.line(surf, steel, _pt(a), _pt(b), 5)
        pygame.draw.circle(surf, OUTLINE, _pt(b), 10)
        pygame.draw.circle(surf, steel, _pt(b), 8)
        pygame.draw.circle(surf, (40, 36, 46), _pt((b[0] + cs * 4, b[1] + sn * 4)), 3)

    def _hay(self, surf, x, y):
        r = self.radius
        pygame.draw.circle(surf, OUTLINE, (x, y), r + 2)
        pygame.draw.circle(surf, (222, 180, 92), (x, y), r)
        rot = self.x * 0.12
        for k in range(4):
            a = rot + k * math.pi / 4
            pygame.draw.line(surf, (150, 108, 52), _pt((x + math.cos(a) * r, y + math.sin(a) * r)),
                             _pt((x - math.cos(a) * r, y - math.sin(a) * r)), 3)
        pygame.draw.circle(surf, (150, 108, 52), (x, y), 4)

    def _shock(self, surf, x, y):
        soft_glow(surf, (x, y), 46, self.color, 120)
        pygame.draw.rect(surf, self.color, (x - 8, y - self.radius, 16, self.radius * 2), border_radius=6)
        pygame.draw.rect(surf, WHITE, (x - 2, y - self.radius + 4, 4, self.radius * 2 - 8))

    def _pillar(self, surf, x, y):
        rect = pygame.Rect(x - 26, y - 40, 52, 80)
        pygame.draw.rect(surf, OUTLINE, rect.inflate(4, 4), border_radius=4)
        pygame.draw.rect(surf, (150, 140, 128), rect, border_radius=4)
        for k in range(1, 4):
            pygame.draw.line(surf, (110, 100, 92), (rect.x + k * 13, rect.y + 6), (rect.x + k * 13 - 3, rect.bottom - 14), 2)
        pygame.draw.rect(surf, (118, 108, 98), (rect.x, rect.bottom - 10, rect.w, 10), border_radius=3)

    def _bag(self, surf, x, y):
        """A money bag, tumbling as it falls."""
        spin = math.sin(self.age * 0.3) * 0.25
        pygame.draw.circle(surf, OUTLINE, (x, y), self.radius + 2)
        pygame.draw.circle(surf, (70, 175, 90), (x, y), self.radius)
        pygame.draw.circle(surf, (120, 220, 150), (int(x - 4 + spin * 6), int(y - 4)), 3)
        text(surf, "$", font_small(), (240, 230, 120), (x, y), anchor="center", shadow=False)

    def _beam(self, surf, x, y):
        """The Nak's golden beam: a long, bright bar with a glowing core."""
        d = 1 if self.vx >= 0 else -1
        tail = x - d * 120
        soft_glow(surf, (x, y), 40, self.color, 120)
        pygame.draw.line(surf, (255, 240, 170), (tail, y), (x, y), 14)
        pygame.draw.line(surf, self.color, (tail, y), (x, y), 8)
        pygame.draw.line(surf, WHITE, (tail + d * 20, y), (x - d * 6, y), 3)

    def _orb(self, surf, x, y):
        """Evil Shlok's void orb: a dark sphere with a violet glow."""
        soft_glow(surf, (x, y), 34, self.color, 140)
        pygame.draw.circle(surf, OUTLINE, (x, y), self.radius + 2)
        pygame.draw.circle(surf, (40, 16, 60), (x, y), self.radius)
        pygame.draw.circle(surf, self.color, (x, y), self.radius - 5)
        pygame.draw.circle(surf, WHITE, (x - 3, y - 3), 2)


_small = None


def font_small():
    global _small
    if _small is None:
        from .drawing import font
        _small = font(12, True)
    return _small
