# Sym3c Tunes

A Spotify-style music player for ArkOS handhelds, built as a PortMaster port. Library, iPod-style Cover Flow, Now Playing, a real audio-spectrum visualiser, and a Music Quiz game — all in one app, running at 640×480 on your device.

![Library](docs/screenshots/library.png)

## Features

- **Library** — every song in one list, with album art, artist, album, and duration
- **Cover Flow** — iPod-style 3D album flow with 13 transitions and a reflection
- **Now Playing** — 4 layouts, blurred album-art background, and 4 ways to show the cover
- **Artists** — browse by artist, then flip through just that artist's albums
- **Playlists** — your music folders become playlists, shown as their own Cover Flow
- **Liked Songs** — heart any song (L2 in Now Playing) and find it here
- **Search** — on-screen keyboard, live results by title, artist, or album
- **Music Quiz** — a game inside the player: hear a snippet (or see a folded cover) and guess the song
- **Real visualiser** — a true audio spectrum, decoded from the track itself, in 10 designs
- **33 themes + custom editor** — pick a look, or build your own
- **Fully remappable controls** — every action, combos, double- and triple-clicks
- **Up Next, Lyrics, shuffle, repeat** — the rest of a proper player

## Screenshots

### Library

![Library](docs/screenshots/library.png)

### Cover Flow

![Cover Flow](docs/screenshots/coverflow.png)

### Now Playing — Centered (default)

![Now Playing Centered](docs/screenshots/now-playing-centered.png)

### Now Playing — the other 3 layouts

| Side by Side | Big Cover | Cover Right |
|---|---|---|
| ![Side by Side](docs/screenshots/now-playing-side-by-side.png) | ![Big Cover](docs/screenshots/now-playing-big-cover.png) | ![Cover Right](docs/screenshots/now-playing-cover-right.png) |

### Artists

![Artists](docs/screenshots/artists.png)

### Playlists

![Playlists](docs/screenshots/playlists.png)

### Liked Songs

![Liked Songs](docs/screenshots/liked-songs.png)

### Search

![Search](docs/screenshots/search.png)

### Disc styles

How the album art is presented in Now Playing. Pick it from the options bar (SELECT → DISC STYLE), or tap the ◉ icon to cycle through them.

| Off (square cover) | CD (spinning disc) |
|---|---|
| ![Disc Off](docs/screenshots/disc-off.png) | ![Disc CD](docs/screenshots/disc-cd.png) |

| Sleeve + CD | Cassette |
|---|---|
| ![Disc Sleeve](docs/screenshots/disc-sleeve.png) | ![Disc Cassette](docs/screenshots/disc-cassette.png) |

The CD spins with the song (45°/sec, freezes when paused). Sleeve + CD slides the spinning disc out from behind the square cover, with the same album art on its face. Cassette puts the art on a cassette label, and the two reels turn while it plays.

### Visualiser

A real audio spectrum — the app decodes the track's PCM and computes 24 log-spaced frequency bands (60 Hz–14 kHz), so the bars move with the music, not a fake animation. 10 designs: Off, Bars, Circular, Waveform, Mirror, Spectrum Line, Particles, Rings, Grid, Tunnel, Bloom. Pick one from the options bar (SELECT → VISUALISER). When it is on, it replaces the blurred art background and the cover is hidden.

![Visualiser Bars](docs/screenshots/visualiser-bars.png)

### Up Next

R2 in Now Playing (or the Up Next action) opens a pop-up with the next 5 songs in the queue.

![Up Next](docs/screenshots/up-next.png)

### Lyrics

Put a `.lrc` file beside a song (same name as the song file), or embed lyrics in the file's tags. Open the lyrics panel from Now Playing (the ♪ icon, or the Lyrics action) and scroll with Up/Down.

![Lyrics](docs/screenshots/lyrics.png)

## Music Quiz

A game inside the player, at the bottom of the sidebar. The app picks a random song from your library and you guess it — the title, the artist, or the album — from a grid of answers. The question type is random every round, and the wrong answers come from your other songs' metadata, so every round is different.

![Quiz audio](docs/screenshots/quiz-audio.png)

