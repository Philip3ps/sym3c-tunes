# Sym3c Tunes

A Spotify-style music player for PortMaster on ArkOS (A10 Mini V4 and other
RK3326/RK3566 handhelds). Dark theme, green accents, album-cover tiles,
a bottom now-playing bar, a full Now Playing screen, and an iPod Classic
style Cover Flow for flipping through your albums - all navigated with
the D-pad and face buttons.

## Library, Artists, Playlists

**Music folders:** songs sitting directly in a music folder are the normal
music. **Each subfolder inside a music folder is a playlist** - the
folder name becomes the playlist name. **Your Library shows ALL songs**
(loose files and playlist songs together), sorted by the songs' metadata
(artist, then title), not by filename.

**Sidebar:** in the Library, press **Left** on the D-pad to move to the
sidebar menu, **Up/Down** to pick Your Library, Cover Flow, Now Playing,
Artists or Playlists, **A** to open it, **Right** (or **B**) to go back to
the track list. **The focused area is highlighted:** when the menu has
focus the picked item lights up in green, when the track list has focus
the selected song lights up and the menu goes dim - so you always see
where you are.

**Artists:** lists every artist with their album and song counts. Tap an
artist and Cover Flow opens showing only that artist's albums (their name
appears in green at the top). **B** in that filtered flow goes back to the
Artists list.

