"""Particles, impact sparks, shock rings, floating text, screen shake and screen flashes."""

import math
import random

import pygame

from .config import OUTLINE


class Effects:
    def __init__(self):
        self.parts = []
        self.texts = []
        self.rings = []
        self.sparks = []
        self.shake = 0
        self.flash_color = (255, 255, 255)
        self.flash_alpha = 0

    def add(self, x, y, vx, vy, life, color, size, gravity=0.0):
        self.parts.append([x, y, vx, vy, life, life, color, size, gravity])

    def burst(self, x, y, color, n=8, speed=4.0, life=22, size=4, gravity=0.25, upward=0.0):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(0.3, 1.0) * speed
            self.add(x, y, math.cos(ang) * sp, math.sin(ang) * sp - upward,
                     random.randint(max(1, life // 2), life), color, size, gravity)

    def spark(self, x, y, color, size=14, life=8):
        """A four-point star at an impact point."""
        self.sparks.append([float(x), float(y), life, life, float(size), color])

    def ring(self, x, y, color, max_r=120, life=22, width=6):
        """An expanding shock ring that thins out as it fades."""
        self.rings.append([float(x), float(y), 4.0, float(max_r), life, life, color, width])

    def text(self, x, y, msg, color):
        self.texts.append([x, y, msg, color, 46, 46])

    def flash(self, color, alpha=120):
        self.flash_color = color
        self.flash_alpha = alpha

    def update(self):
        for p in self.parts:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += p[8]
            p[4] -= 1
        self.parts = [p for p in self.parts if p[4] > 0]
        for s in self.sparks:
            s[2] -= 1
        self.sparks = [s for s in self.sparks if s[2] > 0]
        for r in self.rings:
            r[2] += (r[3] - r[2]) * 0.22 + 0.6
            r[4] -= 1
        self.rings = [r for r in self.rings if r[4] > 0]
        for t in self.texts:
            t[1] -= 0.8
            t[4] -= 1
        self.texts = [t for t in self.texts if t[4] > 0]
        if self.shake:
            self.shake -= 1
        if self.flash_alpha:
            self.flash_alpha = max(0, self.flash_alpha - 10)

    def draw(self, surf, font):
        for x, y, _vx, _vy, life, max_life, color, size, _g in self.parts:
            pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(size * life / max_life)))
        for x, y, life, max_life, size, color in self.sparks:
            r = size * (0.4 + 0.6 * life / max_life)
            pts = []
            for k in range(8):
                ang = k * math.pi / 4 - math.pi / 2
                rad = r if k % 2 == 0 else r * 0.28
                pts.append((x + math.cos(ang) * rad, y + math.sin(ang) * rad))
            pygame.draw.polygon(surf, color, pts)
        for x, y, r, _max_r, life, max_life, color, width in self.rings:
            w = max(1, int(width * life / max_life))
            pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(r)), w)
        for x, y, msg, color, life, max_life in self.texts:
            alpha = int(255 * life / max_life)
            img = font.render(msg, True, color)
            shadow = font.render(msg, True, OUTLINE)
            img.set_alpha(alpha)
            shadow.set_alpha(alpha)
            surf.blit(shadow, (int(x) + 2, int(y) + 2))
            surf.blit(img, (int(x), int(y)))

    def draw_flash(self, surf):
        if self.flash_alpha > 0:
            layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            layer.fill((*self.flash_color, self.flash_alpha))
            surf.blit(layer, (0, 0))
