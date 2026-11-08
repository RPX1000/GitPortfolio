"""Game controller: menus, story and dialogue, fights, combat, specials, KO slow-motion, results
and the ending.

All damage goes through hit_target, which decides between a parry, a block, a counter-hit and a
clean hit, and applies combo scaling, hitstun, knockdown and launches. Punches, kicks, specials,
projectiles, throws and stage hazards all use the same rules, so every fighter reacts the same
way. A boss picks its specials from its own moveset, and its ultimate unlocks when it is enraged."""

import math
import random

import pygame

from .config import (WIDTH, HEIGHT, FLOOR_Y, FPS, ROUND_FRAMES, ROUND_BANNER_FRAMES, KO_FRAMES, PUSH_W,
                     LEFT_EDGE, RIGHT_EDGE, ENEMIES, PLAYER, BUFFER_FRAMES, FADE_FRAMES, THROW, DASH,
                     PARRY_WINDOW, TECH_WINDOW, SNARE_MASH, combo_scale)
from .audio import Audio
from .dialogue import Dialogue, Typewriter
from .drawing import font, clamp, text
from .effects import Effects
from .fighter import Fighter, player_control, ai_step
from .hazards import Hazard
from .hud import draw_fight_hud, draw_round_banner, draw_ko, draw_callout
from .moves import MOVE_REGISTRY, PLAYER_SPECIAL
from .projectiles import Projectile
from .screens import (Menu, story_lines, ending_lines, draw_title, draw_controls, draw_select, draw_story,
                      draw_dialogue, draw_pause, draw_result, draw_ending)
from .sprites import draw_fighter, draw_shadow, bust, portrait
from .stages import make_stage, spawn_ambient, build_vignette

UP_KEYS = (pygame.K_w, pygame.K_UP)
DOWN_KEYS = (pygame.K_s, pygame.K_DOWN)
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
BACK_KEYS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)
MASH_KEYS = (pygame.K_j, pygame.K_k, pygame.K_i, pygame.K_w, pygame.K_l, pygame.K_s, pygame.K_a, pygame.K_d)
AMBIENT_STATES = ("title", "select", "controls", "story", "dialogue", "fight", "paused", "ko", "win", "lose",
                  "ending")
HITSTUN_DEFAULT = 14
BLOCKSTUN_DEFAULT = 8


