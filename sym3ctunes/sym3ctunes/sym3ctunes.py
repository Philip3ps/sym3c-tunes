#!/usr/bin/env python3
"""
Sym3c Tunes - a Spotify-style music player for PortMaster / ArkOS.
Runs on the A10 Mini V4 (640x480, RK3326) and any Linux handheld with pygame.

Controls (handheld):
  D-Pad Up/Down .... navigate tracks (Library / Album view)
                     jump 5 albums (Cover Flow) / volume (Now Playing)
  D-Pad Left/Right . seek -5s / +5s (Library, Album, Now Playing)
                     flip through albums (Cover Flow)
  A ................ play selected / play-pause (Library, Now Playing)
                     open the album (Cover Flow) / play the song (Album view)
  B ................ back (Album -> Cover Flow, Cover Flow / Now Playing -> Library)
  X ................ next track
  Y ................ previous track
  L ................ toggle shuffle
  R ................ toggle repeat (off -> all -> one)
  START ............ (unbound - map it in the Controls screen)
  SELECT + START ... quit
  (Device volume buttons control the volume, as usual.)

Keyboard (for testing on PC):
  Up/Down, Left/Right, Enter/Space, N/P, S, R, C Cover Flow,
  H Library, B back, Esc/Q to quit.
"""

import os
import sys
import math
import time
import json
import random
import hashlib
import threading
import array
from io import BytesIO

import pygame

# ---------------------------------------------------------------- paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

