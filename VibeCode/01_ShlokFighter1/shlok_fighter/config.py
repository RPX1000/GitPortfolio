"""Shared constants, palette, frame data and game data for Shlok Fighter 1."""

VERSION = "1.3"

WIDTH, HEIGHT = 960, 540
FPS = 60
FLOOR_Y = 440

GRAVITY = 0.8
JUMP_VELOCITY = -15.5
WALK_SPEED = 4.2
ROUND_FRAMES = 60 * 60
ROUND_BANNER_FRAMES = 150
KO_FRAMES = 150
BUFFER_FRAMES = 8        # how long an early button press is remembered
FADE_FRAMES = 12         # length of each half of a screen fade
PARRY_WINDOW = 6         # frames before a hit in which tapping block turns it into a parry
TECH_WINDOW = 8          # frames before a throw in which tapping block techs it
SNARE_MASH = 6           # snare time removed by each button press while snared
LEFT_EDGE, RIGHT_EDGE = 44, WIDTH - 44

FIGHTER_H = 144     # standing hurtbox height, in world pixels
CROUCH_H = 112      # crouching hurtbox height
BODY_W = 44         # hurtbox width
PUSH_W = 42         # fighters are pushed apart when closer than this

WHITE = (255, 255, 255)
INK = (16, 13, 22)
OUTLINE = (22, 16, 26)
GOLD = (255, 200, 60)
RED = (230, 70, 70)
MUTED = (150, 150, 168)
SKIN = (238, 198, 152)
PANTS = (46, 44, 64)

PLAYER = {"name": "Shlok", "color": (60, 140, 255), "hair": (30, 26, 40), "look": "headband",
          "eye": (70, 46, 34)}

OPENING_STORY = (
    "Shlok awakes in the middle of a lava lake (Santa Ana, CA), and he finds that "
    "Itzama, the Bandit, and RigoBerto \"Burt\" McWilliams have been kidnapped by his "
    "ultimate OPP - Jeffrey Epstein. This quick heartwarming story follows the fights "
    "of Shlok to save his friends."
)

ENDING_STORY = (
    "Shlok defeats Jeffrey Epstein and frees Itzama, the Bandit, and RigoBerto "
    "\"Burt\" McWilliams. The lava lake cools, the friends are reunited, and everyone "
    "goes home for dinner. THE END."
)

CONTROLS = [
    ("A  /  D", "Move; double-tap to dash or backdash"),
    ("W", "Jump"),
    ("S", "Crouch (S + J low punch, S + K sweep)"),
    ("L", "Block (hold). Tap just before a hit to parry, or a throw to tech"),
    ("J", "Punch (D + J up close to throw; dash + J dash punch)"),
    ("K", "Kick (air + K air kick; air + S + K dive kick)"),
    ("I", "Uppercut launcher (juggle with air attacks)"),
    ("U", "Lava Fist super (needs a full meter)"),
    ("P  /  ESC", "Pause"),
    ("M", "Mute or unmute sound"),
    ("F", "Toggle fullscreen"),
]

