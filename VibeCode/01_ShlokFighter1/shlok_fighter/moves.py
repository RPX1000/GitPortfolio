"""Specials: Shlok's Lava Fist and the moves of every boss.

Every move runs in three parts: a telegraph (the wind-up, which the player can read and react
to), an active part (the damage) and recovery. Bosses flash a "!" while winding up, and a hit
during the wind-up interrupts it, except for moves with armour. Each boss has two regular
specials and an ultimate that unlocks below half health.

Templates (ProjectileVolley, DashCharge, GroundTrap) hold the shared logic. A boss move is a
short subclass that sets its numbers and look."""

import math
import random

import pygame

from .config import FLOOR_Y, LEFT_EDGE, RIGHT_EDGE, WIDTH, ATTACKS
from .drawing import clamp, lerp, soft_glow
from .hazards import draw_tractor
from .projectiles import Projectile
from .sprites import actor, draw_fighter


class Move:
    name = "MOVE"
    color = (255, 255, 255)
    telegraph = 20
    duration = 40
    cooldown = 360
    armor = False
    warning = False
    dim = 0
    weight = 1.0

    def __init__(self, game, owner):
        self.game = game
        self.owner = owner
        self.t = 0
        self.done = False
        self.struck = {}
        self.start()

    @classmethod
    def can_use(cls, owner, foe):
        return True

    @property
    def total(self):
        return self.telegraph + self.duration

    @property
    def winding(self):
        return self.t < self.telegraph

    @property
    def foe(self):
        g = self.game
        return g.player if self.owner is g.enemy else g.enemy

    def can_interrupt(self):
        return self.winding and not self.armor

    def callout(self, life=60):
        self.game.show_callout(self.name + "!", self.color, life)

    def reset_pose(self):
        self.owner.pose = None
        self.owner.aura = None
        self.owner.alpha = 255

    def start(self):
        pass

    def on_telegraph(self, t):
        pass

    def on_active(self, t):
        pass

    def on_end(self):
        pass

    def update(self):
        if self.done:
            return
        if self.winding:
            self.on_telegraph(self.t)
        else:
            self.on_active(self.t - self.telegraph)
        self.t += 1
        if self.t >= self.total:
            self.finish()

    def finish(self):
        if not self.done:
            self.done = True
            self.on_end()

    def cancel(self):
        self.finish()

    def draw_back(self, surf):
        """Drawn before the fighters, for scenery the boss stands on."""
        pass

    def draw(self, surf):
        """Drawn after the fighters, for effects on top of them."""
        pass

    def hit(self, target, damage, knock, sound="punch", spot=None, gap=10, hitstun=None, blockstun=None,
            knockdown=0):
        """Deals damage to target at most once every `gap` frames. Returns the hit result
        ("hit", "block" or "miss"), or None if the target was hit too recently."""
        last = self.struck.get(id(target), -999)
        if self.t - last < gap:
            return None
        self.struck[id(target)] = self.t
        direction = 1 if target.x >= self.owner.x else -1
        spot = spot or (target.x, target.y - 80)
        return self.game.apply_hit(target, damage * self.owner.damage_mult, knock, direction, self.owner, spot,
                                   sound, hitstun=hitstun, blockstun=blockstun, knockdown=knockdown)


# ----- shared templates ----------------------------------------------------------

class ProjectileVolley(Move):
    """Fires a sequence of projectiles at the foe. Subclasses set the pattern."""
    kind = "fireball"
    count = 3
    interval = 12
    damage = 8.0
    knock = 5.0
    radius = 14
    life = 200
    speed = 7.5
    gravity = 0.0          # when set, shots are lobbed to land on the foe's spot
    flight = 40            # frames a lobbed shot takes to land
    homing = 0.0
    max_speed = None
    spread = (0.0,)        # vertical offsets for successive shots
    sound = "fire"

    def start(self):
        self.callout()
        self.shots = 0

    def on_telegraph(self, t):
        o = self.owner
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)

    def on_active(self, t):
        o = self.owner
        if t == 0:
            o.pose = "throw"
            o.aura = None
        if t == 12:
            o.pose = None
        if t % self.interval == 0 and self.shots < self.count:
            self._fire(self.shots)
            self.shots += 1

    def _fire(self, i):
        o, foe = self.owner, self.foe
        x = o.x + o.facing * 44
        y = FLOOR_Y - 92 + self.spread[i % len(self.spread)]
        if self.gravity:
            arc = (0.5 * self.gravity * self.flight * self.flight - 92.0) / self.flight
            vx = clamp((foe.x - x) / self.flight, -14.0, 14.0)
            vy = -arc
        else:
            vx = (1 if foe.x >= x else -1) * self.speed
            vy = 0.0
        self.game.projectiles.append(Projectile(
            x, y, vx, vy, owner=o, damage=self.damage * o.damage_mult, knock=self.knock, kind=self.kind,
            radius=self.radius, life=self.life, color=self.color, gravity=self.gravity, homing=self.homing,
            target=foe, max_speed=self.max_speed, ground=bool(self.gravity)))
        self.game.audio.play(self.sound, 0.6)

    def on_end(self):
        self.reset_pose()