How to play: hear the snippet (or look at the cover) and pick the right answer with Up/Down, then A to answer. The faster you answer, the more points you score — a correct answer is worth up to 100 by speed, times your level multiplier, plus a streak bonus. The score shows karaoke style: a big number and a grade (PERFECT!, EXCELLENT!, GREAT!, GOOD!). A wrong answer scores 0 and breaks your streak. Press X (or Y) to hear the snippet again — the clock keeps running, so replaying costs you speed points. Left/Right changes the level (next round). A after an answer starts the next song.

There are 5 levels, each harder than the last: shorter music, smaller folds, and more answers to pick from.

| Level | Snippet | Answers | Points | The twist |
|---|---|---|---|---|
| Easy | 15s, from the start | 4 | ×1 | — |
| Medium | 10s, from anywhere | 5 | ×2 | — |
| Hard | 5s, from anywhere | 6 | ×3 | wrong answers are close (same artist) |
| Folded | no music — the folded cover is the clue | 7 | ×4 | the album art is folded, one piece visible, and it folds tighter every round |
| Master | no music — the folded cover is the clue | 8 | ×5 | starts already folded tighter, folds tighter still, close wrong answers |

On the Folded and Master levels the album art is shown folded like paper: only one cell of a grid is visible and the rest is covered. Every round the fold tightens by 1, so the piece you see gets smaller — round 1 shows a quarter of the cover, round 2 a ninth, and so on. You guess the title, the artist, the album, or which album the cover belongs to, all from that one folded piece.

![Quiz folded](docs/screenshots/quiz-folded.png)

![Quiz master](docs/screenshots/quiz-master.png)

The cover round shows the whole album cover and asks which album it belongs to — no snippet, just the art.

![Quiz cover](docs/screenshots/quiz-cover.png)

To quit the game and go back to playing music, **triple-click SELECT** (three quick taps). The current song starts from the top in Now Playing. B goes back to the Library instead (music stays paused). The quit instruction is at the top of the quiz screen, so it is always in front of you.

Achievements (saved, shown as a star count at the top): First Note, On a Roll (3 in a row), Hot Streak (5), Unstoppable (10), Perfect Pitch (a perfect 100), Cover Star, High Scorer (500 points), Quiz Master (25 correct), Origami (a folded round right), Mastermind (a Master level round right). Your best total points are saved too.

![Quiz answered](docs/screenshots/quiz-answered.png)

## Installation

1. Download the latest release (`sym3ctunes.zip`) and extract it.
2. Copy the `sym3ctunes` folder into your device's ports folder — `/roms/ports/` on ArkOS (or `/roms2/ports/` if your ROMs live on the second card).
3. **Copy `Sym3c Tunes.sh` out of the folder and into the ports folder itself**, so it sits next to the `sym3ctunes` folder. EmulationStation only lists `.sh` files that sit directly in the ports folder — if the script is only inside the folder, the port will not appear.
4. If you copied the files over on Windows, the script may have lost its executable flag. If the port does not appear, make it executable: `chmod +x "/roms/ports/Sym3c Tunes.sh"`.
5. Restart EmulationStation (or reboot). The port appears in the Ports menu as **Sym3c Tunes**.
6. Put your music in `sym3ctunes/music/` (inside the port folder), or in `/roms/music`, `/roms2/music`, or `~/Music`. The app scans all of them. Supported: mp3, ogg, oga, wav, flac, m4a, opus.

On first run the app walks you through mapping your buttons (press A on each action when it asks). You can skip any action with B, and remap everything later from the Controls screen (hold B for 2 seconds).

## Controls

Default mapping (retrogame layout — Anbernic, Miyoo, and other ArkOS handhelds). Everything is remappable.

| Action | Button |
|---|---|
| Up / Down / Left / Right | D-pad (or stick) |
| Confirm / Play | A |
| Back | B |
| Next track | X |
| Previous track | Y |
| Shuffle | L1 |
| Repeat | R1 |
| Options bar | Select (tap) |
| Go to Cover Flow | (unbound — set it in Controls) |
| Go to Now Playing | (unbound — set it in Controls) |
| Like the song | L2 (Now Playing only) |
| Up Next | R2 |
| Lyrics | (unbound — set it in Controls) |

Shortcuts that always work, even with a blank keymap:

- **SELECT + START** — quit the app
- **SELECT + Y** — reset all controls to the device defaults
- **Hold B for 2 seconds** — open the Controls screen
- **X / Y in the options bar** — switch options pages
- **Triple-click SELECT in the Music Quiz** — quit the game and play music again

### Remapping, combos, and multi-clicks

Open the options bar (SELECT) → **Controls** page, or hold B for 2 seconds. Pick an action, press A, then press the button you want. You can also bind:

- **Two-button combos** — press a second, different button within 0.35s (e.g. A+B for lyrics)
- **Double-click** — press the same button twice quickly
- **Triple-click** — press the same button three times quickly

A button can belong to only one combo. Duplicates are rejected while mapping.

### Now Playing transport

On Now Playing, **A = play/pause, X = next, Y = previous**. A still confirms everywhere else.

## Options bar

Press SELECT (tap) to open it. X/Y switches pages, Up/Down picks (live — you see the change straight away), A keeps the pick and closes, B cancels and closes (reverts to what you had).

| Page | What it does |
|---|---|
| Transition | Cover Flow animation — 13 choices (Slide, Snap, Flip, Fade, Zoom, Bounce, Spin, Cascade, Carousel, Stack, Roll, Elastic, Tilt) |
| Theme | 33 preset themes, plus a Custom editor (background / accent / text, 24 colours) |
| Layout | Now Playing layout — Side by Side, Centered (default), Big Cover, Cover Right |
| Library Size | Compact / Normal / Large / Huge — text and cover size in the Library and Now Playing |
| Disc Style | Off / CD / Sleeve + CD / Cassette — how the album art is presented in Now Playing |
| Visualiser | Off + 10 spectrum designs |
| Controls | Remap every action (see above) |

![Options transition](docs/screenshots/options-transition.png)

![Options disc style](docs/screenshots/options-disc.png)

## Cover Flow

![Cover Flow](docs/screenshots/coverflow.png)

Albums grouped by album + artist. The centre album is big, with a border, reflection, and ambient glow; the neighbours are sheared (not squashed) and darkened. D-pad Left/Right flips albums, Up/Down jumps 5, A opens the album (pick a song and it plays and jumps straight to Now Playing), B goes back. Cover Flow is pure browsing — there is no player bar here.

Pick a transition from the options bar. Carousel and Stack are alternate layouts. A on an artist (in Artists) opens Cover Flow filtered to that artist; B in the filtered flow goes back to Artists.

Album art comes from the file itself, in this order: embedded art first, then a cover image beside the songs (`cover.jpg`, `folder.jpg`, `album.jpg`, `front.jpg`), then a generated gradient tile. No internet lookup — everything is local.

## Themes

33 presets plus a Custom editor (3 slots: background, accent, text; 24-colour palette). Everything in the app follows the theme, including Cover Flow, Now Playing, and the quiz.

![Options theme](docs/screenshots/options-theme.png)

## Requirements

- ArkOS (or another PortMaster-supported OS) on an ARM handheld
- PortMaster installed
- Python 3.7+ with pygame (the port bundles pygame 2.1.2 for Python 3.7; if your Python is different, the launcher falls back to the system pygame, then pip)
- A 640×480 screen (the app draws at 640×480 and scales to the real display)

Tested on the **Anbernic RG353V** (ArkOS, 640×480). It should work on any PortMaster device — including the A10 Mini V4 — but that is still untested. If it will not start on your device, send the port folder's `log.txt` and it can be fixed.

## How it is built

- Python + pygame, single file (`sym3ctunes/sym3ctunes.py`), 640×480
- PortMaster port: `port.json`, `gameinfo.xml`, and the launcher `Sym3c Tunes.sh`
- The launcher probes the system SDL2 versions (2.0.10–2.30.0) with a full `pygame.init()` and uses the first one that works, so it runs on devices where the bundled SDL2 has no display driver
- If the bundled pygame wheel (CPython 3.7) cannot load, the launcher hides it and falls back to the system pygame, then pip
- Music metadata via mutagen (pure Python, vendored); album art from embedded art or a cover image beside the songs
- Settings (theme, layout, controls, quiz achievements and best points) save to `settings.json` in the port's `conf/` folder

## Credits

Built with Muse (muse.ai) and Phil Assistant. The launcher and PortMaster plumbing follow the PortMaster port format.

## License

MIT — do what you like with it, just keep the notice.