# Each boss owns its stage: it is immune to that stage's hazards while standing, and
# becomes exposed to them while stunned. "moves" are its two regular specials, "ultimate"
# unlocks when it is enraged (below half health), "combos" are its normal attack strings,
# and "skill" (0 to 1) sets how well it reads and reacts.
ENEMIES = [
    {
        "name": "Korean David", "color": (220, 70, 70), "hp": 90, "speed": 2.4,
        "damage": 1.0, "aggression": 0.5, "skill": 0.55, "look": "spiky", "hair": (25, 20, 28),
        "eye": (40, 30, 36), "stage": "Lava Lake, Santa Ana", "hazard": "lava", "accent": (255, 130, 50),
        "hazard_text": "Lava geysers erupt across the obsidian floor. Watch the glowing warning strips.",
        "intro": "Korean David blocks the only way out of the lava lake.",
        "moves": ["TornadoHeel", "HeelDrop"], "ultimate": "LavaGeysers",
        "combos": [["kick", "kick", "sweep"], ["low_punch", "kick"]],
    },
    {
        "name": "Sus Finance Bro", "color": (58, 120, 84), "hp": 150, "speed": 2.6,
        "damage": 1.35, "aggression": 0.55, "skill": 0.8, "look": "slick", "hair": (70, 46, 24),
        "eye": (60, 52, 40), "stage": "The Trading Floor", "hazard": "money", "accent": (120, 230, 140),
        "hazard_text": "Money bags rain down from the market crash. Don't get caught under one.",
        "intro": "Sus Finance Bro wants a cut of the rescue fund and is throwing money bags.",
        "moves": ["ShortSqueeze", "MarginCall"], "ultimate": "BullRun",
        "combos": [["punch", "punch", "kick"], ["punch", "uppercut"]],
    },
    {
        "name": "Ronak", "color": (196, 40, 120), "hp": 105, "speed": 2.8,
        "damage": 1.1, "aggression": 0.6, "skill": 0.68, "look": "dapper", "hair": (24, 18, 22),
        "eye": (40, 26, 20), "stage": "Ronak's Wind Tunnel", "hazard": "wind", "accent": (170, 210, 255),
        "hazard_text": "Gusts of wind shove both fighters across the arena.",
        "intro": "Ronak has set up a wind tunnel in his garage and is not letting anyone leave.",
        "moves": ["WrenchBoomerang", "FanGale"], "ultimate": "ToolboxStorm",
        "combos": [["punch", "punch", "kick"], ["kick", "sweep"]],
    },
    {
        "name": "Farmer Rogelio", "color": (120, 80, 46), "hp": 130, "speed": 2.8,
        "damage": 1.15, "aggression": 0.65, "skill": 0.72, "look": "straw", "hair": (120, 80, 40),
        "eye": (60, 40, 30), "stage": "Rogelio's Cornfield", "hazard": "tractor", "accent": (150, 220, 90),
        "hazard_text": "A tractor rolls through the field. Jump it or get flattened.",
        "intro": "Farmer Rogelio defends the cornfield with his tractor and his fists.",
        "moves": ["HayRoll", "PitchforkSpikes"], "ultimate": "TractorCharge",
        "combos": [["sweep", "punch"], ["punch", "kick"]],
    },
    {
        "name": "The Nak (Super Ronak)", "color": (240, 200, 40), "hp": 130, "speed": 3.0,
        "damage": 1.25, "aggression": 0.7, "skill": 0.78, "look": "gold", "hair": (255, 215, 60),
        "eye": (70, 150, 255), "stage": "Super Ronak's Arena", "hazard": "shockwave", "accent": (255, 220, 80),
        "hazard_text": "Ground shockwaves burst out from the center. Jump them.",
        "intro": "The Nak powers up into Super Ronak and the arena starts to shake.",
        "moves": ["ThunderSlam", "ChainLightning"], "ultimate": "GoldenBeam",
        "combos": [["punch", "punch", "uppercut"], ["kick", "kick"]],
    },
    {
        "name": "Evil Shlok", "color": (92, 32, 124), "hp": 125, "speed": 3.2,
        "damage": 1.3, "aggression": 0.8, "skill": 0.85, "look": "hood", "hair": (20, 16, 26),
        "eye": (255, 70, 70), "stage": "Mirror Dimension", "hazard": "mirror", "accent": (180, 110, 255),
        "hazard_text": "Violet fireballs fly in from both sides of the mirror dimension.",
        "intro": "Evil Shlok is your own reflection, and it fights dirty.",
        "moves": ["ShadowClones", "MirrorMimic"], "ultimate": "VoidOrbs",
        "combos": [["punch", "punch", "sweep"], ["punch", "uppercut"]],
    },
    {
        "name": "Jeffrey Epstein", "color": (110, 116, 130), "hp": 200, "speed": 3.2,
        "damage": 1.4, "aggression": 0.85, "skill": 0.94, "look": "gray", "hair": (196, 196, 202),
        "eye": (80, 84, 96), "stage": "Island Ruins", "hazard": "rubble", "accent": (230, 200, 130),
        "hazard_text": "Rubble crashes down on random spots. Keep moving.",
        "intro": "The final boss waits in the ruins to hold your friends hostage.",
        "moves": ["RuinCollapse", "VineSnare"], "ultimate": "FinalCollapse",
        "combos": [["punch", "kick", "uppercut"], ["sweep", "kick"]],
    },
]

