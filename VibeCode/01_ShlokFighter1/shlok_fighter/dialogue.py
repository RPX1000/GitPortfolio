"""Pre-fight dialogue: what each side says before every boss fight, and the typewriter
that reveals it. Each line is (speaker, text) where speaker is "hero" (Shlok) or "boss"."""

import textwrap

from .config import WHITE

DIALOGUE = {
    0: [  # Korean David, Lava Lake
        ("hero", "Itzama! Bandit! Burt! Hang on, I'm coming!"),
        ("boss", "Nobody walks out of my lava lake without going through me first."),
        ("hero", "Then get out of my way, David."),
        ("boss", "Brave words. Let's see if your legs can keep up with my Tornado Heel!"),
    ],
    1: [  # Sus Finance Bro, Trading Floor
        ("boss", "Relax, bro. Your friends are just a liquidity event."),
        ("hero", "They're my friends, not a spreadsheet."),
        ("boss", "Everything is a spreadsheet if you believe hard enough. Time for a short squeeze."),
        ("hero", "You can't even hold a position for ten seconds. Let's go."),
    ],
    2: [  # Ronak, Wind Tunnel
        ("hero", "Ronak! Where are Itzama, Bandit and Burt?"),
        ("boss", "Ask my wrench. It's the real boss of this garage."),
        ("hero", "A wrench? Ronak, that's not even a boss."),
        ("boss", "Watch it come back, then say that."),
    ],
    3: [  # Farmer Rogelio, Cornfield
        ("boss", "Son, these corn rows have seen tougher men than you."),
        ("hero", "Sir, I'm not here to farm. I'm here for my friends."),
        ("boss", "Then you'll have to get past my tractor. And my hay."),
        ("hero", "Hay? Sir, are you rolling those at me?"),
        ("boss", "Jump, son. Or get rolled."),
    ],
    4: [  # The Nak, Super Ronak's Arena
        ("boss", "I got bored of being regular Ronak. Now I am SUPER RONAK!"),
        ("hero", "Ronak, you're not super. You're just loud."),
        ("boss", "LOUD IS A SUPERPOWER!"),
        ("hero", "Fine. Let's see who slams first."),
    ],
    5: [  # Evil Shlok, Mirror Dimension
        ("boss", "Hello, Shlok. Nice hoodie. I have the same one, only cooler."),
        ("hero", "You're a reflection. You don't get a vote."),
        ("boss", "Every version of you gets a vote. Then I get your friends."),
        ("hero", "Clone yourself all you want. I've beaten copies of me before."),
    ],
    6: [  # Jeffrey Epstein, Island Ruins
        ("boss", "Your friends are my insurance, Shlok. Lovely people, stuck here until I'm paid."),
        ("hero", "You're holding them hostage. That ends today."),
        ("boss", "Such a dramatic little hero. Let's see how you handle the ruins."),
        ("hero", "Itzama, Bandit, Burt... this one's for you. Let's finish this."),
    ],
}


class Typewriter:
    """Reveals a list of (text, colour) lines one character at a time."""

    def __init__(self, lines, speed=0.9):
        self.lines = lines
        self.total = sum(len(s) for s, _ in lines)
        self.pos = 0.0
        self.speed = speed

    @property
    def done(self):
        return self.pos >= self.total

    def step(self):
        self.pos = min(self.total, self.pos + self.speed)

    def finish(self):
        self.pos = self.total

    def visible(self):
        left = int(self.pos)
        out = []
        for s, color in self.lines:
            out.append((s[:max(0, left)], color))
            left -= len(s)
        return out


class Dialogue:
    """Walks through one fight's exchange, one line at a time."""

    WRAP = 36

    def __init__(self, index):
        self.lines = DIALOGUE[index]
        self.total = len(self.lines)
        self.i = 0
        self._load()

    def _load(self):
        self.speaker, text = self.lines[self.i]
        wrapped = textwrap.wrap(text, self.WRAP)
        self.tw = Typewriter([(s, WHITE) for s in wrapped], speed=1.1)

    @property
    def typing(self):
        return not self.tw.done

    def update(self):
        self.tw.step()

    def finish_line(self):
        self.tw.finish()

    def advance(self):
        """Moves to the next line. Returns True once the exchange is over."""
        self.i += 1
        if self.i >= self.total:
            return True
        self._load()
        return False

    def visible(self):
        return self.tw.visible()
