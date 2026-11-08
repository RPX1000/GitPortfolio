"""Fighter state, physics, input-driven actions and the boss brain.

Every attack has a startup (a counter-hit window), an active part (the hitbox is live) and a
recovery. A hit that lands can be cancelled into the next attack during recovery, which is how
combos are built. A hit puts the defender into hitstun, a blocked hit into blockstun, a dash
gives a moment of invulnerability, and a snare holds a fighter in place until they mash free.

Stage immunity: a boss is immune to its own stage's hazards while standing, and exposed to
them while stunned (in hitstun or knocked down)."""

import random

import pygame

from .config import (WALK_SPEED, JUMP_VELOCITY, GRAVITY, FLOOR_Y, LEFT_EDGE, RIGHT_EDGE,
                     FIGHTER_H, CROUCH_H, BODY_W, ATTACKS, DASH, THROW)
from .drawing import clamp

WINDUP_FRAMES = 8   # the base pause before a boss's normal attack
TRAIL_LEN = 4


class Fighter:
    """A fighter, either the player or a boss. x is the centre, y is the feet."""

    def __init__(self, name, color, x, facing, hp, is_player, look="spiky", hair=(25, 20, 28), eye=None,
                 speed=WALK_SPEED, damage_mult=1.0, aggression=0.0, skill=0.5):
        self.name = name
        self.color = color
        self.look = look
        self.hair = hair
        self.eye = eye
        self.x = float(x)
        self.y = float(FLOOR_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = facing
        self.max_hp = hp
        self.hp = float(hp)
        self.ghost_hp = float(hp)
        self.is_player = is_player
        self.speed = speed
        self.damage_mult = damage_mult
        self.aggression = aggression
        self.skill = skill
        self.on_ground = True
        self.landed = False
        self.crouching = False
        self.blocking = False
        self.walk_t = 0
        self.flash = 0
        self.meter = 0.0
        # attacks
        self.attack = None
        self.attack_t = 0
        self.attack_landed = False   # the active hitbox has already made contact
        self.attack_hit = False      # the attack connected unblocked, so it may be cancelled
        self.attack_serial = 0       # counts the strikes started, so a boss can tell one strike from the next
        self.air_used = False
        self.last_attack = None
        self.combo_queue = []        # the rest of a boss's combo string
        # stun and states
        self.hurt_t = 0              # hitstun frames left
        self.block_t = 0             # blockstun frames left
        self.down_t = 0              # knocked down, lying on the floor
        self.invuln_t = 0            # brief invulnerability after getting up
        self.throw_t = 0             # the thrower's animation
        self.snare_t = 0             # held in place by vines
        self.block_press_t = -999    # when block was last tapped (for parries and techs)
        self.dash_t = 0
        self.dash_cd = 0
        self.dash_dir = 0
        self.trail = []
        # combo
        self.combo = 0
        self.combo_t = 0
        # specials and the boss brain
        self.special = None
        self.special_cd = 0
        self.move_cd = {}
        self.cd_scale = 1.0
        self.enraged = False
        self.combos = []
        self.windup = 0
        self.pending = "punch"
        self.think_t = 0
        self.plan = "idle"
        self.hazard_t = 0
        self.hazard_react = False
        self.read_serial = -1        # the player's strike the boss has already read
        self.read_block = False      # whether the boss will block that strike
        self.read_punish = False     # whether it will punish that strike if it misses
        self.guard_t = 0             # frames of pre-emptive guard left
        self.guard_cd = 0            # frames before the boss may guard again
        # presentation
        self.pose = None
        self.aura = None
        self.alpha = 255
        self.silhouette = False

    @property
    def alive(self):
        return self.hp > 0

    def busy(self):
        """True while the fighter can't take a new action."""
        return bool(self.attack or self.special is not None or self.hurt_t > 0 or self.block_t > 0
                    or self.windup > 0 or self.down_t > 0 or self.dash_t > 0 or self.throw_t > 0
                    or self.snare_t > 0)

    def invulnerable(self):
        return (self.dash_t > 0 and DASH["invuln"]) or self.invuln_t > 0

    def stunned(self):
        """Stunned means hitstun or knocked down: the state in which the stage can get a boss."""
        return self.hurt_t > 0 or self.down_t > 0

    def stage_immune(self):
        """Bosses are immune to their own stage's hazards while they are not stunned."""
        return (not self.is_player) and not self.stunned()

    def phase(self):
        if not self.attack:
            return None
        spec = ATTACKS[self.attack]
        if self.attack_t < spec["startup"]:
            return "startup"
        if self.attack_t < spec["startup"] + spec["active"]:
            return "active"
        return "recovery"

    def active_attack(self):
        if self.attack is None or self.attack_landed or self.phase() != "active":
            return None
        return ATTACKS[self.attack]

    def hurtbox(self):
        h = CROUCH_H if (self.crouching and self.on_ground) else FIGHTER_H
        return pygame.Rect(int(self.x - BODY_W / 2), int(self.y - h), BODY_W, h)

    def strike_rect(self):
        spec = ATTACKS[self.attack]
        top, h = spec["box"]
        x0 = self.x + self.facing * 18
        x1 = x0 + self.facing * spec["reach"]
        return pygame.Rect(int(min(x0, x1)), int(self.y + top), int(abs(x1 - x0)), h)

    def start_attack(self, kind):
        spec = ATTACKS[kind]
        blocked = (not self.alive or self.special is not None or self.windup > 0 or self.hurt_t > 0
                   or self.block_t > 0 or self.down_t > 0 or self.throw_t > 0 or self.snare_t > 0)
        if blocked:
            return False
        if spec.get("dash"):
            if self.dash_t <= 0 or not self.on_ground:
                return False
            self.dash_t = 0
        elif self.dash_t > 0:
            return False
        if self.attack is not None and not (self.attack_hit and self.phase() == "recovery"):
            return False
        if spec["height"] == "air":
            if self.on_ground or self.air_used:
                return False
            self.air_used = True
            if spec.get("dive"):
                self.vy = spec["dive"]
        elif not self.on_ground:
            return False
        self.attack = kind
        self.attack_serial += 1
        self.attack_t = 0
        self.attack_landed = False
        self.attack_hit = False
        self.last_attack = kind
        if spec["height"] != "air" and not spec.get("dash"):
            self.vx = 0.0
        return True

    def start_dash(self, direction):
        if not self.alive or not self.on_ground or self.busy() or self.dash_cd > 0:
            return False
        self.dash_t = DASH["frames"]
        self.dash_dir = 1 if direction > 0 else -1
        self.dash_cd = DASH["cooldown"]
        self.crouching = False
        self.blocking = False
        return True

    def jump(self):
        if self.alive and self.on_ground and not self.busy():
            self.vy = JUMP_VELOCITY
            self.on_ground = False
            return True
        return False

    def take_hit(self, damage, knock, direction, hitstun, knockdown=0, launch=0):
        if self.special is not None and self.special.can_interrupt():
            self.cancel_special()
        self.attack = None
        self.attack_t = 0
        self.attack_landed = False
        self.attack_hit = False
        self.combo_queue = []
        self.windup = 0
        self.throw_t = 0
        self.dash_t = 0
        self.block_t = 0
        self.hp = max(0.0, self.hp - damage)
        self.hurt_t = hitstun
        self.flash = 6
        self.vx = knock * direction
        if knockdown:
            self.down_t = knockdown
            if self.on_ground:
                self.vy = -4.0
                self.on_ground = False
        if launch:
            self.vy = -launch
            self.on_ground = False
        self.meter = min(100.0, self.meter + damage * 0.5)

    def block_hit(self, chip, knock, direction, blockstun):
        self.hp = max(0.0, self.hp - chip)
        self.block_t = blockstun
        self.vx = knock * direction
        self.flash = 2

    def cancel_special(self):
        move = self.special
        self.special = None
        self.alpha = 255
        self.aura = None
        self.pose = None
        if move is not None:
            move.cancel()

    def tick(self):
        was_on_ground = self.on_ground
        if self.dash_t > 0:
            self.vx = self.dash_dir * DASH["speed"]
        if not self.on_ground:
            self.vy += GRAVITY
        self.y += self.vy
        if self.y >= FLOOR_Y:
            self.y = float(FLOOR_Y)
            self.vy = 0.0
            self.on_ground = True
        self.landed = self.on_ground and not was_on_ground
        if self.landed:
            self.air_used = False
            if self.attack and ATTACKS[self.attack].get("dive"):
                self.attack = None   # a dive ends the moment it lands
        self.x += self.vx
        if self.dash_t > 0:
            self.dash_t -= 1
            if self.dash_t == 0:
                self.vx = 0.0
        elif self.attack == "dash_punch":
            self.vx *= 0.9
        elif self.hurt_t > 0 or self.block_t > 0 or self.down_t > 0:
            self.vx *= 0.85
        self.x = clamp(self.x, LEFT_EDGE, RIGHT_EDGE)

        if self.attack:
            spec = ATTACKS[self.attack]
            self.attack_t += 1
            if self.attack_t >= spec["startup"] + spec["active"] + spec["recovery"]:
                if not self.attack_hit:
                    self.combo_queue = []
                self.attack = None
        for name in ("hurt_t", "block_t", "throw_t", "dash_cd", "invuln_t", "flash", "combo_t", "snare_t"):
            if getattr(self, name) > 0:
                setattr(self, name, getattr(self, name) - 1)
        if self.combo and self.combo_t == 0:
            self.combo = 0
        if self.down_t > 0:
            self.down_t -= 1
            if self.down_t == 0:
                self.invuln_t = 14   # a short window to get back up safely
        if self.ghost_hp > self.hp:
            self.ghost_hp = max(self.hp, self.ghost_hp - 0.5)
        else:
            self.ghost_hp = self.hp
        self.walk_t += 1
        if self.dash_t > 0:
            self.trail.append((self.x, self.y))
            del self.trail[:-TRAIL_LEN]
        elif self.trail:
            self.trail = []


def player_control(p, keys):
    free = p.alive and p.special is None and not p.busy()
    if not free:
        p.blocking = False
        p.crouching = False
        if p.special is not None or p.snare_t > 0:
            p.vx = 0.0
        return
    p.crouching = bool(keys[pygame.K_s]) and p.on_ground
    p.blocking = bool(keys[pygame.K_l]) and p.on_ground
    if p.crouching or p.blocking:
        p.vx = 0.0
    else:
        p.vx = (int(bool(keys[pygame.K_d])) - int(bool(keys[pygame.K_a]))) * WALK_SPEED


def _begin_windup(enemy, kind, frames):
    enemy.pending = kind
    enemy.windup = frames
    enemy.plan = "idle"
    enemy.vx = 0.0


def _windup_frames(enemy):
    """Stronger bosses read the player's moves faster, so their wind-ups are shorter."""
    return max(4, int(round(WINDUP_FRAMES * (1.15 - 0.55 * enemy.skill))))


def _reflex(enemy, player, dist):
    """Real-time reactions, checked every frame rather than on the think timer, so a skilled boss
    answers within a few frames. It blocks a strike it can read, punishes one that misses or is
    blocked, punishes a dash as it ends, and guards before a throw can land. Each strike is read
    once: the odds are rolled when it starts, not every frame. Returns True when the boss is busy
    reacting this frame."""
    skill = enemy.skill
    if enemy.guard_cd > 0:
        enemy.guard_cd -= 1
    if player.attack is not None and player.attack_serial != enemy.read_serial:
        enemy.read_serial = player.attack_serial
        enemy.read_block = random.random() < 0.3 + 0.65 * skill
        enemy.read_punish = random.random() < 0.35 + 0.6 * skill
    if player.attack is not None:
        phase = player.phase()
        delay = 2 + int((1 - skill) * 4)       # frames it takes to read a strike: 3 for early bosses, 2 for late ones
        reach = ATTACKS[player.attack]["reach"]
        if (enemy.read_block and phase in ("startup", "active") and player.attack_t >= delay
                and dist <= reach + 40):
            enemy.blocking = True
            return True
        if enemy.read_punish and phase == "recovery" and not player.attack_hit and dist <= 110:
            enemy.read_punish = False
            _begin_windup(enemy, "punch" if dist <= 92 else "kick", max(1, delay // 2))
            return True
    if player.dash_t == 2 and dist <= 150 and random.random() < 0.25 + 0.5 * skill:
        return enemy.start_attack("punch")
    if enemy.guard_t > 0:
        enemy.guard_t -= 1
        enemy.blocking = True
        return True
    if (enemy.guard_cd == 0 and dist <= THROW["range"] and player.on_ground and not player.busy()
            and random.random() < 0.05 + 0.2 * skill):
        enemy.guard_t = 12
        enemy.guard_cd = 40
        enemy.blocking = True
        return True
    return False


def ai_step(enemy, player, threat=None):
    """The boss brain. Returns a token when the game should do something for it:
    "fireball", "jump", "special", "throw", "dash_in" or "dash_back". Otherwise None.

    `threat` is (kind, x) when a stage hazard is about to land on the boss. A boss standing
    on its own stage is immune, so the game passes None for it and it ignores the stage."""
    dx = player.x - enemy.x
    dist = abs(dx)
    if not enemy.alive:
        return None
    # follow a combo string while each hit keeps connecting
    if enemy.attack and enemy.attack_hit and enemy.phase() == "recovery" and enemy.combo_queue:
        enemy.start_attack(enemy.combo_queue.pop(0))
        return None
    if enemy.windup > 0:
        enemy.vx = 0.0
        enemy.windup -= 1
        if enemy.windup == 0:
            enemy.start_attack(enemy.pending)
        return None
    if enemy.busy():
        enemy.blocking = False
        enemy.crouching = False
        return None
    if not player.alive:
        enemy.vx = 0.0
        enemy.blocking = False
        enemy.crouching = False
        return None
    enemy.facing = 1 if dx >= 0 else -1
    enemy.blocking = False
    enemy.crouching = False
    skill = enemy.skill

    if not enemy.on_ground:  # airborne: strike from the air
        if dist < 130 and random.random() < 0.4 + 0.3 * skill:
            enemy.start_attack(random.choice(("air_kick", "air_punch")))
        return None

    if _reflex(enemy, player, dist):
        return None

    if threat is not None:
        enemy.hazard_t += 1
        if enemy.hazard_t == 6:
            enemy.hazard_react = random.random() < 0.7
        if enemy.hazard_t >= 6 and enemy.hazard_react:
            kind, hx = threat
            if kind == "jump" and enemy.jump():
                return "jump"
            enemy.vx = (1 if enemy.x >= hx else -1) * enemy.speed * 1.5
            return None
    else:
        enemy.hazard_t = 0

    aggr = enemy.aggression
    enemy.think_t -= 1
    if enemy.think_t <= 0:
        enemy.think_t = max(6, random.randint(10, 22) - int(4 * skill))
        roll = random.random()
        in_startup = player.attack is not None and player.phase() == "startup" and dist < 150
        in_recovery = player.attack is not None and player.phase() == "recovery" and dist < 150
        if in_recovery and roll < 0.45 + 0.45 * skill:
            enemy.plan = "punish"
        elif in_startup and roll < 0.2 + 0.6 * skill:
            enemy.plan = "block"
        elif player.dash_t > 0 and dist < 170 and roll < 0.4 + 0.4 * skill:
            enemy.plan = "anti_dash"
        elif player.down_t > 0 and dist < 160 and roll < 0.7:
            enemy.plan = "pressure"
        elif (player.on_ground and dist < THROW["range"] and not player.blocking
              and roll < 0.06 + 0.14 * skill):
            enemy.plan = "throw"
        elif not player.on_ground and dist < 150 and roll < 0.5 + 0.3 * skill:
            enemy.plan = "anti_air"
        elif enemy.special_cd == 0 and 110 < dist < 520 and roll < 0.1 + 0.22 * skill:
            enemy.plan = "special"
        elif dist > 200 and enemy.dash_cd == 0 and roll < 0.1 + 0.12 * skill:
            enemy.plan = "dash_in"
        elif dist < 110 and player.attack is not None and enemy.dash_cd == 0 and roll < 0.25 + 0.2 * skill:
            enemy.plan = "dash_back"
        elif dist > 170 and enemy.meter >= 100 and roll < 0.5:
            enemy.plan = "fireball"
        elif dist > 150:
            enemy.plan = "approach"
        elif roll < 0.4 * aggr + 0.2:
            enemy.plan = "attack"
        elif roll < 0.55:
            enemy.plan = "approach" if dist > 100 else "idle"
        elif roll < 0.63:
            enemy.plan = "jump"
        elif roll < 0.74:
            enemy.plan = "crouch"
        elif roll < 0.84 and 60 < dist < 130:
            enemy.plan = "sweep"
        else:
            enemy.plan = "retreat"

    enemy.vx = 0.0
    plan = enemy.plan
    wf = _windup_frames(enemy)
    if plan == "approach":
        enemy.vx = enemy.speed * enemy.facing
    elif plan == "retreat":
        enemy.vx = -enemy.speed * 0.7 * enemy.facing
    elif plan == "attack":
        if dist <= 105:
            combos = enemy.combos
            if combos and random.random() < 0.5 + 0.3 * skill:
                combo = random.choice(combos)
                enemy.combo_queue = list(combo[1:])
                _begin_windup(enemy, combo[0], wf)
            else:
                _begin_windup(enemy, "punch" if random.random() < 0.55 else "kick", wf)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "punish":
        if dist <= 90:
            _begin_windup(enemy, "punch", 4)
        elif dist <= 130:
            _begin_windup(enemy, "kick", 5)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "anti_dash":
        if dist <= 120:
            _begin_windup(enemy, "punch", 4)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "pressure":
        if dist <= 110:
            _begin_windup(enemy, random.choice(("sweep", "low_punch")), wf)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "sweep":
        if dist <= 110:
            _begin_windup(enemy, "sweep", wf)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "anti_air":
        if dist <= 110:
            _begin_windup(enemy, "punch", 5)
        else:
            enemy.vx = enemy.speed * enemy.facing
    elif plan == "block":
        enemy.blocking = True
    elif plan == "crouch":
        enemy.crouching = True
    elif plan == "jump":
        enemy.plan = "idle"
        if enemy.jump():
            return "jump"
    elif plan == "throw":
        enemy.plan = "idle"
        return "throw"
    elif plan == "dash_in":
        enemy.plan = "idle"
        return "dash_in"
    elif plan == "dash_back":
        enemy.plan = "idle"
        return "dash_back"
    elif plan == "special":
        enemy.plan = "idle"
        return "special"
    elif plan == "fireball":
        enemy.plan = "idle"
        if enemy.meter >= 100:
            return "fireball"
    return None