# Frame data. Each attack has three parts: startup (vulnerable to counter-hits), active
# (the hitbox is live) and recovery (a landed attack can be cancelled into the next one).
#   box:    (top offset from the feet, height) of the hitbox
#   height: high misses crouching fighters; mid misses airborne fighters;
#           low hits grounded fighters (standing or crouching); air hits anyone
#   launch: the target is knocked into the air with this lift
#   dive:   a fast downward strike that ends on landing
#   dash:   only available while dashing, and lunges forward
ATTACKS = {
    "punch":     {"startup": 4, "active": 3, "recovery": 10, "damage": 6, "reach": 56,
                  "box": (-108, 46), "hitstun": 14, "blockstun": 8, "knock": 4,
                  "height": "high", "sound": "punch"},
    "kick":      {"startup": 8, "active": 4, "recovery": 15, "damage": 11, "reach": 74,
                  "box": (-104, 92), "hitstun": 18, "blockstun": 11, "knock": 7,
                  "height": "mid", "sound": "kick"},
    "low_punch": {"startup": 5, "active": 3, "recovery": 11, "damage": 6, "reach": 52,
                  "box": (-44, 34), "hitstun": 14, "blockstun": 8, "knock": 3,
                  "height": "low", "sound": "punch"},
    "sweep":     {"startup": 10, "active": 4, "recovery": 20, "damage": 8, "reach": 72,
                  "box": (-30, 30), "hitstun": 16, "blockstun": 12, "knock": 4,
                  "height": "low", "knockdown": 36, "sound": "kick"},
    "uppercut":  {"startup": 6, "active": 4, "recovery": 16, "damage": 10, "reach": 44,
                  "box": (-124, 90), "hitstun": 26, "blockstun": 12, "knock": 2,
                  "height": "high", "launch": 9, "sound": "kick"},
    "dash_punch": {"startup": 2, "active": 3, "recovery": 12, "damage": 8, "reach": 66,
                   "box": (-108, 48), "hitstun": 16, "blockstun": 9, "knock": 6,
                   "height": "high", "dash": True, "sound": "punch"},
    "air_punch": {"startup": 3, "active": 12, "recovery": 12, "damage": 7, "reach": 46,
                  "box": (-96, 60), "hitstun": 16, "blockstun": 8, "knock": 5,
                  "height": "air", "sound": "punch"},
    "air_kick":  {"startup": 4, "active": 12, "recovery": 12, "damage": 9, "reach": 52,
                  "box": (-80, 60), "hitstun": 18, "blockstun": 9, "knock": 6,
                  "height": "air", "sound": "kick"},
    "dive_kick": {"startup": 4, "active": 30, "recovery": 14, "damage": 12, "reach": 40,
                  "box": (-40, 52), "hitstun": 20, "blockstun": 10, "knock": 3,
                  "height": "air", "dive": 16, "knockdown": 26, "sound": "kick"},
}

THROW = {"damage": 12, "range": 66, "hitstun": 24, "knock": 12, "knockdown": 22, "pose_frames": 14}
DASH = {"frames": 12, "speed": 9.5, "cooldown": 26, "tap_window": 14, "invuln": True}
COMBO_STEP = 0.1         # each extra hit in a combo does 10% less damage (never below half)


def combo_scale(hits):
    return max(0.5, 1.0 - COMBO_STEP * (hits - 1))
