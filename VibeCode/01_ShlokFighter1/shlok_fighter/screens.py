"""Menus and full-screen pages: title, controls, story cards, pre-fight dialogue, pause,
results and the ending."""

import math
import textwrap

import pygame

from .config import (WIDTH, HEIGHT, FLOOR_Y, GOLD, WHITE, MUTED, OUTLINE, CONTROLS, ENDING_STORY,
                     VERSION, PLAYER, ENEMIES)
from .drawing import font, text, stroked, panel, keycap, dim, lerp, grow
from .sprites import draw_fighter, draw_shadow, actor


def blink_color(t):
    v = 255 if (t // 30) % 2 == 0 else 170
    return (v, v, v)


class Menu:
    def __init__(self, items):
        self.items = [list(item) for item in items]  # each item is [label, action]
        self.sel = 0

    def move(self, step):
        self.sel = (self.sel + step) % len(self.items)

    def action(self):
        return self.items[self.sel][1]

    def relabel(self, action, label):
        for item in self.items:
            if item[1] == action:
                item[0] = label

    def draw(self, surf, center_x, top, spacing=50):
        f = font(26, True)
        for i, (label, _action) in enumerate(self.items):
            y = top + i * spacing
            rect = pygame.Rect(0, 0, 300, 40)
            rect.center = (center_x, y)
            if i == self.sel:
                panel(surf, rect, (40, 28, 10), 220, 12, border=GOLD, border_w=2)
                pygame.draw.polygon(surf, GOLD, [(rect.left - 20, y - 8), (rect.left - 8, y), (rect.left - 20, y + 8)])
                pygame.draw.polygon(surf, GOLD, [(rect.right + 20, y - 8), (rect.right + 8, y), (rect.right + 20, y + 8)])
                color = GOLD
            else:
                panel(surf, rect, (12, 9, 18), 150, 12)
                color = (226, 226, 236)
            text(surf, label, f, color, (center_x, y), anchor="center", shadow=False)


def story_lines(info):
    lines = [(s, WHITE) for s in textwrap.wrap(info["intro"], 52)]
    lines += [(s, info["accent"]) for s in textwrap.wrap(info["hazard_text"], 52)]
    return lines


def ending_lines():
    return [(s, WHITE) for s in textwrap.wrap(ENDING_STORY, 46)]


def draw_title(surf, art, t, menu):
    art.draw_back(surf, t, 0, None)
    dim(surf, 110)
    stroked(surf, "SHLOK", font(104, True), GOLD, (WIDTH // 2, 30), anchor="midtop", stroke=5)
    stroked(surf, "FIGHTER 1", font(50, True), WHITE, (WIDTH // 2, 132), anchor="midtop", stroke=4)
    text(surf, "THE GAME", font(18, True), (240, 200, 140), (WIDTH // 2, 196), anchor="midtop")
    pygame.draw.line(surf, GOLD, (WIDTH // 2 - 160, 224), (WIDTH // 2 + 160, 224), 2)

    hero = actor(PLAYER, 200, 1, feet=FLOOR_Y + 6, walk_t=t)
    rival = actor(ENEMIES[0], WIDTH - 200, -1, feet=FLOOR_Y + 6, walk_t=t + 20)
    draw_shadow(surf, 200)
    draw_fighter(surf, hero)
    draw_shadow(surf, WIDTH - 200)
    draw_fighter(surf, rival)

    menu.draw(surf, WIDTH // 2, 284, spacing=46)
    text(surf, "W / S choose     ENTER select     M sound     F fullscreen", font(14), MUTED,
         (WIDTH // 2, HEIGHT - 16), anchor="midbottom")
    text(surf, f"v{VERSION}", font(13), MUTED, (14, HEIGHT - 14), anchor="bottomleft")


def draw_controls(surf, art, t):
    art.draw_back(surf, t, 0, None)
    dim(surf, 160)
    panel(surf, (WIDTH // 2 - 440, 40, 880, 470), (12, 9, 18), 225, 18, border=(80, 70, 100), border_w=2)
    text(surf, "CONTROLS", font(40, True), GOLD, (WIDTH // 2, 58), anchor="midtop")
    y = 128
    for key, action in CONTROLS:
        keycap(surf, (WIDTH // 2 - 410, y - 13, 140, 26), key, font(15, True))
        text(surf, action, font(21), (230, 230, 240), (WIDTH // 2 - 240, y), anchor="midleft")
        y += 28
    text(surf, "Press ESC or ENTER to go back", font(16), MUTED, (WIDTH // 2, 468), anchor="midtop")


def draw_select(surf, art, t, sel, busts):
    """A prototyping screen: pick any boss and jump straight into that fight."""
    art.draw_back(surf, t, 0, None)
    dim(surf, 150)
    panel(surf, (WIDTH // 2 - 360, 40, 720, 470), (12, 9, 18), 225, 18, border=(80, 70, 100), border_w=2)
    text(surf, "CHOOSE YOUR OPPONENT", font(32, True), GOLD, (WIDTH // 2, 56), anchor="midtop")
    top, row_h = 108, 50
    for i, info in enumerate(ENEMIES):
        row = pygame.Rect(WIDTH // 2 - 330, top + i * row_h, 660, row_h - 8)
        picked = i == sel
        if picked:
            panel(surf, row, (40, 28, 10), 220, 12, border=GOLD, border_w=2)
            color = GOLD
        else:
            panel(surf, row, (16, 12, 22), 150, 12)
            color = (226, 226, 236)
        surf.blit(busts[i], (row.x + 5, row.y + (row.h - busts[i].get_height()) // 2))
        text(surf, f"{i + 1}. {info['name']}", font(19, True), color, (row.x + 54, row.y + 4))
        text(surf, info["stage"], font(12), MUTED, (row.x + 54, row.y + 24))
        stats = f"HP {info['hp']}   SKILL {info['skill']:.2f}"
        text(surf, stats, font(12), color if picked else MUTED, (row.right - 10, row.top + row.h / 2),
             anchor="midright")
    text(surf, "W / S choose     ENTER fight     ESC back", font(16, True), (240, 200, 140),
         (WIDTH // 2, 468), anchor="midtop")


def draw_story(surf, art, t, index, portrait_img, typewriter, info):
    art.draw_back(surf, t, 0, None)
    dim(surf, 150)
    panel(surf, (60, 120, 320, 340), (10, 8, 16), 190, 18, border=info["color"], border_w=2)
    surf.blit(portrait_img, portrait_img.get_rect(center=(220, 292)))
    panel(surf, (396, 112, 530, 344), (8, 8, 14), 185, 18)

    name_color = lerp(info["color"], WHITE, 0.35)
    text(surf, f"STAGE {index + 1} OF {len(ENEMIES)}", font(14, True), MUTED, (420, 122))
    text(surf, info["name"].upper(), font(44, True), name_color, (420, 142))
    text(surf, info["stage"], font(26, True), WHITE, (420, 196))
    y = 248
    for line, color in typewriter.visible():
        if line:
            text(surf, line, font(21), color, (420, y))
        y += 28
    prompt = "PRESS ENTER TO CONTINUE" if typewriter.done else "PRESS ENTER TO SKIP"
    text(surf, prompt, font(22, True), blink_color(t), (420, 470))

    dot_x = 220 - (len(ENEMIES) - 1) * 9
    for i in range(len(ENEMIES)):
        center = (dot_x + i * 18, 482)
        if i <= index:
            pygame.draw.circle(surf, GOLD, center, 5)
        else:
            pygame.draw.circle(surf, OUTLINE, center, 5, 2)


def _bubble(surf, box, tail, left):
    base = box.left + 40 if left else box.right - 40
    pts = [(base - 14, box.bottom - 2), (base + 14, box.bottom - 2), tail]
    pygame.draw.polygon(surf, OUTLINE, grow(pts, 3))
    pygame.draw.rect(surf, OUTLINE, box.inflate(6, 6), border_radius=18)
    pygame.draw.polygon(surf, (250, 248, 240), pts)
    pygame.draw.rect(surf, (250, 248, 240), box, border_radius=16)


def draw_dialogue(surf, art, t, dlg, imgs, info):
    """Pre-fight exchange: both fighters face off, the speaker is lit and talks in a bubble."""
    art.draw_back(surf, t, 0, None)
    dim(surf, 120)
    split = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    mid = WIDTH // 2
    pygame.draw.polygon(split, (70, 130, 255, 40), [(0, 0), (mid + 70, 0), (mid - 70, HEIGHT), (0, HEIGHT)])
    pygame.draw.polygon(split, (*info["color"], 50), [(mid + 70, 0), (WIDTH, 0), (WIDTH, HEIGHT), (mid - 70, HEIGHT)])
    surf.blit(split, (0, 0))
    stroked(surf, "VS", font(46, True), GOLD, (WIDTH // 2, 14), anchor="midtop", stroke=3)
    text(surf, info["stage"].upper(), font(15, True), MUTED, (WIDTH // 2, 70), anchor="midtop")

    hero_turn = dlg.speaker == "hero"
    bob = math.sin(t * 0.18) * 5
    hero_y = 150 - (bob if hero_turn else 0)
    boss_y = 150 - (0 if hero_turn else bob)
    surf.blit(imgs["hero"] if hero_turn else imgs["hero_dim"], (34, int(hero_y)))
    boss_img = imgs["boss_dim"] if hero_turn else imgs["boss"]
    surf.blit(boss_img, (WIDTH - 34 - boss_img.get_width(), int(boss_y)))

    box_w, box_h = 420, 150
    if hero_turn:
        box = pygame.Rect(262, 116, box_w, box_h)
        tail = (214, 238)
        name, name_color = PLAYER["name"].upper(), (120, 190, 255)
    else:
        box = pygame.Rect(WIDTH - 262 - box_w, 116, box_w, box_h)
        tail = (WIDTH - 214, 238)
        name, name_color = info["name"].upper(), lerp(info["color"], WHITE, 0.35)
    _bubble(surf, box, tail, hero_turn)
    tag = font(15, True).render(name, True, (20, 16, 26))
    tag_rect = pygame.Rect(box.x + 14, box.y - 30, tag.get_width() + 22, 26)
    pygame.draw.rect(surf, name_color, tag_rect, border_radius=8)
    surf.blit(tag, tag.get_rect(center=tag_rect.center))
    y = box.y + 20
    for line, _color in dlg.visible():
        if line:
            text(surf, line, font(22), (28, 24, 34), (box.x + 22, y), shadow=False)
        y += 30

    first = WIDTH // 2 - (dlg.total - 1) * 8
    for i in range(dlg.total):
        pygame.draw.circle(surf, GOLD if i <= dlg.i else OUTLINE, (first + i * 16, 508), 5)
    prompt = "ENTER  skip line" if dlg.typing else "ENTER  continue"
    text(surf, prompt, font(16, True), blink_color(t), (WIDTH - 24, HEIGHT - 14), anchor="bottomright")
    text(surf, "ESC  skip all", font(14), MUTED, (24, HEIGHT - 14), anchor="bottomleft")


def draw_pause(surf, menu):
    dim(surf, 150)
    panel(surf, (WIDTH // 2 - 200, 120, 400, 320), (12, 9, 18), 230, 18, border=GOLD, border_w=2)
    text(surf, "PAUSED", font(44, True), GOLD, (WIDTH // 2, 138), anchor="midtop")
    menu.draw(surf, WIDTH // 2, 230, spacing=50)
    text(surf, "ESC to resume", font(14), MUTED, (WIDTH // 2, 414), anchor="midtop")


def draw_result(surf, win, info, stats, menu, t):
    dim(surf, 150)
    accent = GOLD if win else (220, 70, 70)
    panel(surf, (WIDTH // 2 - 270, 90, 540, 380), (12, 9, 18), 235, 20, border=accent, border_w=2)
    text(surf, "VICTORY" if win else "DEFEAT", font(52, True), accent, (WIDTH // 2, 112), anchor="midtop")
    text(surf, info["name"], font(22, True), WHITE, (WIDTH // 2, 182), anchor="midtop")
    rows = [("Hits landed", stats["hits"]), ("Best combo", stats["combo"]),
            ("Damage taken", stats["taken"]), ("Time", stats["time"])]
    y = 226
    for label, value in rows:
        text(surf, label, font(20), MUTED, (WIDTH // 2 - 200, y), anchor="midleft", shadow=False)
        text(surf, str(value), font(20, True), WHITE, (WIDTH // 2 + 200, y), anchor="midright", shadow=False)
        y += 34
    if menu is not None:
        if len(menu.items) > 2:
            menu.draw(surf, WIDTH // 2, 374, spacing=34)
        else:
            menu.draw(surf, WIDTH // 2, 392, spacing=48)
    else:
        text(surf, "PRESS ENTER TO CONTINUE", font(18, True), blink_color(t), (WIDTH // 2, 420),
             anchor="midtop")


def draw_ending(surf, art, t, portrait_img, typewriter, fx):
    art.draw_back(surf, t, 0, None)
    dim(surf, 170)
    fx.draw(surf, font(14, True))
    stroked(surf, "YOU SAVED THEM!", font(60, True), GOLD, (WIDTH // 2, 36), anchor="midtop", stroke=4)
    surf.blit(portrait_img, portrait_img.get_rect(center=(230, 300)))
    y = 150
    for line, color in typewriter.visible():
        if line:
            text(surf, line, font(21), color, (440, y))
        y += 30
    text(surf, "Thanks for playing Shlok Fighter 1", font(16), MUTED, (WIDTH // 2, HEIGHT - 58),
         anchor="midbottom")
    text(surf, "PRESS ENTER TO RETURN TO THE TITLE", font(20, True), blink_color(t), (WIDTH // 2, HEIGHT - 26),
         anchor="midbottom")
