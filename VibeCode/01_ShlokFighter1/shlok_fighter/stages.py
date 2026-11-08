"""Stage art. Each stage has a sky, two parallax layers (far and mid), a floor, a
foreground, animated details, and its own ambient particles.

The far and mid layers are drawn wider than the screen so they can shift a little as the
fighters move, which gives the scene depth."""

import math
import random

import pygame

from .config import WIDTH, HEIGHT, FLOOR_Y
from .drawing import lerp, soft_glow, font, text, clamp

LAYER_PAD = 120
LAYER_W = WIDTH + 2 * LAYER_PAD
LAYER_H = FLOOR_Y
FLOOR_H = HEIGHT - FLOOR_Y


def _sample(stops, t):
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1:
            return lerp(c0, c1, (t - t0) / ((t1 - t0) or 1))
    return stops[-1][1]


def _grad_rect(surf, rect, stops):
    x, y, w, h = rect
    for i in range(h):
        surf.fill(_sample(stops, i / max(1, h - 1)), (x, y + i, w, 1))


def _grad(surf, stops, height):
    _grad_rect(surf, (0, 0, surf.get_width(), height), stops)


def _ridge(surf, color, base, amp, rng, step=90):
    w, h = surf.get_size()
    pts = [(0, h)]
    x = -20
    while x <= w + step:
        pts.append((x, base - rng.uniform(0.35, 1.0) * amp))
        x += rng.randint(step // 2, step)
    pts.append((w + 20, h))
    pygame.draw.polygon(surf, color, pts)


def _towers(surf, rng, color, base, minw, maxw, minh, maxh, lit=None, chance=0.25):
    x = -20
    while x < surf.get_width():
        w = rng.randint(minw, maxw)
        h = rng.randint(minh, maxh)
        pygame.draw.rect(surf, color, (x, base - h, w, h))
        if lit:
            for wy in range(base - h + 8, base - 6, 9):
                for wx in range(x + 5, x + w - 5, 7):
                    if rng.random() < chance:
                        pygame.draw.rect(surf, lit, (wx, wy, 3, 4))
        x += w + rng.randint(2, 10)


def _palm(surf, x, base, height, color, lean=0):
    top = (x + lean, base - height)
    bend = (x + lean * 0.3 + 6, base - height * 0.55)
    pygame.draw.lines(surf, color, False, [(x, base), bend, top], 7)
    for ang, length in ((-165, 0.55), (-130, 0.5), (-90, 0.35), (-45, 0.5), (-15, 0.55), (15, 0.4)):
        rad = math.radians(ang)
        end = (top[0] + math.cos(rad) * height * length,
               top[1] + math.sin(rad) * height * length * 0.6 + height * 0.18)
        pygame.draw.line(surf, color, top, end, 6)
        mid = ((top[0] + end[0]) / 2, (top[1] + end[1]) / 2 - 8)
        pygame.draw.polygon(surf, color, [top, mid, end])


def _beam(surf, origin, angle, half_width, length, color):
    ox, oy = origin
    pts = [origin]
    for a in (angle - half_width, angle + half_width):
        pts.append((ox + math.cos(a) * length, oy + math.sin(a) * length))
    pygame.draw.polygon(surf, color, pts)


class StageArt:
    def __init__(self, info):
        self.info = info
        self.rng = random.Random(info["name"])
        self.sky = pygame.Surface((WIDTH, FLOOR_Y))
        self.far = pygame.Surface((LAYER_W, LAYER_H), pygame.SRCALPHA)
        self.mid = pygame.Surface((LAYER_W, LAYER_H), pygame.SRCALPHA)
        self.floor = pygame.Surface((WIDTH, FLOOR_H))
        self.front = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.build()
        self.sky = self.sky.convert()
        self.floor = self.floor.convert()
        self.far = self.far.convert_alpha()
        self.mid = self.mid.convert_alpha()
        self.front = self.front.convert_alpha()

    def build(self):
        pass

    def dyn_sky(self, surf, t, hazard):
        pass

    def dyn_far(self, surf, t, shift, hazard):
        pass

    def dyn_mid(self, surf, t, shift, hazard):
        pass

    def dyn_floor(self, surf, t, hazard):
        pass

    def draw_back(self, surf, t, cam=0.0, hazard=None):
        far_shift = int(clamp(-cam * 0.10, -90, 90))
        mid_shift = int(clamp(-cam * 0.25, -90, 90))
        surf.blit(self.sky, (0, 0))
        self.dyn_sky(surf, t, hazard)
        surf.blit(self.far, (-LAYER_PAD + far_shift, 0))
        self.dyn_far(surf, t, far_shift, hazard)
        surf.blit(self.mid, (-LAYER_PAD + mid_shift, 0))
        self.dyn_mid(surf, t, mid_shift, hazard)
        surf.blit(self.floor, (0, FLOOR_Y))
        self.dyn_floor(surf, t, hazard)

    def draw_front(self, surf, t):
        surf.blit(self.front, (0, 0))


class LavaLake(StageArt):
    """Santa Ana at dusk: a volcano, palms, and a glowing lava lake under the platform."""

    def build(self):
        rng = self.rng
        _grad(self.sky, [(0.0, (26, 8, 14)), (0.45, (84, 20, 22)), (0.8, (190, 64, 32)),
                         (1.0, (255, 140, 64))], FLOOR_Y)
        sx, sy = int(WIDTH * 0.68), FLOOR_Y - 130
        soft_glow(self.sky, (sx, sy), 170, (255, 150, 70), 90)
        pygame.draw.circle(self.sky, (255, 200, 130), (sx, sy), 64)
        for i in range(9):
            y = rng.randint(60, FLOOR_Y - 120)
            pygame.draw.ellipse(self.sky, lerp((120, 40, 30), (60, 20, 24), i / 9),
                                (rng.randint(-100, WIDTH), y, rng.randint(160, 320), rng.randint(14, 26)))

        _ridge(self.far, (70, 22, 26), 330, 120, rng)
        vx = LAYER_PAD + int(WIDTH * 0.2)
        volcano = [(vx - 230, LAYER_H), (vx - 46, 170), (vx - 22, 150), (vx + 22, 150),
                   (vx + 46, 170), (vx + 230, LAYER_H)]
        pygame.draw.polygon(self.far, (46, 14, 20), volcano)
        soft_glow(self.far, (vx, 150), 70, (255, 110, 40), 160)
        pygame.draw.ellipse(self.far, (255, 150, 60), (vx - 20, 142, 40, 12))
        for _ in range(160):
            pygame.draw.rect(self.far, (255, 200, 120), (rng.randint(0, LAYER_W), rng.randint(330, 380), 2, 2))

        for lx, height, lean in ((160, 230, -14), (1010, 260, 14), (1080, 190, 6)):
            _palm(self.mid, lx, LAYER_H - 4, height, (30, 10, 14), lean)

        _grad(self.floor, [(0.0, (46, 30, 34)), (0.25, (26, 18, 22)), (1.0, (12, 8, 10))], FLOOR_H)
        _grad_rect(self.floor, (0, 58, WIDTH, FLOOR_H - 58), [(0.0, (255, 130, 40)), (1.0, (150, 26, 10))])
        for _ in range(16):
            x, y = rng.randint(0, WIDTH), rng.randint(6, 50)
            pts = [(x, y)]
            for _ in range(rng.randint(2, 4)):
                x += rng.randint(-60, 60)
                y += rng.randint(-6, 8)
                pts.append((x, y))
            pygame.draw.lines(self.floor, (255, 110, 30), False, pts, 2)
            for px, py in pts[::2]:
                soft_glow(self.floor, (px, py), 12, (255, 110, 30), 80)

        f = self.front
        pygame.draw.polygon(f, (16, 10, 12), [(0, HEIGHT), (0, FLOOR_Y + 30), (40, FLOOR_Y + 60),
                                              (80, FLOOR_Y + 20), (120, HEIGHT)])
        pygame.draw.polygon(f, (16, 10, 12), [(WIDTH, HEIGHT), (WIDTH, FLOOR_Y + 40),
                                              (WIDTH - 60, FLOOR_Y + 70), (WIDTH - 110, HEIGHT)])

    def dyn_floor(self, surf, t, hazard):
        for i in range(7):
            x = (i * 139 + int(t * 0.3 * (1 + i % 2))) % WIDTH
            r = max(2, 4 + int(3 * math.sin(t * 0.05 + i)))
            y = FLOOR_Y + 62 + (i * 13) % 26
            pygame.draw.circle(surf, (255, 220, 120), (x, y), r)


class TradingFloor(StageArt):
    """A night trading floor: wall of screens, a scrolling ticker, a polished floor."""

    MONITORS = [120, 300, 480, 660, 840]

    def build(self):
        rng = self.rng
        _grad(self.sky, [(0.0, (4, 10, 20)), (1.0, (22, 38, 58))], FLOOR_Y)
        _towers(self.far, rng, (24, 38, 60), 350, 40, 90, 90, 230, lit=(255, 214, 130), chance=0.2)
        for lx in range(0, LAYER_W, 64):
            pygame.draw.line(self.mid, (38, 60, 86), (lx, 40), (lx, LAYER_H), 2)
        pygame.draw.line(self.mid, (38, 60, 86), (0, 40), (LAYER_W, 40), 2)
        for wx in self.MONITORS:
            lx = wx + LAYER_PAD
            rect = pygame.Rect(lx - 60, 150, 120, 78)
            pygame.draw.rect(self.mid, (10, 16, 26), rect, border_radius=4)
            pygame.draw.rect(self.mid, (70, 100, 130), rect, 3, border_radius=4)
            for k in range(10):
                h = rng.randint(8, 46)
                col = (90, 210, 120) if rng.random() < 0.6 else (230, 90, 90)
                pygame.draw.rect(self.mid, col, (lx - 50 + k * 10, rect.bottom - 8 - h, 6, h))
        self.ticker = font(12, True).render(
            "   SHLK +9.9%     ZZZ -1.1%     FUND +2.4%     BANDIT -0.4%     "
            "ITZAMA +3.1%     BURT -7.5%     EPSTEIN LIQUIDITY UNKNOWN      ",
            True, (120, 240, 150))

        _grad(self.floor, [(0.0, (60, 66, 82)), (0.35, (34, 38, 50)), (1.0, (16, 18, 26))], FLOOR_H)
        for wx in self.MONITORS:
            pygame.draw.rect(self.floor, (20, 32, 46), (wx - 60, 8, 120, 26))
        for x in range(-200, WIDTH + 200, 90):
            pygame.draw.line(self.floor, (58, 64, 80), (x, 0), (x - 120, FLOOR_H), 1)

    def dyn_mid(self, surf, t, shift, hazard):
        for i, wx in enumerate(self.MONITORS):
            x0 = wx - 54 + shift
            pts = [(x0 + k * 10.5, 196 + math.sin(t * 0.05 + k * 0.8 + i) * 12) for k in range(10)]
            pygame.draw.lines(surf, (110, 240, 150), False, pts, 2)
        band = pygame.Rect(0, 112, WIDTH, 16)
        pygame.draw.rect(surf, (8, 14, 20), band)
        w = self.ticker.get_width()
        x = -int((t * 1.2) % w)
        while x < WIDTH:
            surf.blit(self.ticker, (x, 113))
            x += w

    def dyn_floor(self, surf, t, hazard):
        sweep = int((t * 2) % (WIDTH + 260)) - 130
        pygame.draw.polygon(surf, (70, 80, 104), [(sweep, 0), (sweep + 60, 0), (sweep + 0, FLOOR_H),
                                                  (sweep - 60, FLOOR_H)])


class WindTunnel(StageArt):
    """A corrugated-metal garage with industrial fans that spin up when the gusts blow."""

    FANS = [int(WIDTH * 0.22), int(WIDTH * 0.78)]

    def build(self):
        for x in range(0, LAYER_W, 22):
            col = (56, 62, 76) if (x // 22) % 2 else (46, 52, 64)
            pygame.draw.rect(self.far, col, (x, 0, 22, LAYER_H))
        _grad(self.sky, [(0.0, (20, 24, 32)), (1.0, (58, 64, 80))], FLOOR_Y)
        for lx in (LAYER_PAD + 160, LAYER_PAD + 480, LAYER_PAD + 800):
            pygame.draw.rect(self.far, (70, 70, 80), (lx - 30, 46, 60, 12))
            soft_glow(self.far, (lx, 60), 60, (255, 236, 190), 120)
        for fx_ in self.FANS:
            lx = fx_ + LAYER_PAD
            pygame.draw.circle(self.far, (16, 18, 22), (lx, 230), 98)
            pygame.draw.circle(self.far, (50, 54, 62), (lx, 230), 90)
        for wx in (40, 820):
            lx = wx + LAYER_PAD
            pygame.draw.rect(self.mid, (120, 84, 50), (lx, 330, 90, 96))
            pygame.draw.rect(self.mid, (120, 84, 50), (lx + 12, 290, 70, 40))
            for k in range(3):
                pygame.draw.line(self.mid, (84, 56, 32), (lx, 346 + k * 26), (lx + 90, 346 + k * 26), 2)
        text(self.mid, "WIND TUNNEL - DO NOT BLOCK", font(22, True), (230, 200, 60),
             (LAYER_PAD + WIDTH // 2, 110), anchor="center", shadow=False)

        _grad(self.floor, [(0.0, (120, 122, 128)), (1.0, (70, 72, 78))], FLOOR_H)
        for x in range(0, WIDTH, 96):
            pygame.draw.line(self.floor, (60, 62, 68), (x, 0), (x - 20, FLOOR_H), 2)
        for y in (30, 62, 96):
            pygame.draw.line(self.floor, (60, 62, 68), (0, y), (WIDTH, y), 2)
        pygame.draw.rect(self.floor, (255, 200, 60), (0, 0, WIDTH, 5))
        for _ in range(10):
            pygame.draw.ellipse(self.floor, (44, 44, 50), (self.rng.randint(0, WIDTH), self.rng.randint(10, 80),
                                                           self.rng.randint(40, 90), 14))

    def dyn_far(self, surf, t, shift, hazard):
        gust = bool(hazard is not None and getattr(hazard, "items", None))
        speed = 0.6 if gust else 0.18
        for fx_ in self.FANS:
            cx, cy = fx_ + shift, 230
            for k in range(4):
                a = t * speed + k * math.pi / 2
                pygame.draw.line(surf, (150, 160, 170), (cx + math.cos(a) * 80, cy + math.sin(a) * 80),
                                 (cx - math.cos(a) * 80, cy - math.sin(a) * 80), 10)
            pygame.draw.circle(surf, (60, 64, 72), (cx, cy), 14)


class CornField(StageArt):
    """Golden hour on a farm: rolling hills, a red barn, rows of corn and a dirt road."""

    def build(self):
        rng = self.rng
        _grad(self.sky, [(0.0, (92, 150, 214)), (0.55, (180, 214, 236)), (0.88, (250, 222, 164)),
                         (1.0, (255, 190, 120))], FLOOR_Y)
        soft_glow(self.sky, (int(WIDTH * 0.28), FLOOR_Y - 190), 180, (255, 240, 190), 120)
        pygame.draw.circle(self.sky, (255, 236, 170), (int(WIDTH * 0.28), FLOOR_Y - 190), 54)
        self.cloud = pygame.Surface((160, 56), pygame.SRCALPHA)
        for ox, oy, w, h in ((0, 16, 110, 30), (40, 6, 90, 36), (84, 20, 70, 26)):
            pygame.draw.ellipse(self.cloud, (255, 255, 255, 170), (ox, oy, w, h))

        _ridge(self.far, (120, 150, 140), 350, 60, rng)
        _ridge(self.far, (92, 130, 110), 372, 36, rng)
        lx = LAYER_PAD + int(WIDTH * 0.7)
        pygame.draw.rect(self.far, (150, 46, 40), (lx - 60, 232, 120, 66))
        pygame.draw.polygon(self.far, (80, 40, 40), [(lx - 72, 232), (lx, 184), (lx + 72, 232)])
        pygame.draw.rect(self.far, (230, 230, 236), (lx - 60, 232, 120, 6))
        pygame.draw.rect(self.far, (100, 30, 28), (lx - 14, 258, 28, 40))
        pygame.draw.rect(self.far, (200, 200, 210), (lx + 90, 200, 36, 98))
        pygame.draw.circle(self.far, (200, 200, 210), (lx + 108, 200), 18)

        for k in range(9):
            base = 296 + k * 15
            height = 20 + k * 6
            step = max(6, 15 - k)
            for x in range(0, LAYER_W, step):
                top_x = x + rng.randint(-3, 3)
                pygame.draw.line(self.mid, (80, 122, 52), (x, base), (top_x, base - height), 3)
                leaf_y = base - height * 0.5
                pygame.draw.polygon(self.mid, (96, 150, 60),
                                    [(x, leaf_y), (x - 7, leaf_y - 6), (x, leaf_y + 4)])

        _grad(self.floor, [(0.0, (96, 148, 64)), (1.0, (60, 100, 40))], FLOOR_H)
        pygame.draw.polygon(self.floor, (160, 118, 74), [(WIDTH // 2 - 70, 0), (WIDTH // 2 + 70, 0),
                                                         (WIDTH - 40, FLOOR_H), (40, FLOOR_H)])
        pygame.draw.line(self.floor, (120, 86, 52), (WIDTH // 2 - 30, 0), (60, FLOOR_H), 3)
        pygame.draw.line(self.floor, (120, 86, 52), (WIDTH // 2 + 30, 0), (WIDTH - 60, FLOOR_H), 3)

        for x in range(0, 120, 12):
            top = (x + rng.randint(-10, 10), HEIGHT - rng.randint(60, 110))
            pygame.draw.line(self.front, (210, 170, 80), (x, HEIGHT), top, 2)
            pygame.draw.ellipse(self.front, (230, 190, 100), (top[0] - 3, top[1] - 8, 6, 14))
        for x in range(WIDTH - 120, WIDTH, 12):
            top = (x + rng.randint(-10, 10), HEIGHT - rng.randint(60, 110))
            pygame.draw.line(self.front, (210, 170, 80), (x, HEIGHT), top, 2)
            pygame.draw.ellipse(self.front, (230, 190, 100), (top[0] - 3, top[1] - 8, 6, 14))

    def dyn_sky(self, surf, t, hazard):
        for i in range(5):
            x = int((i * 260 + t * 0.25) % (WIDTH + 240)) - 120
            surf.blit(self.cloud, (x, 50 + (i * 47) % 110))


class Arena(StageArt):
    """A night arena with stands full of cheering lights, spotlights and rune-marked walls."""

    def build(self):
        rng = self.rng
        _grad(self.sky, [(0.0, (16, 6, 32)), (0.6, (80, 28, 88)), (1.0, (255, 168, 86))], FLOOR_Y)
        soft_glow(self.sky, (int(WIDTH * 0.8), 90), 80, (255, 240, 200), 110)
        pygame.draw.circle(self.sky, (255, 240, 200), (int(WIDTH * 0.8), 90), 26)

        self.crowd = []
        for tier in range(5):
            y_top = 210 + tier * 22
            col = lerp((46, 18, 60), (90, 36, 80), tier / 4)
            pygame.draw.rect(self.far, col, (0, y_top, LAYER_W, 40))
            for x in range(0, LAYER_W, 9):
                y = y_top + rng.randint(2, 8)
                self.crowd.append((x, y))
                pygame.draw.circle(self.far, (255, 210, 130), (x, y), 2)
        for x in range(60, LAYER_W, 170):
            pygame.draw.rect(self.far, (255, 90, 120) if (x // 170) % 2 else (90, 200, 255), (x, 200, 14, 50))

        pygame.draw.rect(self.mid, (70, 46, 76), (0, 330, LAYER_W, 110))
        pygame.draw.rect(self.mid, (255, 220, 80), (0, 364, LAYER_W, 5))
        for x in range(0, LAYER_W, 24):
            pygame.draw.line(self.mid, (150, 100, 50), (x, 384), (x + 8, 378), 2)
        for x in range(60, LAYER_W, 240):
            pygame.draw.rect(self.mid, (84, 58, 90), (x, 230, 26, 210))
            pygame.draw.rect(self.mid, (110, 80, 116), (x - 6, 226, 38, 10))

        _grad(self.floor, [(0.0, (40, 24, 44)), (1.0, (18, 10, 24))], FLOOR_H)
        cx, cy = WIDTH // 2, 10
        for i in range(9):
            rx, ry = 480 - i * 48, 90 - i * 9
            pygame.draw.ellipse(self.floor, lerp((60, 36, 58), (120, 80, 80), i / 8),
                                (cx - rx, cy - ry, rx * 2, ry * 2))
        for ring in range(1, 9):
            rx, ry = 480 - ring * 48, 90 - ring * 9
            pygame.draw.ellipse(self.floor, (150, 110, 60), (cx - rx, cy - ry, rx * 2, ry * 2), 2)
        for k in range(-4, 5):
            pygame.draw.line(self.floor, (100, 64, 88), (cx, cy), (cx + k * 140, FLOOR_H), 2)
        self.beams = pygame.Surface((WIDTH, FLOOR_Y), pygame.SRCALPHA)

    def dyn_sky(self, surf, t, hazard):
        self.beams.fill((0, 0, 0, 0))
        sweep = math.sin(t * 0.012) * 0.35
        _beam(self.beams, (0, 0), math.pi / 2 - 0.6 + sweep, 0.08, 900, (255, 220, 120, 46))
        _beam(self.beams, (WIDTH, 0), math.pi / 2 + 0.6 - sweep, 0.08, 900, (255, 220, 120, 46))
        surf.blit(self.beams, (0, 0))

    def dyn_far(self, surf, t, shift, hazard):
        for i, (x, y) in enumerate(self.crowd):
            if (i + int(t * 0.2)) % 7 == 0:
                pygame.draw.circle(surf, (255, 250, 210), (x - LAYER_PAD + shift, y), 3)


class MirrorDimension(StageArt):
    """A synthwave sun, mirror panels, and a neon grid floor that scrolls toward you."""

    SKY = [(0.0, (8, 2, 22)), (0.5, (44, 10, 70)), (0.85, (170, 40, 130)), (1.0, (255, 110, 160))]

    def build(self):
        rng = self.rng
        _grad(self.sky, self.SKY, FLOOR_Y)
        cx, cy, r = WIDTH // 2, FLOOR_Y - 150, 120
        for y in range(cy - r, cy + r):
            half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            col = lerp((255, 210, 120), (255, 70, 140), (y - (cy - r)) / (2 * r))
            pygame.draw.line(self.sky, col, (cx - half, y), (cx + half, y))
        for k in range(6):
            sy = cy + 12 + k * k * 4
            pygame.draw.rect(self.sky, _sample(self.SKY, sy / FLOOR_Y), (cx - r - 2, sy, 2 * r + 4, 2 + k))

        for i in range(12):
            x = i * 120 - 40 + LAYER_PAD
            h = rng.randint(90, 200)
            pts = [(x, 350), (x + 60, 350 - h), (x + 120, 350)]
            pygame.draw.polygon(self.far, (40, 10, 60), pts)
            pygame.draw.lines(self.far, (200, 90, 200), False, pts[:2], 2)

        self.shards = []
        for wx in (90, 290, 670, 870):
            lx = wx + LAYER_PAD
            pygame.draw.rect(self.mid, (30, 12, 46), (lx - 40, 120, 80, 290))
            pygame.draw.rect(self.mid, (160, 90, 200), (lx - 40, 120, 80, 290), 3)
            pygame.draw.line(self.mid, (120, 80, 160), (lx - 30, 130), (lx + 10, 250), 3)
            pygame.draw.line(self.mid, (120, 80, 160), (lx - 20, 262), (lx + 30, 190), 3)
        for _ in range(7):
            self.shards.append((rng.randint(160, WIDTH - 160), rng.randint(150, 300), rng.uniform(0, 6)))

        _grad(self.floor, [(0.0, (16, 6, 30)), (1.0, (8, 2, 18))], FLOOR_H)
        for x in range(-WIDTH, 2 * WIDTH, 80):
            pygame.draw.line(self.floor, (120, 40, 200), (WIDTH // 2, 0), (x, FLOOR_H), 1)

    def dyn_mid(self, surf, t, shift, hazard):
        for x, y, phase in self.shards:
            bob = math.sin(t * 0.03 + phase) * 6
            cx, cy = x + shift, y + bob
            pts = [(cx, cy - 16), (cx + 10, cy), (cx, cy + 16), (cx - 10, cy)]
            pygame.draw.polygon(surf, (200, 140, 255), pts)
            pygame.draw.polygon(surf, (255, 220, 255), pts, 2)

    def dyn_floor(self, surf, t, hazard):
        z0, dz, n = 1.0, 0.25, 24
        for i in range(n):
            z = z0 + ((i * dz - t * 0.004) % (n * dz))
            y = FLOOR_Y + int(FLOOR_H * z0 / z)
            col = (255, 70, 200) if i % 2 else (70, 220, 255)
            pygame.draw.line(surf, col, (0, y), (WIDTH, y), 1)


class IslandRuins(StageArt):
    """Sunset over the sea, with broken columns, vines and sunlight glinting on the water."""

    def build(self):
        rng = self.rng
        _grad(self.sky, [(0.0, (34, 64, 104)), (0.7, (230, 140, 110)), (1.0, (255, 196, 128))], FLOOR_Y)
        soft_glow(self.sky, (WIDTH // 2, FLOOR_Y - 20), 150, (255, 210, 150), 90)
        pygame.draw.circle(self.sky, (255, 216, 150), (WIDTH // 2, FLOOR_Y - 20), 96)

        _grad_rect(self.far, (0, 378, LAYER_W, 62), [(0.0, (60, 130, 150)), (1.0, (24, 70, 98))])
        for _ in range(7):
            x = rng.randint(0, LAYER_W)
            pygame.draw.ellipse(self.far, (78, 74, 104), (x, 356, rng.randint(120, 220), rng.randint(20, 34)))

        for lx in (LAYER_PAD + 120, LAYER_PAD + 340, LAYER_PAD + 600, LAYER_PAD + 820):
            pygame.draw.rect(self.mid, (110, 96, 96), (lx, 230, 30, 170))
            for k in range(1, 4):
                pygame.draw.line(self.mid, (84, 72, 74), (lx + k * 7, 236), (lx + k * 7, 396), 2)
            pygame.draw.rect(self.mid, (124, 110, 110), (lx - 6, 222, 42, 10))
        for lx in (LAYER_PAD + 120, LAYER_PAD + 600):
            pygame.draw.arc(self.mid, (110, 96, 96), (lx + 30, 240, 160, 120), 0, math.pi, 8)
        for x in range(0, LAYER_W, 46):
            end = (x + rng.randint(-6, 6), rng.randint(60, 140))
            pygame.draw.line(self.mid, (50, 100, 60), (x, 0), end, 2)
            pygame.draw.ellipse(self.mid, (70, 120, 70), (end[0] - 6, end[1] - 4, 12, 8))

        _grad(self.floor, [(0.0, (128, 108, 94)), (1.0, (72, 58, 50))], FLOOR_H)
        for x in range(0, WIDTH, 96):
            pygame.draw.line(self.floor, (60, 48, 42), (x, 0), (x - 20, FLOOR_H), 2)
        for y in (24, 58, 96):
            pygame.draw.line(self.floor, (60, 48, 42), (0, y), (WIDTH, y), 2)
        for _ in range(8):
            x, y = rng.randint(0, WIDTH), rng.randint(10, 80)
            pts = [(x, y), (x + rng.randint(-40, 40), y + rng.randint(-8, 8)),
                   (x + rng.randint(-60, 60), y + rng.randint(-10, 10))]
            pygame.draw.lines(self.floor, (40, 32, 28), False, pts, 2)
        for _ in range(6):
            pygame.draw.ellipse(self.floor, (70, 110, 60), (rng.randint(0, WIDTH), rng.randint(8, 80), 60, 14))

        pygame.draw.polygon(self.front, (50, 42, 42), [(0, HEIGHT), (0, FLOOR_Y + 40), (30, FLOOR_Y + 30),
                                                       (70, FLOOR_Y + 60), (110, HEIGHT)])
        pygame.draw.polygon(self.front, (50, 42, 42), [(WIDTH, HEIGHT), (WIDTH - 90, HEIGHT),
                                                       (WIDTH - 50, FLOOR_Y + 50), (WIDTH, FLOOR_Y + 20)])

    def dyn_far(self, surf, t, shift, hazard):
        for k in range(36):
            x = int((k * 71 + t * 0.9 * (1 + k % 3)) % WIDTH)
            y = FLOOR_Y - 60 + (k * 17) % 56
            pygame.draw.line(surf, (210, 236, 240), (x + shift, y), (x + shift + 12, y), 2)


STAGE_CLASSES = {
    "lava": LavaLake,
    "money": TradingFloor,
    "wind": WindTunnel,
    "tractor": CornField,
    "shockwave": Arena,
    "mirror": MirrorDimension,
    "rubble": IslandRuins,
}


def make_stage(info):
    return STAGE_CLASSES[info["hazard"]](info)


def build_vignette():
    v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(0, 90, 3):
        a = int(150 * (1 - i / 90) ** 2)
        pygame.draw.rect(v, (0, 0, 0, a), (i, i, WIDTH - 2 * i, HEIGHT - 2 * i), 3)
    return v.convert_alpha()


def spawn_ambient(kind, fx):
    """Adds drifting particles that suit each stage. Called once per frame."""
    r = random.random
    if r() > 0.5:
        return
    if kind == "lava":
        fx.add(random.randint(0, WIDTH), FLOOR_Y + random.randint(70, 110), random.uniform(-0.3, 0.3),
               random.uniform(-1.8, -0.7), random.randint(80, 140), (255, 150, 50), 2, gravity=-0.005)
    elif kind == "money":
        fx.add(random.randint(0, WIDTH), -10, random.uniform(-0.4, 0.4), random.uniform(1.0, 1.8), 200,
               random.choice([(90, 210, 120), (240, 200, 80)]), 2)
    elif kind == "wind":
        fx.add(-10 if r() < 0.5 else WIDTH + 10, random.randint(60, FLOOR_Y - 40),
               random.choice((-1, 1)) * random.uniform(4, 7), random.uniform(-0.5, 0.5), 120,
               (210, 230, 180), 2)
    elif kind == "tractor":
        fx.add(random.randint(0, WIDTH), FLOOR_Y - 4, random.uniform(-0.5, 0.5), random.uniform(-1.5, -0.6),
               70, (230, 200, 90), 2, gravity=0.02)
    elif kind == "shockwave":
        fx.add(random.randint(0, WIDTH), FLOOR_Y - 2, random.uniform(-0.2, 0.2), random.uniform(-0.8, -0.2),
               60, (255, 230, 120), 2)
    elif kind == "mirror":
        fx.add(random.randint(0, WIDTH), random.randint(60, FLOOR_Y - 40), random.uniform(-0.2, 0.2),
               random.uniform(-0.6, -0.2), 140, (170, 110, 255), 2)
    elif kind == "rubble":
        fx.add(random.randint(0, WIDTH), random.randint(0, 120), random.uniform(-0.3, 0.3),
               random.uniform(0.4, 0.9), 160, (190, 180, 150), 2)