def targetable(f):
    """A fighter can be hit while alive and visible (shadow-steps and clones are not)."""
    return f.alive and f.alpha > 0


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.scene = pygame.Surface((WIDTH, HEIGHT))
        self.audio = Audio()
        self.fx = Effects()
        self.vignette = build_vignette()
        self.black = pygame.Surface((WIDTH, HEIGHT))
        self.black.fill((0, 0, 0))
        self.t = 0
        self.state = "title"
        self.index = 0
        self.select_index = 0
        self.from_select = False   # True when the current fight was launched from boss select
        self.wants_quit = False
        self.arts = {}
        self.portraits = {}
        self.busts = {}
        self.small_busts = {}
        self.dlg_cache = {}
        self.hero_bust = None
        self.hero_portrait = None
        self.typewriter = None
        self.dialogue = None
        self.player = None
        self.enemy = None
        self.hazard = None
        self.projectiles = []
        self.gust = None
        self.banner_t = 0
        self.round_t = ROUND_FRAMES
        self.hitstop = 0
        self.best_combo = 0
        self.hits = 0
        self.damage_taken = 0.0
        self.prev_hp = 0.0
        self.ko_t = 0
        self.ko_label = "K.O."
        self.result_win = False
        self.callout = None
        self.slowmo = 0
        self.cam = 0.0
        self.buffer = {"punch": 0, "kick": 0, "uppercut": 0, "jump": 0}
        self.last_tap = {pygame.K_a: -999, pygame.K_d: -999}
        self.fade = None
        self.title_menu = Menu([("START", "start"), ("BOSS SELECT", "select"), ("CONTROLS", "controls"),
                                (self._sound_label(), "sound"), ("QUIT", "quit")])
        self.pause_menu = Menu([("RESUME", "resume"), ("RESTART FIGHT", "restart"),
                                (self._sound_label(), "sound"), ("QUIT TO TITLE", "title")])
        self.lose_menu = Menu([("RETRY", "retry"), ("QUIT TO TITLE", "title")])
        self.select_menu = Menu([("REMATCH", "retry"), ("BOSS SELECT", "select"), ("TITLE", "title")])
        self.menu = self.title_menu
        self.audio.set_music("menu")

    # ----- caches -----------------------------------------------------------

    def art(self, index=None):
        index = self.index if index is None else index
        if index not in self.arts:
            self.arts[index] = make_stage(ENEMIES[index])
        return self.arts[index]

    def portrait_for(self, index):
        if index not in self.portraits:
            self.portraits[index] = portrait(ENEMIES[index], 1.45)
        return self.portraits[index]

    def bust_for(self, index):
        if index not in self.busts:
            self.busts[index] = bust(ENEMIES[index])
        return self.busts[index]

    def small_bust(self, index):
        if index not in self.small_busts:
            self.small_busts[index] = pygame.transform.smoothscale(self.bust_for(index), (40, 40))
        return self.small_busts[index]

    def hero_images(self):
        if self.hero_bust is None:
            self.hero_bust = bust(PLAYER)
            self.hero_portrait = portrait(PLAYER, 1.5)
        return self.hero_bust, self.hero_portrait

    def dialogue_images(self, index):
        if index not in self.dlg_cache:
            hero = portrait(PLAYER, 1.6)
            boss = pygame.transform.flip(portrait(ENEMIES[index], 1.6), True, False)
            hero_dim = hero.copy()
            hero_dim.fill((118, 118, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
            boss_dim = boss.copy()
            boss_dim.fill((118, 118, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.dlg_cache[index] = {"hero": hero, "boss": boss, "hero_dim": hero_dim, "boss_dim": boss_dim}
        return self.dlg_cache[index]

    # ----- sound and display settings --------------------------------------

    def _sound_label(self):
        if not self.audio.enabled:
            return "SOUND: N/A"
        return "SOUND: OFF" if self.audio.muted else "SOUND: ON"

    def _refresh_sound_labels(self):
        label = self._sound_label()
        for menu in (self.title_menu, self.pause_menu):
            menu.relabel("sound", label)

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            pass

    # ----- transitions and flow --------------------------------------------

    def transition(self, action):
        """Fades to black, runs `action` at the darkest point, then fades back in."""
        if self.fade is None:
            self.fade = {"t": 0, "phase": "out", "action": action}

    def _update_fade(self):
        f = self.fade
        if f is None:
            return
        f["t"] += 1
        if f["phase"] == "out" and f["t"] >= FADE_FRAMES:
            f["action"]()
            f["phase"] = "in"
            f["t"] = 0
        elif f["phase"] == "in" and f["t"] >= FADE_FRAMES:
            self.fade = None

    def _fade_alpha(self):
        f = self.fade
        if f is None:
            return 0
        p = f["t"] / FADE_FRAMES
        return int(255 * (p if f["phase"] == "out" else 1 - p))

    def go_title(self):
        self.state = "title"
        self.menu = self.title_menu
        self.audio.set_music("menu")

    def open_story(self):
        self.typewriter = Typewriter(story_lines(ENEMIES[self.index]))
        self.state = "story"
        self.menu = None
        self.audio.preload(f"fight{self.index}")
        self.audio.set_music("menu")

    def open_dialogue(self):
        self.dialogue = Dialogue(self.index)
        self.state = "dialogue"
        self.menu = None
        self.audio.set_music("menu")

    def open_ending(self):
        self.typewriter = Typewriter(ending_lines())
        self.state = "ending"
        self.menu = None
        self.audio.set_music("menu")

    def open_select(self):
        """A prototyping screen: jump straight into a fight against any boss, in any order."""
        self.state = "select"
        self.menu = None
        self.select_index = self.index
        self.audio.set_music("menu")

    def _advance_story(self):
        self.index += 1
        self.open_story()

    def next_stage(self):
        if self.index + 1 >= len(ENEMIES):
            self.transition(self.open_ending)
        else:
            self.transition(self._advance_story)

    def start_fight(self):
        info = ENEMIES[self.index]
        self.player = Fighter(PLAYER["name"], PLAYER["color"], 200, 1, 100, True, look=PLAYER["look"],
                              hair=PLAYER["hair"], eye=PLAYER.get("eye"))
        self.enemy = Fighter(info["name"], info["color"], WIDTH - 200, -1, info["hp"], False,
                             look=info["look"], hair=info["hair"], eye=info.get("eye"), speed=info["speed"],
                             damage_mult=info["damage"], aggression=info["aggression"], skill=info["skill"])
        self.enemy.combos = info.get("combos", [])
        self.enemy.think_t = 30
        self.enemy.special_cd = 240
        self.hazard = Hazard(info["hazard"])
        self.projectiles = []
        self.gust = None
        self.callout = None
        self.slowmo = 0
        self.cam = 0.0
        self.buffer = {"punch": 0, "kick": 0, "uppercut": 0, "jump": 0}
        self.last_tap = {pygame.K_a: -999, pygame.K_d: -999}
        self.fx = Effects()
        self.banner_t = ROUND_BANNER_FRAMES
        self.round_t = ROUND_FRAMES
        self.hitstop = 0
        self.best_combo = self.hits = 0
        self.damage_taken = 0.0
        self.prev_hp = self.player.hp
        self.ko_t = 0
        self.state = "fight"
        self.menu = None
        self.audio.set_music(f"fight{self.index}")

    def run_action(self, action):
        if action == "start":
            self.index = 0
            self.from_select = False
            self.transition(self.open_story)
        elif action == "select":
            self.transition(self.open_select)
        elif action == "controls":
            self.state = "controls"
        elif action == "sound":
            self.audio.toggle_mute()
            self._refresh_sound_labels()
        elif action == "quit":
            self.wants_quit = True
        elif action == "resume":
            self.state = "fight"
            self.menu = None
        elif action in ("restart", "retry"):
            self.transition(self.start_fight)
        elif action == "title":
            self.transition(self.go_title)

    # ----- input ------------------------------------------------------------

    def on_key(self, key):
        if key == pygame.K_m:
            self.audio.toggle_mute()
            self._refresh_sound_labels()
            return
        if key == pygame.K_f:
            self.toggle_fullscreen()
            return
        if self.fade is not None:
            return

        if self.state == "title":
            self._menu_key(self.title_menu, key)
        elif self.state == "select":
            self._select_key(key)
        elif self.state == "controls":
            if key in BACK_KEYS + CONFIRM_KEYS:
                self.go_title()
        elif self.state == "story":
            self._story_key(key)
        elif self.state == "dialogue":
            self._dialogue_key(key)
        elif self.state == "fight":
            self._fight_key(key)
        elif self.state == "paused":
            self._menu_key(self.pause_menu, key, back="resume")
        elif self.state == "ko":
            if key in CONFIRM_KEYS:
                self.ko_t = 1
        elif self.state == "win":
            if self.menu is not None:
                self._menu_key(self.menu, key, back="title")
            elif key in CONFIRM_KEYS:
                self.next_stage()
        elif self.state == "lose":
            self._menu_key(self.menu, key, back="title")
        elif self.state == "ending":
            if key in CONFIRM_KEYS:
                if self.typewriter.done:
                    self.transition(self.go_title)
                else:
                    self.typewriter.finish()

    def _menu_key(self, menu, key, back=None):
        if key in UP_KEYS:
            menu.move(-1)
            self.audio.play("menu", 0.7)
        elif key in DOWN_KEYS:
            menu.move(1)
            self.audio.play("menu", 0.7)
        elif key in CONFIRM_KEYS:
            self.audio.play("select")
            self.run_action(menu.action())
        elif key in BACK_KEYS and back:
            self.run_action(back)

    def _story_key(self, key):
        if key in CONFIRM_KEYS:
            if self.typewriter.done:
                self.transition(self.open_dialogue)
            else:
                self.typewriter.finish()
        elif key in BACK_KEYS:
            self.transition(self.go_title)

    def _select_key(self, key):
        if key in UP_KEYS:
            self.select_index = (self.select_index - 1) % len(ENEMIES)
            self.audio.play("menu", 0.7)
        elif key in DOWN_KEYS:
            self.select_index = (self.select_index + 1) % len(ENEMIES)
            self.audio.play("menu", 0.7)
        elif key in CONFIRM_KEYS:
            self.audio.play("select")
            self.index = self.select_index
            self.from_select = True
            self.transition(self.start_fight)
        elif key in BACK_KEYS:
            self.transition(self.go_title)

    def _dialogue_key(self, key):
        if key in CONFIRM_KEYS:
            if self.dialogue.typing:
                self.dialogue.finish_line()
            elif self.dialogue.advance():
                self.transition(self.start_fight)
        elif key in BACK_KEYS:
            self.transition(self.start_fight)

    def _fight_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_p):
            self.state = "paused"
            self.menu = self.pause_menu
            self.pause_menu.sel = 0
            self.audio.play("menu", 0.7)
            return
        if self.banner_t > 0:
            return
        p = self.player
        if key == pygame.K_l:
            p.block_press_t = self.t   # tapping block is what makes a parry or a tech possible
        if p.snare_t > 0 and key in MASH_KEYS:
            p.snare_t = max(0, p.snare_t - SNARE_MASH)
            self.audio.play("menu", 0.4)
            return
        if key in (pygame.K_a, pygame.K_d):
            direction = 1 if key == pygame.K_d else -1
            if self.t - self.last_tap[key] <= DASH["tap_window"] and p.start_dash(direction):
                self.last_tap[key] = -999
                self.audio.play("whoosh", 0.5)
                self.fx.burst(p.x, FLOOR_Y - 4, (200, 190, 170), 6, speed=2.5, life=14, size=3, gravity=-0.02)
            else:
                self.last_tap[key] = self.t
        elif key == pygame.K_j:
            self.buffer["punch"] = BUFFER_FRAMES
        elif key == pygame.K_k:
            self.buffer["kick"] = BUFFER_FRAMES
        elif key == pygame.K_i:
            self.buffer["uppercut"] = BUFFER_FRAMES
        elif key == pygame.K_w:
            self.buffer["jump"] = BUFFER_FRAMES
        elif key == pygame.K_u and p.meter >= PLAYER_SPECIAL.cost and not p.busy():
            p.meter = 0.0
            self.start_special(p, PLAYER_SPECIAL)

    def _run_buffer(self, p, keys):
        """Runs button presses made a few frames early, once the fighter is free to act."""
        for name in ("punch", "kick", "uppercut", "jump"):
            if self.buffer[name] <= 0:
                continue
            if name == "jump":
                ok = p.jump()
            elif name == "punch":
                ok = self._punch(p, keys)
            elif name == "kick":
                ok = self._kick(p, keys)
            else:
                ok = self._uppercut(p)
            if ok:
                self.buffer[name] = 0
            else:
                self.buffer[name] -= 1

    def _punch(self, p, keys):
        if p.dash_t > 0 and p.on_ground:
            ok = p.start_attack("dash_punch")
        elif not p.on_ground:
            ok = p.start_attack("air_punch")
        elif p.crouching:
            ok = p.start_attack("low_punch")
        else:
            forward = keys[pygame.K_d] if p.facing > 0 else keys[pygame.K_a]
            if forward and self.try_throw(p):
                return True
            ok = p.start_attack("punch")
        if ok:
            self.audio.play("swing", 0.7)
        return ok

    def _kick(self, p, keys):
        if not p.on_ground:
            ok = p.start_attack("dive_kick" if keys[pygame.K_s] else "air_kick")
        elif p.crouching:
            ok = p.start_attack("sweep")
        else:
            ok = p.start_attack("kick")
        if ok:
            self.audio.play("swing", 1.0)
        return ok

    def _uppercut(self, p):
        ok = p.on_ground and p.start_attack("uppercut")
        if ok:
            self.audio.play("swing", 1.0)
        return bool(ok)

    # ----- update -----------------------------------------------------------

    def _ambient_kind(self):
        if self.state == "select":
            return ENEMIES[self.select_index]["hazard"]
        if self.state in ("title", "controls", "ending"):
            return "lava"
        return ENEMIES[self.index]["hazard"]

    def update(self, keys):
        self.t += 1
        self.fx.update()
        self._update_fade()
        if self.callout is not None:
            self.callout["t"] += 1
            if self.callout["t"] >= self.callout["life"]:
                self.callout = None
        if self.state in AMBIENT_STATES:
            spawn_ambient(self._ambient_kind(), self.fx)
        if self.state in ("story", "ending") and self.typewriter:
            self.typewriter.step()
        elif self.state == "dialogue" and self.dialogue:
            self.dialogue.update()
        if self.state == "fight":
            if self.slowmo > 0:
                self.slowmo -= 1
                if self.t % 2:  # bullet time: the world only moves on every other frame
                    return
            self.update_fight(keys)
        elif self.state == "ko":
            self.update_ko()

    def update_fight(self, keys):
        p, e = self.player, self.enemy
        if self.banner_t > 0:
            self.banner_t -= 1
            if ROUND_BANNER_FRAMES - self.banner_t == 72:
                self.audio.play("fight")
            return
        if self.hitstop > 0:
            self.hitstop -= 1
            return

        self.round_t -= 1
        self._tick_cooldowns()
        self._check_enrage()
        self._follow_camera()
        if not p.busy():
            p.facing = 1 if e.x >= p.x else -1
        player_control(p, keys)
        self._apply_ai_action(ai_step(e, p, self.threat_for(e)))
        self._run_buffer(p, keys)
        self._update_specials()
        self._apply_gust()
        self.step_bodies()
        for name, volume in self.hazard.update([p, e], self.projectiles, self.fx):
            self.audio.play(name, volume)
        self._apply_hazard_hits()
        self.update_projectiles()
        self.resolve_combat()
        self.push_apart()
        self.track_stats()
        self.check_round_end()

    def update_ko(self):
        self.ko_t -= 1
        if self.ko_t % 2 == 0:  # slow motion: the bodies move at half speed
            self.step_bodies()
        if self.ko_t <= 0:
            self.state = "win" if self.result_win else "lose"
            if self.from_select:
                self.menu = self.select_menu
            else:
                self.menu = None if self.result_win else self.lose_menu
            if self.menu is not None:
                self.menu.sel = 0
            self.audio.set_music("menu")

    def _tick_cooldowns(self):
        for f in (self.player, self.enemy):
            if f.special_cd > 0:
                f.special_cd -= 1
            for name in list(f.move_cd):
                if f.move_cd[name] > 0:
                    f.move_cd[name] -= 1

    def _check_enrage(self):
        e = self.enemy
        if not e.enraged and e.alive and e.hp <= e.max_hp * 0.5:
            e.enraged = True
            e.speed *= 1.15
            e.aggression = min(0.95, e.aggression + 0.15)
            e.cd_scale = 0.6
            e.skill = min(0.98, e.skill + 0.08)   # an enraged boss reads the player faster
            self.show_callout("ENRAGED!", (230, 70, 70), 70)
            self.fx.flash((230, 60, 60), 100)

    def _follow_camera(self):
        target = (self.player.x + self.enemy.x) / 2 - WIDTH / 2
        self.cam += (target - self.cam) * 0.12

    def _apply_gust(self):
        """Ronak's Fan Gale: a strong wind pushes the player back for a while."""
        g = self.gust
        if g is None:
            return
        g["t"] += 1
        if g["t"] >= g["life"]:
            self.gust = None
            return
        p = self.player
        if p.alive and not p.invulnerable():
            p.x = clamp(p.x + g["dir"] * 1.1, LEFT_EDGE, RIGHT_EDGE)
            if p.vx * g["dir"] < 0:
                p.vx *= 0.5   # moving against the gale is hard work
        if g["t"] % 3 == 0:
            self.fx.add(random.randint(0, WIDTH), random.randint(120, FLOOR_Y - 60), g["dir"] * 7.0, 0.0, 26,
                        (200, 225, 255), 2)

    def _apply_ai_action(self, action):
        e = self.enemy
        if action is None:
            return
        if action == "fireball":
            self.spawn_fireball(e)
            e.meter = 0.0
            self.audio.play("fire", 0.6)
        elif action == "jump":
            self.audio.play("jump", 0.5)
        elif action == "special":
            move_cls = self.choose_boss_move(e, self.player)
            if move_cls is None:
                e.special_cd = 30
            else:
                self.start_special(e, move_cls)
        elif action == "throw":
            self.try_throw(e)
        elif action == "dash_in":
            if e.start_dash(e.facing):
                self.audio.play("whoosh", 0.4)
        elif action == "dash_back":
            if e.start_dash(-e.facing):
                self.audio.play("whoosh", 0.4)

    def boss_pool(self):
        info = ENEMIES[self.index]
        pool = [MOVE_REGISTRY[name] for name in info["moves"]]
        if self.enemy.enraged and info.get("ultimate"):
            pool.append(MOVE_REGISTRY[info["ultimate"]])
        return pool

    def choose_boss_move(self, e, p):
        """Picks one of the boss's specials that is ready and suits the distance. Heavier moves
        are picked more often, and ultimates only exist once the boss is enraged."""
        ready = []
        for cls in self.boss_pool():
            if e.move_cd.get(cls.__name__, 0) > 0 or not cls.can_use(e, p):
                continue
            ready.append((cls, cls.weight))
        if not ready:
            return None
        r = random.uniform(0, sum(w for _, w in ready))
        for cls, w in ready:
            r -= w
            if r <= 0:
                return cls
        return ready[-1][0]

    def threat_for(self, f):
        """What is about to land on a fighter: a stage hazard or an incoming projectile. A boss on
        its own stage is immune to the stage, so it doesn't see stage hazards as threats."""
        threat = None if f.stage_immune() else self.hazard.threat_at(f.x)
        if threat is None:
            for pr in self.projectiles:
                if pr.owner is f:
                    continue
                if pr.owner is None and f.stage_immune():
                    continue
                incoming = (pr.vx > 0 and pr.x < f.x) or (pr.vx < 0 and pr.x > f.x)
                if incoming and abs(pr.x - f.x) < 110:
                    return ("move", pr.x)
        return threat

    def _update_specials(self):
        for f in (self.player, self.enemy):
            if f.special is not None:
                f.special.update()
                if f.special.done:
                    f.special = None

    def start_special(self, owner, move_cls):
        foe = self.player if owner is self.enemy else self.enemy
        if not owner.alive or owner.busy() or not move_cls.can_use(owner, foe):
            return None
        move = move_cls(self, owner)
        owner.special = move
        owner.move_cd[move_cls.__name__] = int(move.cooldown * owner.cd_scale)
        if owner is self.enemy:
            gap = 70 + 80 * (1.0 - owner.skill)
            owner.special_cd = int(gap * owner.cd_scale)
        owner.vx = 0.0
        owner.crouching = False
        owner.blocking = False
        return move

    def show_callout(self, msg, color, life=60):
        self.callout = {"text": msg, "color": color, "t": 0, "life": life}

    # ----- physics ------------------------------------------------------------

    def step_bodies(self):
        for f in (self.player, self.enemy):
            f.tick()
            if f.landed:
                self.fx.burst(f.x, FLOOR_Y - 2, (200, 190, 170), 6, speed=2.5, life=16, size=3,
                              gravity=-0.02, upward=0.5)
                self.audio.play("land", 0.5)
            if f.on_ground and abs(f.vx) > 0.5 and f.walk_t % 14 == 0:
                self.fx.add(f.x, FLOOR_Y - 2, -f.vx * 0.1, -0.4, 16, (200, 190, 170), 3, gravity=0.02)
            if f.attack and f.active_attack():
                r = f.strike_rect()
                self.fx.add(r.centerx, r.centery, random.uniform(-1, 1), random.uniform(-1, 1), 10,
                            (255, 255, 255), 3)

    def push_apart(self):
        p, e = self.player, self.enemy
        gap = abs(p.x - e.x)
        if gap < PUSH_W and p.on_ground and e.on_ground:
            overlap = (PUSH_W - gap) / 2
            direction = 1 if p.x >= e.x else -1
            p.x = clamp(p.x + direction * overlap, LEFT_EDGE, RIGHT_EDGE)
            e.x = clamp(e.x - direction * overlap, LEFT_EDGE, RIGHT_EDGE)

    def track_stats(self):
        lost = self.prev_hp - self.player.hp
        if lost > 0:
            self.damage_taken += lost
        self.prev_hp = self.player.hp

    # ----- combat -------------------------------------------------------------

    def spawn_fireball(self, owner):
        self.projectiles.append(Projectile(owner.x + owner.facing * 40, FLOOR_Y - 60, owner.facing * 9.0, 0.0,
                                           owner=owner, damage=16 * owner.damage_mult, knock=5,
                                           kind="fireball", radius=14, life=260, color=owner.color))

    def _is_open_to_counter(self, target):
        """A fighter is open to a counter-hit while it is starting an attack or winding up a special."""
        if target.attack is not None and target.phase() == "startup":
            return True
        if target.windup > 0:
            return True
        return target.special is not None and target.special.winding

    def _parry(self, target, attacker, direction, spot):
        x, y = spot
        target.block_press_t = -999
        attacker.take_hit(0, 3, -direction, 26)
        self.fx.spark(x, y, (255, 255, 255), 22, 10)
        self.fx.ring(x, y, (255, 240, 160), 70, 14, 5)
        self.fx.text(x - 26, y - 56, "PARRY!", (255, 240, 160))
        self.hitstop = max(self.hitstop, 8)
        self.fx.shake = max(self.fx.shake, 4)
        self.audio.play("select", 0.9)
        return "parry"

    def hit_target(self, target, damage, knock, direction, attacker, spot, sound, hitstun, blockstun,
                   knockdown=0, kind="normal", launch=0):
        """Resolves one hit. Returns "hit", "block", "parry" or "miss"."""
        if target.invulnerable():
            return "miss"
        x, y = spot
        blockable = kind in ("normal", "projectile")
        if (blockable and attacker is not None and target.is_player and target.on_ground
                and target.hurt_t == 0 and self.t - target.block_press_t <= PARRY_WINDOW):
            return self._parry(target, attacker, direction, spot)
        if blockable and target.blocking and target.on_ground and target.hurt_t == 0:
            target.block_hit(damage * 0.2, knock * 0.5, direction, blockstun)
            if attacker is not None:
                attacker.meter = min(100.0, attacker.meter + 3)
            self.fx.burst(x, y, (200, 230, 255), 6, speed=3, life=14, size=3, gravity=0.1)
            self.fx.spark(x, y, (200, 230, 255), 10, 6)
            self.fx.text(x - 14, y - 40, "BLOCK", (200, 230, 255))
            self.hitstop = max(self.hitstop, 2)
            self.audio.play("block", 0.8)
            return "block"

        counter = kind in ("normal", "projectile") and self._is_open_to_counter(target)
        if attacker is not None and kind != "hazard":
            # hitting someone who is still reeling from your last hit extends the combo
            attacker.combo = attacker.combo + 1 if (target.hurt_t > 0 and attacker.combo_t > 0) else 1
            attacker.combo_t = 90
            damage *= combo_scale(attacker.combo)
        if counter:
            damage *= 1.25

        target.take_hit(damage, knock, direction, hitstun, knockdown, launch)
        if attacker is not None:
            attacker.meter = min(100.0, attacker.meter + 9)
        if attacker is self.player and kind != "hazard":
            self.hits += 1
            self.best_combo = max(self.best_combo, attacker.combo)

        self.fx.spark(x, y, (255, 245, 190) if not counter else (255, 150, 70), 16 + min(10, damage), 9)
        self.fx.burst(x, y, (255, 240, 170), 10, speed=5, life=20, size=4, gravity=0.2)
        self.fx.burst(x, y, target.color, 3, speed=3, life=18, size=3, gravity=0.15)
        self.fx.text(x - 14, y - 40, f"-{max(1, int(round(damage)))}", (255, 230, 120))
        if counter:
            self.fx.text(x - 34, y - 66, "COUNTER!", (255, 130, 60))
            self.fx.ring(x, y, (255, 130, 60), 60, 12, 4)
        self.hitstop = max(self.hitstop, 4 + int(damage / 3) + (4 if counter else 0))
        self.fx.shake = max(self.fx.shake, int(3 + damage * 0.4))
        self.audio.play(sound, 0.9)
        return "hit"

    def apply_hit(self, target, damage, knock, direction, attacker=None, spot=None, sound="hit", kind="normal",
                  hitstun=None, blockstun=None, knockdown=0):
        """Entry point for specials and projectiles."""
        spot = spot or (target.x, target.y - 80)
        return self.hit_target(target, damage, knock, direction, attacker, spot, sound,
                               HITSTUN_DEFAULT if hitstun is None else hitstun,
                               BLOCKSTUN_DEFAULT if blockstun is None else blockstun, knockdown, kind)

    def try_throw(self, attacker):
        foe = self.enemy if attacker is self.player else self.player
        if attacker.busy() or not attacker.on_ground or not foe.on_ground:
            return False
        if abs(foe.x - attacker.x) > THROW["range"] or not targetable(foe) or foe.invulnerable():
            return False
        if foe.blocking or foe.special is not None or foe.hurt_t > 0 or foe.block_t > 0 or foe.down_t > 0:
            return False
        direction = 1 if foe.x >= attacker.x else -1
        if foe.is_player and self.t - foe.block_press_t <= TECH_WINDOW:
            # a tap of block just before the throw breaks it
            foe.block_press_t = -999
            foe.vx = direction * 3.0
            attacker.vx = -direction * 3.0
            self.fx.text(foe.x - 22, foe.y - 150, "TECH!", (150, 255, 200))
            self.audio.play("block", 0.9)
            return False
        attacker.facing = direction
        attacker.throw_t = THROW["pose_frames"]
        attacker.vx = 0.0
        spot = ((attacker.x + foe.x) / 2, foe.y - 84)
        self.hit_target(foe, THROW["damage"] * attacker.damage_mult, THROW["knock"], direction, attacker, spot,
                        "punch", THROW["hitstun"], 0, THROW["knockdown"], "throw")
        self.fx.text(spot[0] - 30, spot[1] - 70, "THROW!", (255, 210, 90))
        self.fx.ring(spot[0], spot[1], (255, 210, 90), 60, 14, 5)
        self.hitstop = max(self.hitstop, 9)
        return True

    def resolve_combat(self):
        """Checks every live attack hitbox against the other fighter."""
        p, e = self.player, self.enemy
        for attacker, target in ((p, e), (e, p)):
            spec = attacker.active_attack()
            if spec is None or not targetable(target) or target.invulnerable():
                continue
            if not attacker.strike_rect().colliderect(target.hurtbox()):
                continue
            height = spec["height"]
            if height == "high" and target.crouching and target.on_ground:
                continue
            if height in ("mid", "low") and not target.on_ground:
                continue
            direction = 1 if target.x >= attacker.x else -1
            spot = ((attacker.x + target.x) / 2, target.y - 84)
            result = self.hit_target(target, spec["damage"] * attacker.damage_mult, spec["knock"], direction,
                                     attacker, spot, spec["sound"], spec["hitstun"], spec["blockstun"],
                                     spec.get("knockdown", 0), "normal", spec.get("launch", 0))
            attacker.attack_landed = True
            if result == "hit":
                attacker.attack_hit = True

    def _apply_hazard_hits(self):
        for target, damage, knock, direction, hitstun, sound in self.hazard.take_hits():
            if not targetable(target):
                continue
            self.hit_target(target, damage, knock, direction, None, (target.x, target.y - 70), sound,
                            hitstun, 0, 0, "hazard")

    def update_projectiles(self):
        keep = []
        for pr in self.projectiles:
            pr.update()
            if pr.landed:
                self.impact(pr.x, FLOOR_Y, pr.color, shake=8)
                continue
            if pr.dead:
                continue
            if pr.kind == "lava_fist":
                self.fx.add(pr.x - pr.vx * 0.6 + random.uniform(-6, 6), pr.y + random.uniform(-14, 14),
                            random.uniform(-1.2, 1.2) - pr.vx * 0.1, random.uniform(-1.6, 0.2), 22,
                            random.choice([(255, 140, 40), (255, 200, 90)]), random.randint(3, 6),
                            gravity=-0.02)
            for target in (self.player, self.enemy):
                if target is pr.owner or not targetable(target) or id(target) in pr.hit_ids:
                    continue
                if pr.owner is None and target.stage_immune():
                    continue   # the stage's own fireballs pass a boss standing on its stage
                if pr.rect().colliderect(target.hurtbox()):
                    direction = 1 if target.x >= pr.x else -1
                    self.apply_hit(target, pr.damage, pr.knock, direction, pr.owner, (pr.x, pr.y), "hit",
                                   kind="projectile")
                    pr.hit_ids.add(id(target))
                    if pr.kind == "lava_fist":
                        self.explode(pr.x, pr.y, pr.color)
                    if not pr.pierce:
                        pr.dead = True
                        break
            if not pr.dead:
                keep.append(pr)
        self.projectiles = keep

    def explode(self, x, y, color):
        """The Lava Fist's detonation."""
        self.fx.burst(x, y, (255, 240, 180), 36, speed=9, life=34, size=6, gravity=0.18)
        self.fx.burst(x, y, color, 22, speed=6, life=28, size=4, gravity=0.12)
        self.fx.ring(x, y, color, 170, 26, 10)
        self.fx.ring(x, y, (255, 245, 210), 110, 18, 5)
        self.fx.shake = max(self.fx.shake, 14)
        self.fx.flash((255, 190, 110), 110)
        self.hitstop = max(self.hitstop, 9)
        self.audio.play("boom", 1.0)

    def impact(self, x, y, color, shake=6):
        """A heavy landing: dust, a ring and a jolt of shake."""
        self.fx.burst(x, y - 4, color, 14, speed=4, life=24, size=4, gravity=0.2, upward=1.5)
        self.fx.ring(x, y, color, 70, 16, 5)
        self.fx.shake = max(self.fx.shake, shake)
        self.audio.play("thud", 0.6)

    # ----- round flow ---------------------------------------------------------

    def check_round_end(self):
        p, e = self.player, self.enemy
        if p.alive and e.alive and self.round_t > 0:
            return
        if not p.alive:
            self.result_win, self.ko_label = False, "K.O."
        elif not e.alive:
            self.result_win, self.ko_label = True, "K.O."
        else:
            self.result_win, self.ko_label = p.hp >= e.hp, "TIME UP"
        for f in (p, e):
            f.cancel_special()
            f.attack = None
            f.windup = 0
            f.vx = 0.0
            f.dash_t = 0
            f.throw_t = 0
            f.snare_t = 0
        self.projectiles = []
        self.gust = None
        self.callout = None
        self.state = "ko"
        self.ko_t = KO_FRAMES
        self.fx.shake = max(self.fx.shake, 12)
        self.fx.flash((255, 255, 255) if self.result_win else (200, 40, 40), 150)
        self.audio.play("ko")

    def result_stats(self):
        seconds = int((ROUND_FRAMES - self.round_t) / FPS)
        return {
            "hits": self.hits,
            "combo": self.best_combo,
            "taken": int(round(self.damage_taken)),
            "time": f"{seconds // 60}:{seconds % 60:02d}",
        }

    # ----- drawing ----------------------------------------------------------

    def draw(self, surf):
        st = self.state
        if st == "title":
            draw_title(surf, self.art(0), self.t, self.title_menu)
            self.fx.draw(surf, font(16, True))
        elif st == "select":
            busts = [self.small_bust(i) for i in range(len(ENEMIES))]
            draw_select(surf, self.art(self.select_index), self.t, self.select_index, busts)
            self.fx.draw(surf, font(16, True))
        elif st == "controls":
            draw_controls(surf, self.art(0), self.t)
        elif st == "story":
            draw_story(surf, self.art(self.index), self.t, self.index, self.portrait_for(self.index),
                       self.typewriter, ENEMIES[self.index])
            self.fx.draw(surf, font(16, True))
        elif st == "dialogue":
            draw_dialogue(surf, self.art(self.index), self.t, self.dialogue,
                          self.dialogue_images(self.index), ENEMIES[self.index])
            self.fx.draw(surf, font(16, True))
        elif st == "ending":
            _, hero_portrait = self.hero_images()
            draw_ending(surf, self.art(0), self.t, hero_portrait, self.typewriter, self.fx)
        else:
            self.draw_scene(surf)
            self.draw_overlays(surf)
        alpha = self._fade_alpha()
        if alpha:
            self.black.set_alpha(alpha)
            surf.blit(self.black, (0, 0))
        self.fx.draw_flash(surf)

    def _current_dim(self):
        best = 0
        for f in (self.player, self.enemy):
            m = f.special
            if m is not None and m.winding and m.dim:
                best = max(best, int(m.dim * m.t / m.telegraph))
        return best

    def _draw_warnings(self, sc):
        """A flashing "!" over a boss that is winding up a special."""
        e = self.enemy
        m = e.special
        if m is not None and m.warning and m.winding and e.alive:
            col = (255, 80, 80) if (self.t // 5) % 2 == 0 else (255, 225, 90)
            text(sc, "!", font(44, True), col, (int(e.x), FLOOR_Y - 168), anchor="center")

    def _draw_gust(self, sc):
        """Fan Gale's wind: faint streaks across the arena while the gale blows."""
        g = self.gust
        if g is None:
            return
        for k in range(10):
            y = 130 + k * 28
            x = (self.t * 9 * g["dir"] + k * 120) % (WIDTH + 200) - 100
            pygame.draw.line(sc, (200, 225, 255), (x, y), (x + g["dir"] * -40, y + 4), 2)

    def _draw_fighter_state(self, sc, f):
        if not f.alive or f.down_t > 0:
            # knocked out or down: the body lies on the floor
            draw_fighter(sc, f, cx=f.x, feet=FLOOR_Y + 55, angle=90 * f.facing)
            return
        draw_shadow(sc, f.x, 1.0 if f.on_ground else 0.5)
        if f.dash_t > 0 or f.trail:
            for i, (tx, ty) in enumerate(f.trail):   # afterimages while dashing
                draw_fighter(sc, f, cx=tx, feet=ty, alpha=28 + 24 * i)
        draw_fighter(sc, f)

    def draw_scene(self, surf):
        art = self.art()
        sc = self.scene
        art.draw_back(sc, self.t, self.cam, self.hazard)
        self.hazard.draw(sc, font(13, True))
        self._draw_gust(sc)
        dim = self._current_dim()
        if dim:
            self.black.set_alpha(dim)
            sc.blit(self.black, (0, 0))
        for f in (self.enemy, self.player):
            if f.special is not None:
                f.special.draw_back(sc)
        for f in (self.enemy, self.player):
            self._draw_fighter_state(sc, f)
        for f in (self.enemy, self.player):
            if f.special is not None:
                f.special.draw(sc)
        for pr in self.projectiles:
            pr.draw(sc)
        self._draw_warnings(sc)
        self.fx.draw(sc, font(16, True))
        art.draw_front(sc, self.t)
        sc.blit(self.vignette, (0, 0))
        shake = int(self.fx.shake)
        ox = random.randint(-shake, shake) if shake > 0 else 0
        oy = random.randint(-shake, shake) if shake > 0 else 0
        surf.blit(sc, (ox, oy))

    def draw_overlays(self, surf):
        st = self.state
        info = ENEMIES[self.index]
        if st in ("fight", "ko", "paused", "win", "lose"):
            self.draw_hud(surf)
        if st == "fight" and self.banner_t > 0:
            draw_round_banner(surf, ROUND_BANNER_FRAMES - self.banner_t, info["stage"],
                              info["hazard_text"], info["accent"])
        if self.callout is not None and st in ("fight", "ko"):
            c = self.callout
            draw_callout(surf, c["text"], c["color"], c["t"], c["life"])
        if st == "ko":
            draw_ko(surf, self.ko_label, KO_FRAMES - self.ko_t)
        if st == "paused":
            draw_pause(surf, self.pause_menu)
        if st in ("win", "lose"):
            draw_result(surf, st == "win", info, self.result_stats(), self.menu, self.t)

    def draw_hud(self, surf):
        info = ENEMIES[self.index]
        seconds = max(0, math.ceil(self.round_t / FPS))
        label = f"STAGE {self.index + 1} OF {len(ENEMIES)}  -  {info['stage'].upper()}"
        draw_fight_hud(surf, self.player, self.enemy, (self.hero_images()[0], self.bust_for(self.index)),
                       label, seconds, self.player.combo, self.t, info["accent"])