class DashCharge(Move):
    """An armoured charge: the boss runs straight through the arena and cannot be stopped."""
    visual = "bull"
    speed = 10.0
    damage = 12.0
    knock = 9.0
    hitstun = 22
    knockdown = 24
    armor = True
    warning = True
    telegraph = 34
    duration = 42
    cooldown = 480
    weight = 1.4

    @classmethod
    def can_use(cls, owner, foe):
        return 120 < abs(foe.x - owner.x) < 600

    def start(self):
        self.callout()

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t % 4 == 0:
            fx.shake = max(fx.shake, 2)
            fx.burst(o.x - o.facing * 22, FLOOR_Y - 4, (190, 170, 130), 4, speed=2.5, life=18, size=4,
                     gravity=-0.02)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "dash"
            o.aura = None
            g.audio.play("whoosh", 0.9)
            g.fx.shake = max(g.fx.shake, 6)
        run = self.duration - 12
        if t < run:
            o.vx = o.facing * self.speed
            ahead = pygame.Rect(int(min(o.x, o.x + o.facing * 70)), FLOOR_Y - 120, 70, 120)
            foe = self.foe
            if foe.alive and ahead.colliderect(foe.hurtbox()):
                self.hit(foe, self.damage, self.knock, "kick", gap=99, hitstun=self.hitstun,
                         knockdown=self.knockdown)
                g.fx.shake = max(g.fx.shake, 10)
        else:
            o.vx *= 0.7
            if t == self.duration - 1:
                o.vx = 0.0
                o.pose = None

    def draw_back(self, surf):
        if self.visual == "tractor" and self.t >= self.telegraph:
            draw_tractor(surf, self.owner.x - self.owner.facing * 24, self.t * 0.4)

    def draw(self, surf):
        if self.visual == "bull" and self.telegraph <= self.t < self.duration + self.telegraph - 12:
            o = self.owner
            for k in range(4):   # dust streaming off the hooves
                y = FLOOR_Y - 14 - k * 16
                x = o.x - o.facing * (40 + k * 22)
                pygame.draw.line(surf, (200, 180, 140), (x, y), (x - o.facing * 30, y), 2)

    def on_end(self):
        self.reset_pose()