MUSIC_DIRS = [
    os.path.join(BASE_DIR, "music"),          # music shipped next to the app
    "/roms2/music",                           # ArkOS music folder
    "/roms/music",
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/music"),
    "/media/data/music",
]
AUDIO_EXTS = (".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".opus")

# ---------------------------------------------------------------- controls
# Remappable controls. A binding is ("btn", index), ("hat", (x, y)) or
# ("axis", (axis, sign)). The D-pad is a hat on most handhelds, but on
# some (e.g. the RG353V) it reports as axes 0/1 instead - both are
# supported, and the user can remap any action from the Controls view.
CONTROL_ACTIONS = [
    ("up", "Up"), ("down", "Down"), ("left", "Left"), ("right", "Right"),
    ("confirm", "Confirm / Play"), ("back", "Back"),
    ("next", "Next track"), ("prev", "Previous track"),
    ("shuffle", "Shuffle"), ("repeat", "Repeat"),
    ("options", "Options"),
    ("coverflow", "Go to Cover Flow"),
    ("nowplaying", "Go to Now Playing"),
    ("like", "Like song (Now Playing)"),
    ("upnext", "Show Up Next"),
    ("lyrics", "Show lyrics (Now Playing)"),
]
DEFAULT_CONTROLS = {
    "up": ("hat", (0, 1)), "down": ("hat", (0, -1)),
    "left": ("hat", (-1, 0)), "right": ("hat", (1, 0)),
    "confirm": ("btn", 0), "back": ("btn", 1),
    "next": ("btn", 2), "prev": ("btn", 3),
    "shuffle": ("btn", 4), "repeat": ("btn", 5),
    "options": ("btn", 6),
    "coverflow": None,  # unbound: pick a button for it in the Controls screen
    "nowplaying": None,  # unbound: pick a button for it in the Controls screen
    "like": None,
    "upnext": None,
    "lyrics": None,
}
# retrogame D-pad buttons (physical, for the fallback in handle_joy_button)
RETROGAME_DPAD = {13: "up", 14: "down", 15: "left", 16: "right"}

# The retrogame driver (Anbernic RG353V/RG351/RG35XX on ArkOS, RetroPie)
# reports ONE joystick named "retrogame_joypad" with 17 buttons and no
# hat at all. The D-pad is buttons 13-16, A/B are swapped vs Xbox
# (A=1, B=0), and Select/Start are 8/9. These are the exact numbers
# read from a real RG353V log (2026-11-22).
RETROGAME_CONTROLS = {
    "up": ("btn", 13), "down": ("btn", 14),
    "left": ("btn", 15), "right": ("btn", 16),
    "confirm": ("btn", 1), "back": ("btn", 0),
    "next": ("btn", 2), "prev": ("btn", 3),
    "shuffle": ("btn", 4), "repeat": ("btn", 5),
    "options": ("btn", 8),
    "coverflow": None,  # unbound: pick a button for it in the Controls screen
    "nowplaying": None,  # unbound: pick a button for it in the Controls screen
    "like": ("btn", 6),    # L2: like the song (Now Playing only)
    "upnext": ("btn", 7),  # R2: show the Up Next pop-up
    "lyrics": None,  # unbound: pick a button for it in the Controls screen
}
DIR_HAT = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
HAT_DIR = {(0, 1): "up", (0, -1): "down", (-1, 0): "left", (1, 0): "right"}
BTN_NAMES = {0: "A", 1: "B", 2: "X", 3: "Y",
             4: "LB", 5: "RB", 6: "Select", 7: "Start"}
# retrogame (RG353V etc.): A and B are swapped vs Xbox, L2/R2 are 6/7
RETRO_BTN_NAMES = {0: "B", 1: "A", 2: "X", 3: "Y",
                   4: "L1", 5: "R1", 6: "L2", 7: "R2",
                   8: "Select", 9: "Start",
                   13: "D-pad Up", 14: "D-pad Down",
                   15: "D-pad Left", 16: "D-pad Right"}


def control_label(binding, retrogame=False):
    """A short human label for a binding, e.g. 'A', 'D-pad Up', 'Axis 1 -',
    or 'A+B' for a two-button combo."""
    if binding is None:
        return "Not set"
    names = RETRO_BTN_NAMES if retrogame else BTN_NAMES
    kind = binding[0]
    if kind == "btn":
        return "Button " + names.get(binding[1], str(binding[1]))
    if kind == "combo":
        b1, b2 = binding[1]
        return "Button %s+%s" % (names.get(b1, str(b1)), names.get(b2, str(b2)))
    if kind == "double":
        return "Button %s x2" % names.get(binding[1], str(binding[1]))
    if kind == "triple":
        return "Button %s x3" % names.get(binding[1], str(binding[1]))
    if kind == "hat":
        for name, hv in DIR_HAT.items():
            if tuple(binding[1]) == hv:
                return "D-pad " + name.capitalize()
        return "Hat " + str(tuple(binding[1]))
    if kind == "axis":
        return "Axis %d %s" % (binding[1], "+" if binding[2] > 0 else "-")
    return str(binding)

# ---------------------------------------------------------------- cover flow transitions
# (name, one-line description). The style changes how the flow moves
# between albums; Slide is the default.
TRANSITIONS = [
    ("Slide",    "Smooth glide to the next album"),
    ("Snap",     "Instant jump, no animation"),
    ("Flip",     "Albums flip over like cards"),
    ("Fade",     "Albums crossfade through black"),
    ("Zoom",     "The next album zooms in"),
    ("Bounce",   "Slides in with a springy bounce"),
    ("Spin",     "The next album twirls into place"),
    ("Cascade",  "Albums drop in from above"),
    ("Carousel", "Albums ride around a 3D carousel"),
    ("Stack",    "Albums stacked like a deck of cards"),
    ("Roll",     "Albums roll over like a wheel"),
    ("Elastic",  "Slides in with a wobbly spring"),
    ("Tilt",     "Albums lean harder as they glide"),
]

# Music transitions: (name, description, params). "xfade" is a true
# overlap crossfade - the old song fades out while the new one fades
# in on a second channel. The rest are sequential: the old song fades
# out (out_ms), an optional silence (gap_ms), then the new song fades
# in (in_ms). "None" is an instant cut.
MUSIC_TRANSITIONS = [
    ("None",            "Songs cut straight from one to the next",
     {"xfade": False, "out_ms": 0,    "in_ms": 0,    "gap_ms": 0}),
    ("Crossfade",       "The old song fades out as the new one fades in",
     {"xfade": True,  "dur": 3.0}),
    ("Quick Crossfade", "A fast 1 second crossfade",
     {"xfade": True,  "dur": 1.0}),
    ("Long Crossfade",  "A slow 6 second crossfade",
     {"xfade": True,  "dur": 6.0}),
    ("Fade Out & In",   "The old song fades out, then the new one fades in",
     {"xfade": False, "out_ms": 1500, "in_ms": 1500, "gap_ms": 0}),
    ("Fade Out",        "The old song fades out, the new one starts full",
     {"xfade": False, "out_ms": 2000, "in_ms": 0,    "gap_ms": 0}),
    ("Fade In",         "The old song cuts, the new one fades in",
     {"xfade": False, "out_ms": 0,    "in_ms": 2000, "gap_ms": 0}),
    ("Gap",             "A short silence between songs",
     {"xfade": False, "out_ms": 0,    "in_ms": 0,    "gap_ms": 1000}),
    ("Dip",             "Fades out, dips to silence, then fades in",
     {"xfade": False, "out_ms": 1000, "in_ms": 1000, "gap_ms": 500}),
    ("Smooth",          "A very short crossfade that just smooths the cut",
     {"xfade": True,  "dur": 0.5}),
]

# Now Playing visualisers: (name, description). "Off" shows the album
# cover as usual; any other choice hides the cover and draws the
# visualiser instead, driven by the song's real audio spectrum.
VISUALISERS = [
    ("Off",       "No visualiser - the album cover shows as usual"),
    ("Bars",      "Classic vertical frequency bars"),
    ("Circular",  "Bars radiating out from the centre in a circle"),
    ("Waveform",  "The raw audio wave scrolling across the screen"),
    ("Mirror",    "Bars mirrored above and below a centre line"),
    ("Spectrum Line", "A smooth glowing line tracing the spectrum"),
    ("Particles", "Glowing dots that pulse with each frequency band"),
    ("Rings",     "Concentric rings pulsing with bass, mids and treble"),
    ("Grid",      "A LED-matrix grid lighting up with the music"),
    ("Tunnel",    "Bars rushing down a perspective tunnel"),
    ("Bloom",     "Soft glowing orbs blooming with the beat"),
]

class Visualiser:
    """The real audio spectrum for Now Playing. The current track's PCM
    is decoded in a background thread (so the UI never freezes) and the
    frequency bands are computed with Goertzel on demand, cached per
    100 ms slice. Until the PCM is ready it falls back to a smooth
    time-based pulse, so the visualiser is never blank."""
    NBANDS = 24
    FREQS = [60.0 * (14000.0 / 60.0) ** (i / 23.0) for i in range(NBANDS)]

    def __init__(self):
        self.path = None
        self.raw = None          # PCM bytes (16-bit stereo, mixer rate)
        self.sr = 44100
        self.ready = False
        self._cache = {}
        self._smooth = [0.0] * self.NBANDS
        self._ref = 120.0
        self._lock = threading.Lock()

    def set_track(self, path):
        """Start decoding a track's PCM in the background (no-op when
        it is already the current track)."""
        if path == self.path:
            return
        self.path = path
        self.raw = None
        self.ready = False
        self._cache.clear()
        self._smooth = [0.0] * self.NBANDS
        if not path:
            return

        def _load():
            try:
                snd = pygame.mixer.Sound(path)
                raw = snd.get_raw()
                sr = pygame.mixer.get_init()[0] or 44100
                with self._lock:
                    if self.path == path:
                        self.raw = raw
                        self.sr = sr
                        self.ready = True
            except Exception:
                pass

        threading.Thread(target=_load, daemon=True).start()

    def _mono(self, start, count):
        """`count` mono samples (floats -1..1) starting at frame `start`."""
        if not self.raw:
            return None
        total_frames = len(self.raw) // 4
        start = max(0, min(start, total_frames - 1))
        count = max(0, min(count, total_frames - start))
        if count <= 0:
            return None
        a = array.array("h")
        a.frombytes(self.raw[start * 4:(start + count) * 4])
        return [(a[2 * i] + a[2 * i + 1]) * 0.5 / 32768.0
                for i in range(count)]

    @staticmethod
    def _goertzel(samples, freq, sr):
        n = len(samples)
        if n == 0:
            return 0.0
        k = int(0.5 + n * freq / sr)
        w = 2.0 * math.pi * k / n
        coeff = 2.0 * math.cos(w)
        s1 = s2 = 0.0
        for x in samples:
            s0 = x + coeff * s1 - s2
            s2 = s1
            s1 = s0
        return math.sqrt(max(0.0, s1 * s1 + s2 * s2 - coeff * s1 * s2))

    def bands_at(self, t):
        """24 smoothed band levels (0..1) for playback time `t`."""
        if not self.ready:
            # PCM not decoded yet: a gentle time-based pulse
            base = 0.5 + 0.5 * math.sin(t * 2.2)
            return [max(0.0, min(1.0, base * (0.45 + 0.45 * math.sin(t * 1.3 + i * 0.9))))
                    for i in range(self.NBANDS)]
        idx = int(t * 10.0)
        if idx in self._cache:
            mags = self._cache[idx]
        else:
            start = int(t * self.sr)
            samples = self._mono(start, 1024)
            if samples is None:
                return [0.0] * self.NBANDS
            mags = [self._goertzel(samples, f, self.sr) for f in self.FREQS]
            if len(self._cache) > 256:
                self._cache.clear()
            self._cache[idx] = mags
        peak = max(mags) if mags else 0.0
        # the reference tracks the loudest band: it rises instantly and
        # falls slowly, so quiet songs still move and loud ones do not
        # blow out
        if peak > self._ref:
            self._ref = peak
        else:
            self._ref = max(30.0, self._ref * 0.94)
        self._ref = max(30.0, min(400.0, self._ref))
        out = []
        for i, mag in enumerate(mags):
            level = min(1.0, mag / self._ref) ** 0.6
            cur = self._smooth[i]
            self._smooth[i] = cur + (level - cur) * (0.5 if level > cur else 0.12)
            out.append(self._smooth[i])
        return out

    def wave_at(self, t, n=160):
        """`n` waveform samples (-1..1) spanning ~0.12 s around `t`."""
        if not self.ready:
            return [0.35 * math.sin(t * 9.0 + i * 0.45) for i in range(n)]
        start = int(t * self.sr) - int(0.06 * self.sr)
        samples = self._mono(start, int(0.12 * self.sr))
        if not samples:
            return [0.0] * n
        step = max(1, len(samples) // n)
        return [samples[i * step] for i in range(n)]

    def energy(self, bands):
        """Overall energy 0..1 (the bass-heavy average of the bands)."""
        if not bands:
            return 0.0
        return max(0.0, min(1.0, sum(bands[:8]) / 8.0))

# Now Playing layouts: (name, description)
NP_LAYOUTS = [
    ("Side by Side", "Cover on the left, song and controls on the right"),
    ("Centered",     "Big cover in the middle, everything centred below"),
    ("Big Cover",    "Huge cover, song and controls underneath"),
    ("Cover Right",  "Song and controls on the left, cover on the right"),
]
# Now Playing disc styles: "off" is the square cover as usual, "cd"
# is a circle that spins like a CD, "sleeve" keeps the square cover
# and slides a spinning CD with the same album art out from behind
# it, like a record out of its sleeve
DISC_STYLES = ["off", "cd", "sleeve", "cassette"]
DISC_STYLE_NAMES = ["Off", "CD", "Sleeve + CD", "Cassette"]

# Music Quiz: a snippet of a random song plays, you guess the title,
# the artist, or the album from 4 choices. The question type is random
# each round, and the wrong answers come from other songs' metadata.
# The cover round is visual instead of audio: the album cover is shown
# and you guess which album it belongs to (no snippet, the cover is
# the clue). Difficulty levels change the snippet length, where it
# starts, how close the wrong answers are, how long you get to answer,
# and how many points a round is worth.
QUIZ_QUESTIONS = [
    ("title", "What's the title of this song?"),
    ("artist", "Who sings this song?"),
    ("album", "Which album is this song from?"),
    ("cover", "Which album is this cover from?"),
]
# level: (name, snippet seconds, answer seconds, points multiplier,
#         fold the art starts at, fold cap, close wrong answers?,
#         number of answer choices)
# A snippet of 0 means the level is visual: no audio, the folded album
# art is the clue. The fold is a grid (fold+1) x (fold+1) with only one
# cell visible, and it tightens by 1 every round, so the piece you see
# gets smaller the longer you play. Master starts already folded
# tighter and tightens further, with close wrong answers. Every level
# is harder than the one before: shorter music, smaller folds, and
# more answers to pick from.
QUIZ_LEVELS = [
    ("Easy", 15, 20, 1, 0, 0, False, 4),
    ("Medium", 10, 15, 2, 0, 0, False, 5),
    ("Hard", 5, 10, 3, 0, 0, True, 6),
    ("Folded", 0, 20, 4, 1, 4, False, 7),
    ("Master", 0, 15, 5, 2, 5, True, 8),
]
# Karaoke-style round score (0-100) and the word that goes with it.
# A correct answer starts at 100 and loses 5 for every second past
# the first 3, down to 50; a wrong answer or a timeout scores 0.
QUIZ_SCORE_PER_SEC = 5
QUIZ_SCORE_MIN = 50
QUIZ_GRADES = [(100, "PERFECT!"), (90, "EXCELLENT!"), (75, "GREAT!"),
               (50, "GOOD!"), (0, "MISS")]
# Achievements: (id, name, what it says). Unlocked ones are saved.
QUIZ_ACHIEVEMENTS = [
    ("first", "First Note", "Get your first answer right."),
    ("streak3", "On a Roll", "3 correct answers in a row."),
    ("streak5", "Hot Streak", "5 correct answers in a row."),
    ("streak10", "Unstoppable", "10 correct answers in a row."),
    ("perfect", "Perfect Pitch", "Score a perfect 100 on a round."),
    ("cover", "Cover Star", "Get a cover question right."),
    ("score500", "High Scorer", "Reach 500 total points."),
    ("correct25", "Quiz Master", "Answer 25 questions correctly."),
    ("fold", "Origami", "Get a folded-cover round right."),
    ("master", "Mastermind", "Get a Master level round right."),
]
# Library (+ Now Playing) size presets: name, scale for Now Playing,
# Library row height, Library cover size, Library title font, sub font
LIB_SIZES = [
    ("Compact", 0.8,  40, 32, "small_b", "tiny"),
    ("Normal",  1.0,  50, 40, "body_b", "small"),
    ("Large",   1.25, 64, 52, "title", "body"),
    ("Huge",    1.6,  80, 64, "h1", "body"),
]
# On-screen keyboard for search: rows of keys. SPACE types a space,
# DEL deletes the last character, DONE moves to the results.
SEARCH_KEYS = [
    ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
    ["K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
    ["U", "V", "W", "X", "Y", "Z", "0", "1", "2", "3"],
    ["4", "5", "6", "7", "8", "9", "SPACE", "DEL", "DONE"],
]
TRANS_DUR = {"Snap": 0.0, "Slide": 0.28, "Bounce": 0.5, "Elastic": 0.7,
             "Cascade": 0.45, "Carousel": 0.4, "Flip": 0.35, "Fade": 0.35,
             "Zoom": 0.35, "Spin": 0.35, "Roll": 0.35, "Tilt": 0.35, "Stack": 0.3}
# styles whose covers need no per-frame effect work (safe to cache)
PLAIN_STYLES = ("Slide", "Snap", "Bounce", "Elastic", "Carousel", "Stack")

def _ease(style, p):
    """Easing for the flow position, p in [0, 1]."""
    if p >= 1:
        return 1.0
    if style == "Snap":
        return 1.0
    if style == "Bounce":  # easeOutBack: overshoots, then settles
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
    if style == "Elastic":  # easeOutElastic: wobbles past the target
        if p == 0:
            return 0.0
        c4 = (2 * math.pi) / 3
        return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * c4) + 1
    return 1 - (1 - p) ** 3  # easeOutCubic

# ---------------------------------------------------------------- screen
W, H = 640, 480
FPS = 30
SIDEBAR_W = 144
BAR_H = 66            # bottom now-playing bar
HEADER_H = 46
ROW_H = 50

# ---------------------------------------------------------------- themes
def _mix(c1, c2, t):
    """Blend two colors: t=0 gives c1, t=1 gives c2."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def _lighten(c, t):
    return _mix(c, (255, 255, 255), t)

def _darken(c, t):
    return _mix(c, (0, 0, 0), t)

def _luminance(c):
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255

def derive_theme(bg, accent, text):
    """A full 13-color theme from a background, an accent and a text color.
    Light backgrounds get a light theme automatically."""
    light = _luminance(bg) > 0.6
    if light:
        sidebar = _darken(bg, 0.06)
        panel = _darken(bg, 0.02)
        bar = _darken(bg, 0.02)
        row = _darken(bg, 0.05)
        row_sel = _darken(bg, 0.10)
        sub = _mix(text, bg, 0.45)
        dim = _mix(text, bg, 0.65)
    else:
        sidebar = _darken(bg, 0.45)
        panel = _lighten(bg, 0.06)
        bar = _lighten(bg, 0.06)
        row = _lighten(bg, 0.04)
        row_sel = _lighten(bg, 0.10)
        sub = _mix(text, bg, 0.5)
        dim = _mix(text, bg, 0.7)
    return {"bg": bg, "sidebar": sidebar, "panel": panel, "bar": bar,
            "row": row, "row_sel": row_sel, "text": text, "sub": sub,
            "dim": dim, "accent": accent, "accent_d": _darken(accent, 0.25),
            "track_bg": _mix(bg, text, 0.28), "track_fg": _mix(text, bg, 0.3),
            "light": light}

# 33 preset themes: (name, background, accent, text)
THEME_PRESETS = [
    ("Spotify",   (18, 18, 18),   (29, 185, 84),  (255, 255, 255)),
    ("Midnight",  (11, 16, 38),   (77, 124, 254), (255, 255, 255)),
    ("Forest",    (14, 31, 20),   (46, 204, 113), (242, 247, 242)),
    ("Ocean",     (10, 30, 46),   (0, 180, 216),  (240, 248, 255)),
    ("Sunset",    (26, 15, 20),   (255, 107, 53), (255, 245, 238)),
    ("Grape",     (27, 16, 48),   (155, 93, 229), (245, 240, 255)),
    ("Rose",      (32, 15, 24),   (241, 91, 181), (255, 240, 246)),
    ("Ember",     (28, 16, 8),    (255, 159, 28), (255, 248, 240)),
    ("Mint",      (12, 31, 28),   (46, 196, 182), (240, 255, 253)),
    ("Slate",     (22, 24, 29),   (138, 155, 168),(242, 244, 247)),
    ("Crimson",   (30, 10, 10),   (230, 57, 70),  (255, 240, 240)),
    ("Gold",      (23, 18, 7),    (255, 195, 0),  (255, 249, 230)),
    ("Ice",       (13, 27, 38),   (125, 211, 252),(240, 249, 255)),
    ("Lime",      (18, 26, 8),    (163, 230, 53), (247, 254, 231)),
    ("Bubblegum", (34, 16, 28),   (255, 112, 166),(255, 240, 245)),
    ("Teal",      (8, 32, 39),    (20, 184, 166), (240, 253, 250)),
    ("Violet",    (21, 10, 46),   (139, 92, 246), (245, 243, 255)),
    ("Coffee",    (23, 16, 11),   (192, 133, 82), (250, 243, 235)),
    ("Blood Moon",(22, 6, 8),     (220, 38, 38),  (254, 242, 242)),
    ("Arctic",    (11, 18, 32),   (56, 189, 248), (240, 249, 255)),
    ("Matcha",    (16, 26, 14),   (132, 204, 22), (247, 254, 231)),
    ("Peach",     (30, 18, 12),   (251, 146, 60), (255, 247, 237)),
    ("Orchid",    (28, 15, 36),   (192, 132, 252),(250, 245, 255)),
    ("Steel",     (18, 21, 26),   (100, 116, 139),(248, 250, 252)),
    ("Neon",      (5, 5, 5),      (0, 255, 157),  (255, 255, 255)),
    ("Dusk",      (20, 16, 28),   (244, 114, 182),(253, 242, 248)),
    ("Pine",      (10, 31, 27),   (16, 185, 129), (236, 253, 245)),
    ("Berry",     (26, 11, 20),   (232, 121, 249),(253, 244, 255)),
    ("Sand",      (26, 22, 14),   (212, 163, 115),(250, 246, 239)),
    ("Royal",     (14, 10, 42),   (99, 102, 241), (238, 242, 255)),
    ("Paper",     (250, 250, 247), (29, 185, 84),  (26, 26, 26)),
    ("Daybreak",  (255, 247, 237), (234, 88, 12),  (28, 25, 23)),
    ("Sky",       (239, 246, 255), (2, 132, 199),  (12, 74, 110)),
]
THEMES = [(name, derive_theme(bg, ac, tx)) for name, bg, ac, tx in THEME_PRESETS]

# palette for the custom theme editor: (name, color)
PALETTE = [
    ("Black", (0, 0, 0)), ("Charcoal", (52, 52, 52)), ("Grey", (128, 128, 128)),
    ("Silver", (192, 192, 192)), ("White", (255, 255, 255)),
    ("Red", (232, 57, 53)), ("Orange", (255, 111, 0)), ("Amber", (255, 179, 0)),
    ("Yellow", (255, 235, 59)), ("Lime", (139, 195, 74)), ("Green", (46, 125, 50)),
    ("Mint", (0, 191, 165)), ("Teal", (0, 151, 167)), ("Cyan", (0, 188, 212)),
    ("Sky", (3, 169, 244)), ("Blue", (33, 150, 243)), ("Indigo", (63, 81, 181)),
    ("Violet", (124, 77, 255)), ("Purple", (156, 39, 176)), ("Pink", (233, 30, 99)),
    ("Rose", (255, 64, 129)), ("Brown", (121, 85, 72)), ("Gold", (212, 175, 55)),
    ("Navy", (13, 27, 62)),
]
CUSTOM_SLOTS = ("Background", "Accent", "Text")

# ---------------------------------------------------------------- fonts
def load_font(name, size, bold=False):
    path = os.path.join(ASSETS_DIR, name)
    try:
        return pygame.font.Font(path, size)
    except Exception:
        try:
            return pygame.font.SysFont("dejavusans", size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size)

# ---------------------------------------------------------------- helpers
def fmt_time(sec):
    if sec is None or sec < 0:
        sec = 0
    m = int(sec) // 60
    s = int(sec) % 60
    return "%d:%02d" % (m, s)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def hue_color(name):
    """Deterministic pleasant colour from a string (for generated covers)."""
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:6], 16)
    r = 90 + (h % 130)
    g = 90 + ((h >> 8) % 130)
    b = 90 + ((h >> 16) % 130)
    return (r, g, b)

def vertical_gradient(size, top, bottom):
    surf = pygame.Surface(size)
    w, h = size
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(surf, c, (0, y), (w, y))
    return surf

def draw_note(surf, cx, cy, size, color):
    """A simple music-note glyph, drawn with shapes (no font glyphs)."""
    # note head
    rx, ry = int(size * 0.32), int(size * 0.22)
    pygame.draw.ellipse(surf, color, (cx - rx, cy - ry // 2, rx * 2, ry * 2))
    # stem
    pygame.draw.rect(surf, color, (cx + rx - 3, cy - int(size * 0.95), 5, int(size * 0.95)))
    # flag
    pygame.draw.polygon(surf, color, [
        (cx + rx + 2, cy - int(size * 0.95)),
        (cx + rx + int(size * 0.5), cy - int(size * 0.62)),
        (cx + rx + 2, cy - int(size * 0.45)),
    ])

# ---------------------------------------------------------------- tracks
class Track:
    def __init__(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        self.artist = "Unknown Artist"
        self.album = "Unknown Album"
        self.duration = 0.0
        self.cover = None          # pygame Surface (embedded art) or None
        self.lyrics = None         # lyrics text, loaded lazily by get_lyrics()
        self._lyrics_loaded = False
        self._read_tags()

    def get_lyrics(self):
        """Lyrics for this song, loaded on first use: a .lrc file next
        to the song first, then lyrics embedded in the file (ID3 USLT
        or the easy 'lyrics' tag). Returns "" when there are none."""
        if self._lyrics_loaded:
            return self.lyrics or ""
        self._lyrics_loaded = True
        self.lyrics = ""
        # 1. a .lrc file with the same name, next to the song
        lrc = os.path.splitext(self.path)[0] + ".lrc"
        try:
            if os.path.isfile(lrc):
                with open(lrc, "r", encoding="utf-8", errors="replace") as f:
                    lines = []
                    for raw in f:
                        line = raw.strip()
                        # strip [mm:ss.xx] timestamps
                        while line.startswith("[") and "]" in line:
                            line = line.split("]", 1)[1].strip()
                        if line:
                            lines.append(line)
                    if lines:
                        self.lyrics = "\n".join(lines)
                        return self.lyrics
        except Exception:
            pass
        # 2. lyrics embedded in the file
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(self.path)
            if audio is not None and hasattr(audio, "tags") and audio.tags:
                for key in list(audio.tags.keys()):
                    if key.startswith("USLT"):
                        text = str(getattr(audio.tags[key], "text", "") or "")
                        if text.strip():
                            self.lyrics = text.strip()
                            return self.lyrics
                if hasattr(audio, "tags") and "lyrics" in audio.tags:
                    vals = audio.tags["lyrics"]
                    if vals and str(vals[0]).strip():
                        self.lyrics = str(vals[0]).strip()
        except Exception:
            pass
        return self.lyrics

    def _read_tags(self):
        base = os.path.splitext(os.path.basename(self.path))[0]
        if " - " in base:
            a, t = base.split(" - ", 1)
            self.artist, self.title = a.strip(), t.strip()
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(self.path, easy=True)
            if audio is not None:
                tags = audio.tags or {}
                if tags.get("title"):
                    self.title = tags["title"][0]
                if tags.get("artist"):
                    self.artist = tags["artist"][0]
                if tags.get("album"):
                    self.album = tags["album"][0]
                if getattr(audio, "info", None) and getattr(audio.info, "length", None):
                    self.duration = float(audio.info.length)
            # embedded cover art (full mutagen, not easy interface)
            audio2 = MutagenFile(self.path)
            if audio2 is not None:
                pic = None
                if hasattr(audio2, "tags") and audio2.tags:
                    for key in ("APIC:", "APIC:Cover", "APIC:cover"):
                        if key in audio2.tags:
                            pic = audio2.tags[key].data
                            break
                    if pic is None:
                        for key in audio2.tags.keys():
                            if key.startswith("APIC"):
                                pic = audio2.tags[key].data
                                break
                    if pic is None and "covr" in audio2.tags:
                        pic = bytes(audio2.tags["covr"][0])
                if pic:
                    try:
                        surf = pygame.image.load(BytesIO(pic))
                        try:
                            surf = surf.convert()
                        except Exception:
                            pass  # no display mode yet; use the raw surface
                        self.cover = surf
                    except Exception:
                        self.cover = None
        except Exception:
            pass

    def display_name(self):
        return self.title

def find_music_dirs():
    found = []
    for d in MUSIC_DIRS:
        if d and os.path.isdir(d):
            found.append(d)
    return found

def scan_music():
    """Scan the music folders. Returns (tracks, playlists).

    tracks: every song found (loose files and playlist folders alike),
        sorted by metadata (artist, then title) - this is the Library.
    playlists: one per subfolder inside a music folder - the folder name
        is the playlist name, and it holds every song under that folder.
        A playlist's indices are in tracks order, so its songs are
        already sorted by metadata too.
    """
    loose, by_folder = [], {}
    for d in find_music_dirs():
        for root, _dirs, files in os.walk(d):
            for f in sorted(files):
                if not f.lower().endswith(AUDIO_EXTS):
                    continue
                path = os.path.join(root, f)
                rel = os.path.relpath(root, d)
                if rel == ".":
                    loose.append(path)
                else:
                    name = rel.split(os.sep)[0]
                    by_folder.setdefault(name.lower(), {"name": name, "paths": []})
                    by_folder[name.lower()]["paths"].append(path)
    # de-dupe by path, keep order
    def dedupe(paths):
        seen, out = set(), []
        for p in paths:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out
    loose = dedupe(loose)
    all_paths = list(loose)
    for pl in by_folder.values():
        all_paths.extend(dedupe(pl["paths"]))
    seen, tracks = set(), []
    for p in all_paths:
        if p not in seen:
            seen.add(p)
            tracks.append(Track(p))
    tracks.sort(key=lambda t: (t.artist.lower(), t.title.lower()))
    by_path = {t.path: i for i, t in enumerate(tracks)}
    playlists = []
    for pl in sorted(by_folder.values(), key=lambda p: p["name"].lower()):
        idxs = sorted({by_path[p] for p in pl["paths"] if p in by_path})
        if idxs:
            playlists.append({"name": pl["name"], "indices": idxs})
    return tracks, playlists

def group_albums(tracks):
    """Group tracks into albums (by album + artist), keeping library order."""
    albums = []
    by_key = {}
    for gi, t in enumerate(tracks):
        key = (t.album or "Unknown Album").strip().lower() + "\x00" + \
              (t.artist or "Unknown Artist").strip().lower()
        if key not in by_key:
            alb = {"title": t.album or "Unknown Album",
                   "artist": t.artist or "Unknown Artist",
                   "tracks": [], "indices": []}
            by_key[key] = alb
            albums.append(alb)
        by_key[key]["tracks"].append(t)
        by_key[key]["indices"].append(gi)
    albums.sort(key=lambda a: (a["artist"].lower(), a["title"].lower()))
    return albums

def group_artists(tracks):
    """Group tracks by artist (by artist name), keeping library order."""
    artists = []
    by_key = {}
    for gi, t in enumerate(tracks):
        key = (t.artist or "Unknown Artist").strip().lower()
        if key not in by_key:
            art = {"name": t.artist or "Unknown Artist",
                   "tracks": [], "indices": []}
            by_key[key] = art
            artists.append(art)
        by_key[key]["tracks"].append(t)
        by_key[key]["indices"].append(gi)
    artists.sort(key=lambda a: a["name"].lower())
    return artists

# ---------------------------------------------------------------- covers
_cover_cache = {}
_folder_cover_cache = {}
FOLDER_COVERS = ("cover.jpg", "cover.jpeg", "cover.png", "folder.jpg",
                 "folder.png", "album.jpg", "album.png", "front.jpg", "front.png")

def folder_cover(track):
    """A cover image sitting next to the song file (cover.jpg, folder.jpg...).

    Checked once per folder and cached. This is how most music players
    find art when the file itself has none embedded.
    """
    d = os.path.dirname(track.path)
    if d in _folder_cover_cache:
        return _folder_cover_cache[d]
    surf = None
    for name in FOLDER_COVERS:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            try:
                img = pygame.image.load(p)
                try:
                    img = img.convert()
                except Exception:
                    pass
                surf = img
            except Exception:
                surf = None
            break
    _folder_cover_cache[d] = surf
    return surf

def cover_surface(track, size):
    """Embedded art if present, else a cover.jpg/folder.jpg next to the file,
    else a generated gradient tile with a note."""
    key = (track.path, size)
    if key in _cover_cache:
        return _cover_cache[key]
    surf = None
    if track.cover is not None:
        try:
            surf = pygame.transform.smoothscale(track.cover, (size, size))
        except Exception:
            surf = None
    if surf is None:
        fc = folder_cover(track)
        if fc is not None:
            try:
                surf = pygame.transform.smoothscale(fc, (size, size))
            except Exception:
                surf = None
    if surf is None:
        c1 = hue_color(track.artist + track.album)
        c2 = tuple(max(0, int(v * 0.45)) for v in c1)
        surf = vertical_gradient((size, size), c1, c2)
        draw_note(surf, size // 2, size // 2 + size // 6, size // 3,
                  (255, 255, 255))
    _cover_cache[key] = surf
    return surf

# ---------------------------------------------------------------- player
MUSIC_END = pygame.USEREVENT + 1

class Player:
    def __init__(self, tracks):
        self.tracks = tracks
        self.index = -1
        self.playing = False
        self.shuffle = False
        self.repeat = 0          # 0 off, 1 all, 2 one
        self.volume = 0.8
        self._pos_base = 0.0     # seconds at (re)start of timing
        self._pos_started = 0.0  # time.time() when playback (re)started
        # the queue is what Next/Prev (and shuffle) walk through: all
        # tracks by default, or just one album's / playlist's songs when
        # playback started from there
        self._queue = list(range(len(tracks)))
        self._order = list(self._queue)
        self._order_pos = -1
        self.error = None
        self.music_trans = "None"   # transitions removed: songs cut instantly
        # crossfade state: a dict while a crossfade runs, else None
        self._xfade = None
        # sequential transition: a dict while the next song is waiting
        # to start (fade-out / silence), else None
        self._pending_play = None
        # after a crossfade the song plays on a Sound channel, not the
        # music stream - so pause/stop/seek/volume route to it
        self._sound_channel = None
        self._sound_mode = False
        try:
            pygame.mixer.music.set_endevent(MUSIC_END)
        except Exception:
            pass
        pygame.mixer.music.set_volume(self.volume)

    # -- position -------------------------------------------------------
    def position(self):
        if self.index < 0:
            return 0.0
        if self.playing:
            return self._pos_base + (time.time() - self._pos_started)
        return self._pos_base

    def duration(self):
        if 0 <= self.index < len(self.tracks):
            return self.tracks[self.index].duration
        return 0.0

    def current(self):
        if 0 <= self.index < len(self.tracks):
            return self.tracks[self.index]
        return None

    # -- music transitions --------------------------------------------
    def _music_trans_params(self):
        for name, _desc, params in MUSIC_TRANSITIONS:
            if name == self.music_trans:
                return params
        return MUSIC_TRANSITIONS[0][2]

    def _is_audio_playing(self):
        """Is a song actually sounding right now (music stream or the
        Sound channel left over from a crossfade)?"""
        if self._sound_mode and self._sound_channel is not None:
            try:
                return self._sound_channel.get_busy()
            except Exception:
                return False
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    def _cancel_transition(self):
        """Stop any crossfade or pending song change (a new Next/Prev
        or a fresh play replaces it)."""
        if self._xfade is not None:
            try:
                if self._xfade.get("channel") is not None:
                    self._xfade["channel"].stop()
            except Exception:
                pass
            self._xfade = None
        self._pending_play = None
        # the old song's volume may have been faded down - restore it
        if not self._sound_mode:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def _play_direct(self, idx):
        """Play a track straight away on the music stream (no
        transition) - used for the first song, and when the transition
        is None or nothing is playing to fade from."""
        self._cancel_transition()
        if self._sound_mode and self._sound_channel is not None:
            try:
                self._sound_channel.stop()
            except Exception:
                pass
            self._sound_mode = False
            self._sound_channel = None
        try:
            self._load(idx)
            pygame.mixer.music.play()
            self.playing = True
            if idx in self._order:
                self._order_pos = self._order.index(idx)
            return True
        except Exception as e:
            self.error = "Can't play this file (%s)" % type(e).__name__
            self.playing = False
            return False

    def _start_xfade(self, idx, dur):
        """True crossfade: the new song plays on a second channel and
        fades in while the old song fades out. The new song becomes
        the current track at once, so its position tracks from the
        moment it starts."""
        track = self.tracks[idx]
        try:
            snd = pygame.mixer.Sound(track.path)
        except Exception as e:
            self.error = "Can't play this file (%s)" % type(e).__name__
            return self._play_direct(idx)
        # the old output - the music stream, or a Sound channel left
        # over from a previous crossfade
        old_kind = "sound" if self._sound_mode else "music"
        old_ch = self._sound_channel if self._sound_mode else None
        ch = snd.play()
        if ch is None:
            return self._play_direct(idx)
        try:
            ch.set_endevent(MUSIC_END)
        except Exception:
            pass
        ch.set_volume(0.0)
        self._xfade = {"sound": snd, "channel": ch,
                       "old_kind": old_kind, "old_ch": old_ch,
                       "start": time.time(), "dur": max(0.2, dur),
                       "idx": idx}
        # the new song is current from the moment it starts fading in
        self.index = idx
        self._pos_base = 0.0
        self._pos_started = time.time()
        self.playing = True
        if idx in self._order:
            self._order_pos = self._order.index(idx)
        return True

    def _update_xfade(self):
        """Ramp the crossfade volumes each frame. When it finishes the
        old song is stopped and the new song's channel is the output."""
        if self._xfade is None:
            return
        x = self._xfade
        t = (time.time() - x["start"]) / x["dur"]
        if t >= 1.0:
            # fade done: stop the old song, the new channel is live
            try:
                if x["old_kind"] == "sound" and x["old_ch"] is not None:
                    x["old_ch"].stop()
                else:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass
            self._sound_channel = x["channel"]
            self._sound_mode = True
            self._xfade = None
            return
        t = max(0.0, min(1.0, t))
        try:
            x["channel"].set_volume(t * self.volume)
            if x["old_kind"] == "sound" and x["old_ch"] is not None:
                x["old_ch"].set_volume((1.0 - t) * self.volume)
            else:
                pygame.mixer.music.set_volume((1.0 - t) * self.volume)
        except Exception:
            pass

    def _start_sequential(self, idx, params):
        """Fade out / silence, then start the new song. The new song is
        scheduled and starts from the run loop when its time comes."""
        out_ms = params.get("out_ms", 0)
        in_ms = params.get("in_ms", 0)
        gap_ms = params.get("gap_ms", 0)
        # stop the old song: fade it out if asked, else cut it now
        if self._sound_mode and self._sound_channel is not None:
            try:
                if out_ms > 0:
                    self._sound_channel.fadeout(out_ms)
                else:
                    self._sound_channel.stop()
            except Exception:
                pass
            self._sound_mode = False
            self._sound_channel = None
        else:
            try:
                if out_ms > 0:
                    pygame.mixer.music.fadeout(out_ms)
                else:
                    pygame.mixer.music.stop()
            except Exception:
                pass
        delay = (out_ms + gap_ms) / 1000.0
        self._pending_play = {"idx": idx, "at": time.time() + delay,
                              "in_ms": in_ms}
        self.index = idx
        self._pos_base = 0.0
        self._pos_started = time.time() + delay
        self.playing = True
        if idx in self._order:
            self._order_pos = self._order.index(idx)
        return True

    def _update_pending(self):
        """Start a scheduled song (after its fade-out / silence)."""
        if self._pending_play is None:
            return
        if time.time() < self._pending_play["at"]:
            return
        p = self._pending_play
        self._pending_play = None
        self._sound_mode = False
        self._sound_channel = None
        try:
            self._load(p["idx"])
            pygame.mixer.music.play(fade_ms=p["in_ms"])
            self.playing = True
        except Exception as e:
            self.error = "Can't play this file (%s)" % type(e).__name__
            self.playing = False

    def update_transitions(self):
        """Drive the crossfade and any pending song start. Call once
        per frame from the app's run loop."""
        self._update_xfade()
        self._update_pending()

    # -- transport ------------------------------------------------------
    def _load(self, idx):
        track = self.tracks[idx]
        pygame.mixer.music.load(track.path)
        self.index = idx
        self._pos_base = 0.0
        self._pos_started = time.time()
        self.error = None

    def play_index(self, idx, queue=None):
        """Play the track at global index idx. When queue is given (a
        list of global indices - one album's or one playlist's songs),
        it becomes the new queue: Next, Prev and shuffle stay inside
        it until something else is played. With no queue the current
        queue is kept. The change uses the picked music transition
        (crossfade, fade out/in, gap, ...) when a song is already
        playing; the first song always starts straight away."""
        if not self.tracks or not (0 <= idx < len(self.tracks)):
            return False
        if queue is not None:
            self._queue = list(queue)
            if self.shuffle:
                rest = [i for i in self._queue if i != idx]
                random.shuffle(rest)
                self._order = [idx] + rest
            else:
                self._order = list(self._queue)
        params = self._music_trans_params()
        # no transition: the first song, nothing playing to fade from,
        # or the transition is None
        if (not self._is_audio_playing() or params is None
                or (not params.get("xfade")
                    and not params.get("out_ms")
                    and not params.get("in_ms")
                    and not params.get("gap_ms"))):
            return self._play_direct(idx)
        if params.get("xfade"):
            return self._start_xfade(idx, params.get("dur", 3.0))
        return self._start_sequential(idx, params)

    def play_pause(self):
        if self.index < 0:
            if self.tracks:
                return self.play_index(0)
            return False
        if self.playing:
            if self._sound_mode and self._sound_channel is not None:
                try:
                    self._sound_channel.pause()
                except Exception:
                    pass
            else:
                pygame.mixer.music.pause()
            self._pos_base = self.position()
            self.playing = False
        else:
            if self._sound_mode and self._sound_channel is not None:
                try:
                    self._sound_channel.unpause()
                except Exception:
                    pass
            else:
                pygame.mixer.music.unpause()
            self._pos_started = time.time()
            self.playing = True
        return True

    def stop(self):
        self._cancel_transition()
        try:
            if self._sound_mode and self._sound_channel is not None:
                self._sound_channel.stop()
            else:
                pygame.mixer.music.stop()
        except Exception:
            pass
        self._sound_mode = False
        self._sound_channel = None
        self.playing = False

    def next(self, auto=False):
        if not self.tracks:
            return False
        if self.repeat == 2 and auto:
            return self.play_index(self.index)
        if self.shuffle:
            choices = [i for i in self._order if i != self.index]
            if not choices:
                return self.play_index(self.index)
            return self.play_index(random.choice(choices))
        self._order_pos += 1
        if self._order_pos >= len(self._order):
            if self.repeat == 1 or not auto:
                self._order_pos = 0
            else:
                self._order_pos = len(self._order) - 1
                self.stop()
                return False
        return self.play_index(self._order[self._order_pos])

    def prev(self):
        if not self.tracks:
            return False
        if self.position() > 3.0:
            self.seek(0)
            return True
        self._order_pos -= 1
        if self._order_pos < 0:
            self._order_pos = len(self._order) - 1
        return self.play_index(self._order[self._order_pos])

    def seek(self, sec):
        if self.index < 0:
            return
        dur = self.duration()
        sec = clamp(sec, 0, dur - 0.5 if dur > 1 else 0)
        if self._sound_mode:
            # a Sound can't seek: switch this song back to the music
            # stream at the wanted position
            self._cancel_transition()
            try:
                if self._sound_channel is not None:
                    self._sound_channel.stop()
            except Exception:
                pass
            self._sound_mode = False
            self._sound_channel = None
            try:
                pygame.mixer.music.load(self.tracks[self.index].path)
            except Exception:
                pass
        try:
            pygame.mixer.music.play(start=sec)
            if not self.playing:
                pygame.mixer.music.pause()
        except Exception:
            try:
                pygame.mixer.music.rewind()
            except Exception:
                pass
            self._pos_base = sec
            self._pos_started = time.time()
            return
        self._pos_base = sec
        self._pos_started = time.time()

    def seek_rel(self, delta):
        self.seek(self.position() + delta)

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        if self.shuffle:
            rest = [i for i in self._queue if i != self.index]
            random.shuffle(rest)
            self._order = ([self.index] if self.index >= 0 else []) + rest
            self._order_pos = 0
        else:
            cur = self.index
            self._order = list(self._queue)
            self._order_pos = self._order.index(cur) if cur in self._order else 0
        return self.shuffle

    def toggle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        return self.repeat

    def set_volume(self, v):
        self.volume = clamp(v, 0.0, 1.0)
        if self._xfade is not None:
            # the crossfade applies the volume itself each frame
            return self.volume
        if self._sound_mode and self._sound_channel is not None:
            try:
                self._sound_channel.set_volume(self.volume)
            except Exception:
                pass
        else:
            pygame.mixer.music.set_volume(self.volume)
        return self.volume

    def on_track_end(self):
        if self.repeat == 2:
            self.play_index(self.index)
        else:
            self.next(auto=True)

# ---------------------------------------------------------------- UI
class App:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.key.set_repeat(260, 90)
        # No FULLSCREEN flag: on ArkOS/KMSDRM handhelds SDL renders a
        # 640x480 surface fullscreen anyway; the flag only caused trouble
        # (wrong surface size on some drivers). SCALED keeps the app
        # drawing at 640x480 and lets pygame scale the frame to the
        # real display, so it works on any screen size (a 640x480
        # display is a 1:1 no-op; a bigger one is scaled up). SCALED
        # needs a renderer, and some drivers cannot provide one, so if
        # it fails, fall back to a plain 640x480 surface (the old
        # behaviour) instead of not starting at all.
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Sym3c Tunes")
        self.clock = pygame.time.Clock()
        self.fonts = {
            "logo":   load_font("DejaVuSans-Bold.ttf", 20, bold=True),
            "title":  load_font("DejaVuSans-Bold.ttf", 19, bold=True),
            "h1":     load_font("DejaVuSans-Bold.ttf", 21, bold=True),
            "body":   load_font("DejaVuSans.ttf", 15),
            "body_b": load_font("DejaVuSans-Bold.ttf", 15, bold=True),
            "small":  load_font("DejaVuSans.ttf", 13),
            "small_b": load_font("DejaVuSans-Bold.ttf", 13, bold=True),
            "tiny":   load_font("DejaVuSans.ttf", 11),
            "big":    load_font("DejaVuSans-Bold.ttf", 24, bold=True),
            "huge":   load_font("DejaVuSans-Bold.ttf", 48, bold=True),
        }
        self.tracks, self.playlists = scan_music()
        self.albums = group_albums(self.tracks)
        self.artists = group_artists(self.tracks)
        _emb = sum(1 for _t in self.tracks if _t.cover is not None)
        print("Music: %d tracks, %d albums, %d with embedded art" % (
            len(self.tracks), len(self.albums), _emb), flush=True)
        self.player = Player(self.tracks)
        self.sel = 0
        self.scroll = 0
        self.view = "library"      # library | coverflow | album | nowplaying | artists | playlists | playlist | liked | search
        self.menu = 0              # sidebar: 0 library, 1 cover flow, 2 now playing, 3 artists, 4 playlists, 5 liked, 6 search
        self.lib_focus = "list"    # library focus: "list" (tracks) or "menu" (sidebar)
        self.menu_sel = 0          # sidebar highlight while the menu has focus
        # artists
        self.artist_sel = 0
        self.artist_scroll = 0
        # playlists (one per subfolder inside a music folder)
        self.playlist = None       # open playlist dict (or None)
        self.pl_track_sel = 0
        self.pl_track_scroll = 0
        # liked songs (file paths, saved in settings.json)
        self.liked = set()
        self.liked_sel = 0
        self.liked_scroll = 0
        # up next pop-up + lyrics panel (overlays on Now Playing)
        self.upnext_open = False
        self.lyrics_open = False
        self.lyrics_scroll = 0
        # search
        self.search_query = ""
        self.search_row = 0
        self.search_col = 0
        self.search_results = []
        self.search_sel = 0
        self.search_focus = "keys"   # "keys" (keyboard) or "results"
        # library size preset (index into LIB_SIZES)
        self.lib_size = 1            # 0 Compact, 1 Normal, 2 Large, 3 Huge
        self.lib_size_sel = 1
        self.opt_prev_lib_size = None
        # Disc style: how the Now Playing cover is shown - "off" is the
        # square cover as usual, "cd" is a circle that spins like a CD,
        # "sleeve" keeps the square cover and slides a spinning CD with
        # the same album art out from behind it, like a record out of
        # its sleeve
        self.cd_mode = "off"
        self.cd_sel = 0              # 0 Off, 1 CD, 2 Sleeve + CD, 3 Cassette
        self.opt_prev_cd = None
        self._cd_cache = {}          # (track path, size) -> circular disc surface
        # Now Playing visualiser: hides the album cover when on
        self.visualiser = "Off"          # see VISUALISERS
        self.viz_sel = 0
        self.opt_prev_viz = None
        self.viz = Visualiser()
        # Music Quiz: a snippet plays, you guess the title / artist /
        # album from 4 choices. The song's identity is never shown on
        # the quiz screen, or the game would give itself away.
        self.quiz_song = -1        # index into self.tracks, -1 = no round
        self.quiz_field = None     # "title" / "artist" / "album" / "cover"
        self.quiz_choices = []     # 4 answer strings, shuffled
        self.quiz_correct = 0      # index of the right answer
        self.quiz_sel = 0          # highlighted choice
        self.quiz_answered = False
        self.quiz_picked = -1      # the choice the player picked
        self.quiz_score = 0        # correct answers
        self.quiz_total = 0        # answers given
        self.quiz_streak = 0       # correct in a row
        self.quiz_best = 0         # best streak so far
        self.quiz_snippet_until = None  # time the snippet stops by itself
        self.quiz_snippet_start = 0     # where the snippet starts (seconds)
        self.quiz_fold = 0         # fold level of this round (visual levels)
        self.quiz_fold_cell = (0, 0)  # the one visible cell of the folded art
        self.quiz_new_achievement = ""  # achievement unlocked by the last answer
        self.quiz_select_presses = []  # times of Select taps in the quiz
        # (triple-click Select quits the game and plays music again)
        self.quiz_level = 1        # index into QUIZ_LEVELS (0 Easy, 1 Medium, 2 Hard)
        self.quiz_points = 0       # total karaoke-style points
        self.quiz_round_score = 0  # 0-100 for the round just played
        self.quiz_grade = ""       # PERFECT! / EXCELLENT! / ... for the round
        self.quiz_earned = 0       # points the round just played was worth
        self.quiz_round_start = 0  # time the round (and its clock) started
        self.quiz_timeout = False  # the round ran out of time
        self.quiz_achievements = []  # unlocked achievement ids (saved)
        self.quiz_best_points = 0  # best total points in one session (saved)
        # playlist flow state (the Playlists view is a Cover Flow of
        # the playlist folders)
        self.pl_flow_target = 0
        self.pl_flow_pos = 0.0
        self.pl_trans_from = 0.0
        self.pl_trans_start = 0.0
        self.pl_trans_p = 1.0
        self._pl_cover_cache = {}
        # cover flow state
        self.flow_target = 0       # album index the flow is heading to
        self.flow_pos = 0.0        # animated float position (eased toward target)
        self.flow_filter = None    # artist name: cover flow shows only their albums
        self.trans_style = "Slide"   # see TRANSITIONS
        self.trans_from = 0.0        # flow_pos when the current move started
        self.trans_start = 0.0       # time the current move started
        self.trans_p = 1.0           # 0..1 progress of the current move (1 = idle)
        # transition options bar
        self.options_open = False
        self.opt_sel = 0
        self.opt_prev = None
        self._select_open_pending = False
        # themes
        self.theme_name = "Spotify"
        self.custom_theme = {"bg": (18, 18, 18), "accent": (29, 185, 84),
                             "text": (255, 255, 255)}
        # now playing layouts (Centered is the default look)
        self.np_layout = "Centered"
        self.np_sel = 1
        self.opt_prev_layout = None
        self.opt_page = "transition"   # transition | theme | custom | layout
        self.opt_prev_theme = None
        self.theme_sel = 0
        self.custom_slot = 0           # 0 background, 1 accent, 2 text
        self.custom_idx = [0, 0, 0]    # palette index per slot
        self.custom_backup = None
        self._np_bg_cache = {}         # blurred Now Playing backgrounds
        self.album = None          # open album dict (album view)
        self.album_sel = 0
        self.album_scroll = 0
        self._refl_cache = {}
        self._glow_cache = {}
        self._flow_cache = {}      # sheared side covers, keyed by (album, offset)
        self.toast = ""
        self.toast_until = 0.0
        self.select_held = False
        self._select_phys_held = False  # physical Select button held (for SELECT+START quit)
        self.running = True
        # remappable controls (see CONTROL_ACTIONS / DEFAULT_CONTROLS)
        # (initialised before load_settings so saved mappings load)
        self.controls = dict(DEFAULT_CONTROLS)
        self.controls_sel = 0            # selected row in the Controls view
        self.controls_scroll = 0         # first visible row in the Controls view
        self._vol_show_until = 0.0       # volume popup visible until this time
        self._np_trans = None            # (cx, cy, gap, r_side) of the Now Playing transport row
        self.controls_listen = None      # action being remapped, or None
        self._capture_first = None       # (btn, time, count) - first button(s) of a combo/multi capture
        self._held_btns = set()          # joystick buttons currently held down
        self._pending_btn = None         # (btn, time) - a combo member pressed alone, waiting for its partner
        self._multi_count = {}           # btn -> [count, last_time] for double/triple-click
        self._pending_multi = None       # (btn, count, time) - a multi-press waiting to resolve
        self._axis_dir = {}              # axis index -> current direction (-1/0/1)
        self._back_hold_since = None     # when the Back action was pressed (long-press)
        self.setup_done = False          # first-run key setup completed
        self._setup_first_run = False    # currently in the first-run setup
        self.load_settings()
        self.apply_theme(self.theme_name)
        # joysticks (handheld controls) - open EVERY joystick, not just
        # the first: on some handhelds the D-pad/buttons and the sticks
        # are separate devices, and the D-pad lives on the second one
        self.joy = None
        self.joys = []
        self._is_retrogame = False  # retrogame driver: RG353V/RG351/RG35XX
        try:
            pygame.joystick.init()
            for _i in range(pygame.joystick.get_count()):
                _j = pygame.joystick.Joystick(_i)
                _j.init()
                self.joys.append(_j)
                print("Joystick %d: %s buttons=%d axes=%d hats=%d" % (
                    _i, _j.get_name(), _j.get_numbuttons(),
                    _j.get_numaxes(), _j.get_numhats()), flush=True)
                if "retrogame" in _j.get_name().lower():
                    self._is_retrogame = True
            if self.joys:
                self.joy = self.joys[0]
        except Exception:
            self.joy = None
        # use the right default mapping for the detected handheld, and
        # repair a saved mapping that left an essential action unbound
        self._apply_device_defaults()
        # first-run key setup: before the main app, let the user map
        # every action by pressing the button for it. It runs exactly
        # once: mark it done (and save) as soon as it shows, so it never
        # pops up again on later launches even if the user quits mid-way.
        # Start with a blank slate - nothing pre-mapped - so the user
        # maps every action themself (B skips one action).
        if not self.setup_done:
            self._setup_first_run = True
            self.controls = {name: None for name, _ in CONTROL_ACTIONS}
            self.setup_done = True
            self.save_settings()
            self.open_controls()
            self.controls_listen = CONTROL_ACTIONS[0][0]

    # -- text -----------------------------------------------------------
    def text(self, font, s, color, pos, align="left"):
        surf = self.fonts[font].render(s, True, color)
        x, y = pos
        if align == "center":
            x -= surf.get_width() // 2
        elif align == "right":
            x -= surf.get_width()
        self.screen.blit(surf, (x, y))
        return surf

    def fit(self, font, s, max_w):
        f = self.fonts[font]
        if f.size(s)[0] <= max_w:
            return s
        ell = "..."
        while s and f.size(s + ell)[0] > max_w:
            s = s[:-1]
        return s + ell

    def show_toast(self, msg):
        self.toast = msg
        self.toast_until = time.time() + 2.5

    # -- selection ------------------------------------------------------
    def move_sel(self, d):
        if not self.tracks:
            return
        self.sel = clamp(self.sel + d, 0, len(self.tracks) - 1)
        self.ensure_visible()

    def ensure_visible(self):
        vis = self.visible_rows()
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + vis:
            self.scroll = self.sel - vis + 1

    def visible_rows(self):
        return (H - BAR_H - HEADER_H) // self.lib_row_h()

    # -- actions --------------------------------------------------------
    def play_selected(self):
        if not self.tracks:
            return
        if self.player.index == self.sel and self.player.playing:
            self.player.play_pause()
        else:
            # the Library is all songs, so the queue is everything
            if self.player.play_index(self.sel,
                                      queue=list(range(len(self.tracks)))):
                self.show_toast("Now playing: %s" % self.tracks[self.sel].title)
            elif self.player.error:
                self.show_toast(self.player.error)

    def settings_path(self):
        """settings.json lives in the port's conf/ folder when it exists,
        else next to the app, so the chosen transition survives restarts."""
        conf = os.path.join(os.path.dirname(BASE_DIR), "conf")
        folder = conf if os.path.isdir(conf) else BASE_DIR
        return os.path.join(folder, "settings.json")

    def load_settings(self):
        try:
            with open(self.settings_path(), "r") as f:
                data = json.load(f)
            name = data.get("transition")
            if name in [t[0] for t in TRANSITIONS]:
                self.trans_style = name
            tname = data.get("theme")
            if tname in [n for n, _ in THEMES] + ["Custom"]:
                self.theme_name = tname
            lname = data.get("layout")
            if lname in [n for n, _ in NP_LAYOUTS]:
                self.np_layout = lname
                self.np_sel = [n for n, _ in NP_LAYOUTS].index(lname)
            if (lname == "Side by Side"
                    and data.get("layout_v", 1) < 2):
                # one-time migration: "Side by Side" was the old default
                # (never picked, just the default), and Centered is the
                # new default - upgrade it once, then leave the choice
                # alone so picking Side by Side later still sticks
                self.np_layout = "Centered"
                self.np_sel = 1
            c = data.get("custom")
            if isinstance(c, dict):
                for k in ("bg", "accent", "text"):
                    v = c.get(k)
                    if (isinstance(v, list) and len(v) == 3
                            and all(isinstance(x, int) and 0 <= x <= 255 for x in v)):
                        self.custom_theme[k] = tuple(v)
            if isinstance(data.get("setup_done"), bool):
                self.setup_done = data["setup_done"]
            liked = data.get("liked")
            if isinstance(liked, list):
                self.liked = {p for p in liked if isinstance(p, str)}
            ls = data.get("lib_size")
            if isinstance(ls, int) and 0 <= ls < len(LIB_SIZES):
                self.lib_size = ls
                self.lib_size_sel = ls
            cm = data.get("cd_mode")
            if isinstance(cm, bool):
                # old settings saved CD mode as true/false
                self.cd_mode = "cd" if cm else "off"
                self.cd_sel = 1 if cm else 0
            elif isinstance(cm, str) and cm in DISC_STYLES:
                self.cd_mode = cm
                self.cd_sel = DISC_STYLES.index(cm)
            vz = data.get("visualiser")
            if vz in [n for n, _d in VISUALISERS]:
                self.visualiser = vz
                self.viz_sel = [n for n, _d in VISUALISERS].index(vz)
            # Music Quiz: unlocked achievements, best total points, and
            # the difficulty level survive restarts; the score itself
            # is per session, so it starts at 0 every launch
            ach = data.get("quiz_achievements")
            if isinstance(ach, list):
                known = {a[0] for a in QUIZ_ACHIEVEMENTS}
                self.quiz_achievements = [a for a in ach if a in known]
            bp = data.get("quiz_best_points")
            if isinstance(bp, int) and bp >= 0:
                self.quiz_best_points = bp
            lv = data.get("quiz_level")
            if isinstance(lv, int) and 0 <= lv < len(QUIZ_LEVELS):
                self.quiz_level = lv
            ctrls = data.get("controls")
            if isinstance(ctrls, dict):
                for name, b in ctrls.items():
                    if name not in DEFAULT_CONTROLS:
                        continue
                    if b is None:
                        self.controls[name] = None
                        continue
                    if not isinstance(b, list):
                        continue
                    try:
                        if b[0] == "btn" and isinstance(b[1], int):
                            self.controls[name] = ("btn", b[1])
                        elif (b[0] == "hat" and len(b) == 3
                                and all(isinstance(x, int) for x in b[1:])):
                            self.controls[name] = ("hat", (b[1], b[2]))
                        elif (b[0] == "axis" and len(b) == 3
                                and isinstance(b[1], int) and b[2] in (-1, 1)):
                            self.controls[name] = ("axis", b[1], b[2])
                        elif (b[0] == "combo" and len(b) == 2
                                and isinstance(b[1], list) and len(b[1]) == 2
                                and all(isinstance(x, int) for x in b[1])):
                            self.controls[name] = ("combo", (b[1][0], b[1][1]))
                        elif (b[0] in ("double", "triple") and len(b) == 2
                                and isinstance(b[1], int)):
                            self.controls[name] = (b[0], b[1])
                    except Exception:
                        pass
        except Exception:
            pass

    def save_settings(self):
        try:
            def _enc(v):
                if v is None:
                    return None
                if v[0] == "hat":
                    return ["hat", v[1][0], v[1][1]]
                return list(v)
            with open(self.settings_path(), "w") as f:
                json.dump({"transition": self.trans_style,
                           "theme": self.theme_name,
                           "layout": self.np_layout,
                           "layout_v": 2,
                           "lib_size": self.lib_size,
                           "cd_mode": self.cd_mode,
                           "visualiser": self.visualiser,
                           "liked": sorted(self.liked),
                           "quiz_achievements": list(self.quiz_achievements),
                           "quiz_best_points": self.quiz_best_points,
                           "quiz_level": self.quiz_level,
                           "custom": {k: list(v) for k, v in self.custom_theme.items()},
                           "setup_done": self.setup_done,
                           "controls": {k: _enc(v)
                                        for k, v in self.controls.items()}}, f)
        except Exception:
            pass

    # ------------------------------------------------------------ themes
    def theme_list(self):
        """All pickable themes: the 33 presets plus the user's Custom one."""
        lst = list(THEMES)
        lst.append(("Custom", derive_theme(self.custom_theme["bg"],
                                           self.custom_theme["accent"],
                                           self.custom_theme["text"])))
        return lst

    def apply_theme(self, name):
        self.theme_name = name
        if name == "Custom":
            t = derive_theme(self.custom_theme["bg"], self.custom_theme["accent"],
                             self.custom_theme["text"])
        else:
            t = dict(next(th for n, th in THEMES if n == name))
        self.theme = t
        self.theme_light = t["light"]
        self.c_bg = t["bg"]
        self.c_sidebar = t["sidebar"]
        self.c_panel = t["panel"]
        self.c_bar = t["bar"]
        self.c_row = t["row"]
        self.c_row_sel = t["row_sel"]
        self.c_text = t["text"]
        self.c_sub = t["sub"]
        self.c_dim = t["dim"]
        self.c_accent = t["accent"]
        self.c_accent_d = t["accent_d"]
        self.c_track_bg = t["track_bg"]
        self.c_track_fg = t["track_fg"]

    def theme_move(self, d):
        lst = self.theme_list()
        self.theme_sel = max(0, min(len(lst) - 1, self.theme_sel + d))
        self.apply_theme(lst[self.theme_sel][0])
        self.save_settings()

    def np_move(self, d):
        self.np_sel = max(0, min(len(NP_LAYOUTS) - 1, self.np_sel + d))
        self.np_layout = NP_LAYOUTS[self.np_sel][0]
        self.save_settings()

    # ------------------------------------------------------------ flow movement
    def _update_flow(self):
        """Advance the flow position from the time-based easing."""
        if not self.albums:
            return
        dur = TRANS_DUR.get(self.trans_style, 0.28)
        if dur <= 0:
            self.flow_pos = float(self.flow_target)
            self.trans_p = 1.0
            return
        p = (time.time() - self.trans_start) / dur
        if p >= 1:
            p = 1.0
            self.flow_pos = float(self.flow_target)
        else:
            e = _ease(self.trans_style, p)
            self.flow_pos = self.trans_from + (self.flow_target - self.trans_from) * e
        self.trans_p = p

    def flow_albums(self):
        """Albums shown in Cover Flow - all of them, or only one
        artist's when an artist was picked (flow_filter)."""
        if self.flow_filter is None:
            return self.albums
        f = self.flow_filter.lower()
        return [a for a in self.albums if a["artist"].lower() == f]

    def move_flow(self, d):
        albs = self.flow_albums()
        if not albs:
            return
        self._update_flow()
        new = max(0, min(len(albs) - 1, self.flow_target + d))
        if new == self.flow_target:
            return
        self.trans_from = self.flow_pos
        self.flow_target = new
        self.trans_start = time.time()
        if TRANS_DUR.get(self.trans_style, 0.28) <= 0:
            self.flow_pos = float(new)
            self.trans_p = 1.0

    # ------------------------------------------------------------ options bar
    def open_options(self, page="transition"):
        self.opt_prev = self.trans_style
        self.opt_prev_theme = self.theme_name
        self.opt_prev_layout = self.np_layout
        self.opt_prev_lib_size = self.lib_size
        self.opt_prev_cd = self.cd_mode
        self.opt_prev_viz = self.visualiser
        self.opt_sel = [t[0] for t in TRANSITIONS].index(self.trans_style)
        self.theme_sel = [n for n, _ in self.theme_list()].index(self.theme_name)
        self.np_sel = [n for n, _ in NP_LAYOUTS].index(self.np_layout)
        self.lib_size_sel = self.lib_size
        self.cd_sel = DISC_STYLES.index(self.cd_mode)
        self.viz_sel = [n for n, _d in VISUALISERS].index(self.visualiser)
        self.opt_page = page
        self.options_open = True
        if page in ("layout", "visualiser"):
            # show the Now Playing screen so the layout / visualiser
            # previews live; start the first track if nothing is playing
            if self.player.current() is None and self.tracks:
                self.player.play_index(0)
            self.go_view("nowplaying")
        else:
            self.go_view("coverflow")   # so the flow is visible behind the bar

    def close_options(self, keep=True):
        self.options_open = False
        if not keep:
            if self.opt_page == "custom" and self.custom_backup is not None:
                self.custom_theme = dict(self.custom_backup)
                self.apply_theme(self.theme_name)
            elif self.opt_page == "theme" and self.opt_prev_theme is not None:
                self.apply_theme(self.opt_prev_theme)
            elif self.opt_page == "layout" and self.opt_prev_layout is not None:
                self.np_layout = self.opt_prev_layout
                self.np_sel = [n for n, _ in NP_LAYOUTS].index(self.np_layout)
            elif self.opt_page == "size" and self.opt_prev_lib_size is not None:
                self.lib_size = self.opt_prev_lib_size
                self.lib_size_sel = self.lib_size
            elif self.opt_page == "cd" and self.opt_prev_cd is not None:
                self.cd_mode = self.opt_prev_cd
                self.cd_sel = DISC_STYLES.index(self.cd_mode)
            elif self.opt_page == "visualiser" and self.opt_prev_viz is not None:
                self.visualiser = self.opt_prev_viz
                self.viz_sel = [n for n, _d in VISUALISERS].index(self.visualiser)
            elif self.opt_page == "transition" and self.opt_prev is not None:
                self.trans_style = self.opt_prev
            self.save_settings()

    def opt_move(self, d):
        if self.opt_page == "controls":
            return
        if self.opt_page == "theme":
            self.theme_move(d)
            return
        if self.opt_page == "layout":
            self.np_move(d)
            return
        if self.opt_page == "size":
            self.lib_size_move(d)
            return
        if self.opt_page == "cd":
            self.cd_move(d)
            return
        if self.opt_page == "visualiser":
            self.viz_move(d)
            return
        self.opt_sel = max(0, min(len(TRANSITIONS) - 1, self.opt_sel + d))
        self.trans_style = TRANSITIONS[self.opt_sel][0]
        self.save_settings()

    def viz_move(self, d):
        """Pick the Now Playing visualiser (live + saves)."""
        self.viz_sel = max(0, min(len(VISUALISERS) - 1,
                                  self.viz_sel + d))
        self.visualiser = VISUALISERS[self.viz_sel][0]
        self.save_settings()

    def toggle_opt_page(self):
        """Cycle the options bar through transitions, themes, layouts, size, CD mode, visualiser, controls."""
        pages = ["transition", "theme", "layout", "size", "cd", "visualiser", "controls"]
        if self.opt_page == "custom":
            self.opt_page = "theme"
            return
        nxt = pages[(pages.index(self.opt_page) + 1) % len(pages)]
        self.opt_page = nxt
        if nxt in ("layout", "visualiser"):
            if self.player.current() is None and self.tracks:
                self.player.play_index(0)
            self.go_view("nowplaying")
        else:
            self.go_view("coverflow")

    def open_custom_editor(self):
        self.custom_backup = dict(self.custom_theme)
        self.custom_slot = 0
        # point each slot at the palette color closest to its current value
        self.custom_idx = []
        for key in ("bg", "accent", "text"):
            cur = self.custom_theme[key]
            best = min(range(len(PALETTE)),
                       key=lambda k: sum((a - b) ** 2 for a, b in zip(PALETTE[k][1], cur)))
            self.custom_idx.append(best)
        self.opt_page = "custom"

    def custom_cycle(self, d):
        """Cycle the current slot's color through the palette (live preview)."""
        key = ("bg", "accent", "text")[self.custom_slot]
        self.custom_idx[self.custom_slot] = (
            self.custom_idx[self.custom_slot] + d) % len(PALETTE)
        self.custom_theme[key] = PALETTE[self.custom_idx[self.custom_slot]][1]
        self.apply_theme("Custom")
        self.save_settings()

    def custom_save(self):
        self.theme_name = "Custom"
        self.theme_sel = len(self.theme_list()) - 1
        self.apply_theme("Custom")
        self.save_settings()
        self.options_open = False

    def go_view(self, name):
        """Switch views; centres the flow on the playing album when entering it."""
        self.view = name
        self.menu = {"library": 0, "coverflow": 1, "album": 1,
                     "nowplaying": 2, "artists": 3, "playlists": 4,
                     "playlist": 4, "liked": 5, "search": 6,
                     "quiz": 7}.get(name, 0)
        if name == "library":
            self.lib_focus = "list"
        if name == "quiz":
            # entering the quiz starts a fresh round
            self.quiz_start_round()
        if name == "coverflow":
            albs = self.flow_albums()
            self.flow_target = min(self.flow_target, max(0, len(albs) - 1))
            if albs:
                cur = self.player.current()
                if cur is not None:
                    for i, alb in enumerate(albs):
                        if cur in alb["tracks"]:
                            self.flow_target = i
                            break
            self.flow_pos = float(self.flow_target)
            self.trans_from = float(self.flow_target)
            self.trans_p = 1.0

    def open_album(self):
        albs = self.flow_albums()
        if not albs:
            return
        self.album = albs[self.flow_target]
        self.album_sel = 0
        self.album_scroll = 0
        self.go_view("album")

    def play_album_track(self):
        if not self.album:
            return
        gi = self.album["indices"][self.album_sel]
        self.sel = gi
        if self.player.play_index(gi, queue=self.album["indices"]):
            # picking a song from the flow jumps straight to Now Playing
            self.go_view("nowplaying")
        elif self.player.error:
            self.show_toast(self.player.error)

    def open_artist(self):
        """Tap an artist: open Cover Flow with only their albums."""
        if not self.artists:
            return
        name = self.artists[self.artist_sel]["name"]
        self.flow_filter = name
        self.flow_target = 0
        self.flow_pos = 0.0
        self.go_view("coverflow")

    def open_playlist(self):
        """Tap a playlist folder: open its songs."""
        if not self.playlists:
            return
        self.playlist = self.playlists[self.pl_flow_target]
        self.pl_track_sel = 0
        self.pl_track_scroll = 0
        self.go_view("playlist")

    def play_playlist_track(self):
        if not self.playlist:
            return
        gi = self.playlist["indices"][self.pl_track_sel]
        if self.player.index == gi and self.player.playing:
            self.player.play_pause()
        else:
            # Next/Prev stay inside this playlist from now on
            if self.player.play_index(gi, queue=self.playlist["indices"]):
                self.show_toast("Now playing: %s" % self.tracks[gi].title)
            elif self.player.error:
                self.show_toast(self.player.error)

    # -- liked songs ----------------------------------------------------
    def liked_tracks(self):
        """The liked songs, in library (metadata) order."""
        return [t for t in self.tracks if t.path in self.liked]

    def toggle_like(self):
        """Like / unlike the song that is playing now. Only used from
        Now Playing - that is the one place liking is allowed."""
        cur = self.player.current()
        if cur is None:
            return
        if cur.path in self.liked:
            self.liked.discard(cur.path)
            self.show_toast("Removed from Liked Songs")
        else:
            self.liked.add(cur.path)
            self.show_toast("Liked")
        self.save_settings()

    def play_liked_track(self):
        liked = self.liked_tracks()
        if not liked:
            return
        gi = self.tracks.index(liked[self.liked_sel])
        if self.player.index == gi and self.player.playing:
            self.player.play_pause()
        else:
            idxs = [self.tracks.index(t) for t in liked]
            if self.player.play_index(gi, queue=idxs):
                self.show_toast("Now playing: %s" % self.tracks[gi].title)
            elif self.player.error:
                self.show_toast(self.player.error)

    # -- library size ---------------------------------------------------
    def lib_preset(self):
        return LIB_SIZES[self.lib_size]

    def lib_row_h(self):
        return LIB_SIZES[self.lib_size][2]

    def lib_cover_size(self):
        return LIB_SIZES[self.lib_size][3]

    def lib_title_font(self):
        return LIB_SIZES[self.lib_size][4]

    def lib_sub_font(self):
        return LIB_SIZES[self.lib_size][5]

    def lib_scale(self):
        return LIB_SIZES[self.lib_size][1]

    def lib_size_move(self, d):
        self.lib_size_sel = max(0, min(len(LIB_SIZES) - 1, self.lib_size_sel + d))
        self.lib_size = self.lib_size_sel
        self.save_settings()

    def cd_move(self, d):
        self.cd_sel = max(0, min(len(DISC_STYLES) - 1, self.cd_sel + d))
        self.cd_mode = DISC_STYLES[self.cd_sel]
        self.save_settings()

    # -- search ---------------------------------------------------------
    def update_search_results(self):
        q = self.search_query.strip().lower()
        if not q:
            self.search_results = []
        else:
            self.search_results = [
                t for t in self.tracks
                if q in t.title.lower() or q in t.artist.lower()
                or q in t.album.lower()]
        self.search_sel = clamp(self.search_sel, 0,
                                max(0, len(self.search_results) - 1))

    def press_search_key(self):
        """Press the on-screen keyboard key under the cursor."""
        row = SEARCH_KEYS[self.search_row]
        key = row[self.search_col]
        if key == "SPACE":
            self.search_query += " "
        elif key == "DEL":
            self.search_query = self.search_query[:-1]
        elif key == "DONE":
            self.search_focus = "results"
            self.search_sel = 0
            return
        else:
            self.search_query += key.lower()
        self.update_search_results()

    def open_menu_item(self):
        """Tap a sidebar menu item (menu has focus in the Library)."""
        views = ["library", "coverflow", "nowplaying", "artists",
                 "playlists", "liked", "search", "quiz"]
        name = views[self.menu_sel]
        self.lib_focus = "list"
        if name == "search":
            self.search_query = ""
            self.search_row = 0
            self.search_col = 0
            self.search_focus = "keys"
            self.update_search_results()
        self.go_view(name)

    def go_back(self):
        if self.view == "album":
            self.go_view("coverflow")
        elif self.view == "coverflow":
            if self.flow_filter is not None:
                # came here from an artist: back to the artists list
                self.flow_filter = None
                self.flow_target = 0
                self.go_view("artists")
            else:
                self.go_view("library")
        elif self.view in ("nowplaying", "artists", "playlists", "liked", "search", "quiz"):
            if self.view == "quiz":
                self.quiz_stop()
            self.go_view("library")
        elif self.view == "playlist":
            self.go_view("playlists")

    def ensure_album_visible(self):
        if not self.album:
            return
        vis = (H - BAR_H - HEADER_H - 90) // ROW_H
        if self.album_sel < self.album_scroll:
            self.album_scroll = self.album_sel
        elif self.album_sel >= self.album_scroll + vis:
            self.album_scroll = self.album_sel - vis + 1

    def _ensure_row_visible(self, sel, scroll_attr, total):
        vis = (H - BAR_H - HEADER_H) // ROW_H
        scroll = getattr(self, scroll_attr)
        if sel < scroll:
            scroll = sel
        elif sel >= scroll + vis:
            scroll = sel - vis + 1
        setattr(self, scroll_attr, max(0, scroll))

    def ensure_artist_visible(self):
        self._ensure_row_visible(self.artist_sel, "artist_scroll", len(self.artists))

    def ensure_liked_visible(self):
        self._ensure_row_visible(self.liked_sel, "liked_scroll", len(self.liked_tracks()))

    def ensure_pl_track_visible(self):
        total = len(self.playlist["indices"]) if self.playlist else 0
        self._ensure_row_visible(self.pl_track_sel, "pl_track_scroll", total)

    # -- input ----------------------------------------------------------
    def handle_key(self, key):
        if self.view == "controls":
            if key in (pygame.K_ESCAPE, pygame.K_b):
                if self.controls_listen is not None:
                    self.controls_listen = None
                elif self._setup_first_run:
                    self._finish_setup()
                else:
                    self.go_view("library")
            elif key == pygame.K_UP:
                rows = len(self._controls_rows())
                self.controls_sel = (self.controls_sel - 1) % rows
                self._ensure_controls_visible()
            elif key == pygame.K_DOWN:
                rows = len(self._controls_rows())
                self.controls_sel = (self.controls_sel + 1) % rows
                self._ensure_controls_visible()
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                rows = self._controls_rows()
                k = rows[self.controls_sel][0]
                if k == "reset":
                    self.reset_controls()
                    self.show_toast("Controls reset to defaults")
                elif self.controls_listen is None:
                    self.controls_listen = k
            return
        if key == pygame.K_o:
            if self.options_open:
                self.close_options(keep=True)
            else:
                self.open_options()
            return
        if key == pygame.K_t:
            # hotkey for the theme picker
            if self.options_open:
                self.toggle_opt_page()
            else:
                self.open_options(page="theme")
            return
        if self.options_open:
            if self.opt_page == "custom":
                if key == pygame.K_UP:
                    self.custom_slot = (self.custom_slot - 1) % 3
                elif key == pygame.K_DOWN:
                    self.custom_slot = (self.custom_slot + 1) % 3
                elif key == pygame.K_LEFT:
                    self.custom_cycle(-1)
                elif key == pygame.K_RIGHT:
                    self.custom_cycle(1)
                elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.custom_save()
                elif key in (pygame.K_b, pygame.K_ESCAPE):
                    self.close_options(keep=False)
                return
            if key == pygame.K_UP:
                self.opt_move(-1)
            elif key == pygame.K_DOWN:
                self.opt_move(1)
            elif key == pygame.K_LEFT:
                if self.opt_page in ("theme", "layout", "size", "cd"):
                    self.opt_move(-1)
                else:
                    self.move_flow(-1)
            elif key == pygame.K_RIGHT:
                if self.opt_page in ("theme", "layout", "size", "cd"):
                    self.opt_move(1)
                else:
                    self.move_flow(1)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.opt_page == "theme" and self.theme_sel == len(self.theme_list()) - 1:
                    self.open_custom_editor()
                elif self.opt_page == "controls":
                    self.close_options(keep=True)
                    self.open_controls()
                else:
                    self.close_options(keep=True)
            elif key in (pygame.K_b, pygame.K_ESCAPE):
                self.close_options(keep=False)
            return
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif key == pygame.K_UP:
            self.handle_dir("up")
        elif key == pygame.K_DOWN:
            self.handle_dir("down")
        elif key == pygame.K_LEFT:
            self.handle_dir("left")
        elif key == pygame.K_RIGHT:
            self.handle_dir("right")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.view == "coverflow":
                self.open_album()
            elif self.view == "album":
                self.play_album_track()
            elif self.view == "nowplaying":
                if self.lyrics_open:
                    self.lyrics_open = False
                else:
                    self.player.play_pause()
            elif self.view == "artists":
                self.open_artist()
            elif self.view == "playlists":
                self.open_playlist()
            elif self.view == "playlist":
                self.play_playlist_track()
            elif self.view == "liked":
                self.play_liked_track()
            elif self.view == "search":
                if self.search_focus == "keys":
                    self.press_search_key()
                elif self.search_results:
                    gi = self.tracks.index(self.search_results[self.search_sel])
                    if self.player.play_index(gi, queue=list(range(len(self.tracks)))):
                        self.show_toast("Now playing: %s" % self.tracks[gi].title)
            elif self.view == "library" and self.lib_focus == "menu":
                self.open_menu_item()
            else:
                self.play_selected()
        elif key == pygame.K_SPACE:
            self.player.play_pause()
        elif key == pygame.K_n:
            self.player.next()
        elif key == pygame.K_p:
            self.player.prev()
        elif key == pygame.K_s:
            self.show_toast("Shuffle " + ("on" if self.player.toggle_shuffle() else "off"))
        elif key == pygame.K_r:
            rep = self.player.toggle_repeat()
            self.show_toast(["Repeat off", "Repeat all", "Repeat one"][rep])
        elif key in (pygame.K_PLUS, pygame.K_EQUALS):
            self.player.set_volume(self.player.volume + 0.05)
            self._vol_show_until = time.time() + 1.5
            self.show_toast("Volume %d%%" % int(self.player.volume * 100))
        elif key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
            self.player.set_volume(self.player.volume - 0.05)
            self._vol_show_until = time.time() + 1.5
            self.show_toast("Volume %d%%" % int(self.player.volume * 100))
        elif key == pygame.K_c:
            self.go_view("coverflow")
        elif key == pygame.K_h:
            self.go_view("library")
        elif key == pygame.K_l:
            if self.view == "nowplaying":
                self.toggle_like()
        elif key == pygame.K_u:
            if self.player.current() is not None:
                self.upnext_open = not self.upnext_open
        elif key == pygame.K_y:
            if self.view == "nowplaying" and self.player.current() is not None:
                cur = self.player.current()
                if cur.get_lyrics():
                    self.lyrics_open = not self.lyrics_open
                    self.lyrics_scroll = 0
                else:
                    self.show_toast("No lyrics for this song")
        elif key == pygame.K_b:
            if self.upnext_open:
                self.upnext_open = False
            elif self.lyrics_open:
                self.lyrics_open = False
            elif self.view == "search" and self.search_focus == "results":
                self.search_focus = "keys"
            elif self.view == "library" and self.lib_focus == "menu":
                self.lib_focus = "list"
            else:
                self.go_back()

    # ------------------------------------------------------------ controls
    def _action_for_button(self, btn):
        for name, b in self.controls.items():
            if b is not None and b[0] == "btn" and b[1] == btn:
                return name
        return None

    def _action_for_hat(self, value):
        value = tuple(value)
        for name, b in self.controls.items():
            if b is not None and b[0] == "hat" and tuple(b[1]) == value:
                return name
        return None

    def _action_for_axis(self, axis, sign):
        for name, b in self.controls.items():
            if b is not None and b[0] == "axis" and b[1] == axis and b[2] == sign:
                return name
        return None

    def _combo_members(self):
        """Button index -> (action, partner button) for every combo binding."""
        out = {}
        for name, b in self.controls.items():
            if b is not None and b[0] == "combo":
                b1, b2 = b[1]
                out[b1] = (name, b2)
                out[b2] = (name, b1)
        return out

    def _fire_pending_single(self):
        """A combo member pressed on its own fires its single action
        (on release, or after a short wait) - so a lone A still confirms."""
        if self._pending_btn is None:
            return
        btn = self._pending_btn[0]
        self._pending_btn = None
        act = self._action_for_button(btn)
        if act is not None:
            if act == "back":
                self._back_hold_since = time.time()
            self.press_action(act)

    def _multi_bound_counts(self, btn):
        """Which multi-press counts are bound for a button, e.g. {2, 3}."""
        out = set()
        for _name, b in self.controls.items():
            if b is not None and b[0] == "double" and b[1] == btn:
                out.add(2)
            elif b is not None and b[0] == "triple" and b[1] == btn:
                out.add(3)
        return out

    def _multi_action(self, btn, count):
        """The action bound to pressing btn `count` times, or None."""
        kind = {2: "double", 3: "triple"}.get(count)
        if kind is None:
            return None
        for name, b in self.controls.items():
            if b is not None and b[0] == kind and b[1] == btn:
                return name
        return None

    def _resolve_pending_multi(self):
        """A multi-press sequence ended: fire the action for the count
        reached (or the single action, for a lone press)."""
        if self._pending_multi is None:
            return
        btn, count, _t = self._pending_multi
        self._pending_multi = None
        self._multi_count.pop(btn, None)
        act = self._multi_action(btn, count)
        if act is None and count == 1:
            act = self._action_for_button(btn)
        if act is not None:
            if act == "back":
                self._back_hold_since = time.time()
            self.press_action(act)

    def device_defaults(self):
        """The default mapping for the detected handheld."""
        if self._is_retrogame:
            return dict(RETROGAME_CONTROLS)
        return dict(DEFAULT_CONTROLS)

    def _apply_device_defaults(self):
        """Use the right default mapping for the detected handheld when
        the user has never remapped anything (saved mapping is still
        the generic default). Deliberately unbound actions are left
        alone - the user chose to leave them empty."""
        if self._is_retrogame and self.controls == DEFAULT_CONTROLS:
            self.controls = self.device_defaults()
            self.save_settings()

    def set_control(self, action, binding):
        """Bind an action; clear any other action that had this input."""
        for name, b in self.controls.items():
            if name != action and b is not None and b == binding:
                self.controls[name] = None
        self.controls[action] = binding
        self.save_settings()

    def reset_controls(self):
        self.controls = self.device_defaults()
        self.save_settings()

    def _controls_rows(self):
        rows = [(name, label) for name, label in CONTROL_ACTIONS]
        rows.append(("reset", "Reset to defaults"))
        return rows

    def _ensure_controls_visible(self):
        """Scroll the Controls list so the selected row is on screen
        (12 rows fit between the header and the footer)."""
        visible = 12
        total = len(self._controls_rows())
        if self.controls_sel < self.controls_scroll:
            self.controls_scroll = self.controls_sel
        elif self.controls_sel >= self.controls_scroll + visible:
            self.controls_scroll = self.controls_sel - visible + 1
        self.controls_scroll = max(0, min(self.controls_scroll,
                                          max(0, total - visible)))

    def open_controls(self):
        self.controls_sel = 0
        self.controls_scroll = 0
        self.controls_listen = None
        self.options_open = False
        self.go_view("controls")

    def _skip_binding(self):
        """Skip the action being mapped (leave it unbound) and move on."""
        act = self.controls_listen
        self.controls[act] = None
        self.save_settings()
        names = [n for n, _ in CONTROL_ACTIONS]
        idx = names.index(act)
        if idx + 1 < len(names):
            self.controls_listen = names[idx + 1]
            self.controls_sel = idx + 1
            self._ensure_controls_visible()
        else:
            self.controls_listen = None
            self.show_toast("Controls saved")
            if self._setup_first_run:
                self._finish_setup()

    def _capture_binding(self, binding):
        """Bind the action being remapped, then listen for the next one."""
        act = self.controls_listen
        if self._setup_first_run:
            # during the first-run setup a button that is already used
            # for another action is almost always a mistake (e.g. the
            # D-pad pressed again while mapping Back) - reject it
            # instead of stealing the binding and scrambling the map
            for name, b in self.controls.items():
                if name != act and b is not None and b == binding:
                    self.show_toast("Already used for %s - press another button"
                                    % dict(CONTROL_ACTIONS)[name])
                    return
        if binding[0] == "combo":
            # a button can only belong to one combo - two combos sharing
            # a button would be ambiguous when that button is pressed
            for name, b in self.controls.items():
                if name != act and b is not None and b[0] == "combo":
                    if set(b[1]) & set(binding[1]):
                        self.show_toast("That button is already in a combo for %s"
                                        % dict(CONTROL_ACTIONS)[name])
                        return
        self.set_control(act, binding)
        if not self._setup_first_run:
            # a one-off remap from the Controls screen: bind this one
            # action and stop - do not walk through the whole list
            self.controls_listen = None
            self.show_toast("%s: %s" % (dict(CONTROL_ACTIONS)[act],
                                        control_label(binding, self._is_retrogame)))
            return
        names = [n for n, _ in CONTROL_ACTIONS]
        idx = names.index(act)
        if idx + 1 < len(names):
            self.controls_listen = names[idx + 1]
            self.controls_sel = idx + 1
            self._ensure_controls_visible()
        else:
            self.controls_listen = None
            self.show_toast("Controls saved")
            self._finish_setup()

    def _finish_setup(self):
        """First-run setup is done: remember it and go to the Library."""
        self._setup_first_run = False
        self.setup_done = True
        self.save_settings()
        self.go_view("library")

    def controls_button(self, act):
        """Button presses while the Controls view is open."""
        rows = self._controls_rows()
        key = rows[self.controls_sel][0]
        if act == "back":
            if self.controls_listen is not None:
                self.controls_listen = None
            elif self._setup_first_run:
                self._finish_setup()
            else:
                self.go_view("library")
            return
        if act == "confirm":
            if key == "reset":
                self.reset_controls()
                self.show_toast("Controls reset to defaults")
            elif self.controls_listen is None:
                self.controls_listen = key
            return

    def handle_axis(self, axis, value):
        """D-pad / stick axes. Both sticks navigate (left axes 0/1,
        right axes 2/3), and any axis can be bound to any action.
        Edge-triggered: one step per press."""
        d = 1 if value > 0.5 else (-1 if value < -0.5 else 0)
        if self._axis_dir.get(axis, 0) == d:
            return
        self._axis_dir[axis] = d
        # diagnostics: log every axis crossing the dead zone, so the
        # real mapping can be read from log.txt
        print("INPUT axis %d %s" % (axis, "+" if d > 0 else "-" if d < 0 else "0"),
              flush=True)
        if not d:
            return
        # capture: any axis can be bound to any action
        if self.controls_listen is not None:
            self._capture_binding(("axis", axis, d))
            return
        # exact binding first (an axis can be bound to any action)
        act = self._action_for_axis(axis, d)
        if act is not None:
            if act in DIR_HAT:
                self.handle_dir(act)
            else:
                self.press_action(act)
            return
        # geometric fallback: either stick navigates in the direction
        # pushed, if that direction is bound to anything at all - so the
        # sticks keep working after a direction is remapped to a button,
        # and the D-pad keeps working after a direction is remapped to
        # a stick
        if axis in (0, 2):
            geo = "right" if d > 0 else "left"
        else:  # axis 1 or 3
            geo = "down" if d > 0 else "up"
        # always navigate, even when the direction is unbound - so the
        # sticks stay usable with a blank keymap
        self.handle_dir(geo)

    def _start_button(self):
        """Physical Start button index for the detected handheld
        (SELECT+START quits; Start on its own does nothing now that
        Change view is removed)."""
        return 9 if self._is_retrogame else 7

    def _select_button(self):
        """Physical Select button index for the detected handheld."""
        return 8 if self._is_retrogame else 6

    def _back_button(self):
        """Physical B button index for the detected handheld
        (hold it 2s to open Controls; tap it during the first-run
        setup to skip the current action)."""
        return 0 if self._is_retrogame else 1

    def handle_joy_button(self, btn):
        # capturing a new binding
        if self.controls_listen is not None:
            # a second press while the first is still fresh: the same
            # button again is a double/triple-click, a different one
            # is a combo (press two buttons together, e.g. A+B)
            if self._capture_first is not None:
                first_btn, first_time, first_cnt = self._capture_first
                if time.time() - first_time < 0.35:
                    if btn == first_btn:
                        cnt = first_cnt + 1
                        if cnt >= 3:
                            self._capture_first = None
                            self._capture_binding(("triple", btn))
                            return
                        self._capture_first = (btn, time.time(), cnt)
                        return
                    self._capture_first = None
                    self._capture_binding(("combo", (first_btn, btn)))
                    return
                # too late: the run loop already bound the first one,
                # so start fresh with this press
                self._capture_first = None
            # during the first-run setup, B skips the current action
            # (leaves it unbound and moves on) - except when mapping
            # Back itself, where B is the button being mapped
            if (self._setup_first_run and self.controls_listen != "back"
                    and btn == self._back_button()):
                self._skip_binding()
                return
            back_b = self.controls.get("back")
            if (self.controls_listen != "back" and back_b is not None
                    and back_b[0] == "btn" and back_b[1] == btn):
                self.controls_listen = None
                return
            # wait a beat for a second press (a combo or a double/
            # triple-click) before binding this one on its own - the
            # run loop binds it if no partner follows within 0.35s
            self._capture_first = (btn, time.time(), 1)
            return
        # track which buttons are held (for combos and multi-press)
        self._held_btns.add(btn)
        # track the physical Select button (SELECT+START quits even
        # when the Select/Start actions are unbound)
        if btn == self._select_button():
            self._select_phys_held = True
        # SELECT+START quits
        if btn == self._start_button() and self._select_phys_held:
            self._select_open_pending = False
            self.running = False
            return
        # SELECT+Y resets the key mapping to the defaults - a safety
        # net if the mapping gets scrambled and Controls can't be
        # reached (physical buttons, so it works with a blank keymap)
        if btn == 3 and self._select_phys_held:
            self._select_open_pending = False
            self.select_held = False
            self.reset_controls()
            self.show_toast("Controls reset to defaults")
            return
        if btn == self._select_button() and 3 in self._held_btns:
            self._select_open_pending = False
            self.select_held = False
            self.reset_controls()
            self.show_toast("Controls reset to defaults")
            return
        # the physical X / Y buttons (btn 2 / 3 on every layout) always
        # switch the options bar pages when it is open, no matter what
        # they are mapped to - so the "X/Y: themes" hint is always true
        # even when Next/Previous track are unbound or on other buttons
        if self.options_open and btn in (2, 3):
            self.toggle_opt_page()
            return
        # hold B 2s to open Controls: the physical B button, or
        # whichever button the Back action is bound to - so Controls
        # is always reachable even with a blank keymap
        if btn == self._back_button():
            self._back_hold_since = time.time()
        # a combo: both buttons held together fire the combo action,
        # and the single actions for those buttons do not fire
        for name, b in self.controls.items():
            if b is not None and b[0] == "combo" and btn in b[1]:
                other = b[1][0] if b[1][1] == btn else b[1][1]
                if other in self._held_btns:
                    self._pending_btn = None
                    self._pending_multi = None
                    self._multi_count.pop(btn, None)
                    self._multi_count.pop(other, None)
                    self.press_action(name)
                    return
        # double / triple-click: count consecutive presses of the same
        # button within 0.35s; the action fires when the count reaches
        # a bound multi, or when the window closes (see run loop)
        now = time.time()
        counts = self._multi_bound_counts(btn)
        if counts:
            prev = self._multi_count.get(btn)
            if prev is not None and now - prev[1] < 0.35:
                cnt = prev[0] + 1
            else:
                cnt = 1
            self._multi_count[btn] = [cnt, now]
            top = max(counts)
            if cnt >= top:
                act = self._multi_action(btn, min(cnt, top))
                if act is None:
                    act = self._multi_action(btn, top)
                self._pending_multi = None
                self._multi_count.pop(btn, None)
                if act is not None:
                    self.press_action(act)
                return
            # below the highest bound multi: wait for another press
            self._pending_multi = (btn, cnt, now)
            return
        # a combo member pressed on its own: wait to see if its partner
        # follows (so A+B opens lyrics instead of A confirming and B
        # going back); the single fires on release or after 0.3s
        if btn in self._combo_members():
            self._pending_btn = (btn, time.time())
            return
        act = self._action_for_button(btn)
        if act is not None:
            if act == "back":
                self._back_hold_since = time.time()
            self.press_action(act)
            return
        # D-pad fallback (retrogame): the physical D-pad still navigates
        # even when a direction is bound to something else (e.g. a stick),
        # so the D-pad and the sticks stay usable together
        if self._is_retrogame and btn in RETROGAME_DPAD:
            self.handle_dir(RETROGAME_DPAD[btn])

    def press_action(self, act):
        """Run an action by name (from a button, hat or axis)."""
        if act in DIR_HAT:
            # a direction bound to a button (e.g. a D-pad that reports
            # as buttons) navigates just like a hat direction
            self.handle_dir(act)
            return
        if self.view == "controls":
            self.controls_button(act)
            return
        # standard SDL mapping: 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 6 Select, 7 Start
        if self.options_open:
            if self.opt_page == "custom":
                if act == "confirm":    # A: save the custom theme
                    self.custom_save()
                elif act == "back":     # B: cancel, back to the previous theme
                    self.close_options(keep=False)
                return
            if act == "confirm":    # A: keep the picked item
                if self.opt_page == "theme" and self.theme_sel == len(self.theme_list()) - 1:
                    self.open_custom_editor()
                elif self.opt_page == "controls":
                    self.close_options(keep=True)
                    self.open_controls()
                else:
                    self.close_options(keep=True)
            elif act == "back":     # B: cancel, back to the previous one
                self.close_options(keep=False)
            elif act in ("next", "prev"):  # X / Y: switch option pages
                self.toggle_opt_page()
            return
        if act == "confirm":      # A
            if self.view == "quiz":
                if self.quiz_answered:
                    self.quiz_start_round()
                else:
                    self.quiz_answer()
            elif self.view == "coverflow":
                self.open_album()
            elif self.view == "album":
                self.play_album_track()
            elif self.view == "nowplaying":
                if self.lyrics_open:
                    self.lyrics_open = False
                else:
                    self.player.play_pause()
            elif self.view == "artists":
                self.open_artist()
            elif self.view == "playlists":
                self.open_playlist()
            elif self.view == "playlist":
                self.play_playlist_track()
            elif self.view == "liked":
                self.play_liked_track()
            elif self.view == "search":
                if self.search_focus == "keys":
                    self.press_search_key()
                elif self.search_results:
                    gi = self.tracks.index(self.search_results[self.search_sel])
                    if self.player.play_index(gi, queue=list(range(len(self.tracks)))):
                        self.show_toast("Now playing: %s" % self.tracks[gi].title)
            elif self.view == "library" and self.lib_focus == "menu":
                self.open_menu_item()
            else:
                self.play_selected()
        elif act == "back":    # B: back
            if self.upnext_open:
                self.upnext_open = False
            elif self.lyrics_open:
                self.lyrics_open = False
            elif self.view == "search" and self.search_focus == "results":
                self.search_focus = "keys"
            elif self.view == "library" and self.lib_focus == "menu":
                self.lib_focus = "list"
            else:
                self.go_back()
        elif act == "next":    # X: next
            if self.view == "quiz":
                self.quiz_replay()
            else:
                self.player.next()
        elif act == "prev":    # Y: previous
            if self.view == "quiz":
                self.quiz_replay()
            else:
                self.player.prev()
        elif act == "shuffle":    # L: shuffle
            self.show_toast("Shuffle " + ("on" if self.player.toggle_shuffle() else "off"))
        elif act == "repeat":    # R: repeat
            rep = self.player.toggle_repeat()
            self.show_toast(["Repeat off", "Repeat all", "Repeat one"][rep])
        elif act == "options":    # Select: tap (release) opens the options bar
            if self.view == "quiz":
                # in the quiz, Select is the quit button: triple-click
                # it to leave the game and go back to the music. A
                # single tap does nothing here, so the options bar
                # does not pop open while you tap out the triple-click.
                now = time.time()
                self.quiz_select_presses = [t for t in self.quiz_select_presses
                                            if now - t < 0.6]
                self.quiz_select_presses.append(now)
                if len(self.quiz_select_presses) >= 3:
                    self.quiz_exit_to_music()
                return
            self.select_held = True
            self._select_open_pending = True
        elif act == "coverflow":    # jump straight to Cover Flow
            self.go_view("coverflow")
        elif act == "nowplaying":    # jump straight to Now Playing
            self.go_view("nowplaying")
        elif act == "like":    # L2: like the song - Now Playing only
            if self.view == "nowplaying":
                self.toggle_like()
        elif act == "upnext":    # R2: the Up Next pop-up
            if self.player.current() is not None:
                self.upnext_open = not self.upnext_open
        elif act == "lyrics":    # show the lyrics panel in Now Playing
            if self.view == "nowplaying" and self.player.current() is not None:
                cur = self.player.current()
                if cur.get_lyrics():
                    self.lyrics_open = not self.lyrics_open
                    self.lyrics_scroll = 0
                else:
                    self.show_toast("No lyrics for this song")

    def handle_joy_button_up(self, btn):
        if btn == self._select_button():
            self._select_phys_held = False
        if btn == self._back_button():
            self._back_hold_since = None
        self._held_btns.discard(btn)
        # a combo member released on its own: fire its single action
        # (a lone A still confirms, a lone B still goes back)
        if self._pending_btn is not None and self._pending_btn[0] == btn:
            self._fire_pending_single()
        act = self._action_for_button(btn)
        if act == "back":
            self._back_hold_since = None
        if act == "options":
            self.select_held = False
            if self._select_open_pending and not self.options_open:
                self.open_options()
            elif self.options_open:
                self.close_options(keep=True)
            self._select_open_pending = False

    def handle_hat(self, hat):
        if self.controls_listen is not None:
            if tuple(hat) != (0, 0):
                self._capture_binding(("hat", tuple(hat)))
            return
        if self.view == "controls":
            geo = HAT_DIR.get(tuple(hat))
            if geo is not None:
                self.handle_dir(geo)
            return
        # exact binding first (a hat can be bound to any action)
        act = self._action_for_hat(hat)
        if act is not None:
            if act in DIR_HAT:
                self.handle_dir(act)
            else:
                self.press_action(act)
            return
        # geometric fallback: the D-pad direction - so a hat D-pad works
        # with axis defaults, and the D-pad keeps working after a
        # direction is remapped to a button or left unbound
        geo = HAT_DIR.get(tuple(hat))
        if geo is not None:
            self.handle_dir(geo)

    def handle_dir(self, act):
        if self.view == "controls":
            rows = len(self._controls_rows())
            if act == "up":
                self.controls_sel = (self.controls_sel - 1) % rows
            elif act == "down":
                self.controls_sel = (self.controls_sel + 1) % rows
            self._ensure_controls_visible()
            return
        x, y = DIR_HAT[act]
        if self.options_open:
            if self.opt_page == "custom":
                if y == 1:
                    self.custom_slot = (self.custom_slot - 1) % 3
                elif y == -1:
                    self.custom_slot = (self.custom_slot + 1) % 3
                elif x == -1:
                    self.custom_cycle(-1)
                elif x == 1:
                    self.custom_cycle(1)
                return
            if y == 1:
                self.opt_move(-1)
            elif y == -1:
                self.opt_move(1)
            elif x == -1:
                if self.opt_page in ("theme", "layout", "size", "cd"):
                    self.opt_move(-1)
                else:
                    self.move_flow(-1)
            elif x == 1:
                if self.opt_page in ("theme", "layout", "size", "cd"):
                    self.opt_move(1)
                else:
                    self.move_flow(1)
            return
        if self.view == "coverflow":
            if x == -1:
                self.move_flow(-1)
            elif x == 1:
                self.move_flow(1)
            elif y == 1:
                self.move_flow(-5)
            elif y == -1:
                self.move_flow(5)
            return
        if self.view == "playlists":
            # the Playlists view is a Cover Flow of the playlist folders
            if x == -1:
                self.move_pl_flow(-1)
            elif x == 1:
                self.move_pl_flow(1)
            elif y == 1:
                self.move_pl_flow(-5)
            elif y == -1:
                self.move_pl_flow(5)
            return
        if self.view == "quiz":
            # Up/Down picks an answer, Left/Right changes the level
            if not self.quiz_choices:
                return
            if y == 1:
                self.quiz_sel = (self.quiz_sel - 1) % len(self.quiz_choices)
            elif y == -1:
                self.quiz_sel = (self.quiz_sel + 1) % len(self.quiz_choices)
            elif x == -1:
                self.quiz_cycle_level(-1)
            elif x == 1:
                self.quiz_cycle_level(1)
            return
        if self.view == "library" and self.lib_focus == "menu":
            # the sidebar has focus: Up/Down picks a menu item,
            # Right goes back to the track list
            if y == 1:
                self.menu_sel = (self.menu_sel - 1) % 8
            elif y == -1:
                self.menu_sel = (self.menu_sel + 1) % 8
            elif x == 1:
                self.lib_focus = "list"
            return
        if self.view == "search":
            if self.search_focus == "keys":
                if y == 1:
                    self.search_row = (self.search_row - 1) % len(SEARCH_KEYS)
                    self.search_col = min(self.search_col,
                                          len(SEARCH_KEYS[self.search_row]) - 1)
                elif y == -1:
                    self.search_row = (self.search_row + 1) % len(SEARCH_KEYS)
                    self.search_col = min(self.search_col,
                                          len(SEARCH_KEYS[self.search_row]) - 1)
                elif x == -1:
                    self.search_col = (self.search_col - 1) % len(SEARCH_KEYS[self.search_row])
                elif x == 1:
                    self.search_col = (self.search_col + 1) % len(SEARCH_KEYS[self.search_row])
            else:
                if y == 1:
                    self.search_sel = clamp(self.search_sel - 1, 0, max(0, len(self.search_results) - 1))
                elif y == -1:
                    self.search_sel = clamp(self.search_sel + 1, 0, max(0, len(self.search_results) - 1))
            return
        if self.view == "nowplaying" and self.lyrics_open:
            # Up/Down scrolls the lyrics
            if y == 1:
                self.lyrics_scroll = max(0, self.lyrics_scroll - 1)
            elif y == -1:
                self.lyrics_scroll += 1
            return
        if y == 1:
            if self.view == "album":
                self.album_sel = clamp(self.album_sel - 1, 0, len(self.album["tracks"]) - 1)
                self.ensure_album_visible()
            elif self.view == "nowplaying":
                self.player.set_volume(self.player.volume + 0.05)
                self._vol_show_until = time.time() + 1.5
            elif self.view == "artists":
                self.artist_sel = clamp(self.artist_sel - 1, 0, max(0, len(self.artists) - 1))
                self.ensure_artist_visible()
            elif self.view == "liked":
                self.liked_sel = clamp(self.liked_sel - 1, 0, max(0, len(self.liked_tracks()) - 1))
                self.ensure_liked_visible()
            elif self.view == "playlist" and self.playlist is not None:
                self.pl_track_sel = clamp(self.pl_track_sel - 1, 0, max(0, len(self.playlist["indices"]) - 1))
                self.ensure_pl_track_visible()
            else:
                self.move_sel(-1)
        elif y == -1:
            if self.view == "album":
                self.album_sel = clamp(self.album_sel + 1, 0, len(self.album["tracks"]) - 1)
                self.ensure_album_visible()
            elif self.view == "nowplaying":
                self.player.set_volume(self.player.volume - 0.05)
                self._vol_show_until = time.time() + 1.5
            elif self.view == "artists":
                self.artist_sel = clamp(self.artist_sel + 1, 0, max(0, len(self.artists) - 1))
                self.ensure_artist_visible()
            elif self.view == "liked":
                self.liked_sel = clamp(self.liked_sel + 1, 0, max(0, len(self.liked_tracks()) - 1))
                self.ensure_liked_visible()
            elif self.view == "playlist" and self.playlist is not None:
                self.pl_track_sel = clamp(self.pl_track_sel + 1, 0, max(0, len(self.playlist["indices"]) - 1))
                self.ensure_pl_track_visible()
            else:
                self.move_sel(1)
        elif x == -1:
            if self.view == "library" and self.lib_focus == "list":
                # Left moves focus to the sidebar menu
                self.lib_focus = "menu"
                self.menu_sel = self.menu
            else:
                self.player.seek_rel(-5)
        elif x == 1:
            self.player.seek_rel(5)

    # -- drawing --------------------------------------------------------
    def draw(self):
        self.screen.fill(self.c_bg)
        if self.view == "controls":
            self.draw_controls()
        elif not self.tracks:
            self.draw_empty()
        elif self.view == "library":
            self.draw_sidebar()
            self.draw_header()
            self.draw_list()
            self.draw_bar()
        elif self.view == "coverflow":
            self.draw_coverflow()   # pure browsing - no player bar, no buttons
        elif self.view == "album":
            self.draw_album()
            self.draw_bar()
        elif self.view == "artists":
            self.draw_artists()
            self.draw_bar()
        elif self.view == "playlists":
            self.draw_pl_flow()   # Cover Flow of the playlist folders
        elif self.view == "playlist":
            self.draw_playlist()
            self.draw_bar()
        elif self.view == "liked":
            self.draw_liked()
            self.draw_bar()
        elif self.view == "search":
            self.draw_search()
        elif self.view == "quiz":
            self.draw_quiz()
        else:
            self.draw_now_playing()
        if self.upnext_open:
            self.draw_upnext()
        if self.lyrics_open:
            self.draw_lyrics_panel()
        if self.options_open:
            self.draw_options_bar()
        self.draw_toast()
        pygame.display.flip()

    def draw_controls(self):
        """Full-screen button remapping (or the first-run key setup)."""
        if self._setup_first_run:
            self.text("h1", "Set up your controls", self.c_text, (16, 14))
        else:
            self.text("h1", "Controls", self.c_text, (16, 14))
        if self.controls_listen is not None:
            name = dict(CONTROL_ACTIONS)[self.controls_listen]
            self.text("body", "Press a button for %s... (two together = combo, twice = double, 3x = triple)" % name,
                      self.c_accent, (16, 52))
            if self._setup_first_run:
                self.text("small", "Press B to skip this one.",
                          self.c_sub, (16, 76))
            else:
                self.text("small", "Press Back to stop.",
                          self.c_sub, (16, 76))
        elif self._setup_first_run:
            self.text("body", "Press the button for each action, in order.",
                      self.c_sub, (16, 52))
            self.text("small", "It only takes a moment - B skips the setup.",
                      self.c_sub, (16, 76))
        else:
            self.text("body", "Map the buttons and D-pad to each action.",
                      self.c_sub, (16, 52))
            self.text("small", "A: remap the selected action  -  B: back",
                      self.c_sub, (16, 76))
        rows = self._controls_rows()
        self._ensure_controls_visible()
        visible = 12
        y = 104
        row_h = 26
        for i in range(self.controls_scroll,
                       min(len(rows), self.controls_scroll + visible)):
            key, label = rows[i]
            sel = (i == self.controls_sel)
            if sel:
                pygame.draw.rect(self.screen, self.c_row,
                                 (12, y - 3, W - 24, row_h), border_radius=6)
            if key == "reset":
                self.text("small_b" if sel else "small", label,
                          self.c_accent if sel else self.c_sub, (20, y))
            else:
                self.text("small_b" if sel else "small", label,
                          self.c_text if sel else self.c_sub, (20, y))
                if self.controls_listen == key:
                    blabel, bcol = "Press a button...", self.c_accent
                else:
                    blabel = control_label(self.controls.get(key), self._is_retrogame)
                    bcol = self.c_sub
                self.text("small", blabel, bcol, (W - 20, y), "right")
            y += row_h
        # scroll arrows: more rows above / below
        if self.controls_scroll > 0:
            self.text("body_b", "▲", self.c_sub, (W // 2, 100), "center")
        if self.controls_scroll + visible < len(rows):
            self.text("body_b", "▼", self.c_sub, (W // 2, y + 2), "center")
        self.text("tiny", "Hold B for 2s to open this screen. SELECT+Y resets all controls.",
                  self.c_dim, (W // 2, H - 24), "center")

    def draw_empty(self):
        self.text("h1", "Sym3c Tunes", self.c_accent, (W // 2, 120), "center")
        self.text("body", "No music found.", self.c_text, (W // 2, 170), "center")
        self.text("small", "Put MP3, OGG or WAV files in one of these folders:",
                  self.c_sub, (W // 2, 205), "center")
        y = 235
        for d in MUSIC_DIRS[:4]:
            self.text("small", d, self.c_dim, (W // 2, y), "center")
            y += 22
        self.text("small", "Then launch the app again.  SELECT + START to quit.",
                  self.c_sub, (W // 2, y + 14), "center")

    def draw_sidebar(self):
        pygame.draw.rect(self.screen, self.c_sidebar, (0, 0, SIDEBAR_W, H))
        # logo
        self.text("logo", "Sym3c", self.c_text, (14, 14))
        self.text("logo", "Tunes", self.c_accent, (14, 36))
        pygame.draw.circle(self.screen, self.c_accent, (104, 24), 5)
        items = [("Your Library", 0), ("Cover Flow", 1), ("Now Playing", 2),
                 ("Artists", 3), ("Playlists", 4), ("Liked Songs", 5),
                 ("Search", 6), ("Music Quiz", 7)]
        # when the menu has focus the picked item gets a bright accent
        # highlight, so it is obvious the menu is where you are;
        # otherwise the highlight is just a dim marker for the view
        hi = self.menu_sel if self.lib_focus == "menu" else self.menu
        menu_focused = (self.lib_focus == "menu")
        y = 92
        for label, idx in items:
            sel = (hi == idx)
            if sel and menu_focused:
                pygame.draw.rect(self.screen, self.c_accent,
                                 (8, y - 6, SIDEBAR_W - 16, 28), border_radius=6)
                self.text("body_b", label, self.c_bg, (16, y))
            elif sel:
                pygame.draw.rect(self.screen, self.c_row, (8, y - 6, SIDEBAR_W - 16, 28), border_radius=6)
                self.text("body_b", label, self.c_text, (16, y))
            else:
                self.text("body", label, self.c_sub, (16, y))
            y += 28
        pygame.draw.line(self.screen, self.c_row, (14, y + 2), (SIDEBAR_W - 14, y + 2))
        y += 14
        self.text("tiny", "PLAYLISTS", self.c_dim, (16, y))
        y += 20
        self.text("body", "All Songs", self.c_text, (16, y))
        y += 18
        self.text("small", "%d tracks" % len(self.tracks), self.c_dim, (16, y))
        # credits, at the bottom of the sidebar, above the player bar
        self.text("tiny", "muse.ai", self.c_dim, (16, H - BAR_H - 32))
        self.text("tiny", "x Phil Assistant", self.c_dim, (16, H - BAR_H - 16))

    def draw_header(self):
        self.text("h1", "Your Library", self.c_text, (SIDEBAR_W + 16, 12))
        self.text("small", "%d songs" % len(self.tracks), self.c_sub,
                  (W - 16, 20), "right")

    def draw_list(self):
        x0 = SIDEBAR_W + 8
        list_w = W - x0 - 8
        y0 = HEADER_H
        row_h = self.lib_row_h()
        cov = self.lib_cover_size()
        tf = self.lib_title_font()
        sf = self.lib_sub_font()
        vis = self.visible_rows()
        for i in range(vis):
            idx = self.scroll + i
            if idx >= len(self.tracks):
                break
            t = self.tracks[idx]
            y = y0 + i * row_h
            if idx == self.sel:
                if self.lib_focus == "list":
                    pygame.draw.rect(self.screen, self.c_row_sel,
                                     (x0, y + 2, list_w, row_h - 4), border_radius=6)
                    pygame.draw.rect(self.screen, self.c_accent,
                                     (x0, y + 6, 3, row_h - 12), border_radius=2)
                else:
                    # the menu has focus - the track is only a dim marker
                    pygame.draw.rect(self.screen, self.c_row,
                                     (x0, y + 2, list_w, row_h - 4), border_radius=6)
            cover = cover_surface(t, cov)
            self.screen.blit(cover, (x0 + 10, y + (row_h - cov) // 2))
            playing = (self.player.index == idx and self.player.playing)
            title_col = self.c_accent if self.player.index == idx else self.c_text
            # centre the two text lines in the row
            th = self.fonts[tf].get_height()
            sh = self.fonts[sf].get_height()
            title_y = y + (row_h - th - sh - 4) // 2
            tx = x0 + 10 + cov + 10
            title = self.fit(tf, t.title, list_w - (tx - x0) - 70)
            self.text(tf, title, title_col, (tx, title_y))
            artist = self.fit(sf, "%s  ·  %s" % (t.artist, t.album), list_w - (tx - x0) - 70)
            self.text(sf, artist, self.c_sub, (tx, title_y + th + 4))
            dur = fmt_time(t.duration) if t.duration else "--:--"
            self.text(sf, dur, self.c_sub, (W - 16, y + (row_h - sh) // 2), "right")
            if playing:
                self.draw_eq(tx + self.fonts[tf].size(title)[0] + 10, y + 12)

    def draw_eq(self, x, y):
        # tiny animated equaliser bars next to the playing track
        bars = [6, 12, 8]
        ph = int(time.time() * 6) % 3
        for i, h in enumerate(bars):
            hh = h if i != ph else h + 4
            pygame.draw.rect(self.screen, self.c_accent,
                             (x + i * 5, y + 14 - hh, 3, hh))

    def draw_bar(self):
        y0 = H - BAR_H
        pygame.draw.rect(self.screen, self.c_bar, (0, y0, W, BAR_H))
        pygame.draw.line(self.screen, self.c_row, (0, y0), (W, y0))
        cur = self.player.current()
        if cur is not None:
            cover = cover_surface(cur, 48)
            self.screen.blit(cover, (12, y0 + 9))
            title = self.fit("body_b", cur.title, 200)
            self.text("body_b", title, self.c_text, (70, y0 + 12))
            artist = self.fit("small", cur.artist, 200)
            self.text("small", artist, self.c_sub, (70, y0 + 34))
        else:
            self.text("body", "Nothing playing", self.c_sub, (70, y0 + 22))
        # transport
        cx = W // 2
        self.draw_transport(cx - 62, y0 + 8, 26, "prev")
        self.draw_transport(cx, y0 + 2, 38, "play" if not self.player.playing else "pause")
        self.draw_transport(cx + 62, y0 + 8, 26, "next")
        # progress - centred on the screen, under the transport buttons
        pos = self.player.position()
        dur = self.player.duration()
        frac = clamp(pos / dur, 0, 1) if dur > 0 else 0
        bw = 240
        bx = (W - bw) // 2
        by = y0 + 50
        pygame.draw.rect(self.screen, self.c_track_bg, (bx, by, bw, 4), border_radius=2)
        if frac > 0:
            pygame.draw.rect(self.screen, self.c_text, (bx, by, int(bw * frac), 4), border_radius=2)
            pygame.draw.circle(self.screen, self.c_text, (bx + int(bw * frac), by + 2), 5)
        self.text("tiny", fmt_time(pos), self.c_sub, (bx - 8, by - 4), "right")
        self.text("tiny", fmt_time(dur), self.c_sub, (bx + bw + 8, by - 4))
        # right side: shuffle / repeat / volume - the volume bar must
        # fit between the transport's next button and the right edge,
        # or it overlaps the buttons (as seen on the Library photo)
        rx = W - 16
        if self.player.repeat:
            lab = "REP 1" if self.player.repeat == 2 else "REP"
            self.text("small_b", lab, self.c_accent, (rx, y0 + 14), "right")
            rx -= 52
        if self.player.shuffle:
            self.text("small_b", "SHUF", self.c_accent, (rx, y0 + 14), "right")
            rx -= 56
        pct_w = 36
        trans_right = (W // 2) + 62 + 26 + 10
        vol_right = rx - pct_w
        vol_w = max(40, min(120, vol_right - trans_right))
        pygame.draw.rect(self.screen, self.c_track_bg, (vol_right - vol_w, y0 + 18, vol_w, 4), border_radius=2)
        pygame.draw.rect(self.screen, self.c_text, (vol_right - vol_w, y0 + 18, int(vol_w * self.player.volume), 4), border_radius=2)
        self.text("tiny", "%d%%" % int(self.player.volume * 100),
                  self.c_sub, (vol_right + 4, y0 + 14))

    def draw_transport(self, cx, cy, size, kind):
        r = size // 2
        if kind in ("play", "pause"):
            pygame.draw.circle(self.screen, self.c_text, (cx, cy), r)
            fg = self.c_bg
        else:
            fg = self.c_text
        if kind == "play":
            pygame.draw.polygon(self.screen, fg, [
                (cx - 6, cy - 9), (cx - 6, cy + 9), (cx + 9, cy)])
        elif kind == "pause":
            pygame.draw.rect(self.screen, fg, (cx - 8, cy - 8, 5, 16))
            pygame.draw.rect(self.screen, fg, (cx + 3, cy - 8, 5, 16))
        elif kind == "prev":
            pygame.draw.rect(self.screen, fg, (cx - 11, cy - 8, 4, 16))
            pygame.draw.polygon(self.screen, fg, [
                (cx + 10, cy - 9), (cx + 10, cy + 9), (cx - 6, cy)])
        elif kind == "next":
            pygame.draw.rect(self.screen, fg, (cx + 7, cy - 8, 4, 16))
            pygame.draw.polygon(self.screen, fg, [
                (cx - 10, cy - 9), (cx - 10, cy + 9), (cx + 6, cy)])

    # -- cover flow -----------------------------------------------------
    def album_glow(self, album):
        key = (album["title"], album["artist"])
        if key in self._glow_cache:
            return self._glow_cache[key]
        try:
            tiny = pygame.transform.smoothscale(
                cover_surface(album["tracks"][0], 40), (1, 1))
            col = tuple(tiny.get_at((0, 0))[:3])
        except Exception:
            col = self.c_accent
        self._glow_cache[key] = col
        return col

    def playlist_cover(self, pl, size=200):
        """A playlist's cover: the album art of up to 4 songs inside it,
        tiled 2x2 (like Spotify's playlist covers). Fewer than 4 songs
        repeats them to fill the four tiles."""
        key = (pl["name"], size, tuple(pl["indices"][:4]))
        if key in self._pl_cover_cache:
            return self._pl_cover_cache[key]
        half = size // 2
        surf = pygame.Surface((size, size))
        idxs = pl["indices"]
        for k in range(4):
            if not idxs:
                break
            t = self.tracks[idxs[k % len(idxs)]]
            tile = cover_surface(t, half)
            surf.blit(tile, ((k % 2) * half, (k // 2) * half))
        if len(self._pl_cover_cache) > 40:
            self._pl_cover_cache.clear()
        self._pl_cover_cache[key] = surf
        return surf

    def playlist_glow(self, pl):
        """The ambient glow colour for a playlist, from its tiled cover."""
        key = ("pl", pl["name"])
        if key in self._glow_cache:
            return self._glow_cache[key]
        try:
            tiny = pygame.transform.smoothscale(self.playlist_cover(pl, 40), (1, 1))
            col = tuple(tiny.get_at((0, 0))[:3])
        except Exception:
            col = self.c_accent
        self._glow_cache[key] = col
        return col

    def _update_pl_flow(self):
        """Advance the playlist flow position (Slide easing)."""
        if not self.playlists:
            return
        dur = 0.28
        p = (time.time() - self.pl_trans_start) / dur
        if p >= 1:
            p = 1.0
            self.pl_flow_pos = float(self.pl_flow_target)
        else:
            e = _ease("Slide", p)
            self.pl_flow_pos = self.pl_trans_from + (self.pl_flow_target - self.pl_trans_from) * e
        self.pl_trans_p = p

    def move_pl_flow(self, d):
        if not self.playlists:
            return
        self._update_pl_flow()
        new = max(0, min(len(self.playlists) - 1, self.pl_flow_target + d))
        if new == self.pl_flow_target:
            return
        self.pl_trans_from = self.pl_flow_pos
        self.pl_flow_target = new
        self.pl_trans_start = time.time()

    def make_reflection(self, cover, size):
        key = (id(cover), size)
        if key in self._refl_cache:
            return self._refl_cache[key]
        h = 52
        refl = pygame.transform.flip(cover, False, True)
        refl = pygame.transform.smoothscale(refl, (size, h))
        # dim it, then fade it into the background from top to bottom
        dim = pygame.Surface((size, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        refl.blit(dim, (0, 0))
        fade = pygame.Surface((size, h), pygame.SRCALPHA)
        for y in range(h):
            a = int(255 * (y / h) ** 1.15)
            pygame.draw.line(fade, self.c_bg + (a,), (0, y), (size, y))
        refl.blit(fade, (0, 0))
        self._refl_cache[key] = refl
        return refl

    def shear_surface(self, surf, shear):
        """Slant a surface like a plane turned about a vertical axis.

        Each 1px column is shifted vertically by its distance from the
        middle, so the cover becomes a parallelogram - the look of a
        cover turned away from you, rather than just squeezed sideways.
        """
        w, h = surf.get_size()
        shift = int(abs(shear) * w)
        out = pygame.Surface((w, h + shift), pygame.SRCALPHA)
        for dx in range(w):
            yoff = int((dx - w / 2) * shear)
            out.blit(surf, (dx, yoff + shift // 2), (dx, 0, 1, h))
        return out

    def silhouette(self, surf, alpha=90):
        """A soft black shadow in the exact shape of a surface."""
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        s.blit(surf, (0, 0))
        s.fill((0, 0, 0, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        return s

    def draw_coverflow(self):
        albs = self.flow_albums()
        if not albs:
            return
        self._update_flow()
        # when the options bar is open the flow compacts to the top half
        compact = self.options_open
        base = 150 if compact else 200
        cy = 165 if compact else 215
        label_ys = (300, 322, 344) if compact else (384, 408, 432)
        centre = albs[self.flow_target]
        # ambient glow from the centre album's cover colour
        glow = self.album_glow(centre)
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        for r, a in ((250, 20), (200, 15), (150, 10)):
            pygame.draw.ellipse(ov, glow + (a,),
                                (320 - r, cy - r * 0.62, r * 2, int(r * 1.24)))
        self.screen.blit(ov, (0, 0))
        self.text("small_b", "COVER FLOW", self.c_dim, (16, 14))
        if self.flow_filter is not None:
            self.text("small", "·  " + self.fit("small", self.flow_filter, 200),
                      self.c_accent, (118, 14))
        self.text("small", "%d albums" % len(albs), self.c_dim, (W - 16, 14), "right")
        p = self.trans_p
        s = math.sin(p * math.pi) if p < 1 else 0.0   # mid-move emphasis
        style = self.trans_style
        direction = 1 if self.flow_target >= self.trans_from else -1
        vis = []
        for i, alb in enumerate(albs):
            off = i - self.flow_pos
            if abs(off) > 2.6:
                continue
            vis.append((abs(off), i, off))
        vis.sort(reverse=True)  # farthest first, centre last
        nearest = min(vis, key=lambda v: abs(v[2]))[1] if vis else -1
        for _a, i, off in vis:
            alb = albs[i]
            a = abs(off)
            # ---- layout for this transition style ----
            if style == "Carousel":
                ang = off * 0.55
                size = int(base * (0.45 + 0.55 * math.cos(ang)))
                cx = int(320 + 215 * math.sin(ang))
                cy0 = int(cy + 52 * math.cos(ang) - 52)
                squash, shear = 1.0, 0.0
            elif style == "Stack":
                size = int(base - 16 * min(a, 3))
                cx = int(320 + off * 26)
                cy0 = int(cy + off * 8)
                squash, shear = 1.0, 0.0
            else:
                size = int(base * (1 - 0.26 * min(a, 2.2)))
                cx = int(320 + off * 128)
                cy0 = cy
                squash, shear = 1.0, 0.0
                if a >= 0.4:
                    squash = max(0.62, 1 - 0.22 * min(a, 1.6))
                    shear = (0.16 + 0.06 * min(a, 2)) * (1 if off > 0 else -1)
            # ---- per-style effects (only while a move is in progress) ----
            if style == "Zoom" and i == nearest:
                size = int(size * (1 + 0.4 * s))
            if style == "Tilt" and a >= 0.4:
                shear += 0.30 * s * (1 if off > 0 else -1)
            cascade_dy = int(-120 * (1 - p) * (1 + 0.3 * a)) if style == "Cascade" and p < 1 else 0
            cover = cover_surface(alb["tracks"][0], 200)
            w = max(8, int(size * squash))
            h = size
            # plain styles cache the (scaled + darkened + sheared) cover
            surf = None
            if style in PLAIN_STYLES:
                fkey = (i, round(off, 1), style)
                surf = self._flow_cache.get(fkey)
            if surf is None:
                surf = pygame.transform.smoothscale(cover, (w, h))
                if a >= 0.4:
                    dark = pygame.Surface((w, h), pygame.SRCALPHA)
                    dark.fill((0, 0, 0, int(110 * min(a / 2, 1))))
                    surf.blit(dark, (0, 0))
                if shear:
                    surf = self.shear_surface(surf, shear)
                    w, h = surf.get_size()
                if style in PLAIN_STYLES:
                    if len(self._flow_cache) > 60:
                        self._flow_cache.clear()
                    self._flow_cache[fkey] = surf
            # effects that reshape the cover mid-move
            if style == "Flip" and p < 1:
                fw = max(6, int(w * max(0.06, abs(math.cos(p * math.pi)))))
                surf = pygame.transform.smoothscale(surf, (fw, h))
                w = fw
            if style == "Roll" and p < 1:
                hh = max(8, int(h * (1 - 0.45 * s)))
                surf = pygame.transform.smoothscale(surf, (w, hh))
                h = hh
            if style == "Spin" and i == self.flow_target and p < 1:
                surf = pygame.transform.rotozoom(surf, -45 * (1 - p) * direction, 1.0)
                w, h = surf.get_size()
            w, h = surf.get_size()  # the real size (shear/spin may have grown it)
            dx = cx - w // 2
            dy = cy0 - h // 2 + cascade_dy
            # soft shadow in the shape of the cover
            self.screen.blit(self.silhouette(surf), (dx + 4, dy + 6))
            self.screen.blit(surf, (dx, dy))
            if style == "Fade" and p < 1:
                ov2 = pygame.Surface((w, h), pygame.SRCALPHA)
                ov2.fill(self.c_bg + (int(160 * s),))
                self.screen.blit(ov2, (dx, dy))
            if i == self.flow_target and abs(self.flow_pos - self.flow_target) < 0.05:
                pygame.draw.rect(self.screen, self.c_accent, (dx - 1, dy - 1, w + 2, h + 2), 2)
                refl = self.make_reflection(cover, h)
                self.screen.blit(refl, (dx, dy + h + 4))
        # centre album labels
        title = self.fit("body_b", centre["title"], W - 60)
        self.text("body_b", title, self.c_text, (W // 2, label_ys[0]), "center")
        artist = self.fit("small", centre["artist"], W - 60)
        self.text("small", artist, self.c_sub, (W // 2, label_ys[1]), "center")
        cur = self.player.current()
        playing_here = cur is not None and cur in centre["tracks"]
        info = "Album %d of %d  ·  %d songs" % (
            self.flow_target + 1, len(albs), len(centre["tracks"]))
        if playing_here:
            info += "  ·  ▶ playing"
        self.text("tiny", info, self.c_accent if playing_here else self.c_dim,
                  (W // 2, label_ys[2]), "center")
        if not compact:
            self.text("tiny", "SELECT: options (transitions · themes · designs)", self.c_dim, (W // 2, 458), "center")

    def draw_pl_flow(self):
        """The Playlists view as a Cover Flow: each playlist folder is a
        card whose cover is the 2x2 tile of album art from its songs."""
        if not self.playlists:
            self.text("h1", "Playlists", self.c_text, (16, 12))
            self.text("body", "No playlists yet.", self.c_text, (16, 100))
            self.text("small", "Make a folder inside your music folder",
                      self.c_sub, (16, 130))
            self.text("small", "and put songs in it - the folder name",
                      self.c_sub, (16, 152))
            self.text("small", "becomes the playlist.", self.c_sub, (16, 174))
            return
        self._update_pl_flow()
        self.pl_flow_target = max(0, min(len(self.playlists) - 1, self.pl_flow_target))
        base, cy = 200, 215
        label_ys = (384, 408, 432)
        centre = self.playlists[self.pl_flow_target]
        # ambient glow from the centre playlist's tiled cover
        glow = self.playlist_glow(centre)
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        for r, a in ((250, 20), (200, 15), (150, 10)):
            pygame.draw.ellipse(ov, glow + (a,),
                                (320 - r, cy - r * 0.62, r * 2, int(r * 1.24)))
        self.screen.blit(ov, (0, 0))
        self.text("small_b", "PLAYLISTS", self.c_dim, (16, 14))
        self.text("small", "%d playlists" % len(self.playlists), self.c_dim,
                  (W - 16, 14), "right")
        vis = []
        for i, pl in enumerate(self.playlists):
            off = i - self.pl_flow_pos
            if abs(off) > 2.6:
                continue
            vis.append((abs(off), i, off))
        vis.sort(reverse=True)  # farthest first, centre last
        for _a, i, off in vis:
            pl = self.playlists[i]
            a = abs(off)
            size = int(base * (1 - 0.26 * min(a, 2.2)))
            cx = int(320 + off * 128)
            cy0 = cy
            squash, shear = 1.0, 0.0
            if a >= 0.4:
                squash = max(0.62, 1 - 0.22 * min(a, 1.6))
                shear = (0.16 + 0.06 * min(a, 2)) * (1 if off > 0 else -1)
            cover = self.playlist_cover(pl, 200)
            w = max(8, int(size * squash))
            h = size
            surf = pygame.transform.smoothscale(cover, (w, h))
            if a >= 0.4:
                dark = pygame.Surface((w, h), pygame.SRCALPHA)
                dark.fill((0, 0, 0, int(110 * min(a / 2, 1))))
                surf.blit(dark, (0, 0))
            if shear:
                surf = self.shear_surface(surf, shear)
                w, h = surf.get_size()
            dx = cx - w // 2
            dy = cy0 - h // 2
            self.screen.blit(self.silhouette(surf), (dx + 4, dy + 6))
            self.screen.blit(surf, (dx, dy))
            if i == self.pl_flow_target and abs(self.pl_flow_pos - self.pl_flow_target) < 0.05:
                pygame.draw.rect(self.screen, self.c_accent, (dx - 1, dy - 1, w + 2, h + 2), 2)
                refl = self.make_reflection(cover, h)
                self.screen.blit(refl, (dx, dy + h + 4))
        # centre playlist labels
        title = self.fit("body_b", centre["name"], W - 60)
        self.text("body_b", title, self.c_text, (W // 2, label_ys[0]), "center")
        n = len(centre["indices"])
        self.text("small", "%d song%s" % (n, "" if n == 1 else "s"),
                  self.c_sub, (W // 2, label_ys[1]), "center")
        info = "Playlist %d of %d" % (self.pl_flow_target + 1, len(self.playlists))
        self.text("tiny", info, self.c_dim, (W // 2, label_ys[2]), "center")
        self.text("tiny", "A: open  ·  B: back", self.c_dim, (W // 2, 458), "center")

    def draw_options_bar(self):
        """The options bar: transition picker, theme picker, custom editor."""
        if self.opt_page == "custom":
            self.draw_custom_editor()
            return
        panel_h = 120
        y0 = H - panel_h
        pygame.draw.rect(self.screen, self.c_panel, (0, y0, W, panel_h))
        pygame.draw.line(self.screen, self.c_accent, (0, y0), (W, y0), 2)
        if self.opt_page == "theme":
            title = "THEME"
            lst = self.theme_list()
            names = [n for n, _ in lst]
            sel = self.theme_sel
            descs = [("Light theme" if t["light"] else "Dark theme") + "  -  " + n
                     for n, t in lst]
        elif self.opt_page == "layout":
            title = "NOW PLAYING DESIGN"
            names = [n for n, _ in NP_LAYOUTS]
            sel = self.np_sel
            descs = [t[1] for t in NP_LAYOUTS]
        elif self.opt_page == "size":
            title = "LIBRARY SIZE"
            names = [t[0] for t in LIB_SIZES]
            sel = self.lib_size_sel
            descs = ["Small text and covers - the most songs on screen",
                     "The standard size",
                     "Bigger text and covers - easier to read",
                     "The biggest text and covers"]
        elif self.opt_page == "cd":
            title = "DISC STYLE"
            names = DISC_STYLE_NAMES
            sel = self.cd_sel
            descs = ["The cover is a square, as usual",
                     "The cover is a circle that spins like a CD",
                     "The square cover stays, and a spinning CD with the same art slides out behind it",
                     "The art on a cassette, and the reels turn while it plays"]
        elif self.opt_page == "visualiser":
            title = "VISUALISER"
            names = [t[0] for t in VISUALISERS]
            sel = self.viz_sel
            descs = [t[1] for t in VISUALISERS]
        elif self.opt_page == "controls":
            title = "CONTROLS"
            names = ["Remap controls"]
            sel = 0
            descs = ["Map the buttons and D-pad to each action"]
        else:
            title = "COVER FLOW TRANSITION"
            names = [t[0] for t in TRANSITIONS]
            sel = self.opt_sel
            descs = [t[1] for t in TRANSITIONS]
        self.text("small_b", title, self.c_text, (16, y0 + 10))
        self.text("tiny", "SELECT / O: close", self.c_dim, (W - 16, y0 + 10), "right")
        count = min(5, len(names))
        start = max(0, min(sel - 2, len(names) - count))
        pill_w, gap = 108, 8
        row_y = y0 + 38
        x = (W - (count * pill_w + (count - 1) * gap)) // 2
        for k in range(count):
            idx = start + k
            px = x + k * (pill_w + gap)
            label = self.fit("small", names[idx], pill_w - 12)
            if idx == sel:
                # the selected pill wears that item's own accent color
                if self.opt_page == "theme":
                    fill = self.theme_list()[idx][1]["accent"]
                else:
                    fill = self.c_accent
                fg = (0, 0, 0) if _luminance(fill) > 0.55 else (255, 255, 255)
                pygame.draw.rect(self.screen, fill, (px, row_y, pill_w, 34), border_radius=8)
                self.text("small_b", label, fg, (px + pill_w // 2, row_y + 9), "center")
            else:
                pygame.draw.rect(self.screen, self.c_row, (px, row_y, pill_w, 34), border_radius=8)
                self.text("small", label, self.c_text, (px + pill_w // 2, row_y + 9), "center")
        if start > 0:
            self.text("body_b", "\u25c0", self.c_sub, (x - 24, row_y + 4))
        if start + count < len(names):
            self.text("body_b", "\u25b6", self.c_sub, (x + count * pill_w + (count - 1) * gap + 8, row_y + 4))
        self.text("small", descs[sel], self.c_sub, (W // 2, y0 + 86), "center")
        if self.opt_page == "theme":
            # swatches of the picked theme: background, panel, accent
            t = self.theme_list()[sel][1]
            sx = W // 2 + 150
            for col in (t["bg"], t["panel"], t["accent"]):
                pygame.draw.rect(self.screen, col, (sx, y0 + 84, 18, 18), border_radius=4)
                pygame.draw.rect(self.screen, self.c_dim, (sx, y0 + 84, 18, 18), 1, border_radius=4)
                sx += 24
            hint = "Up/Down: pick  -  A: keep (Custom: edit)  -  B: cancel  -  X/Y: designs"
        elif self.opt_page == "layout":
            hint = "Up/Down: pick  -  A: keep  -  B: cancel  -  X/Y: size"
        elif self.opt_page == "size":
            hint = "Up/Down: pick  -  A: keep  -  B: cancel  -  X/Y: CD mode"
        elif self.opt_page == "cd":
            hint = "Up/Down: pick  -  A: keep  -  B: cancel  -  X/Y: controls"
        elif self.opt_page == "controls":
            hint = "A: open the Controls screen  -  B: cancel  -  X/Y: transitions"
        else:
            hint = "Up/Down: pick  -  Left/Right: preview the flip  -  A: keep  -  B: cancel  -  X/Y: themes"
        self.text("tiny", hint, self.c_dim, (W // 2, y0 + 103), "center")

    def draw_custom_editor(self):
        """Make-your-own theme: pick Background, Accent and Text colors."""
        panel_h = 220
        y0 = H - panel_h
        pygame.draw.rect(self.screen, self.c_panel, (0, y0, W, panel_h))
        pygame.draw.line(self.screen, self.c_accent, (0, y0), (W, y0), 2)
        self.text("small_b", "CUSTOM THEME", self.c_text, (16, y0 + 10))
        self.text("tiny", "B: cancel", self.c_dim, (W - 16, y0 + 10), "right")
        keys = ("bg", "accent", "text")
        for i, key in enumerate(keys):
            ry = y0 + 40 + i * 30
            sel = (i == self.custom_slot)
            if sel:
                pygame.draw.rect(self.screen, self.c_row, (12, ry - 4, 200, 26), border_radius=6)
            self.text("small_b" if sel else "small", CUSTOM_SLOTS[i],
                      self.c_text if sel else self.c_sub, (20, ry))
            col = self.custom_theme[key]
            pygame.draw.rect(self.screen, col, (216, ry - 2, 26, 22), border_radius=4)
            pygame.draw.rect(self.screen, self.c_dim, (216, ry - 2, 26, 22), 1, border_radius=4)
            pname = PALETTE[self.custom_idx[i]][0]
            self.text("small", pname, self.c_sub, (250, ry))
        # palette grid: 24 swatches in 2 rows of 12
        gx, gy = 20, y0 + 140
        sw, gap = 30, 6
        for k, (pname, col) in enumerate(PALETTE):
            px = gx + (k % 12) * (sw + gap)
            py = gy + (k // 12) * (sw + gap)
            pygame.draw.rect(self.screen, col, (px, py, sw, sw), border_radius=5)
            pygame.draw.rect(self.screen, self.c_dim, (px, py, sw, sw), 1, border_radius=5)
            if k == self.custom_idx[self.custom_slot]:
                pygame.draw.rect(self.screen, self.c_text, (px - 2, py - 2, sw + 4, sw + 4), 2, border_radius=7)
        self.text("tiny", "Up/Down: colour  -  Left/Right: pick a colour  -  A: save  -  B: cancel",
                  self.c_dim, (W // 2, y0 + 204), "center")


    def draw_album(self):
        alb = self.album
        if alb is None:
            return
        cover = cover_surface(alb["tracks"][0], 84)
        self.screen.blit(cover, (16, 16))
        title = self.fit("h1", alb["title"], W - 140)
        self.text("h1", title, self.c_text, (112, 20))
        artist = self.fit("body", alb["artist"], W - 140)
        self.text("body", artist, self.c_sub, (112, 48))
        total = sum(t.duration for t in alb["tracks"])
        self.text("small", "%d songs · %s" % (len(alb["tracks"]), fmt_time(total)),
                  self.c_dim, (112, 74))
        self.text("tiny", "B: back to Cover Flow", self.c_dim, (W - 16, 20), "right")
        pygame.draw.line(self.screen, self.c_row, (16, 116), (W - 16, 116))
        x0 = 16
        list_w = W - 32
        y0 = 128
        vis = (H - BAR_H - y0) // ROW_H
        for i in range(vis):
            idx = self.album_scroll + i
            if idx >= len(alb["tracks"]):
                break
            t = alb["tracks"][idx]
            gi = alb["indices"][idx]
            y = y0 + i * ROW_H
            if idx == self.album_sel:
                pygame.draw.rect(self.screen, self.c_row_sel,
                                 (x0, y + 2, list_w, ROW_H - 4), border_radius=6)
                pygame.draw.rect(self.screen, self.c_accent,
                                 (x0, y + 6, 3, ROW_H - 12), border_radius=2)
            self.text("small", "%d" % (idx + 1), self.c_dim, (x0 + 14, y + 16))
            playing = (self.player.index == gi and self.player.playing)
            title_col = self.c_accent if self.player.index == gi else self.c_text
            name = self.fit("body_b", t.title, list_w - 130)
            self.text("body_b", name, title_col, (x0 + 48, y + 6))
            self.text("small", t.artist, self.c_sub, (x0 + 48, y + 27))
            dur = fmt_time(t.duration) if t.duration else "--:--"
            self.text("small", dur, self.c_sub, (W - 16, y + 16), "right")

    def draw_search(self):
        """Search: an on-screen keyboard, results that filter as you type."""
        self.text("h1", "Search", self.c_text, (16, 12))
        self.text("tiny", "A: type / play  ·  B: back", self.c_dim, (W - 16, 20), "right")
        # the query box
        q = self.search_query
        pygame.draw.rect(self.screen, self.c_panel, (16, 46, W - 32, 34), border_radius=8)
        pygame.draw.rect(self.screen, self.c_accent if self.search_focus == "keys" else self.c_row,
                         (16, 46, W - 32, 34), 2, border_radius=8)
        self.text("body", q if q else "Type to search songs, artists, albums...",
                  self.c_text if q else self.c_dim, (28, 54))
        # the keyboard
        key_w, key_h, gap = 54, 40, 6
        y = 96
        for ri, row in enumerate(SEARCH_KEYS):
            row_w = len(row) * key_w + (len(row) - 1) * gap
            x0 = (W - row_w) // 2
            for ci, key in enumerate(row):
                kx = x0 + ci * (key_w + gap)
                focused = (self.search_focus == "keys"
                           and self.search_row == ri and self.search_col == ci)
                if focused:
                    pygame.draw.rect(self.screen, self.c_accent,
                                     (kx, y, key_w, key_h), border_radius=8)
                    self.text("body_b", key, self.c_bg,
                              (kx + key_w // 2, y + 11), "center")
                else:
                    pygame.draw.rect(self.screen, self.c_panel,
                                     (kx, y, key_w, key_h), border_radius=8)
                    self.text("body", key, self.c_text,
                              (kx + key_w // 2, y + 11), "center")
            y += key_h + gap
        # the results
        ry = y + 8
        self.text("tiny", "RESULTS", self.c_dim, (16, ry))
        ry += 20
        if not q:
            self.text("small", "Start typing and matches will show here.",
                      self.c_dim, (16, ry + 8))
        elif not self.search_results:
            self.text("small", "No matches for \"%s\"." % q, self.c_dim, (16, ry + 8))
        else:
            for i, t in enumerate(self.search_results[:4]):
                yy = ry + i * 40
                sel = (self.search_focus == "results" and self.search_sel == i)
                if sel:
                    pygame.draw.rect(self.screen, self.c_row_sel,
                                     (16, yy, W - 32, 36), border_radius=6)
                    pygame.draw.rect(self.screen, self.c_accent,
                                     (16, yy + 4, 3, 28), border_radius=2)
                title = self.fit("body_b", t.title, W - 120)
                self.text("body_b", title, self.c_text, (28, yy + 2))
                artist = self.fit("small", "%s  ·  %s" % (t.artist, t.album), W - 120)
                self.text("small", artist, self.c_sub, (28, yy + 20))
            if len(self.search_results) > 4:
                self.text("small", "+ %d more" % (len(self.search_results) - 4),
                          self.c_dim, (16, ry + 4 * 40))

    # -- Music Quiz -------------------------------------------------
    def quiz_distinct(self, field):
        """Distinct values for a metadata field across the library."""
        return {getattr(t, field) for t in self.tracks if getattr(t, field)}

    def quiz_playable_types(self):
        """Question types that have enough distinct answers (as many
        as this level's choice count)."""
        n = QUIZ_LEVELS[self.quiz_level][7]
        ok = []
        for field, _q in QUIZ_QUESTIONS:
            if field == "cover":
                # the cover round asks for the album, so it needs enough albums
                if len(self.quiz_distinct("album")) >= n:
                    ok.append(field)
            elif len(self.quiz_distinct(field)) >= n:
                ok.append(field)
        return ok

    def quiz_build_choices(self, field, correct):
        """This level's number of choices: the right answer plus the
        rest wrong. On levels with close answers, the wrong ones are
        other titles / albums by the same artist, so you cannot guess
        from the artist alone."""
        n = QUIZ_LEVELS[self.quiz_level][7]
        pool = self.quiz_distinct(field) - {correct}
        close = QUIZ_LEVELS[self.quiz_level][6]
        if close and field in ("title", "album") and self.quiz_song >= 0:
            artist = self.tracks[self.quiz_song].artist
            close_pool = {getattr(t, field) for t in self.tracks
                          if t.artist == artist and getattr(t, field) != correct}
            if len(close_pool) >= n - 1:
                pool = close_pool
        wrong = random.sample(sorted(pool), min(n - 1, len(pool)))
        choices = wrong + [correct]
        random.shuffle(choices)
        return choices, choices.index(correct)

    def quiz_start_round(self):
        """Start a new round: a random song, a random question type, a
        snippet (or the cover), and 4 choices. Returns False when the
        library is too small to play."""
        types = self.quiz_playable_types()
        if not self.tracks or not types:
            self.quiz_song = -1
            self.quiz_choices = []
            return False
        self.quiz_song = random.randrange(len(self.tracks))
        self.quiz_field = random.choice(types)
        song = self.tracks[self.quiz_song]
        field = "album" if self.quiz_field == "cover" else self.quiz_field
        correct = getattr(song, field)
        self.quiz_choices, self.quiz_correct = self.quiz_build_choices(field, correct)
        self.quiz_sel = 0
        self.quiz_answered = False
        self.quiz_picked = -1
        self.quiz_timeout = False
        self.quiz_new_achievement = ""
        self.quiz_round_score = 0
        self.quiz_grade = ""
        self.quiz_earned = 0
        self.quiz_round_start = time.time()
        # the clue: in a visual level (Folded / Master, snippet 0) the
        # album art is folded and that is the clue for every question
        # type, and the fold tightens by 1 every round so the piece
        # you see gets smaller. A cover round is visual too, but the
        # cover is shown whole. Otherwise a snippet plays from a random
        # spot (Easy starts near the beginning, Hard starts anywhere)
        # and stops by itself after the level's snippet length.
        self.quiz_snippet_until = None
        self.quiz_fold = 0
        _lname, snip_len, _ans, _mult, fold0, fold_max, _close, _nch = QUIZ_LEVELS[self.quiz_level]
        if snip_len == 0:
            # visual level: fold the art, one cell stays visible
            rnd = self.quiz_total + 1  # the round you are about to play
            self.quiz_fold = min(fold0 + rnd - 1, fold_max)
            n = self.quiz_fold + 1
            self.quiz_fold_cell = (random.randrange(n), random.randrange(n))
            if self.player.playing:
                self.player.play_pause()
        elif self.quiz_field == "cover":
            if self.player.playing:
                self.player.play_pause()
        else:
            self.player.play_index(self.quiz_song)
            dur = self.player.duration() or 0
            if dur > snip_len + 2:
                if self.quiz_level == 0:
                    start = random.uniform(0, 5)
                else:
                    start = random.uniform(5, dur - snip_len - 2)
            else:
                start = 0
            self.quiz_snippet_start = start
            self.player.seek(start)
            self.quiz_snippet_until = time.time() + snip_len
        return True

    def quiz_grade_for(self, score):
        for need, word in QUIZ_GRADES:
            if score >= need:
                return word
        return "MISS"

    def quiz_answer(self):
        """Answer the highlighted choice. Scores it karaoke-style: a
        correct answer is worth up to 100 by speed, times the level
        multiplier, plus a streak bonus; a wrong answer scores 0."""
        if self.quiz_answered or not self.quiz_choices or self.quiz_song < 0:
            return
        self.quiz_answered = True
        self.quiz_picked = self.quiz_sel
        self.quiz_total += 1
        # stop the snippet so the song does not give the answer away
        if self.player.playing:
            self.player.play_pause()
        self.quiz_snippet_until = None
        elapsed = time.time() - self.quiz_round_start
        if self.quiz_sel == self.quiz_correct:
            self.quiz_score += 1
            self.quiz_streak += 1
            self.quiz_best = max(self.quiz_best, self.quiz_streak)
            over = max(0.0, elapsed - 3.0)
            self.quiz_round_score = max(QUIZ_SCORE_MIN,
                                        100 - int(over * QUIZ_SCORE_PER_SEC))
            self.quiz_grade = self.quiz_grade_for(self.quiz_round_score)
            _lname, _snip, _ans, mult, _f0, _fmax, _close, _nch = QUIZ_LEVELS[self.quiz_level]
            self.quiz_earned = self.quiz_round_score * mult
            if self.quiz_streak >= 3:
                self.quiz_earned += (self.quiz_streak - 2) * 10
            self.quiz_points += self.quiz_earned
            if self.quiz_points > self.quiz_best_points:
                self.quiz_best_points = self.quiz_points
        else:
            self.quiz_streak = 0
            self.quiz_round_score = 0
            self.quiz_grade = "MISS"
            self.quiz_earned = 0
        self.quiz_check_achievements()
        self.save_settings()

    def quiz_timeout_round(self):
        """The player ran out of time to answer: the round is a miss."""
        if self.quiz_answered or self.quiz_song < 0:
            return
        self.quiz_answered = True
        self.quiz_picked = -1
        self.quiz_timeout = True
        self.quiz_total += 1
        self.quiz_streak = 0
        self.quiz_round_score = 0
        self.quiz_grade = "MISS"
        self.quiz_earned = 0
        if self.player.playing:
            self.player.play_pause()
        self.quiz_snippet_until = None
        self.save_settings()

    def quiz_replay(self):
        """Hear the snippet again (X / Y in the quiz). Only before
        answering - after that the answer is on screen. The answer
        clock keeps running, so replaying costs you speed points.
        Visual levels have no snippet, so there is nothing to replay."""
        if self.quiz_answered or self.quiz_song < 0 or self.quiz_field == "cover":
            return
        _lname, snip_len, _ans, _mult, _f0, _fmax, _close, _nch = QUIZ_LEVELS[self.quiz_level]
        if snip_len == 0:
            return
        self.player.play_index(self.quiz_song)
        self.player.seek(self.quiz_snippet_start)
        self.quiz_snippet_until = time.time() + snip_len

    def quiz_stop(self):
        """Leave the quiz: stop the snippet and clear the round."""
        if self.player.playing:
            self.player.play_pause()
        self.quiz_snippet_until = None
        self.quiz_song = -1
        self.quiz_choices = []

    def quiz_exit_to_music(self):
        """Triple-click Select in the quiz: leave the game and go back
        to playing music - the current song starts from the top in
        Now Playing."""
        self.quiz_stop()
        self.quiz_select_presses = []
        self.go_view("nowplaying")
        if self.player.index >= 0:
            self.player.play_index(self.player.index)
        elif self.tracks:
            self.player.play_index(0)

    def quiz_cycle_level(self, d):
        """Change the difficulty level (Left/Right in the quiz). It
        applies to the next round, not the one already playing."""
        self.quiz_level = (self.quiz_level + d) % len(QUIZ_LEVELS)
        # the level shows in the info line at the top, so no toast is
        # needed (a toast would sit on the choices)
        self.save_settings()

    def quiz_unlock(self, aid):
        """Unlock an achievement (once). In the quiz it is shown in the
        result line, not as a floating toast - the toast would sit on
        top of the score."""
        if aid in self.quiz_achievements:
            return
        self.quiz_achievements.append(aid)
        name = dict((a[0], a[1]) for a in QUIZ_ACHIEVEMENTS).get(aid, aid)
        self.quiz_new_achievement = name
        self.save_settings()

    def quiz_check_achievements(self):
        if self.quiz_score >= 1:
            self.quiz_unlock("first")
        if self.quiz_streak >= 3:
            self.quiz_unlock("streak3")
        if self.quiz_streak >= 5:
            self.quiz_unlock("streak5")
        if self.quiz_streak >= 10:
            self.quiz_unlock("streak10")
        if self.quiz_round_score >= 100:
            self.quiz_unlock("perfect")
        if self.quiz_field == "cover" and self.quiz_picked == self.quiz_correct:
            self.quiz_unlock("cover")
        if self.quiz_points >= 500:
            self.quiz_unlock("score500")
        if self.quiz_score >= 25:
            self.quiz_unlock("correct25")
        _lname, snip_len, _ans, _mult, _f0, _fmax, _close, _nch = QUIZ_LEVELS[self.quiz_level]
        if (self.quiz_picked == self.quiz_correct
                and not self.quiz_timeout and snip_len == 0):
            self.quiz_unlock("fold")
            if _lname == "Master":
                self.quiz_unlock("master")

    def _quiz_bar(self, x, y, w, h, frac):
        """A thin progress bar (snippet left, or time left to answer).
        Green while there is plenty left, red when it is almost gone."""
        pygame.draw.rect(self.screen, self.c_row, (x, y, w, h), border_radius=3)
        if frac > 0:
            col = self.c_accent if frac > 0.25 else (220, 60, 60)
            pygame.draw.rect(self.screen, col,
                             (x, y, max(2, int(w * frac)), h), border_radius=3)

    def _draw_folded_cover(self, song, x, y, size, fold, cell):
        """The album art, folded: only one cell of a grid is visible,
        the rest is covered like folded paper. The grid is (fold+1) x
        (fold+1), so a bigger fold means a smaller visible piece."""
        n = min(fold + 1, 6)
        cell_w = size // n
        # the folded paper
        pygame.draw.rect(self.screen, (200, 198, 192),
                         (x, y, size, size), border_radius=8)
        # the one visible cell of the real art
        art = cover_surface(song, size)
        cx, cy = cell
        cx = min(cx, n - 1)
        cy = min(cy, n - 1)
        px, py = cx * cell_w, cy * cell_w
        cw = size - px if cx == n - 1 else cell_w
        ch = size - py if cy == n - 1 else cell_w
        piece = art.subsurface((px, py, cw, ch))
        self.screen.blit(piece, (x + px, y + py))
        # the fold creases
        for i in range(1, n):
            pos = i * cell_w
            pygame.draw.line(self.screen, (150, 148, 140),
                             (x + pos, y), (x + pos, y + size), 2)
            pygame.draw.line(self.screen, (150, 148, 140),
                             (x, y + pos), (x + size, y + pos), 2)

    def draw_quiz(self):
        """Music Quiz: a snippet (or a cover) and a grid of choices.
        The song's identity is never shown here, or the game gives
        itself away. How to quit is at the top, how to play is under
        it, so nobody has to guess either one."""
        self.text("h1", "MUSIC QUIZ", self.c_text, (16, 12))
        self.text("body_b", "POINTS %d" % self.quiz_points, self.c_accent,
                  (W - 16, 16), "right")
        self.text("small", "Triple-click SELECT to quit and play music",
                  self.c_accent, (W // 2, 36), "center")
        self.text("small",
                  "Hear the snippet or see the cover, guess the title, "
                  "artist or album. Faster = more points!",
                  self.c_sub, (W // 2, 52), "center")
        lvl_name = QUIZ_LEVELS[self.quiz_level][0]
        info = ("Level: %s   •   %d/%d correct   •   Streak %d   •   "
                "Best %d pts   •   ★ %d/%d" % (
                    lvl_name, self.quiz_score, self.quiz_total,
                    self.quiz_streak, self.quiz_best_points,
                    len(self.quiz_achievements), len(QUIZ_ACHIEVEMENTS)))
        self.text("small", info, self.c_sub, (16, 68))
        pygame.draw.line(self.screen, self.c_row, (16, 84), (W - 16, 84))
        if self.quiz_song < 0 or not self.quiz_choices:
            self.text("body", "Add more music to play the quiz.",
                      self.c_text, (W // 2, 200), "center")
            self.text("small",
                      "It needs enough different titles, artists and albums.",
                      self.c_sub, (W // 2, 230), "center")
            self.text("small", "B: back to the library",
                      self.c_dim, (W // 2, 270), "center")
            return
        q = dict(QUIZ_QUESTIONS)[self.quiz_field]
        self.text("big", q, self.c_text, (W // 2, 96), "center")
        _lname, snip_len, ans_len, _mult, _f0, _fmax, _close, _nch = QUIZ_LEVELS[self.quiz_level]
        replay = control_label(self.controls.get("next"), self._is_retrogame)
        visual = (self.quiz_field == "cover" or snip_len == 0)
        if visual:
            # the cover (folded on the Folded / Master levels, whole
            # on a cover round) above the choices
            song = self.tracks[self.quiz_song]
            cs = 80
            cx, cy = (W - cs) // 2, 124
            if snip_len == 0:
                self._draw_folded_cover(song, cx, cy, cs,
                                        self.quiz_fold, self.quiz_fold_cell)
            else:
                pygame.draw.rect(self.screen, (0, 0, 0),
                                 (cx + 5, cy + 5, cs, cs), border_radius=10)
                self.screen.blit(cover_surface(song, cs), (cx, cy))
            frac = 1.0
            if not self.quiz_answered:
                left = (self.quiz_round_start + ans_len) - time.time()
                frac = max(0.0, min(1.0, left / ans_len))
            self._quiz_bar((W - 160) // 2, cy + cs + 10, 160, 5, frac)
            row_y, row_h, gap = cy + cs + 24, 32, 4
            res_y = row_y + ((len(self.quiz_choices) + 1) // 2) * (row_h + gap) + 6
        else:
            # snippet status + progress, then the answer timer
            if self.player.playing and self.quiz_snippet_until is not None:
                self.text("body", "♪  Playing the snippet...",
                          self.c_accent, (W // 2, 128), "center")
                left = self.quiz_snippet_until - time.time()
                frac = max(0.0, min(1.0, left / snip_len))
                self._quiz_bar((W - 360) // 2, 150, 360, 8, frac)
            else:
                self.text("body", "♪  Snippet done - %s to hear it again" % replay,
                          self.c_sub, (W // 2, 128), "center")
                self._quiz_bar((W - 360) // 2, 150, 360, 8, 0.0)
            frac = 1.0
            if not self.quiz_answered:
                left = (self.quiz_round_start + ans_len) - time.time()
                frac = max(0.0, min(1.0, left / ans_len))
            self._quiz_bar((W - 360) // 2, 164, 360, 5, frac)
            row_y, row_h, gap = 182, 40, 6
            res_y = row_y + ((len(self.quiz_choices) + 1) // 2) * (row_h + gap) + 8
        # the choices, in two columns, in reading order (A, B, C, ...)
        col_w = 270
        col_x = [40, 40 + col_w + 20]
        for i, ch in enumerate(self.quiz_choices):
            row, col = divmod(i, 2)
            x = col_x[col]
            y = row_y + row * (row_h + gap)
            if self.quiz_answered:
                if i == self.quiz_correct:
                    colr = self.c_accent
                    tcol = self.c_bg
                elif i == self.quiz_picked:
                    colr = (220, 60, 60)
                    tcol = (255, 255, 255)
                else:
                    colr = self.c_panel
                    tcol = self.c_dim
            elif i == self.quiz_sel:
                colr = self.c_accent
                tcol = self.c_bg
            else:
                colr = self.c_panel
                tcol = self.c_text
            pygame.draw.rect(self.screen, colr,
                             (x, y, col_w, row_h), border_radius=8)
            self.text("body_b", "ABCDEFGH"[i], tcol, (x + 12, y + (row_h - 15) // 2))
            label = self.fit("body_b", ch, col_w - 40)
            self.text("body_b", label, tcol, (x + 34, y + (row_h - 15) // 2))
        # result, once answered: karaoke-style score + grade
        if self.quiz_answered:
            if self.quiz_picked == self.quiz_correct and not self.quiz_timeout:
                self.text("huge", "%d" % self.quiz_round_score, self.c_accent,
                          (W // 2, res_y), "center")
                line = "%s   •   +%d points   •   A: next song" % (
                    self.quiz_grade, self.quiz_earned)
                if self.quiz_new_achievement:
                    line += "   •   ★ %s!" % self.quiz_new_achievement
                self.text("small", self.fit("small", line, W - 32),
                          self.c_text, (W // 2, res_y + 52), "center")
            else:
                if self.quiz_timeout:
                    msg = "Out of time!"
                else:
                    msg = "Wrong!"
                self.text("body_b", msg, (220, 60, 60),
                          (W // 2, res_y + 6), "center")
                correct = self.quiz_choices[self.quiz_correct]
                self.text("small", "It was: %s" % self.fit("small", correct, W - 80),
                          self.c_sub, (W // 2, res_y + 30), "center")
                self.text("small", "A: next song", self.c_dim,
                          (W // 2, res_y + 52), "center")
        # footer hint
        hint = ("Up/Down: pick   •   A: answer   •   %s: hear it again   •   "
                "Left/Right: level   •   B: library" % replay)
        self.text("tiny", hint, self.c_dim, (W // 2, H - 14), "center")

    def draw_artists(self):
        """Artists list - tap one to open Cover Flow with their albums."""
        self.text("h1", "Artists", self.c_text, (16, 12))
        self.text("small", "%d artists" % len(self.artists), self.c_sub,
                  (W - 16, 20), "right")
        self.text("tiny", "A: open their albums  ·  B: back", self.c_dim, (W - 16, 44), "right")
        pygame.draw.line(self.screen, self.c_row, (16, 68), (W - 16, 68))
        x0 = 16
        list_w = W - 32
        y0 = 80
        vis = (H - BAR_H - y0) // ROW_H
        for i in range(vis):
            idx = self.artist_scroll + i
            if idx >= len(self.artists):
                break
            art = self.artists[idx]
            n_alb = len({(t.album or "").lower() for t in art["tracks"]})
            y = y0 + i * ROW_H
            if idx == self.artist_sel:
                pygame.draw.rect(self.screen, self.c_row_sel,
                                 (x0, y + 2, list_w, ROW_H - 4), border_radius=6)
                pygame.draw.rect(self.screen, self.c_accent,
                                 (x0, y + 6, 3, ROW_H - 12), border_radius=2)
            cover = cover_surface(art["tracks"][0], 40)
            self.screen.blit(cover, (x0 + 10, y + 5))
            name = self.fit("body_b", art["name"], list_w - 130)
            self.text("body_b", name, self.c_text, (x0 + 60, y + 6))
            sub = "%d album%s · %d song%s" % (
                n_alb, "" if n_alb == 1 else "s",
                len(art["tracks"]), "" if len(art["tracks"]) == 1 else "s")
            self.text("small", sub, self.c_sub, (x0 + 60, y + 27))

    def draw_liked(self):
        """Liked songs - the songs you hearted on the Now Playing screen."""
        liked = self.liked_tracks()
        self.text("h1", "Liked Songs", self.c_text, (16, 12))
        self.text("small", "%d song%s" % (len(liked), "" if len(liked) == 1 else "s"),
                  self.c_sub, (W - 16, 20), "right")
        self.text("tiny", "A: play  ·  B: back", self.c_dim, (W - 16, 44), "right")
        pygame.draw.line(self.screen, self.c_row, (16, 68), (W - 16, 68))
        if not liked:
            self.text("body", "No liked songs yet.", self.c_sub, (16, 120))
            self.text("body", "On the Now Playing screen, press L2 to like",
                      self.c_sub, (16, 148))
            self.text("body", "the song that is playing.", self.c_sub, (16, 172))
            return
        x0 = 16
        list_w = W - 32
        y0 = 80
        vis = (H - BAR_H - y0) // ROW_H
        for i in range(vis):
            idx = self.liked_scroll + i
            if idx >= len(liked):
                break
            t = liked[idx]
            y = y0 + i * ROW_H
            if idx == self.liked_sel:
                pygame.draw.rect(self.screen, self.c_row_sel,
                                 (x0, y + 2, list_w, ROW_H - 4), border_radius=6)
                pygame.draw.rect(self.screen, self.c_accent,
                                 (x0, y + 6, 3, ROW_H - 12), border_radius=2)
            cover = cover_surface(t, 40)
            self.screen.blit(cover, (x0 + 10, y + 5))
            title = self.fit("body_b", t.title, list_w - 130)
            self.text("body_b", title, self.c_text, (x0 + 60, y + 6))
            artist = self.fit("small", "%s  ·  %s" % (t.artist, t.album), list_w - 130)
            self.text("small", artist, self.c_sub, (x0 + 60, y + 27))
            dur = fmt_time(t.duration) if t.duration else "--:--"
            self.text("small", dur, self.c_sub, (W - 16, y + 16), "right")

    def draw_playlist(self):
        """One playlist's songs, sorted by metadata (artist, title)."""
        pl = self.playlist
        if pl is None:
            return
        self.text("h1", self.fit("h1", pl["name"], W - 140), self.c_text, (16, 12))
        total = sum(self.tracks[gi].duration for gi in pl["indices"])
        self.text("small", "%d songs · %s" % (len(pl["indices"]), fmt_time(total)),
                  self.c_dim, (16, 44))
        self.text("tiny", "B: back to Playlists", self.c_dim, (W - 16, 20), "right")
        pygame.draw.line(self.screen, self.c_row, (16, 68), (W - 16, 68))
        x0 = 16
        list_w = W - 32
        y0 = 80
        vis = (H - BAR_H - y0) // ROW_H
        for i in range(vis):
            idx = self.pl_track_scroll + i
            if idx >= len(pl["indices"]):
                break
            gi = pl["indices"][idx]
            t = self.tracks[gi]
            y = y0 + i * ROW_H
            if idx == self.pl_track_sel:
                pygame.draw.rect(self.screen, self.c_row_sel,
                                 (x0, y + 2, list_w, ROW_H - 4), border_radius=6)
                pygame.draw.rect(self.screen, self.c_accent,
                                 (x0, y + 6, 3, ROW_H - 12), border_radius=2)
            cover = cover_surface(t, 40)
            self.screen.blit(cover, (x0 + 10, y + 5))
            playing = (self.player.index == gi and self.player.playing)
            title_col = self.c_accent if self.player.index == gi else self.c_text
            name = self.fit("body_b", t.title, list_w - 130)
            self.text("body_b", name, title_col, (x0 + 60, y + 6))
            self.text("small", t.artist, self.c_sub, (x0 + 60, y + 27))
            dur = fmt_time(t.duration) if t.duration else "--:--"
            self.text("small", dur, self.c_sub, (W - 16, y + 16), "right")
            if playing:
                self.draw_eq(x0 + 60 + self.fonts["body_b"].size(name)[0] + 10, y + 12)

    def now_playing_bg(self, track):
        """The current cover, blurred to fill the screen and dimmed so the
        text stays readable - the glassy backdrop for Now Playing."""
        key = track.path
        if key in self._np_bg_cache:
            return self._np_bg_cache[key]
        cover = cover_surface(track, 480)
        small = pygame.transform.smoothscale(cover, (32, 24))
        blurred = pygame.transform.smoothscale(small, (W, H))
        small2 = pygame.transform.smoothscale(blurred, (16, 12))
        blurred = pygame.transform.smoothscale(small2, (W, H))
        tint = pygame.Surface((W, H), pygame.SRCALPHA)
        if self.theme_light:
            tint.fill((255, 255, 255, 150))
        else:
            tint.fill((0, 0, 0, 140))
        blurred.blit(tint, (0, 0))
        if len(self._np_bg_cache) > 8:
            self._np_bg_cache.clear()
        self._np_bg_cache[key] = blurred
        return blurred

    def draw_progress(self, x, y, w):
        """Progress bar with times, at (x, y) and w wide."""
        pos = self.player.position()
        dur = self.player.duration()
        frac = clamp(pos / dur, 0, 1) if dur > 0 else 0
        pygame.draw.rect(self.screen, self.c_track_bg, (x, y, w, 5), border_radius=2)
        if frac > 0:
            pygame.draw.rect(self.screen, self.c_text, (x, y, int(w * frac), 5), border_radius=2)
            pygame.draw.circle(self.screen, self.c_text, (x + int(w * frac), y + 2), 6)
        self.text("tiny", fmt_time(pos), self.c_sub, (x, y + 12))
        self.text("tiny", fmt_time(dur), self.c_sub, (x + w, y + 12), "right")

    def draw_transport_row(self, cx, cy, r_play=54, r_side=34, gap=80):
        """Prev / play / next, centred on cx."""
        self._np_trans = (cx, cy, gap, r_side)
        self.draw_transport(cx - gap, cy, r_side, "prev")
        self.draw_transport(cx, cy, r_play, "play" if not self.player.playing else "pause")
        self.draw_transport(cx + gap, cy, r_side, "next")

    def draw_shuffle_repeat(self, x, y, gap=110):
        self.text("small_b", "SHUFFLE", self.c_accent if self.player.shuffle else self.c_dim, (x, y))
        rep_lab = ["REPEAT: OFF", "REPEAT: ALL", "REPEAT: ONE"][self.player.repeat]
        self.text("small_b", rep_lab,
                  self.c_accent if self.player.repeat else self.c_dim, (x + gap, y))

    def draw_track_no(self, x, y, align="left"):
        if self.player.index >= 0:
            self.text("tiny", "Track %d of %d" % (self.player.index + 1, len(self.tracks)),
                      self.c_dim, (x, y), align)

    def draw_now_playing(self):
        cur = self.player.current()
        if self.visualiser != "Off" and cur is not None:
            # visualiser on: hide the album cover (and its blurred
            # background) and draw the visualiser instead
            self.viz.set_track(cur.path)
            self.draw_visualiser(cur)
        elif cur is not None:
            self.screen.blit(self.now_playing_bg(cur), (0, 0))
        if self.np_layout != "Big Cover":
            # the big cover fills the top of the screen, so it has no header
            self.text("small_b", "NOW PLAYING", self.c_sub, (W // 2, 16), "center")
        if cur is None:
            self.text("body", "Nothing playing yet.", self.c_sub, (W // 2, 200), "center")
            self.text("small", "Go to Your Library and press A on a song.",
                      self.c_dim, (W // 2, 230), "center")
            return
        if self.np_layout == "Centered":
            self.draw_np_centered(cur)
        elif self.np_layout == "Big Cover":
            self.draw_np_bigcover(cur)
        elif self.np_layout == "Cover Right":
            self.draw_np_coverright(cur)
        else:
            self.draw_np_sidebyside(cur)
        self.draw_heart(cur)
        self.draw_np_icons(cur)
        self.draw_volume_popup()

    def draw_volume_popup(self):
        """A big volume bar + percentage, shown briefly whenever the
        volume changes - Now Playing has no player bar, so this is
        the only volume slider on that screen."""
        if time.time() >= self._vol_show_until:
            return
        bw, bh = 300, 44
        bx, by = (W - bw) // 2, H - 96
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (bx, by))
        pygame.draw.rect(self.screen, (255, 255, 255),
                         (bx, by, bw, bh), 1, border_radius=8)
        vw = bw - 76
        vx, vy = bx + 44, by + bh // 2 - 2
        pygame.draw.rect(self.screen, (128, 128, 128),
                         (vx, vy, vw, 4), border_radius=2)
        pygame.draw.rect(self.screen, (255, 255, 255),
                         (vx, vy, int(vw * self.player.volume), 4),
                         border_radius=2)
        self.text("body_b", "♪", (255, 255, 255), (bx + 22, by + 8))
        self.text("body_b", "%d%%" % int(self.player.volume * 100),
                  (255, 255, 255), (bx + bw - 8, by + 8), "right")

    def np_cover(self, base, cap=300):
        """Cover size in Now Playing, scaled by the size preset and
        clamped so the layout still fits on screen."""
        return int(clamp(base * self.lib_scale(), 120, cap))

    def _cd_disc(self, cur, size):
        """The cover art cut into a circle, like a CD - with the spindle
        hole in the middle and a faint outer ring. Cached per track/size."""
        key = (cur.path, size)
        if key in self._cd_cache:
            return self._cd_cache[key]
        base = cover_surface(cur, size)
        disc = pygame.Surface((size, size), pygame.SRCALPHA)
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255),
                           (size // 2, size // 2), size // 2)
        disc.blit(base, (0, 0))
        disc.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        # the spindle hole in the middle, like a real CD
        hole = max(4, size // 12)
        pygame.draw.circle(disc, (20, 20, 20, 255), (size // 2, size // 2), hole)
        pygame.draw.circle(disc, (255, 255, 255, 255), (size // 2, size // 2), hole, 1)
        # a faint outer ring
        pygame.draw.circle(disc, (255, 255, 255, 70),
                           (size // 2, size // 2), size // 2 - 1, 2)
        if len(self._cd_cache) > 20:
            self._cd_cache.clear()
        self._cd_cache[key] = disc
        return disc

    def _draw_cassette(self, cur, x, y, size):
        """A cassette tape: dark body, the album art on a light label,
        and two reels that turn while the song plays (and stop when you
        pause). Wider than tall, centred in the cover square. All
        offsets scale with size, so it works at every cover size."""
        u = size / 200.0
        cw, ch = size, int(size * 0.64)
        bx = x + (size - cw) // 2
        by = y + (size - ch) // 2
        pygame.draw.rect(self.screen, (22, 22, 26),
                         (bx, by, cw, ch), border_radius=int(14 * u))
        pygame.draw.rect(self.screen, (70, 70, 78),
                         (bx, by, cw, ch), 2, border_radius=int(14 * u))
        # label: light background, the square art on the left (kept
        # square, never squished), thin lines for the title on the right
        lx, ly = bx + int(18 * u), by + int(12 * u)
        lw, lh = cw - int(36 * u), int(ch * 0.52)
        pygame.draw.rect(self.screen, (238, 234, 225),
                         (lx, ly, lw, lh), border_radius=int(6 * u))
        art = cover_surface(cur, lh - int(8 * u))
        self.screen.blit(art, (lx + int(4 * u), ly + int(4 * u)))
        tx = lx + lh + int(10 * u)
        for ty in (ly + int(16 * u), ly + int(30 * u), ly + int(44 * u)):
            pygame.draw.line(self.screen, (90, 86, 78),
                             (tx, ty), (lx + lw - int(12 * u), ty), 2)
        # reels: turn with the song position, stop when paused
        ang = (self.player.position() * 45.0) % 360.0
        for i, rx in enumerate((bx + cw // 2 - int(52 * u),
                                bx + cw // 2 + int(52 * u))):
            ry = by + ch - int(34 * u)
            rr = int(18 * u)
            pygame.draw.circle(self.screen, (205, 205, 205), (rx, ry), rr)
            pygame.draw.circle(self.screen, (40, 40, 44), (rx, ry), rr - 4)
            a2 = ang if i == 0 else -ang
            for k in range(3):
                th = math.radians(a2 + k * 120)
                ex = rx + int((rr - 6) * math.cos(th))
                ey = ry + int((rr - 6) * math.sin(th))
                pygame.draw.line(self.screen, (225, 225, 225), (rx, ry), (ex, ey), 2)
            pygame.draw.circle(self.screen, (205, 205, 205), (rx, ry), 3)
        pygame.draw.line(self.screen, (120, 120, 130),
                         (bx + int(18 * u), by + ch - int(14 * u)),
                         (bx + cw - int(18 * u), by + ch - int(14 * u)), 2)

    def blit_np_cover(self, cur, x, y, size):
        """Draw the Now Playing cover at (x, y) with the given size.
        Off: the square cover, as usual. CD: a circle that spins like
        a CD while the song plays (and stops when you pause). Sleeve:
        the square cover stays, and a spinning CD with the same album
        art slides out from behind it, like a record out of its sleeve
        - the disc is the same circular art as CD mode, so it spins at
        the same speed. Cassette: the album art on a cassette label,
        and the reels turn while the song plays. Hidden entirely while
        a visualiser is on."""
        if self.visualiser != "Off":
            return
        if self.cd_mode == "off":
            pygame.draw.rect(self.screen, (0, 0, 0), (x + 6, y + 6, size, size), border_radius=10)
            self.screen.blit(cover_surface(cur, size), (x, y))
            return
        if self.cd_mode == "cassette":
            self._draw_cassette(cur, x, y, size)
            return
        disc = self._cd_disc(cur, size)
        # the angle follows the song position, so the disc spins while
        # the music plays and stops when it is paused
        ang = (self.player.position() * 45.0) % 360.0
        rot = pygame.transform.rotate(disc, ang)
        if self.cd_mode == "cd":
            rect = rot.get_rect(center=(x + size // 2, y + size // 2))
            self.screen.blit(rot, rect)
            return
        # sleeve + CD: the disc slides out to the right from behind the
        # square sleeve. Shift both by half the slide-out so the whole
        # sleeve-and-disc unit stays centred on the cover's old centre.
        off = max(24, size // 3)
        sx = x - off // 2
        dx = x + off // 2
        rect = rot.get_rect(center=(dx + size // 2, y + size // 2))
        self.screen.blit(rot, rect)
        pygame.draw.rect(self.screen, (0, 0, 0), (sx + 6, y + 6, size, size), border_radius=10)
        self.screen.blit(cover_surface(cur, size), (sx, y))

    def draw_np_sidebyside(self, cur):
        """Cover on the left, song and controls on the right."""
        cs = self.np_cover(210, 240)
        self.blit_np_cover(cur, 40, 60, cs)
        tx = 280
        title = self.fit("big", cur.title, W - tx - 20)
        self.text("big", title, self.c_text, (tx, 90))
        artist = self.fit("body", cur.artist, W - tx - 20)
        self.text("body", artist, self.c_sub, (tx, 130))
        album = self.fit("small", cur.album, W - tx - 20)
        self.text("small", album, self.c_sub, (tx, 156))
        self.draw_progress(tx, 210, W - tx - 24)
        self.draw_transport_row(tx + (W - tx - 24) // 2, 300)
        self.draw_shuffle_repeat(tx, 360)
        self.draw_track_no(tx, 400)

    def draw_np_centered(self, cur):
        """Big cover in the middle, everything centred below it."""
        cs = self.np_cover(200, 210)
        cx = W // 2
        self.blit_np_cover(cur, cx - cs // 2, 30, cs)
        y = 30 + cs + 12
        title = self.fit("big", cur.title, W - 60)
        self.text("big", title, self.c_text, (cx, y), "center")
        y += 28
        artist = self.fit("body", cur.artist, W - 60)
        self.text("body", artist, self.c_sub, (cx, y), "center")
        y += 22
        album = self.fit("small", cur.album, W - 60)
        self.text("small", album, self.c_sub, (cx, y), "center")
        y += 34
        self.draw_progress(60, y, W - 120)
        y += 66
        self.draw_transport_row(cx, y, r_play=46, r_side=30, gap=72)
        y += 28
        self.draw_shuffle_repeat(cx - 105, y, gap=120)
        self.draw_track_no(W - 16, 16, align="right")

    def draw_np_bigcover(self, cur):
        """Huge cover, song and controls underneath."""
        cs = self.np_cover(300, 300)
        cx = W // 2
        self.blit_np_cover(cur, cx - cs // 2, 20, cs)
        # shuffle / repeat up in the top corners
        self.text("small_b", "SHUFFLE", self.c_accent if self.player.shuffle else self.c_dim, (16, 16))
        rep_lab = ["REPEAT: OFF", "REPEAT: ALL", "REPEAT: ONE"][self.player.repeat]
        self.text("small_b", rep_lab,
                  self.c_accent if self.player.repeat else self.c_dim, (W - 16, 16), "right")
        title = self.fit("big", cur.title, W - 60)
        self.text("big", title, self.c_text, (cx, 330), "center")
        artist = self.fit("body", cur.artist, W - 60)
        self.text("body", artist, self.c_sub, (cx, 358), "center")
        self.draw_progress(60, 386, W - 120)
        self.draw_transport_row(cx, 436, r_play=40, r_side=28, gap=68)

    def draw_np_coverright(self, cur):
        """Song and controls on the left, cover on the right."""
        cs = self.np_cover(210, 240)
        self.blit_np_cover(cur, 390, 60, cs)
        tx = 16
        w = 340
        title = self.fit("big", cur.title, w)
        self.text("big", title, self.c_text, (tx, 90))
        artist = self.fit("body", cur.artist, w)
        self.text("body", artist, self.c_sub, (tx, 130))
        album = self.fit("small", cur.album, w)
        self.text("small", album, self.c_sub, (tx, 156))
        self.draw_progress(tx, 210, w)
        self.draw_transport_row(tx + w // 2, 300)
        self.draw_shuffle_repeat(tx, 360)
        self.draw_track_no(tx, 400)

    def draw_heart(self, cur):
        """The like heart in Now Playing (top right). Filled when the
        song is liked, dim when it is not. Liking only happens here."""
        liked = cur.path in self.liked
        col = (255, 45, 85) if liked else self.c_dim
        self.text("big", "♥", col, (W - 16, 44), "right")

    # The four tappable icons on Now Playing: lyrics, add to favorites
    # (the heart), the spinning CD, and go to your favorites.
    NP_ICONS = [("lyrics", "♪"), ("like", "♥"), ("cd", "◉"), ("favorites", "★")]

    def np_icon_rects(self):
        """The four icon buttons, flanking the transport row: lyrics
        and like on the left of the prev button, CD and favorites on
        the right of the next button, all at the transport's height.
        Falls back to a centred row at the bottom when the transport
        is in a narrow column (Side by Side / Cover Right) and the
        icons would not fit beside it."""
        size, gap, margin = 30, 14, 12
        if self._np_trans is not None:
            cx, cy, tgap, r_side = self._np_trans
            y = cy - size // 2
            # left pair: right edge sits `margin` left of prev's edge
            left_right = cx - tgap - r_side - margin
            left = [(key, pygame.Rect(left_right - 2 * size - gap + i * (size + gap), y, size, size))
                    for i, key in enumerate(("lyrics", "like"))]
            # right pair: left edge sits `margin` right of next's edge
            right_left = cx + tgap + r_side + margin
            right = [(key, pygame.Rect(right_left + i * (size + gap), y, size, size))
                     for i, key in enumerate(("cd", "favorites"))]
            rects = left + right
            if rects[0][1].left >= 8 and rects[-1][1].right <= W - 8:
                return rects
        # fallback: centred row at the bottom
        total = len(self.NP_ICONS) * size + (len(self.NP_ICONS) - 1) * gap
        x0 = (W - total) // 2
        y = H - 34
        return [(key, pygame.Rect(x0 + i * (size + gap), y, size, size))
                for i, (key, _sym) in enumerate(self.NP_ICONS)]

    def np_icon_active(self, key, cur):
        if key == "lyrics":
            return self.lyrics_open
        if key == "like":
            return cur is not None and cur.path in self.liked
        if key == "cd":
            return self.cd_mode != "off"
        return False

    def draw_np_icons(self, cur):
        """The tappable icon row at the bottom of Now Playing - plain
        white glyphs with no background, like Spotify. An active icon
        (liked, CD on, lyrics open) is drawn in the accent colour."""
        rects = self.np_icon_rects()
        for key, rect in rects:
            active = self.np_icon_active(key, cur)
            sym = dict(self.NP_ICONS)[key]
            cx, cy = rect.centerx, rect.centery
            col = self.c_accent if active else (255, 255, 255)
            self.text("body_b", sym, col, (cx, cy - 8), "center")

    def np_icon_action(self, key):
        """What a tap on a Now Playing icon does."""
        cur = self.player.current()
        if key == "lyrics":
            if cur is not None and cur.get_lyrics():
                self.lyrics_open = not self.lyrics_open
                self.lyrics_scroll = 0
            else:
                self.show_toast("No lyrics for this song")
        elif key == "like":
            if cur is not None:
                self.toggle_like()
        elif key == "cd":
            self.cd_sel = (self.cd_sel + 1) % len(DISC_STYLES)
            self.cd_mode = DISC_STYLES[self.cd_sel]
            self.save_settings()
            self.show_toast("Style: " + DISC_STYLE_NAMES[self.cd_sel])
        elif key == "favorites":
            # your liked songs live in Liked Songs, in the sidebar
            self.lyrics_open = False
            self.upnext_open = False
            self.go_view("liked")

    def draw_visualiser(self, cur):
        """The Now Playing visualiser (cover hidden). Draws the chosen
        design in the stage above the transport, driven by the song's
        real spectrum; the layout's title/transport draw on top."""
        if cur is None or self.visualiser == "Off":
            return
        t = self.player.position()
        bands = self.viz.bands_at(t)
        energy = self.viz.energy(bands)
        acc = self.c_accent
        dark = tuple(max(0, int(c * 0.35)) for c in acc)
        vy0, vy1 = 0, H - 100
        midy = (vy0 + vy1) // 2
        name = self.visualiser
        if name == "Bars":
            n = len(bands)
            bw = W / n
            for i, lv in enumerate(bands):
                h = max(2, int(lv * (vy1 - vy0 - 20)))
                x = int(i * bw) + 2
                w = max(2, int(bw) - 4)
                pygame.draw.rect(self.screen, acc, (x, vy1 - h, w, h),
                                 border_radius=3)
        elif name == "Circular":
            cx, cy = W // 2, midy
            r0 = 55
            for i, lv in enumerate(bands):
                ang = 2.0 * math.pi * i / len(bands) - math.pi / 2
                r1 = r0
                r2 = r0 + lv * 130
                pygame.draw.line(self.screen, acc,
                                 (cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                                 (cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)), 5)
            pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy),
                               max(3, int(6 + energy * 14)), 2)
        elif name == "Waveform":
            wave = self.viz.wave_at(t, 160)
            amp = (vy1 - vy0) * 0.28
            pts = [(int(i * W / (len(wave) - 1)), int(midy - s * amp))
                   for i, s in enumerate(wave)]
            pygame.draw.lines(self.screen, acc, False, pts, 2)
            pts2 = [(int(i * W / (len(wave) - 1)), int(midy + s * amp))
                    for i, s in enumerate(wave)]
            pygame.draw.lines(self.screen, dark, False, pts2, 2)
        elif name == "Mirror":
            n = len(bands)
            bw = W / n
            for i, lv in enumerate(bands):
                h = max(2, int(lv * (vy1 - vy0) * 0.32))
                x = int(i * bw) + 2
                w = max(2, int(bw) - 4)
                pygame.draw.rect(self.screen, acc, (x, midy - h, w, h),
                                 border_radius=3)
                pygame.draw.rect(self.screen, dark, (x, midy, w, h),
                                 border_radius=3)
        elif name == "Spectrum Line":
            n = len(bands)
            pts = []
            for i, lv in enumerate(bands):
                x = int((i + 0.5) * W / n)
                y = int(vy1 - 8 - lv * (vy1 - vy0 - 30))
                pts.append((x, y))
            if len(pts) > 1:
                poly = [(pts[0][0], vy1)] + pts + [(pts[-1][0], vy1)]
                pygame.draw.polygon(self.screen, dark, poly)
                pygame.draw.lines(self.screen, acc, False, pts, 3)
        elif name == "Particles":
            n = len(bands)
            for i, lv in enumerate(bands):
                x = int((i + 0.5) * W / n)
                y = int(midy + math.sin(t * 1.5 + i * 0.9) * 46)
                r = max(2, int(4 + lv * 16))
                pygame.draw.circle(self.screen, acc, (x, y), r)
                if lv > 0.5:
                    pygame.draw.circle(self.screen, (255, 255, 255), (x, y),
                                       max(1, r // 3))
        elif name == "Rings":
            cx, cy = W // 2, midy
            bass = sum(bands[0:6]) / 6.0
            mid = sum(bands[6:16]) / 10.0
            treb = sum(bands[16:24]) / 8.0
            for val, base, col in ((bass, 46, acc), (mid, 96, (255, 255, 255)),
                                   (treb, 146, dark)):
                pygame.draw.circle(self.screen, col, (cx, cy),
                                   max(4, int(base + val * 56)), 3)
            pygame.draw.circle(self.screen, acc, (cx, cy),
                               max(3, int(5 + energy * 12)))
        elif name == "Grid":
            cols, rows = 24, 9
            cw, ch = W // cols, (vy1 - vy0 - 16) // rows
            for i, lv in enumerate(bands):
                lit = int(round(lv * rows))
                for r in range(rows):
                    if r < lit:
                        # lit rows counted from the bottom; top rows are hot
                        row_from_top = rows - 1 - r
                        col = (255, 90, 90) if row_from_top <= 1 else (
                            (255, 255, 255) if row_from_top <= 3 else acc)
                        pygame.draw.rect(self.screen, col,
                                         (i * cw + 2, vy0 + 8 + row_from_top * ch + 2,
                                          cw - 4, ch - 4), border_radius=2)
        elif name == "Tunnel":
            cx, cy = W // 2, midy
            for k in range(6):
                s = 1.0 - k * 0.14
                w = int(W * 0.46 * s * (1.0 + energy * 0.18))
                h = int((vy1 - vy0) * 0.46 * s * (1.0 + energy * 0.18))
                pygame.draw.rect(self.screen, acc if k % 2 == 0 else dark,
                                 (cx - w // 2, cy - h // 2, w, h), 2,
                                 border_radius=12)
            for i, lv in enumerate(bands):
                ang = 2.0 * math.pi * i / len(bands)
                r1, r2 = 26, 26 + lv * 150
                pygame.draw.line(self.screen, dark,
                                 (cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                                 (cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)), 2)
        elif name == "Bloom":
            cx, cy = W // 2, midy
            bass = sum(bands[0:6]) / 6.0
            mid = sum(bands[6:16]) / 10.0
            treb = sum(bands[16:24]) / 8.0
            for val, ox, oy, base in ((bass, cx - 150, cy, 34),
                                      (mid, cx, cy - 40, 42),
                                      (treb, cx + 150, cy, 30)):
                r = int(base + val * 72)
                pygame.draw.circle(self.screen, dark, (ox, oy), r)
                pygame.draw.circle(self.screen, acc, (ox, oy), max(4, r // 2))
                pygame.draw.circle(self.screen, (255, 255, 255), (ox, oy),
                                   max(2, r // 5))

    def draw_upnext(self):
        """The Up Next pop-up: the next songs in the queue, in a panel
        with a glowing accent border."""
        cur = self.player.current()
        if cur is None:
            return
        # the songs coming next, in queue order
        order = self.player._order
        pos = self.player._order_pos
        nxt = []
        for k in range(1, len(order) + 1):
            gi = order[(pos + k) % len(order)]
            if gi != self.player.index:
                nxt.append(self.tracks[gi])
            if len(nxt) >= 5:
                break
        pw, ph = 480, 40 + len(nxt) * 40 + 20
        px = (W - pw) // 2
        py = (H - ph) // 2
        # the glow: soft accent rectangles behind the panel
        glow = pygame.Surface((pw + 32, ph + 32), pygame.SRCALPHA)
        pygame.draw.rect(glow, self.c_accent + (40,), (0, 0, pw + 32, ph + 32), border_radius=22)
        self.screen.blit(glow, (px - 16, py - 16))
        glow2 = pygame.Surface((pw + 16, ph + 16), pygame.SRCALPHA)
        pygame.draw.rect(glow2, self.c_accent + (90,), (0, 0, pw + 16, ph + 16), border_radius=18)
        self.screen.blit(glow2, (px - 8, py - 8))
        pygame.draw.rect(self.screen, self.c_panel, (px, py, pw, ph), border_radius=16)
        pygame.draw.rect(self.screen, self.c_accent, (px, py, pw, ph), 3, border_radius=16)
        self.text("title", "UP NEXT", self.c_accent, (px + 20, py + 12))
        self.text("small", "B: close", self.c_dim, (px + pw - 20, py + 16), "right")
        for i, t in enumerate(nxt):
            yy = py + 44 + i * 40
            cover = cover_surface(t, 32)
            self.screen.blit(cover, (px + 20, yy))
            title = self.fit("body_b", t.title, pw - 140)
            self.text("body_b", title, self.c_text, (px + 62, yy))
            artist = self.fit("small", t.artist, pw - 140)
            self.text("small", artist, self.c_sub, (px + 62, yy + 20))
            dur = fmt_time(t.duration) if t.duration else "--:--"
            self.text("small", dur, self.c_sub, (px + pw - 20, yy + 8), "right")

    def draw_lyrics_panel(self):
        """The lyrics for the song that is playing, in a panel over
        Now Playing. Up/Down scrolls, A or B closes it."""
        cur = self.player.current()
        if cur is None:
            return
        text = cur.get_lyrics()
        pw, ph = 520, 340
        px = (W - pw) // 2
        py = (H - ph) // 2
        pygame.draw.rect(self.screen, self.c_panel, (px, py, pw, ph), border_radius=16)
        pygame.draw.rect(self.screen, self.c_accent, (px, py, pw, ph), 2, border_radius=16)
        self.text("title", "LYRICS", self.c_accent, (px + 20, py + 12))
        self.text("small", "B: close", self.c_dim, (px + pw - 20, py + 16), "right")
        self.text("body_b", self.fit("body_b", cur.title, pw - 40), self.c_text, (px + 20, py + 44))
        lines = text.split("\n") if text else ["No lyrics for this song."]
        # scroll so the selected line stays visible
        vis = (ph - 90) // 20
        self.lyrics_scroll = clamp(self.lyrics_scroll, 0, max(0, len(lines) - vis))
        for i in range(vis):
            li = self.lyrics_scroll + i
            if li >= len(lines):
                break
            self.text("body", self.fit("body", lines[li], pw - 40),
                      self.c_text, (px + 20, py + 74 + i * 20))


    def draw_toast(self):
        if not self.toast or time.time() > self.toast_until:
            return
        if self.view == "quiz":
            # the quiz shows its own result and achievements in the
            # result line, so a floating toast would sit on top of them
            return
        f = self.fonts["small_b"]
        surf = f.render(self.toast, True, self.c_text)
        pad = 12
        x = (W - surf.get_width()) // 2 - pad
        y = 44 if self.view == "coverflow" else H - BAR_H - 40
        pygame.draw.rect(self.screen, self.c_panel,
                         (x, y, surf.get_width() + pad * 2, 28), border_radius=14)
        self.screen.blit(surf, (x + pad, y + 6))

    # -- main loop ------------------------------------------------------
    def run(self):
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN:
                    self.handle_key(ev.key)
                elif ev.type == pygame.JOYHATMOTION:
                    # diagnostics: log the hat, so the real mapping can
                    # be read from log.txt
                    print("INPUT hat %s" % (ev.value,), flush=True)
                    self.handle_hat(ev.value)
                elif ev.type == pygame.JOYAXISMOTION:
                    self.handle_axis(ev.axis, ev.value)
                elif ev.type == pygame.JOYBUTTONDOWN:
                    # diagnostics: log the button index
                    print("INPUT button down %d" % ev.button, flush=True)
                    self.handle_joy_button(ev.button)
                elif ev.type == pygame.JOYBUTTONUP:
                    self.handle_joy_button_up(ev.button)
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    # a tap on the touchscreen (or a mouse click) - the
                    # Now Playing icons are tappable
                    if self.view == "nowplaying" and self.player.current() is not None:
                        for key, rect in self.np_icon_rects():
                            if rect.collidepoint(ev.pos):
                                self.np_icon_action(key)
                                break
                elif ev.type == pygame.FINGERDOWN:
                    # a touchscreen tap (some drivers report touch, not mouse)
                    if self.view == "nowplaying" and self.player.current() is not None:
                        px, py = int(ev.x * W), int(ev.y * H)
                        for key, rect in self.np_icon_rects():
                            if rect.collidepoint(px, py):
                                self.np_icon_action(key)
                                break
                elif ev.type == MUSIC_END:
                    self.player.on_track_end()
            # drive the music transition (crossfade volumes, or start a
            # song that was waiting for its fade-out / silence)
            self.player.update_transitions()
            # hold Back 2s to open the Controls screen (for devices
            # where Select/Start do not work)
            if (self._back_hold_since is not None and self.view != "controls"
                    and not self.options_open and self.controls_listen is None
                    and time.time() - self._back_hold_since > 2.0):
                self._back_hold_since = None
                self.open_controls()
                self.show_toast("Hold B opened Controls")
            # a combo member held on its own fires its single action
            # after a short wait (so a lone A still confirms)
            if (self._pending_btn is not None
                    and time.time() - self._pending_btn[1] > 0.3):
                self._fire_pending_single()
            # a multi-press sequence ended with no more presses: fire
            # the action for the count reached (or the single, for one)
            if (self._pending_multi is not None
                    and time.time() - self._pending_multi[2] > 0.35):
                self._resolve_pending_multi()
            # capturing a binding: a first button with no partner after
            # 0.35s binds on its own - once for a single, twice for a
            # double-click, three times for a triple-click
            if (self.controls_listen is not None and self._capture_first is not None
                    and time.time() - self._capture_first[1] > 0.35):
                btn, _t, cnt = self._capture_first
                self._capture_first = None
                if cnt >= 3:
                    self._capture_binding(("triple", btn))
                elif cnt == 2:
                    self._capture_binding(("double", btn))
                else:
                    self._capture_binding(("btn", btn))
            # backup end-of-track detection (some mixers don't fire the event)
            if (self.player.playing and self.player.duration() > 0
                    and self.player.position() >= self.player.duration()):
                self.player.on_track_end()
            # Music Quiz: stop the snippet by itself when its time is
            # up, and call time on a round the player never answered
            if self.view == "quiz" and self.quiz_song >= 0 and not self.quiz_answered:
                if (self.quiz_snippet_until is not None
                        and time.time() >= self.quiz_snippet_until):
                    if self.player.playing:
                        self.player.play_pause()
                    self.quiz_snippet_until = None
                _lname, _snip, ans_len, _mult, _f0, _fmax, _close, _nch = QUIZ_LEVELS[self.quiz_level]
                if time.time() - self.quiz_round_start > ans_len:
                    self.quiz_timeout_round()
            # the flow position is advanced by the time-based easing
            # inside draw_coverflow() (see _update_flow)
            self.draw()
            self.clock.tick(FPS)
        self.save_settings()
        self.player.stop()
        pygame.quit()


def main():
    app = App()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