**Playlists:** lists your playlist folders with their song counts. Tap one
to see its songs (sorted by metadata) and play them. To make a playlist,
just make a folder inside your music folder and put songs in it - no
in-app setup needed. **The Playlists view is a Cover Flow:** each playlist
folder is a card whose cover is the album art of up to 4 songs inside it,
tiled 2x2 (like Spotify's playlist covers). **Left/Right** flips through
your playlists, **A** opens the one in the centre, **B** goes back.
**When you play a song from a playlist, Next and Prev stay inside that
playlist** (same for an album - Next stays in the album; from the Library,
Next walks all your songs). Shuffle also stays inside the playlist or
album you started from.

## Liked Songs

On the **Now Playing** screen, press **L2** to like the song that is
playing (a red heart shows top-right when it's liked; press L2 again to
unlike it). Liking only works on Now Playing. Your liked songs live in
**Liked Songs** in the sidebar - open it and press A on a song to play
it; Next and Prev stay inside your liked songs.

## Now Playing icons

At the bottom of Now Playing there are four tappable icons - plain
white glyphs with no background, just like Spotify - **tap them
on the touchscreen** (or use the buttons in brackets):

- **♪ Lyrics** - shows the lyrics for the song that is playing.
- **♥ Like** - adds the song to your favorites (L2 does the same). The
  heart turns green when the song is liked.
- **◉ CD** - cycles the disc style: Off, CD, Sleeve + CD, or Cassette. The icon turns green
  when a disc style is on.
- **★ Favorites** - jumps straight to your **Liked Songs** list.

- **♪ Lyrics** - shows the lyrics for the song that is playing.
- **♥ Like** - adds the song to your favorites (L2 does the same). The
  heart turns green when the song is liked.
- **◉ CD** - cycles the disc style: Off, CD, Sleeve + CD, or Cassette. The icon turns green
  when a disc style is on.
- **★ Favorites** - jumps straight to your **Liked Songs** list.

## Disc styles

Open the options bar (SELECT) and press X/Y to the **DISC STYLE** page. Four choices:

- **Off** - the cover art is a square, as usual.
- **CD** - the cover art becomes a circle that spins like a CD while the song plays, and stops when you pause.
- **Sleeve + CD** - the square cover stays, and a spinning CD with the same album art slides out from behind it, like a record out of its sleeve. The disc spins at the same speed as CD mode.
- **Cassette** - the album art on a cassette label, and the reels turn while the song plays, and stop when you pause.

Works in all 4 Now Playing layouts. You can also tap the **◉** icon at the bottom of Now Playing to cycle through the four styles. Your pick is saved.

## Visualiser

A real audio visualiser for Now Playing, driven by the song's actual
spectrum (not a fake animation). When a visualiser is on, the album
cover is hidden and the visualiser takes its place; the song title,
progress bar and transport stay on top. Open the options bar (SELECT)
and press X/Y to the **VISUALISER** page. 10 designs:

- **Bars** - classic vertical frequency bars.
- **Circular** - bars radiating out from the centre in a circle.
- **Waveform** - the raw audio wave scrolling across the screen.
- **Mirror** - bars mirrored above and below a centre line.
- **Spectrum Line** - a smooth glowing line tracing the spectrum.
- **Particles** - glowing dots that pulse with each frequency band.
- **Rings** - concentric rings pulsing with bass, mids and treble.
- **Grid** - a LED-matrix grid lighting up with the music.
- **Tunnel** - bars rushing down a perspective tunnel.
- **Bloom** - soft glowing orbs blooming with the beat.

Pick **Off** to go back to the album cover. Your pick is saved. The
spectrum is computed from the song itself (Goertzel, 24 bands) and
the audio is decoded in the background, so turning it on never
freezes the player.

Any action can be bound to **two buttons pressed together** - for
example A+B to open the lyrics. Hold B for 2 seconds to open
**Controls**, pick the action (e.g. Show lyrics), press A, then press
the two buttons together (A then B). The Controls screen shows it as
"Button A+B". Pressing A or B on its own still does its normal thing
(A confirms, B goes back) - only pressing both together fires the
combo. A button can only belong to one combo.

## Double-click and triple-click

Any action can also be bound to pressing the **same button twice
(AA) or three times (AAA)**. In Controls, pick the action, press A,
then press the button twice quickly for a double-click ("Button X
x2") or three times for a triple-click ("Button Y x3"). A single
press of that button still does its normal thing - it just waits a
beat (0.35s) to see if another press follows.

## Reset the key mapping

If the mapping ever gets scrambled and you can't reach Controls,
press **SELECT+Y** together. It resets all controls back to the
defaults for your handheld. It uses the physical buttons, so it
works even with a blank or broken keymap.

## Up Next

Press **R2** anywhere to pop up **Up Next** - the next songs in the queue
in a glowing panel. Press B or R2 again to close it.

## Lyrics

On the Now Playing screen, press the **Lyrics** button (map one in
Controls - hold B for 2 seconds) to show the lyrics for the song that is
playing. Lyrics come from a `.lrc` file next to the song, or from lyrics
embedded in the file. Up/Down scrolls, A or B closes it.

## Search

**Search** is in the sidebar, below Playlists. Type with the on-screen
keyboard (D-pad moves, A types a letter), and matching songs, artists
and albums show up live below. Press DONE, pick a result with Up/Down,
and A plays it.

## Music Quiz

**Music Quiz** is in the sidebar, at the bottom. The app picks a random
song from your library and you guess it - the title, the artist, or
the album - from a grid of answers. The question type is random every
round, and the wrong answers come from your other songs' metadata, so
every round is different.

How to play: hear the snippet (or look at the cover) and pick the right
answer with Up/Down, then A to answer. The faster you answer, the more
points you score - a correct answer is worth up to 100 by speed, times
your level multiplier, plus a streak bonus. The score shows karaoke
style: a big number and a grade (PERFECT!, EXCELLENT!, GREAT!, GOOD!).
A wrong answer scores 0 and breaks your streak. Press X (or Y) to hear
the snippet again - the clock keeps running, so replaying costs you
speed points. Left/Right changes the level (next round). A after an
answer starts the next song.

There are 5 levels, each harder than the last: shorter music, smaller
folds, and more answers to pick from.

| Level | Snippet | Answers | Points | The twist |
|-------|---------|---------|--------|-----------|
| Easy | 15s, from the start | 4 | x1 | - |
| Medium | 10s, from anywhere | 5 | x2 | - |
| Hard | 5s, from anywhere | 6 | x3 | wrong answers are close (same artist) |
| Folded | no music - the folded cover is the clue | 7 | x4 | the album art is folded, one piece visible, and it folds tighter every round |
| Master | no music - the folded cover is the clue | 8 | x5 | starts already folded tighter, folds tighter still, close wrong answers |

On the Folded and Master levels the album art is shown folded like
paper: only one cell of a grid is visible and the rest is covered. Every
round the fold tightens by 1, so the piece you see gets smaller - round
1 shows a quarter of the cover, round 2 a ninth, and so on. You guess
the title, the artist, the album, or which album the cover belongs to,
all from that one folded piece.

To quit the game and go back to playing music, **triple-click SELECT**
(three quick taps). The current song starts from the top in Now
Playing. B goes back to the Library instead (music stays paused). The
quit instruction is at the top of the quiz screen, so it is always in
front of you.

Achievements (saved, shown as a star count at the top): First Note,
On a Roll (3 in a row), Hot Streak (5), Unstoppable (10), Perfect
Pitch (a perfect 100), Cover Star, High Scorer (500 points), Quiz
Master (25 correct), Origami (a folded round right), Mastermind (a
Master level round right). Your best total points are saved too.

## Library size

Open the options bar (SELECT) and press X/Y to the **Library Size** page.
Four presets - **Compact, Normal, Large, Huge** - change the text and
cover art size in the Library, and the cover size in Now Playing.

The sidebar is signed at the bottom: **muse.ai x Phil Assistant**.

## Now Playing

The default look is **Centered** (big cover in the middle, everything
centred below). Pick another of the 4 layouts from the options bar
(SELECT) - Designs page - and it sticks.

## Cover Flow

Press START to cycle: Library -> Cover Flow -> Now Playing.

### Cover Flow transitions

Press **SELECT** on the handheld (or **O** on a keyboard) to open the
transition options bar at the bottom of the screen. It lists 13 ways the
flow can move between albums:

| # | Transition | What it does |
|---|------------|--------------|
| 1 | Slide | Smooth glide to the next album (default) |
| 2 | Snap | Instant jump, no animation |
| 3 | Flip | Albums flip over like cards |
| 4 | Fade | Albums crossfade through black |
| 5 | Zoom | The next album zooms in |
| 6 | Bounce | Slides in with a springy bounce |
| 7 | Spin | The next album twirls into place |
| 8 | Cascade | Albums drop in from above |
| 9 | Carousel | Albums ride around a 3D carousel |
| 10 | Stack | Albums stacked like a deck of cards |
| 11 | Roll | Albums roll over like a wheel |
| 12 | Elastic | Slides in with a wobbly spring |
| 13 | Tilt | Albums lean harder as they glide |

While the bar is open: **Up/Down** picks a transition, **Left/Right**
flips albums so you can preview it live, **A** keeps it, **B** cancels
back to the one you had. Your pick is saved (in `settings.json`) and
remembered next time you launch. **SELECT + START still quits** — tap
SELECT on its own for the bar, hold it and press START to quit.

## Install

1. Copy the `sym3ctunes` folder to the ports folder on your SD card:
   **ArkOS: `/roms2/ports/sym3ctunes/`**
2. Put your music (MP3, OGG, WAV, FLAC, M4A) in `sym3ctunes/music/`
   inside that folder - or in `/roms2/music/`. The app scans both.
3. Launch **Sym3c Tunes** from the Ports section in EmulationStation.

First run needs pygame **version 2.x**. The port ships its own pygame
2.1.2 inside `sym3ctunes/pygame/` (built for this Python 3.7 + ARM
chip), because the version apt ships on this firmware is pygame 1.9.4,
which is too old and broken (its own files are incomplete). The launcher
uses the bundled copy first, so no download is needed. On a device with
a different Python version, the bundled copy cannot import at all — so
the launcher hides its folder and tries the system pygame 2 instead,
then falls back to installing pygame 2 from pip (needs Wi-Fi). Without
Wi-Fi, install it once over SSH instead:
`sudo apt install python3-pip && python3 -m pip install --user pygame`
The app draws at 640x480 and scales to the real display, so it works on
any screen size, not just 640x480.

Known issue (RG353V, 2026-11-22): the bundled pygame loads, but its
SDL2 has no KMS video driver, so on a KMS-only handheld the app fails
with "video system not initialized". Fixed in launcher v6: the bundled
pygame was repointed to the device's own SDL2, and the launcher tries
each system SDL2 in turn (default, then 2.0.16, 2.0.18, 2.0.14, 2.0.10,
2.26.5, 2.28.2, 2.30.0 via LD_PRELOAD) and runs the app with the first
one that passes a full pygame.init() probe.
Launcher v7: a corrupt bytecode cache (.pyc) on the device broke the
import ("marshal data too short") — the launcher now never writes
.pyc files and clears any stale __pycache__ and retries if the import
fails. Launcher v8: the system-pygame fallback above, for devices that
do not run Python 3.7. If the app ever fails to start, check `log.txt`
in the port folder - it records the exact error.

## Controls

| Button | Action |
|---|---|
| D-Pad Up / Down | Move through the track list (Library / Album view) |
| | Jump 5 albums (Cover Flow) / volume (Now Playing) |
| D-Pad Left / Right | Seek -5s / +5s (Library, Album, Now Playing) |
| | Flip through albums (Cover Flow) |
| A | Play selected track / play-pause (Library, Now Playing) |
| | Open the album (Cover Flow) / play the song and go to Now Playing (Album view) |
| B | Back (Album -> Cover Flow, Cover Flow / Now Playing -> Library) |
| X | Next track |
| Y | Previous track |
| L | Toggle shuffle |
| R | Toggle repeat (off -> all -> one) |
| START | (unbound — map it in the Controls screen if you want it) |
| SELECT | Open the options bar (tap) — transitions list |
| SELECT + START | Quit |
| SELECT + Y | Reset all controls to the defaults |
| T (keyboard) / X or Y in the bar | Open/switch to the theme list |
| O (keyboard) | Open/close the options bar |
| Device volume buttons | Volume (OS level) |

On a PC keyboard: arrows to navigate/seek, Enter to play, Space to
pause, N/P next/previous, S shuffle, R repeat, C Cover Flow,
H Library, +/- volume, Esc to quit.

**Now Playing transport:** on Now Playing, **A is play/pause, X is
the next song and Y is the previous song**. There is also a mappable
**Go to Now Playing** action in the Controls screen - pick any
button for it and it jumps straight to Now Playing from anywhere.

**Both sticks work:** the left stick (axes 0/1) and the right stick
(axes 2/3) both navigate, and either stick can be remapped to any
action in the Controls screen (push the stick direction when it asks
for a button). The D-pad and the sticks stay usable together — if
you bind a direction to a stick, the D-pad button for that direction
still navigates, and if you bind a direction to the D-pad, the sticks
still navigate.

**RG353V / retrogame devices:** the app detects the `retrogame_joypad`
and uses the right mapping automatically — D-pad is buttons 13–16,
A=1, B=0, X=2, Y=3, L1=4, R1=5, L2=6, R2=7, Select=8, Start=9.
If a button is pressed twice during the first-run setup, the second
press is rejected ("Already used for X") so one action can't steal
another's button.

**Go to Cover Flow shortcut:** there is a remappable action
**Go to Cover Flow** that jumps straight to the Cover Flow view from
anywhere. It is unbound by default — map it to a button in the
Controls screen (hold **B** for 2 seconds to open it, move to
Go to Cover Flow, press **A**, then press the button you want, e.g.
L3). **Change view (cycling) is removed** — Start no longer cycles
through the views; use the Go to Cover Flow shortcut, or B to go
back to the Library.

**First-run setup:** the first time you launch the app, a **Set up your
controls** screen appears before the Library — and only that once, it
never pops up again. Nothing is pre-mapped: press the button (or
D-pad direction, or stick direction) for each action in order — Up,
Down, Left, Right, Confirm/Play, Back, Next track, Previous track,
Shuffle, Repeat, Options, Go to Cover Flow — and it saves your mapping and
opens the Library. Press **B** to skip one action and move on (it stays
unmapped; when it asks for Back, B maps Back to B). The D-pad and both
sticks still navigate even with actions unmapped, and **SELECT+START
always quits**, even with a blank keymap. To change your mapping later,
hold **B** for 2 seconds to open the Controls screen. The app opens every
joystick it finds, so the D-pad works even when it lives on a separate
device from the sticks.

**Remap later:** the D-pad works as a hat, as axes 0/1, or as
buttons (some handhelds, e.g. the RG353V, report the D-pad as axes or
buttons, and Select/Start sit at different numbers than the standard).
If a button or the D-pad does not do what you expect, remap it: open
the Controls screen with **SELECT** (options bar, **X/Y** to the
Controls page, **A**) — or, if Select does not work, **hold B for
2 seconds**. Press **A** on an action, then press the button (or D-pad
direction) you want for it — remapping runs through the actions in
order, and **B** stops it. Your mapping is saved and remembered. The
last row, **Reset to defaults**, restores the standard mapping.

## Themes

**SELECT** opens the options bar; **T** opens it straight on the theme
page. **X / Y** switch between the bar's pages — Cover Flow transitions,
Themes, Now Playing designs, Controls — no matter what X and Y are mapped
to, so the "X/Y: themes" hint is always true even when Next/Previous
track are unbound or on other buttons. When the bar is closed, X and Y
do whatever they are mapped to (next/previous track by default). There
are **33 themes** to pick from —
Spotify (default), Midnight, Forest, Ocean, Sunset, Grape, Rose, Ember,
Mint, Slate, Crimson, Gold, Ice, Lime, Bubblegum, Teal, Violet, Coffee,
Blood Moon, Arctic, Matcha, Peach, Orchid, Steel, Neon, Dusk, Pine, Berry,
Sand, Royal, Paper, Daybreak and Sky — plus **Custom** at the end of the
list. A theme changes the whole app: background, sidebar, panels, text
and the accent colour. Your pick is saved and remembered.

**Make your own:** pick **Custom** in the theme list and press **A** to
open the editor. Choose Background, Accent and Text (Up/Down), then cycle
each one through 24 colours (Left/Right) — the app previews it live.
**A** saves it, **B** cancels. Everything else (sidebar, panels, dimmed
text) is worked out from your three colours, and a light background
automatically gets a light theme.

## Now Playing

The album art is the background: the current cover is blurred to fill
the screen and dimmed, with the song info, progress bar and transport
drawn straight on top of it. The transport buttons are centred on the
info block, in line with the progress bar above them. Works with
embedded art, `cover.jpg`, and generated tiles alike.

### Designs

Four ways to arrange the same art and controls — pick the one you like
best in the options bar (**SELECT**, then **X/Y** to the design list;
**T** cycles the lists too). The design previews live on the Now
Playing screen behind the bar, and your pick is saved:

1. **Side by Side** (default) — cover on the left, song and controls on
   the right.
2. **Centered** — big cover in the middle, everything centred below it.
3. **Big Cover** — huge cover, song and controls underneath.
4. **Cover Right** — song and controls on the left, cover on the right.

Opening the design list switches to Now Playing and starts the first
track if nothing is playing yet, so you can see each design. **A**
keeps the pick, **B** cancels back to the previous design.

The app does not download anything - it reads the art that is already
with your music, in this order:

1. **Embedded art** - the picture stored inside the music file itself
   (ID3 cover in MP3s, picture block in FLAC, `covr` in M4A). Most songs
   bought or downloaded already have this. The tag reader (mutagen) is
   bundled with the port, so this works even though the handheld has no
   mutagen installed.
2. **A cover file next to the songs** - put one square image in the
   album's folder, named `cover.jpg` (or `folder.jpg`, `album.jpg`,
   `front.jpg`, `.png` works too). One image covers the whole folder.
3. **A generated tile** - if a song has no art at all, the app draws a
   coloured gradient tile with a music note, so the list never looks empty.

To add art to files that have none, the easiest way on a PC is a tag
editor like Mp3tag or MusicBrainz Picard (Picard can also fetch the art
for you). Or just drop a `cover.jpg` in the folder - no editing needed.

- Track titles, artists, albums and lengths come from the files' ID3
  tags when present, otherwise from the file name (`Artist - Title.mp3`).
- Embedded album art is shown when a file has it, else a `cover.jpg`
  next to the songs, else the app draws a coloured gradient tile.
- No music is shipped with the port - add your own files.

## Thanks

Built for Phil's A10 Mini V4. Thanks to the PortMaster team and the
pygame project - this app would not exist without them.
