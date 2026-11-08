"""Sound effects and music, synthesised in code so the game ships without audio files.

If no audio device is available the game simply runs silent. The hot per-sample loops
(_sweep, _noise, _render_track) hand off to a small compiled library when one has been
built (see native/build.sh) and fall back to the plain-Python versions otherwise."""

import array
import ctypes
import math
import os
import random
import sys

import pygame

RATE = 22050
MUSIC_VOLUME = 0.22
SFX_VOLUME = 0.7
MUSIC_CHANNEL = 0

_MINOR = (0, 3, 7)
_MAJOR = (0, 4, 7)
_WAVE_IDS = {"sine": 0, "square": 1, "tri": 2}
_rate = RATE   # replaced by the mixer's real sample rate once it is open


def _load_native():
    """Loads the compiled synth library for this platform, if native/build.sh has been run."""
    names = {"darwin": "libsynth.dylib", "linux": "libsynth.so", "win32": "synth.dll"}
    name = next((n for prefix, n in names.items() if sys.platform.startswith(prefix)), None)
    if name is None:
        return None
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native", name)
    if not os.path.exists(path):
        return None
    try:
        lib = ctypes.CDLL(path)
        d, i, ui = ctypes.c_double, ctypes.c_int, ctypes.c_uint
        dp, ip = ctypes.POINTER(d), ctypes.POINTER(i)
        lib.sweep.argtypes = [d, d, i, d, d, i, dp, i]
        lib.sweep.restype = None
        lib.noise.argtypes = [d, d, d, ui, dp, i]
        lib.noise.restype = None
        lib.render_track.argtypes = [d, d, d, i, dp, ip, i, i, i, i, ui, i, dp]
        lib.render_track.restype = None
        return lib
    except OSError:
        return None


_native = _load_native()

TRACKS = {
    "menu": {"seed": 1, "root": 45, "bpm": 72, "chords": [(0, "m"), (8, "M")], "arp": True},
    "fight0": {"seed": 2, "root": 40, "bpm": 110, "chords": [(0, "m"), (8, "M"), (5, "M"), (7, "M")],
               "kick": True, "hats": True},
    "fight1": {"seed": 3, "root": 43, "bpm": 116, "chords": [(0, "m"), (10, "M"), (5, "M"), (7, "M")],
               "kick": True, "hats": True, "arp": True},
    "fight2": {"seed": 4, "root": 45, "bpm": 120, "chords": [(0, "m"), (5, "M"), (8, "M"), (10, "M")],
               "kick": True, "hats": True},
    "fight3": {"seed": 5, "root": 43, "bpm": 112, "chords": [(0, "M"), (9, "m"), (5, "M"), (7, "M")],
               "kick": True, "arp": True},
    "fight4": {"seed": 6, "root": 41, "bpm": 124, "chords": [(0, "m"), (3, "M"), (8, "M"), (10, "M")],
               "kick": True, "hats": True, "arp": True},
    "fight5": {"seed": 7, "root": 38, "bpm": 100, "chords": [(0, "m"), (8, "M"), (1, "M"), (10, "M")],
               "kick": True, "arp": True},
    "fight6": {"seed": 8, "root": 42, "bpm": 104, "chords": [(0, "m"), (5, "M"), (3, "M"), (10, "M")],
               "kick": True, "hats": True},
}


def _midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _sweep(f0, f1, dur, wave="sine", amp=1.0, decay=5.0):
    n = max(1, int(dur * _rate))
    if _native is not None:
        buf = (ctypes.c_double * n)()
        _native.sweep(f0, f1, _WAVE_IDS.get(wave, 0), amp, decay, _rate, buf, n)
        return list(buf)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += 2.0 * math.pi * (f0 + (f1 - f0) * t) / _rate
        if wave == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "tri":
            s = 2.0 / math.pi * math.asin(math.sin(phase))
        else:
            s = math.sin(phase)
        out[i] = amp * s * math.exp(-decay * t)
    return out


def _tone(freq, dur, amp=0.4, decay=5.0):
    return _sweep(freq, freq, dur, "sine", amp, decay)


