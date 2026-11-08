"""Fight HUD: portraits, health bars, special meters, timer, combo counter, callouts,
round banner and the KO stamp."""

import math

import pygame

from .config import WIDTH, HEIGHT, OUTLINE, WHITE, GOLD, ROUND_BANNER_FRAMES
from .drawing import font, text, stroked, lerp, clamp, ease_out


def _bar(surf, rect, frac, ghost, color, from_right=False):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, OUTLINE, rect.inflate(6, 6), border_radius=7)
    pygame.draw.rect(surf, (52, 18, 24), rect, border_radius=5)
    for amount, col in ((ghost, (236, 236, 242)), (frac, color)):
        w = int(rect.w * clamp(amount, 0.0, 1.0))
        if w <= 0:
            continue
        x = rect.right - w if from_right else rect.x
        fill = pygame.Rect(x, rect.y, w, rect.h)
        pygame.draw.rect(surf, col, fill, border_radius=5)
        if col == color:
            pygame.draw.rect(surf, lerp(color, WHITE, 0.4), (fill.x, fill.y, fill.w, max(3, fill.h // 3)),
                             border_radius=5)
    for i in range(1, 4):
        x = rect.x + rect.w * i // 4
        pygame.draw.line(surf, OUTLINE, (x, rect.y + 2), (x, rect.bottom - 3), 2)


def _meter(surf, x, y, value, t):
    for i in range(3):
        r = pygame.Rect(x + i * 66, y, 60, 9)
        pygame.draw.rect(surf, OUTLINE, r.inflate(2, 2), border_radius=3)
        pygame.draw.rect(surf, (50, 42, 28), r, border_radius=3)
        fill = clamp(value / 100 * 3 - i, 0.0, 1.0)
        if fill > 0:
            col = (255, 214, 70)
            if value >= 100:
                col = lerp(col, WHITE, 0.5 + 0.5 * math.sin(t * 0.25))
            pygame.draw.rect(surf, col, (r.x, r.y, int(r.w * fill), r.h), border_radius=3)


def _portrait_frame(surf, img, pos, color):
    rect = pygame.Rect(pos[0], pos[1], 64, 64)
    pygame.draw.rect(surf, OUTLINE, rect.inflate(6, 6), border_radius=10)
    pygame.draw.rect(surf, (24, 20, 34), rect, border_radius=8)
    surf.blit(img, rect.topleft)
    pygame.draw.rect(surf, color, rect, 2, border_radius=8)


def draw_fight_hud(surf, player, enemy, busts, stage_label, seconds, combo, t, accent):
    p_bust, e_bust = busts
    _portrait_frame(surf, p_bust, (18, 14), (90, 170, 255))
    text(surf, "SHLOK", font(13, True), (150, 205, 255), (94, 8))
    _bar(surf, pygame.Rect(94, 26, 350, 18), player.hp / player.max_hp,
         player.ghost_hp / player.max_hp, (90, 170, 255))
    _meter(surf, 94, 50, player.meter, t)
    if player.meter >= 100:
        text(surf, "LAVA FIST READY - PRESS U", font(11, True), GOLD, (94, 62))
    if player.snare_t > 0:
        text(surf, "SNARED - MASH THE BUTTONS!", font(11, True), (150, 230, 120), (94, 76))

    _portrait_frame(surf, e_bust, (WIDTH - 82, 14), enemy.color)
    text(surf, enemy.name.upper(), font(13, True), (255, 228, 200), (WIDTH - 94, 8), anchor="topright")
    _bar(surf, pygame.Rect(WIDTH - 444, 26, 350, 18), enemy.hp / enemy.max_hp,
         enemy.ghost_hp / enemy.max_hp, enemy.color, from_right=True)
    if enemy.stage_immune():
        text(surf, "HOME TURF - STAGE IMMUNE", font(11, True), (190, 190, 210), (WIDTH - 94, 46),
             anchor="topright")
    elif enemy.stunned():
        text(surf, "EXPOSED - THE STAGE CAN HIT", font(11, True), (255, 120, 110), (WIDTH - 94, 46),
             anchor="topright")

    box = pygame.Rect(WIDTH // 2 - 34, 12, 68, 46)
    pygame.draw.rect(surf, OUTLINE, box.inflate(4, 4), border_radius=10)
    pygame.draw.rect(surf, (18, 14, 24), box, border_radius=9)
    text(surf, str(seconds), font(34, True), (255, 96, 96) if seconds <= 10 else WHITE,
         box.center, anchor="center")
    text(surf, stage_label, font(12, True), (230, 230, 240), (WIDTH // 2, 64), anchor="midtop")

    if combo >= 2:
        stroked(surf, f"{combo} HIT COMBO", font(28, True), GOLD, (30, 118), stroke=2)


def draw_callout(surf, msg, color, elapsed, life):
    """A special's name slams onto the screen, then fades out."""
    slam = clamp(1 - elapsed / 10, 0.0, 1.0)
    scale = 1.0 + 1.3 * slam
    fade = clamp((life - elapsed) / 14, 0.0, 1.0)
    band = pygame.Surface((WIDTH, 96), pygame.SRCALPHA)
    band.fill((0, 0, 0, int(120 * fade)))
    surf.blit(band, (0, 124))
    body = pygame.transform.rotozoom(font(60, True).render(msg, True, color), 0, scale)
    edge = pygame.transform.rotozoom(font(60, True).render(msg, True, OUTLINE), 0, scale)
    alpha = int(255 * fade)
    body.set_alpha(alpha)
    edge.set_alpha(alpha)
    rect = body.get_rect(center=(WIDTH // 2, 172))
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        surf.blit(edge, rect.move(dx, dy))
    surf.blit(body, rect)


def draw_round_banner(surf, elapsed, stage_name, hazard_text, accent):
    """elapsed counts up from 0 to ROUND_BANNER_FRAMES."""
    fade = clamp((ROUND_BANNER_FRAMES - elapsed) / 30, 0.0, 1.0)
    layer = pygame.Surface((WIDTH, 180), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (0, 0, 0, 190), [(0, 22), (WIDTH, 0), (WIDTH, 158), (0, 180)])
    if elapsed < 72:
        label, color = "ROUND 1", WHITE
        x = WIDTH / 2 + (1 - ease_out(elapsed / 26)) * 600
    else:
        label, color = "FIGHT!", GOLD
        x = WIDTH / 2
    text(layer, label, font(64, True), color, (x, 92), anchor="center")
    text(layer, stage_name.upper(), font(18, True), accent, (WIDTH / 2, 128), anchor="center")
    text(layer, hazard_text, font(16), (220, 220, 230), (WIDTH / 2, 152), anchor="center")
    layer.set_alpha(int(255 * fade))
    surf.blit(layer, (0, 180))


def draw_ko(surf, label, elapsed):
    scale = 1.0 + clamp((14 - elapsed) / 14, 0.0, 1.0) * 1.4
    body = pygame.transform.rotozoom(font(108, True).render(label, True, GOLD), 0, scale)
    edge = pygame.transform.rotozoom(font(108, True).render(label, True, OUTLINE), 0, scale)
    alpha = int(255 * clamp(elapsed / 8, 0.0, 1.0))
    body.set_alpha(alpha)
    edge.set_alpha(alpha)
    rect = body.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
        surf.blit(edge, rect.move(dx, dy))
    surf.blit(body, rect)