class GroundTrap(Move):
    """Marks spots on the floor around the foe, then springs a trap on each one."""
    kind = "geyser"        # geyser | bolt | snare
    offsets = (-40.0, 40.0)
    damage = 12.0
    knock = 8.0
    radius = 46
    delay = 14
    snare_frames = 50
    hitstun = 16
    knockdown = 0
    color = (255, 120, 40)
    warning = True

    def start(self):
        self.callout()
        self.spots = []
        self.traps = []
        self.sprung = 0

    def on_telegraph(self, t):
        o = self.owner
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t == 0:
            foe = self.foe
            self.spots = [clamp(foe.x + off, LEFT_EDGE, RIGHT_EDGE) for off in self.offsets]

    def on_active(self, t):
        o = self.owner
        if t == 0:
            o.pose = "raise"
            o.aura = None
        if t == 10:
            o.pose = None
        if self.sprung < len(self.spots) and t % self.delay == 0:
            x = self.spots[self.sprung]
            self.sprung += 1
            self._spring(x)
        for tr in self.traps:
            tr["t"] += 1
        self.traps = [tr for tr in self.traps if tr["t"] < 44]

    def _spring(self, x):
        g = self.game
        self.traps.append({"x": x, "t": 0})
        g.audio.play("boom", 0.7)
        g.fx.shake = max(g.fx.shake, 6)
        if self.kind == "geyser":
            g.fx.burst(x, FLOOR_Y - 4, self.color, 22, speed=7, life=28, size=5, gravity=0.3, upward=6)
            g.fx.ring(x, FLOOR_Y, self.color, 80, 14, 6)
        elif self.kind == "bolt":
            g.fx.ring(x, FLOOR_Y, (255, 240, 140), 70, 12, 5)
            g.fx.burst(x, FLOOR_Y - 6, (255, 240, 140), 16, speed=6, life=16, size=4, gravity=0.1)
        else:
            g.fx.burst(x, FLOOR_Y - 6, (120, 190, 90), 16, speed=4, life=24, size=4, gravity=-0.02, upward=2)
        foe = self.foe
        if not (foe.alive and foe.on_ground and not foe.invulnerable() and abs(foe.x - x) < self.radius):
            return
        if self.kind == "snare":
            if self.hit(foe, self.damage, 0, "punch", spot=(x, FLOOR_Y - 60), gap=99, hitstun=10) == "hit":
                foe.snare_t = self.snare_frames
        else:
            self.hit(foe, self.damage, self.knock, "kick", spot=(x, FLOOR_Y - 70), gap=99,
                     hitstun=self.hitstun, knockdown=self.knockdown)

    def draw(self, surf):
        if self.winding:
            pulse = 0.5 + 0.5 * math.sin(self.t * 0.45)
            col = lerp((120, 30, 20), self.color, pulse)
            for x in self.spots:
                pygame.draw.ellipse(surf, col, (x - self.radius, FLOOR_Y - 6, self.radius * 2, 14), 2)
                pygame.draw.ellipse(surf, col, (x - self.radius * 0.5, FLOOR_Y - 3, self.radius, 8), 1)
        for tr in self.traps:
            x, age = int(tr["x"]), tr["t"]
            if self.kind == "geyser":
                h = min(120, age * 14) if age < 16 else max(0, 120 - (age - 16) * 10)
                if h > 0:
                    pygame.draw.rect(surf, (255, 130, 40), (x - 22, FLOOR_Y - h, 44, h), border_radius=10)
                    pygame.draw.rect(surf, (255, 230, 140), (x - 9, FLOOR_Y - h + 6, 18, max(0, h - 12)),
                                     border_radius=6)
            elif self.kind == "bolt":
                if age < 10:
                    pts = [(x, 0)]
                    for k in range(1, 8):
                        pts.append((x + random.randint(-12, 12), k * (FLOOR_Y // 8)))
                    pts.append((x, FLOOR_Y))
                    pygame.draw.lines(surf, (255, 250, 200), False, pts, 4)
                    pygame.draw.lines(surf, (255, 230, 120), False, pts, 2)
            else:
                grow = min(1.0, age / 24)
                for k in range(-2, 3):
                    top = FLOOR_Y - 60 * grow - abs(k) * 4
                    pygame.draw.line(surf, (90, 160, 60), (x + k * 9, FLOOR_Y), (x + k * 9 + k * 3, top), 4)

    def on_end(self):
        self.reset_pose()


# ----- the player's super ---------------------------------------------------------

class LavaFist(Move):
    """Shlok's super. Charge it, then release a blazing comet."""
    name = "LAVA FIST"
    color = (255, 140, 40)
    telegraph = 34
    duration = 40
    cooldown = 0
    cost = 100
    armor = True
    dim = 120

    def start(self):
        self.callout(72)
        self.game.slowmo = 40
        self.game.fx.shake = max(self.game.fx.shake, 4)

    def fist(self):
        o = self.owner
        return o.x + o.facing * 46, FLOOR_Y - 84

    def draw(self, surf):
        """A molten orb swells in the fist while the energy gathers."""
        if not self.winding:
            return
        x, y = self.fist()
        ix, iy = int(x), int(y)
        s = self.t / self.telegraph
        soft_glow(surf, (ix, iy), 30 + 6 * int(s * 5), (255, 150, 60), 60 + 20 * int(s * 4))
        pygame.draw.circle(surf, (255, 170, 80), (ix, iy), 4 + int(12 * s))
        pygame.draw.circle(surf, (255, 246, 214), (ix, iy), 2 + int(5 * s))
        ring = 44 - 34 * ((self.t * 0.2) % 1.0)
        pygame.draw.circle(surf, (255, 190, 110), (ix, iy), max(2, int(ring)), 2)

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        fx_x, fx_y = self.fist()
        for _ in range(3):  # energy pulled from the room into the fist
            a = random.uniform(0, math.tau)
            d = random.uniform(80, 140)
            px, py = fx_x + math.cos(a) * d, fx_y + math.sin(a) * d
            fx.add(px, py, (fx_x - px) / 14, (fx_y - py) / 14, 16,
                   random.choice([(255, 170, 60), (255, 240, 160)]), 3)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            x, y = self.fist()
            g.projectiles.append(Projectile(x, y, o.facing * 11.0, 0.0, owner=o,
                                            damage=24 * o.damage_mult, knock=13, kind="lava_fist",
                                            radius=26, life=200, color=self.color))
            g.fx.shake = max(g.fx.shake, 12)
            g.fx.flash((255, 170, 80), 110)
            g.fx.burst(x, y, (255, 200, 120), 26, speed=8, life=26, size=6, gravity=0.1)
            g.fx.ring(x, y, self.color, 90, 18, 8)
            g.audio.play("fire", 1.0)
            o.pose = "throw"
        if t == 14:
            o.pose = None
        o.aura = (self.color, 1 - t / 20) if t < 20 else None

    def on_end(self):
        self.reset_pose()


# ----- Korean David ---------------------------------------------------------------

class TornadoHeel(Move):
    """Korean David: spins up, then dashes forward in a whirling heel kick that can hit twice."""
    name = "TORNADO HEEL"
    color = (235, 80, 70)
    telegraph = 26
    duration = 50
    cooldown = 420
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 140 < abs(foe.x - owner.x) < 380

    def start(self):
        self.callout()
        self.owner.pose = "charge"

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = (self.color, t / self.telegraph)
        if t % 2 == 0:
            a = t * 0.9
            fx.add(o.x + math.cos(a) * 46, FLOOR_Y - 62 + math.sin(a) * 26, math.cos(a + 1.6) * 1.2,
                   math.sin(a + 1.6) * 1.2, 16, (255, 160, 120), 3)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "spin"
            o.vx = o.facing * 7.5
            o.aura = None
            g.fx.shake = max(g.fx.shake, 4)
            g.audio.play("whoosh", 0.9)
        if t < 30:
            box = pygame.Rect(int(min(o.x, o.x + o.facing * 96)), FLOOR_Y - 124, 96, 96)
            foe = self.foe
            if foe.alive and box.colliderect(foe.hurtbox()):
                self.hit(foe, 6, 4, "kick", spot=(o.x + o.facing * 40, FLOOR_Y - 70), gap=8)
        if t == 30:
            o.vx = 0.0
            o.pose = None

    def draw(self, surf):
        if not (self.telegraph <= self.t < self.telegraph + 30):
            return
        o = self.owner
        rect = pygame.Rect(int(o.x) - 58, FLOOR_Y - 120, 116, 116)
        for k in range(3):
            a0 = self.t * 0.8 + k * 2.1
            pygame.draw.arc(surf, (255, 178, 130), rect, a0, a0 + 1.5, 6)

    def on_end(self):
        self.reset_pose()


class HeelDrop(Move):
    """Korean David: leaps high, then drops heel-first. The landing flares out in a ring of fire."""
    name = "HEEL DROP"
    color = (255, 120, 60)
    telegraph = 20
    duration = 64
    cooldown = 400
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 90 < abs(foe.x - owner.x) < 300

    def start(self):
        self.callout()
        self.landed = False

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t % 3 == 0:
            fx.add(o.x + random.uniform(-26, 26), FLOOR_Y - 4, random.uniform(-0.4, 0.4),
                   random.uniform(-2.2, -1.0), 22, (255, 170, 80), 3)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "raise"
            o.aura = None
            o.vy = -17.0
            o.on_ground = False
            o.vx = clamp((self.foe.x - o.x) / 40.0, -7.0, 7.0)   # the leap is aimed at the foe
            g.audio.play("whoosh", 0.9)
        if t > 6 and o.on_ground and not self.landed:
            o.vx = 0.0
            self.landed = True
            o.pose = None
            g.fx.shake = max(g.fx.shake, 14)
            g.fx.flash((255, 130, 60), 100)
            g.fx.ring(o.x, FLOOR_Y, self.color, 160, 24, 9)
            g.fx.ring(o.x, FLOOR_Y, (255, 220, 120), 90, 16, 5)
            g.fx.burst(o.x, FLOOR_Y - 4, self.color, 26, speed=8, life=26, size=5, gravity=0.2)
            g.audio.play("boom", 1.0)
            foe = self.foe
            if foe.alive and foe.on_ground and abs(foe.x - o.x) < 120:
                self.hit(foe, 16, 9, "kick", hitstun=24, knockdown=22, gap=99)

    def on_end(self):
        self.reset_pose()


class LavaGeysers(GroundTrap):
    """Korean David's ultimate: two geysers erupt under the foe."""
    name = "LAVA GEYSERS"
    color = (255, 120, 40)
    kind = "geyser"
    offsets = (-44.0, 44.0)
    damage = 14.0
    knock = 9.0
    radius = 46
    delay = 16
    hitstun = 18
    knockdown = 18
    telegraph = 34
    duration = 56
    cooldown = 480
    weight = 1.4


# ----- Sus Finance Bro ------------------------------------------------------------

class ShortSqueeze(Move):
    """Sus Finance Bro: vanishes in a puff of smoke, reappears behind Shlok and punches."""
    name = "SHORT SQUEEZE"
    color = (120, 230, 140)
    telegraph = 26
    duration = 40
    cooldown = 420
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) > 200

    def start(self):
        self.callout()

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = (self.color, t / self.telegraph)
        o.alpha = 255 if (t // 3) % 2 == 0 else 150
        if t % 4 == 0:
            fx.add(o.x + random.uniform(-22, 22), o.y - 96, random.uniform(-0.4, 0.4), -1.3, 26,
                   self.color, 3)

    def on_active(self, t):
        o, g, foe = self.owner, self.game, self.foe
        if t == 0:
            o.alpha = 0
            o.aura = None
            g.fx.burst(o.x, FLOOR_Y - 70, (110, 120, 110), 24, speed=4, life=30, size=8, gravity=-0.04)
            g.audio.play("whoosh", 0.8)
        if t == 10:
            o.x = clamp(foe.x - foe.facing * 62, LEFT_EDGE, RIGHT_EDGE)
            o.facing = 1 if foe.x >= o.x else -1
            o.alpha = 255
            o.pose = "throw"
            g.fx.burst(o.x, FLOOR_Y - 70, self.color, 18, speed=5, life=24, size=4)
            g.fx.shake = max(g.fx.shake, 5)
        if t == 13 and abs(foe.x - o.x) < 86:
            self.hit(foe, 12, 9, "punch", gap=99)
        if t == 22:
            o.pose = None

    def on_end(self):
        self.reset_pose()


class MarginCall(ProjectileVolley):
    """Sus Finance Bro: lobs three money bags that land on the foe's spot."""
    name = "MARGIN CALL"
    color = (120, 220, 140)
    telegraph = 26
    duration = 66
    cooldown = 320
    kind = "bag"
    count = 3
    interval = 14
    damage = 7.0
    knock = 4.0
    radius = 14
    life = 170
    gravity = 0.5
    flight = 42
    sound = "coin"
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 160 < abs(foe.x - owner.x) < 420


class BullRun(DashCharge):
    """Sus Finance Bro's ultimate: a bull charge across the trading floor."""
    name = "BULL RUN"
    color = (150, 210, 150)
    visual = "bull"
    speed = 11.0
    telegraph = 34
    duration = 42
    cooldown = 480
    weight = 1.4


# ----- Ronak ----------------------------------------------------------------------

class WrenchBoomerang(Move):
    """Ronak: throws a spinning wrench that flies out, turns around and comes back."""
    name = "WRENCH BOOMERANG"
    color = (235, 150, 50)
    telegraph = 22
    duration = 26
    cooldown = 360
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) > 130

    def start(self):
        self.callout()

    def on_telegraph(self, t):
        o = self.owner
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "throw"
            o.aura = None
            g.projectiles.append(Projectile(o.x + o.facing * 44, FLOOR_Y - 96, o.facing * 8.5, 0.0, owner=o,
                                            damage=9 * o.damage_mult, knock=6, kind="wrench", radius=15,
                                            life=180, color=self.color, pierce=True, returns_at=34))
            g.audio.play("whoosh", 0.7)
        if t == 12:
            o.pose = None

    def on_end(self):
        self.reset_pose()


class FanGale(Move):
    """Ronak: switches the fans to full power. A gale pushes the foe back across the arena."""
    name = "FAN GALE"
    color = (170, 210, 255)
    telegraph = 26
    duration = 26
    cooldown = 360
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 130 < abs(foe.x - owner.x) < 380

    def start(self):
        self.callout()

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = (self.color, t / self.telegraph)
        if t % 3 == 0:
            fx.add(random.uniform(0, WIDTH), random.uniform(120, FLOOR_Y - 60), -o.facing * 4.0, 0.0, 22,
                   self.color, 2)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.aura = None
            o.pose = "raise"
            foe = self.foe
            direction = 1 if foe.x >= o.x else -1
            g.gust = {"dir": direction, "t": 0, "life": 150}
            g.fx.shake = max(g.fx.shake, 6)
            g.audio.play("whoosh", 1.0)
        if t == 12:
            o.pose = None

    def on_end(self):
        self.reset_pose()


class ToolboxStorm(ProjectileVolley):
    """Ronak's ultimate: a storm of wrenches at three heights."""
    name = "TOOLBOX STORM"
    color = (235, 150, 50)
    telegraph = 24
    duration = 46
    cooldown = 420
    weight = 1.4
    kind = "wrench"
    count = 3
    interval = 8
    damage = 8.0
    knock = 5.0
    radius = 15
    life = 150
    speed = 9.0
    spread = (-30.0, 0.0, 30.0)
    sound = "whoosh"
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 120 < abs(foe.x - owner.x) < 500


# ----- Farmer Rogelio -------------------------------------------------------------

class HayRoll(Move):
    """Farmer Rogelio: rolls two hay bales along the ground. Jump them."""
    name = "HAY BALE ROLL"
    color = (205, 155, 75)
    telegraph = 30
    duration = 26
    cooldown = 420
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) > 180

    def start(self):
        self.callout()

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = None
        if t >= self.telegraph - 10:
            o.pose = "raise"
        if t % 5 == 0:
            fx.burst(o.x + o.facing * 20, FLOOR_Y - 4, (200, 170, 120), 5, speed=2.5, life=18, size=4,
                     gravity=-0.02)
            fx.shake = max(fx.shake, 2)

    def on_active(self, t):
        o = self.owner
        if t == 0:
            o.pose = None
            self._bale(o)
        if t == 16:
            self._bale(o)

    def _bale(self, o):
        self.game.projectiles.append(Projectile(o.x + o.facing * 34, FLOOR_Y - 18, o.facing * 6.5, 0.0, owner=o,
                                                damage=9 * o.damage_mult, knock=7, kind="hay", radius=18,
                                                life=260, color=self.color))
        self.game.audio.play("thud", 0.6)

    def on_end(self):
        self.reset_pose()


class PitchforkSpikes(Move):
    """Farmer Rogelio: pitchfork spikes erupt in a line toward the foe, one after another."""
    name = "PITCHFORK SPIKES"
    color = (160, 180, 150)
    telegraph = 24
    duration = 60
    cooldown = 380
    warning = True
    count = 5

    @classmethod
    def can_use(cls, owner, foe):
        return 150 < abs(foe.x - owner.x) < 420

    def start(self):
        self.callout()
        self.xs = []
        self.spikes = []

    def on_telegraph(self, t):
        o = self.owner
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t == 0:
            self.xs = [clamp(o.x + o.facing * (56 + k * 54), LEFT_EDGE, RIGHT_EDGE) for k in range(self.count)]

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.aura = None
        if t == 2:
            o.pose = None
        if t % 6 == 0 and len(self.spikes) < len(self.xs):
            x = self.xs[len(self.spikes)]
            self.spikes.append({"x": x, "t": 0, "hit": False})
            g.audio.play("thud", 0.5)
            g.fx.burst(x, FLOOR_Y - 2, (190, 170, 120), 6, speed=3, life=16, size=3, gravity=-0.02, upward=1.5)
        for s in self.spikes:
            s["t"] += 1
            if not s["hit"] and 4 <= s["t"] <= 20:
                foe = self.foe
                if foe.alive and foe.on_ground and abs(foe.x - s["x"]) < 18:
                    s["hit"] = True
                    self.hit(foe, 9, 4, "punch", spot=(s["x"], FLOOR_Y - 40), gap=99, hitstun=16)

    def draw(self, surf):
        if self.winding:
            for x in self.xs:
                pygame.draw.ellipse(surf, (120, 60, 40), (x - 14, FLOOR_Y - 4, 28, 8), 2)
        for s in self.spikes:
            age = s["t"]
            if age >= 24:
                continue
            h = min(58, age * 14) if age < 6 else max(0, 58 - (age - 6) * 4)
            x = int(s["x"])
            if h <= 0:
                continue
            pygame.draw.polygon(surf, (30, 26, 30), [(x - 12, FLOOR_Y), (x, FLOOR_Y - h - 2), (x + 12, FLOOR_Y)])
            for k in (-7, 0, 7):   # three tines
                pygame.draw.line(surf, (200, 200, 190), (x + k, FLOOR_Y - 4), (x + k * 0.4, FLOOR_Y - h), 3)

    def on_end(self):
        self.reset_pose()


class TractorCharge(DashCharge):
    """Farmer Rogelio's ultimate: he drives the tractor straight through the arena."""
    name = "TRACTOR CHARGE"
    color = (60, 165, 70)
    visual = "tractor"
    speed = 9.0
    telegraph = 40
    duration = 50
    cooldown = 520
    weight = 1.4


# ----- The Nak --------------------------------------------------------------------

class ThunderSlam(Move):
    """The Nak: leaps high, slams down and sends shock waves out both ways."""
    name = "THUNDER SLAM"
    color = (255, 222, 80)
    telegraph = 30
    duration = 62
    cooldown = 480
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) < 240

    def start(self):
        self.callout()
        self.landed = False

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t % 2 == 0:  # crackling energy around the fists
            fx.add(o.x + random.uniform(-44, 44), FLOOR_Y - random.uniform(70, 120),
                   random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 9,
                   random.choice([(255, 245, 170), (255, 255, 255)]), 3)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "raise"
            o.aura = None
            o.vy = -17.0
            o.on_ground = False
            g.fx.shake = max(g.fx.shake, 4)
            g.audio.play("whoosh", 0.8)
        if not self.landed and t > 2 and o.on_ground:
            self.landed = True
            o.pose = None
            g.fx.shake = max(g.fx.shake, 14)
            g.fx.flash((255, 230, 140), 90)
            g.fx.ring(o.x, FLOOR_Y, self.color, 150, 24, 8)
            g.fx.burst(o.x, FLOOR_Y - 4, self.color, 24, speed=7, life=26, size=5, gravity=0.2)
            g.audio.play("boom", 1.0)
            foe = self.foe
            if foe.alive and foe.on_ground and abs(foe.x - o.x) < 80:
                self.hit(foe, 14, 11, "kick", gap=99)
            for d in (-1, 1):
                g.projectiles.append(Projectile(o.x, FLOOR_Y - 20, d * 8.0, 0.0, owner=o,
                                                damage=10 * o.damage_mult, knock=9, kind="shock",
                                                radius=20, life=90, color=self.color))

    def on_end(self):
        self.reset_pose()