def _noise(dur, amp=1.0, decay=6.0, brightness=0.5):
    """Filtered noise. A low brightness value gives a dull thud, a high one a hiss."""
    n = max(1, int(dur * _rate))
    if _native is not None:
        buf = (ctypes.c_double * n)()
        _native.noise(amp, decay, brightness, random.getrandbits(32), buf, n)
        return list(buf)
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        y += (random.uniform(-1.0, 1.0) - y) * brightness
        out[i] = amp * y * math.exp(-decay * i / n)
    return out


def _mix(*tracks):
    out = [0.0] * max(len(t) for t in tracks)
    for track in tracks:
        for i, s in enumerate(track):
            out[i] += s
    return out


def _cat(*tracks):
    out = []
    for track in tracks:
        out.extend(track)
    return out


def _sfx_table():
    return {
        "punch": _mix(_noise(0.09, 0.9, 22, 0.25), _sweep(170, 70, 0.12, "sine", 0.9, 18)),
        "kick": _mix(_noise(0.13, 1.0, 16, 0.2), _sweep(130, 46, 0.2, "sine", 1.0, 11)),
        "hit": _mix(_noise(0.08, 0.7, 30, 0.6), _sweep(420, 170, 0.1, "tri", 0.5, 22)),
        "block": _mix(_sweep(1900, 1200, 0.09, "sine", 0.45, 30), _noise(0.03, 0.4, 60, 0.9)),
        "swing": _noise(0.12, 0.3, 14, 0.7),
        "jump": _sweep(260, 540, 0.14, "sine", 0.35, 6),
        "land": _mix(_noise(0.06, 0.45, 35, 0.15), _sweep(110, 70, 0.08, "sine", 0.6, 20)),
        "fire": _mix(_sweep(320, 900, 0.35, "tri", 0.35, 3), _noise(0.35, 0.25, 3, 0.85)),
        "boom": _mix(_noise(0.6, 1.0, 5, 0.12), _sweep(90, 34, 0.6, "sine", 0.9, 4)),
        "thud": _mix(_noise(0.12, 0.8, 18, 0.2), _sweep(80, 40, 0.14, "sine", 0.9, 14)),
        "whoosh": _noise(0.5, 0.35, 4, 0.6),
        "coin": _cat(_tone(1500, 0.05, 0.4, 12), _tone(2000, 0.1, 0.35, 8)),
        "ko": _mix(_sweep(440, 110, 1.1, "tri", 0.6, 2.5), _noise(0.5, 0.35, 6, 0.2)),
        "menu": _tone(660, 0.05, 0.3, 20),
        "select": _cat(_tone(660, 0.06, 0.3, 14), _tone(880, 0.12, 0.3, 10)),
        "fight": _cat(_tone(523, 0.12), _tone(659, 0.12), _tone(784, 0.35, 0.4, 3)),
    }


