"""Drawing helpers: fonts, text, glows, panels, key caps and a supersampled canvas
that gives the fighter art smooth, anti-aliased outlines."""

import math

import pygame

from .config import WHITE, OUTLINE

FONT_NAMES = "avenirnext,helveticaneue,arial"
_fonts = {}
_glows = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(FONT_NAMES, size, bold=bold)
    return _fonts[key]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def tint(c, amount):
    return lerp(c, WHITE, max(0.0, min(1.0, amount)))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_out(t):
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def grow(points, amount):
    """Push a polygon's points outward from its centre. Used to draw outlines."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        length = math.hypot(dx, dy) or 1.0
        out.append((x + dx / length * amount, y + dy / length * amount))
    return out


def text(surf, s, f, color, pos, anchor="topleft", shadow=True):
    img = f.render(s, True, color)
    rect = img.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    if shadow:
        surf.blit(f.render(s, True, OUTLINE), rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def stroked(surf, s, f, color, pos, anchor="topleft", stroke=3, stroke_color=OUTLINE):
    """Text with a thick outline, for logos and big headings."""
    img = f.render(s, True, color)
    edge = f.render(s, True, stroke_color)
    rect = img.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    for dx in (-stroke, 0, stroke):
        for dy in (-stroke, 0, stroke):
            if dx or dy:
                surf.blit(edge, rect.move(dx, dy))
    surf.blit(img, rect)
    return rect


def soft_glow(surf, pos, radius, color, alpha=80):
    key = (radius, color, alpha)
    glow = _glows.get(key)
    if glow is None:
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for i in range(radius, 0, -2):
            a = int(alpha * (1 - i / radius) ** 1.5)
            pygame.draw.circle(glow, (*color, a), (radius, radius), i)
        _glows[key] = glow
    surf.blit(glow, (int(pos[0]) - radius, int(pos[1]) - radius))


def dim(surf, alpha):
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    layer.fill((0, 0, 0, alpha))
    surf.blit(layer, (0, 0))


def panel(surf, rect, color=(12, 9, 18), alpha=200, radius=14, border=None, border_w=2):
    rect = pygame.Rect(rect)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, alpha), layer.get_rect(), border_radius=radius)
    surf.blit(layer, rect.topleft)
    if border:
        pygame.draw.rect(surf, border, rect, border_w, border_radius=radius)


def keycap(surf, rect, label, f):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, (6, 5, 10), rect.move(0, 3), border_radius=8)
    pygame.draw.rect(surf, (96, 92, 116), rect, border_radius=8)
    pygame.draw.rect(surf, (128, 124, 150), rect.inflate(-6, -8).move(0, -1), border_radius=6)
    text(surf, label, f, WHITE, rect.center, anchor="center", shadow=False)


class Canvas:
    """Draws in world coordinates onto a supersampled transparent surface, then
    shrinks it back down. The shrink averages edge pixels, so outlines look smooth."""

    def __init__(self, x0, y0, w, h, ss=2):
        self.x0, self.y0, self.w, self.h, self.ss = x0, y0, w, h, ss
        self.surf = pygame.Surface((int(w * ss), int(h * ss)), pygame.SRCALPHA)

    def pt(self, p):
        return (int(round((p[0] - self.x0) * self.ss)), int(round((p[1] - self.y0) * self.ss)))

    def polygon(self, pts, color):
        pygame.draw.polygon(self.surf, color, [self.pt(p) for p in pts])

    def circle(self, c, r, color):
        pygame.draw.circle(self.surf, color, self.pt(c), max(1, int(round(r * self.ss))))

    def line(self, a, b, w, color):
        pygame.draw.line(self.surf, color, self.pt(a), self.pt(b), max(1, int(round(w * self.ss))))

    def ellipse(self, rect, color):
        x, y, w, h = rect
        r = (int(round((x - self.x0) * self.ss)), int(round((y - self.y0) * self.ss)),
             int(round(w * self.ss)), int(round(h * self.ss)))
        pygame.draw.ellipse(self.surf, color, r)

    def image(self):
        return pygame.transform.smoothscale(self.surf, (int(self.w), int(self.h)))