class ChainLightning(GroundTrap):
    """The Nak: three bolts of lightning strike where the foe was standing."""
    name = "CHAIN LIGHTNING"
    color = (255, 230, 120)
    kind = "bolt"
    offsets = (-34.0, 0.0, 34.0)
    damage = 10.0
    knock = 4.0
    radius = 40
    delay = 12
    hitstun = 14
    telegraph = 30
    duration = 60
    cooldown = 380


class GoldenBeam(Move):
    """The Nak's ultimate: a long charge that cannot be interrupted, then a golden beam."""
    name = "GOLDEN BEAM"
    color = (255, 220, 80)
    telegraph = 60
    duration = 40
    cooldown = 480
    armor = True
    warning = True
    weight = 1.4

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) > 140

    def start(self):
        self.callout(80)

    def on_telegraph(self, t):
        o, g = self.owner, self.game
        o.pose = "charge"
        o.aura = (self.color, t / self.telegraph)
        if t % 3 == 0:
            g.fx.add(o.x + random.uniform(-30, 30), FLOOR_Y - random.uniform(80, 140), random.uniform(-0.5, 0.5),
                     random.uniform(-2.0, -0.6), 18, (255, 245, 190), 3)
        if t % 10 == 0:
            g.fx.shake = max(g.fx.shake, 2)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = "throw"
            o.aura = None
            g.projectiles.append(Projectile(o.x + o.facing * 46, FLOOR_Y - 96, o.facing * 16.0, 0.0, owner=o,
                                            damage=22 * o.damage_mult, knock=10, kind="beam", radius=16,
                                            life=80, color=self.color, pierce=True))
            g.fx.shake = max(g.fx.shake, 14)
            g.fx.flash((255, 240, 180), 120)
            g.audio.play("boom", 1.0)
        if t == 14:
            o.pose = None

    def on_end(self):
        self.reset_pose()