def _render_track(spec):
    beat = 60.0 / spec["bpm"]
    bar = beat * 4
    n_bar = int(bar * _rate)
    bars = len(spec["chords"])
    if _native is not None:
        offsets = (ctypes.c_double * bars)(*(float(o) for o, _ in spec["chords"]))
        majors = (ctypes.c_int * bars)(*(1 if q == "M" else 0 for _, q in spec["chords"]))
        buf = (ctypes.c_double * (n_bar * bars))()
        _native.render_track(float(spec["root"]), beat, bar, n_bar, offsets, majors, bars,
                             1 if spec.get("kick") else 0, 1 if spec.get("hats") else 0,
                             1 if spec.get("arp") else 0, spec["seed"] & 0xffffffff, _rate, buf)
        return list(buf)
    buf = [0.0] * (n_bar * bars)
    rnd = random.Random(spec["seed"])

    for bi, (offset, quality) in enumerate(spec["chords"]):
        base = bi * n_bar
        intervals = _MINOR if quality == "m" else _MAJOR
        root = spec["root"] + offset

        for iv in intervals:  # warm pad, faded in and out so the loop joins are silent
            step = 2 * math.pi * _midi_freq(root + iv + 12) / _rate
            phase = 0.0
            for i in range(n_bar):
                t = i / n_bar
                env = min(1.0, t / 0.18) * min(1.0, (1.0 - t) / 0.22)
                buf[base + i] += 0.05 * env * math.sin(phase)
                phase += step

        bass_step = 2 * math.pi * _midi_freq(root - 12) / _rate  # plucked bass on every beat
        ln = int(0.5 * beat * _rate)
        for b in range(4):
            start = base + int(b * beat * _rate)
            phase = 0.0
            for j in range(ln):
                idx = start + j
                if idx >= base + n_bar:
                    break
                buf[idx] += 0.18 * math.exp(-5.5 * j / ln) * math.sin(phase)
                phase += bass_step

        if spec.get("kick"):
            ln = int(0.22 * _rate)
            for b in (0, 2):
                start = base + int(b * beat * _rate)
                phase = 0.0
                for j in range(ln):
                    idx = start + j
                    if idx >= base + n_bar:
                        break
                    freq = 42 + 90 * math.exp(-4.0 * j / ln)
                    phase += 2 * math.pi * freq / _rate
                    buf[idx] += 0.3 * math.exp(-7.0 * j / ln) * math.sin(phase)

        if spec.get("hats"):
            ln = int(0.04 * _rate)
            for k in range(8):
                start = base + int(k * bar / 8 * _rate)
                for j in range(ln):
                    idx = start + j
                    if idx >= base + n_bar:
                        break
                    buf[idx] += 0.05 * math.exp(-60.0 * j / ln) * rnd.uniform(-1.0, 1.0)

        if spec.get("arp"):
            ln = int(0.5 * beat * _rate)
            notes = [root + 24 + iv for iv in intervals]
            for k in range(8):
                step = 2 * math.pi * _midi_freq(notes[k % 3]) / _rate
                start = base + int(k * bar / 8 * _rate)
                phase = 0.0
                for j in range(ln):
                    idx = start + j
                    if idx >= base + n_bar:
                        break
                    buf[idx] += 0.045 * math.exp(-7.0 * j / ln) * math.sin(phase)
                    phase += step
    return buf


def _to_sound(samples, gain, channels):
    peak = max((abs(s) for s in samples), default=0.0) or 1.0
    scale = 0.85 * gain / peak
    data = array.array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s * scale)) * 32767)
        data.append(v)
        if channels == 2:
            data.append(v)
    return pygame.mixer.Sound(buffer=data.tobytes())


class Audio:
    def __init__(self):
        global _rate
        self.enabled = False
        self.muted = False
        self.sfx = {}
        self.tracks = {}
        self.current = None
        self.channels = 1
        try:
            pygame.mixer.quit()
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
        except pygame.error:
            return
        _rate, _, self.channels = pygame.mixer.get_init()
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)
        self.enabled = True
        self.sfx = {name: _to_sound(samples, SFX_VOLUME, self.channels)
                    for name, samples in _sfx_table().items()}

    def play(self, name, volume=1.0):
        if self.enabled and not self.muted and name in self.sfx:
            sound = self.sfx[name]
            sound.set_volume(max(0.0, min(1.0, volume)))
            sound.play()

    def _track(self, key):
        if key not in self.tracks:
            self.tracks[key] = _to_sound(_render_track(TRACKS[key]), MUSIC_VOLUME, self.channels)
        return self.tracks[key]

    def preload(self, key):
        """Renders a track ahead of time, so the work happens during a screen change."""
        if self.enabled:
            self._track(key)

    def set_music(self, key):
        if not self.enabled or key == self.current:
            return
        self.current = key
        pygame.mixer.Channel(MUSIC_CHANNEL).play(self._track(key), loops=-1)
        self._apply_music_volume()

    def toggle_mute(self):
        self.muted = not self.muted
        self._apply_music_volume()
        return self.muted

    def _apply_music_volume(self):
        if self.enabled:
            pygame.mixer.Channel(MUSIC_CHANNEL).set_volume(0.0 if self.muted else 1.0)