# ----- Evil Shlok -----------------------------------------------------------------

class ShadowClones(Move):
    """Evil Shlok: two shadow copies dash at Shlok one after the other."""
    name = "SHADOW CLONES"
    color = (170, 100, 255)
    telegraph = 28
    duration = 80
    cooldown = 480
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return 150 < abs(foe.x - owner.x) < 420

    def start(self):
        self.callout()
        self.clones = []

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = (self.color, t / self.telegraph)
        o.alpha = 255 if (t // 4) % 2 == 0 else 170
        if t == self.telegraph - 1:
            for side in (-1, 1):
                cx = o.x + side * 76
                self.clones.append({"x": cx, "facing": o.facing, "alpha": 0.0, "dash": None, "hit": False})
                fx.burst(cx, FLOOR_Y - 60, self.color, 14, speed=4, life=22, size=4)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.alpha = 255
            o.aura = None
        for i, c in enumerate(self.clones):
            if c["dash"] is None:
                if t == 8 + i * 16:
                    c["dash"] = 0
                else:
                    c["alpha"] = min(170.0, c["alpha"] + 14)
                continue
            c["dash"] += 1
            foe = self.foe
            direction = 1 if foe.x >= c["x"] else -1
            c["facing"] = direction
            c["x"] = clamp(c["x"] + direction * 9.5, LEFT_EDGE, RIGHT_EDGE)
            if c["dash"] > 26:
                c["alpha"] = max(0.0, c["alpha"] - 14)
            elif foe.alive and not c["hit"] and abs(foe.x - c["x"]) < 42:
                c["hit"] = True
                g.apply_hit(foe, 8 * o.damage_mult, 7, direction, o, (c["x"], FLOOR_Y - 80), "punch")

    def draw(self, surf):
        for c in self.clones:
            if c["alpha"] <= 0:
                continue
            info = {"name": "", "color": (46, 26, 66), "hair": (20, 14, 30), "look": self.owner.look}
            shadow = actor(info, c["x"], c["facing"], feet=FLOOR_Y, alpha=int(c["alpha"]),
                           silhouette=(104, 66, 160), walk_t=self.t)
            draw_fighter(surf, shadow)

    def on_end(self):
        self.reset_pose()


class MirrorMimic(Move):
    """Evil Shlok copies the last attack Shlok threw, and throws it back."""
    name = "MIRROR MIMIC"
    color = (190, 130, 255)
    telegraph = 24
    duration = 30
    cooldown = 360
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) < 240 and foe.last_attack is not None

    def start(self):
        foe = self.foe
        self.copy = foe.last_attack if foe.last_attack in ATTACKS else "punch"
        spec = ATTACKS[self.copy]
        self.duration = spec["startup"] + spec["active"] + spec["recovery"] + 6
        self.game.show_callout(f"MIRROR {self.copy.replace('_', ' ').upper()}!", self.color, 60)

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        o.aura = (self.color, t / self.telegraph)
        o.alpha = 255 if (t // 3) % 2 == 0 else 200
        if t % 4 == 0:
            fx.add(o.x + random.uniform(-30, 30), FLOOR_Y - random.uniform(40, 130), random.uniform(-0.6, 0.6),
                   random.uniform(-1.0, -0.2), 20, self.color, 3)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.alpha = 255
            o.aura = None
            foe = self.foe
            # the reflection steps in to where the foe stands before it copies the move
            o.x = clamp(foe.x - foe.facing * 60, LEFT_EDGE, RIGHT_EDGE)
            o.facing = 1 if foe.x >= o.x else -1
            o.attack = self.copy
            o.attack_t = 0
            o.attack_landed = False
            o.attack_hit = False
            o.last_attack = self.copy
            o.vx = 0.0
            g.audio.play("whoosh", 0.7)

    def on_end(self):
        self.reset_pose()


class VoidOrbs(ProjectileVolley):
    """Evil Shlok's ultimate: three void orbs that home in on the foe."""
    name = "VOID ORBS"
    color = (170, 100, 255)
    telegraph = 30
    duration = 84
    cooldown = 480
    weight = 1.4
    kind = "orb"
    count = 3
    interval = 16
    damage = 8.0
    knock = 5.0
    radius = 12
    life = 280
    speed = 3.6
    homing = 0.085
    max_speed = 5.4
    spread = (-120.0, -90.0, -60.0)
    sound = "fire"
    warning = True

    @classmethod
    def can_use(cls, owner, foe):
        return True


# ----- Jeffrey Epstein ------------------------------------------------------------

class RuinCollapse(Move):
    """Jeffrey Epstein: marks spots on the floor, then drops pillars on them in turn."""
    name = "RUIN COLLAPSE"
    color = (232, 200, 130)
    telegraph = 44
    duration = 120
    cooldown = 600
    warning = True
    spot_count = 5
    interval = 16
    spots_pool = (120, 250, 380, 510, 640, 770, 880)

    @classmethod
    def can_use(cls, owner, foe):
        return abs(foe.x - owner.x) > 90

    def start(self):
        self.callout(80)
        # always mark the spot nearest the foe, so the collapse threatens where they stand
        foe_x = self.foe.x
        nearest = min(self.spots_pool, key=lambda x: abs(x - foe_x))
        others = [x for x in self.spots_pool if x != nearest]
        self.spots = sorted([nearest] + random.sample(others, self.spot_count - 1))
        self.game.slowmo = 20

    def on_telegraph(self, t):
        o, fx = self.owner, self.game.fx
        if t >= self.telegraph - 14:
            o.pose = "raise"
        if t % 6 == 0:
            fx.shake = max(fx.shake, 2)
            for x in self.spots:
                fx.add(x + random.uniform(-30, 30), FLOOR_Y - 2, random.uniform(-0.3, 0.3),
                       -random.uniform(0.6, 1.4), 22, (190, 170, 130), 3, gravity=0.02)

    def on_active(self, t):
        o, g = self.owner, self.game
        if t == 0:
            o.pose = None
        if t % self.interval == 0 and t // self.interval < len(self.spots):
            x = self.spots[t // self.interval] + random.randint(-12, 12)
            g.projectiles.append(Projectile(x, -60.0, 0.0, 6.0, owner=o, damage=8 * o.damage_mult, knock=6,
                                            kind="pillar", radius=26, life=140, color=self.color,
                                            gravity=0.55))
            g.audio.play("thud", 0.5)

    def draw(self, surf):
        if not self.winding:
            return
        pulse = 0.5 + 0.5 * math.sin(self.t * 0.4)
        col = lerp((150, 40, 40), (255, 90, 70), pulse)
        for x in self.spots:
            pygame.draw.ellipse(surf, col, (x - 44, FLOOR_Y - 6, 88, 14))
            pygame.draw.ellipse(surf, (40, 10, 10), (x - 44, FLOOR_Y - 6, 88, 14), 2)

    def on_end(self):
        self.reset_pose()


class FinalCollapse(RuinCollapse):
    """Jeffrey Epstein's ultimate: every spot at once, in quick succession."""
    name = "FINAL COLLAPSE"
    color = (240, 210, 140)
    telegraph = 40
    duration = 96
    cooldown = 520
    weight = 1.4
    spot_count = 7
    interval = 8


class VineSnare(GroundTrap):
    """Jeffrey Epstein: vines erupt under Shlok and hold him in place until he mashes free."""
    name = "VINE SNARE"
    color = (120, 190, 90)
    kind = "snare"
    offsets = (0.0,)
    damage = 4.0
    radius = 56
    delay = 1
    snare_frames = 56
    hitstun = 10
    telegraph = 26
    duration = 44
    cooldown = 420


# Every move a boss can use, by name. ENEMIES in config.py refers to these names.
MOVE_REGISTRY = {cls.__name__: cls for cls in (
    LavaFist, TornadoHeel, HeelDrop, LavaGeysers,
    ShortSqueeze, MarginCall, BullRun,
    WrenchBoomerang, FanGale, ToolboxStorm,
    HayRoll, PitchforkSpikes, TractorCharge,
    ThunderSlam, ChainLightning, GoldenBeam,
    ShadowClones, MirrorMimic, VoidOrbs,
    RuinCollapse, FinalCollapse, VineSnare,
)}
PLAYER_SPECIAL = LavaFist
