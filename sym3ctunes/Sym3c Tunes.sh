#!/bin/bash
# Sym3c Tunes - Spotify-style music player for PortMaster / ArkOS
# Launch script. Follows the PortMaster packaging template: sources
# control.txt, gets the SDL controller config, then runs the Python app.
#
# v8 - work on any PortMaster device, not just Python 3.7 ones:
#  The bundled pygame 2.1.2 is built for Python 3.7. On a device with
#  a different Python it can never import, and it shadows any working
#  system pygame (the port folder is first on the path), so the old
#  pip fallback could not help either. Now, if the bundled pygame
#  cannot import, the launcher hides its folder (renamed to
#  pygame.bundled, restored on the next launch if a run is cut short)
#  and tries the system pygame 2, then pip, before giving up. The
#  video probe also tries newer system SDL2 releases (2.26/2.28/2.30)
#  as well as the older 2.0.x ones.
# v7 - stop corrupt bytecode caches breaking the import:
#  v6 failed with "EOFError: marshal data too short" loading
#  pygame.sprite: a .pyc cache file written on the device got
#  truncated, so the import fails even though the sources are fine.
#  The launcher now never writes .pyc files (PYTHONDONTWRITEBYTECODE)
#  and, if the import still fails, deletes any stale __pycache__ dirs
#  and retries once before assuming pygame is missing.

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
export PYGAME_HIDE_SUPPORT_PROMPT=1

# --- PortMaster helpers: real ones when control.txt exists, log-only
# fallbacks otherwise, so the script never dies on "command not found".
pm_message() { echo "Sym3c Tunes: $*" >&2; }
pm_finish() { :; }

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
elif [ -d "/roms/ports/PortMaster" ]; then
  controlfolder="/roms/ports/PortMaster"
elif [ -d "/roms2/ports/PortMaster" ]; then
  controlfolder="/roms2/ports/PortMaster"
fi

if [ -n "$controlfolder" ] && [ -f "$controlfolder/control.txt" ]; then
  source "$controlfolder/control.txt"
  [ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
  get_controls
else
  controlfolder=""
  directory="roms2"
fi

# --- Find the port folder (works on /roms and /roms2 installs).
GAMEDIR=""
for d in "/$directory/ports/sym3ctunes" /roms/ports/sym3ctunes /roms2/ports/sym3ctunes; do
  if [ -d "$d" ]; then GAMEDIR="$d"; break; fi
done
[ -z "$GAMEDIR" ] && GAMEDIR="$(cd "$(dirname "$0")" && pwd)"

cd "$GAMEDIR" || exit 1
> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

# If a previous run was cut short while the bundled pygame was hidden
# (see below), restore it so the next launch starts from a clean state.
if [ -d "$GAMEDIR/sym3ctunes/pygame.bundled" ] && [ ! -d "$GAMEDIR/sym3ctunes/pygame" ]; then
  mv "$GAMEDIR/sym3ctunes/pygame.bundled" "$GAMEDIR/sym3ctunes/pygame"
  echo "Restored bundled pygame from a previous run"
fi
# 1 while the bundled pygame folder is hidden (running on a system
# or pip-installed pygame instead); restored after the app exits.
HIDDEN=0

echo "Sym3c Tunes launcher v8 - $(date)"
echo "python3: $(python3 --version 2>&1)"
echo "GAMEDIR: $GAMEDIR"
[ -n "$controlfolder" ] && echo "PortMaster control.txt: $controlfolder" || echo "PortMaster control.txt: not found (standalone mode)"

# The port ships its own pygame 2.1.2 (built for this Python 3.7 + ARM
# chip) inside sym3ctunes/pygame/, because the system's pygame 1.9.4
# is broken and too old. Put it first so it always wins.
# Never write .pyc bytecode caches: on an SD card a half-written
# cache corrupts the next import ("marshal data too short").
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$GAMEDIR/sym3ctunes${PYTHONPATH:+:$PYTHONPATH}"
[ -d "$GAMEDIR/sym3ctunes/pygame" ] && echo "Bundled pygame: yes" || echo "Bundled pygame: MISSING"

[ -n "$sdl_controllerconfig" ] && export SDL_GAMECONTROLLERCONFIG="$sdl_controllerconfig"

# --- pygame 2.x is required. Logs the real error when the import fails.
check_pygame() {
  local out ver major
  out=$(python3 -c "import pygame; print(pygame.version.ver)" 2>&1) || {
    echo "import pygame failed:"
    echo "$out"
    return 1
  }
  ver=$(printf '%s\n' "$out" | tail -n 1)
  major=${ver%%.*}
  if [ "$major" -lt 2 ] 2>/dev/null; then
    echo "pygame $ver is too old (need 2.x - 1.x cannot open this screen)"
    return 1
  fi
  echo "pygame $ver OK"
  return 0
}

# A corrupt bytecode cache (.pyc) breaks the import even when the
# sources are fine ("marshal data too short"). Clear any stale
# __pycache__ dirs and retry once before assuming pygame is missing.
if ! check_pygame; then
  echo "Import failed - clearing stale bytecode caches and retrying..."
  find "$GAMEDIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
fi

# If the bundled pygame still cannot import, it is almost certainly
# built for a different Python than this device runs (the wheel is
# CPython 3.7). It also shadows any working system pygame, so hide
# its folder and try the system pygame 2 next. mutagen is pure
# Python and stays visible, so the app keeps its tag reading.
if ! check_pygame; then
  echo "Bundled pygame cannot import here (probably a different Python version) - hiding it to try the system pygame..."
  mv "$GAMEDIR/sym3ctunes/pygame" "$GAMEDIR/sym3ctunes/pygame.bundled"
  HIDDEN=1
fi

if [ "$HIDDEN" = "1" ] && ! check_pygame; then
  pm_message "pygame 2 is missing, installing it (needs Wi-Fi)..."
  if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=; fi
  # apt's own pygame is 1.9.x here - too old, and pip 18.1 cannot read
  # modern wheels, so upgrade pip itself first, then pygame.
  # (--upgrade matters: without it pip sees the broken system pygame
  # and reports "Requirement already satisfied" without installing 2.x.)
  timeout 120 $SUDO apt-get update -qq || echo "apt update timed out or failed - continuing"
  timeout 120 $SUDO apt-get install -y python3-pip || echo "apt install python3-pip failed"
  if python3 -m pip --version >/dev/null 2>&1; then
    timeout 300 python3 -m pip install --user --upgrade pip \
      || echo "pip self-upgrade failed"
    # Prebuilt wheel only: never a slow source build on the handheld.
    timeout 300 python3 -m pip install --user --upgrade --only-binary :all: pygame \
      || echo "pip install pygame failed"
  else
    echo "pip is not available, cannot install pygame 2"
  fi
fi

if ! check_pygame; then
  # Nothing worked: put the bundled folder back and give up.
  [ "$HIDDEN" = "1" ] && mv "$GAMEDIR/sym3ctunes/pygame.bundled" "$GAMEDIR/sym3ctunes/pygame"
  pm_message "Could not get pygame 2. Connect to Wi-Fi and launch again. See log.txt for the error."
  echo "Giving up - the import error above is the cause."
  sleep 5
  pm_finish
  exit 1
fi

# --- System SDL2 facts: the fix needs the device's own SDL2 (the one
# EmulationStation uses), so log its version and location.
echo "--- system SDL2 ---"
ls /usr/lib/aarch64-linux-gnu/libSDL2* /usr/lib/libSDL2* /usr/local/lib/libSDL2* 2>/dev/null
ls -la /usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0 /lib/aarch64-linux-gnu/libSDL2-2.0.so.0 2>/dev/null
sdl2-config --version 2>/dev/null && echo "(sdl2-config version above)"
ldconfig -p 2>/dev/null | grep -i "sdl2"
dpkg -l 2>/dev/null | grep -i "libsdl2" | awk '{print $2, $3}'
echo "--- display devices ---"
ls -la /dev/dri/ /dev/fb0 2>&1
echo "--- video env ---"
echo "SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-unset} DISPLAY=${DISPLAY:-unset} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-unset}"

# --- Video probe: does a full pygame.init() (the same call the app
# makes), so it catches both a missing video driver AND pygame's
# SDL version check ("compiled with 2.0.16, linked to ...").
probe_video() {
  python3 -c "
import sys
try:
    import pygame
    pygame.init()
except Exception as e:
    print('video probe error:', e)
    sys.exit(1)
if pygame.display.get_init():
    print('VIDEO_OK')
    sys.exit(0)
print('VIDEO_FAIL display not initialized')
sys.exit(1)
" 2>&1
}

# --- Try the default system SDL2 first, then each versioned SDL2
# file in turn (the exact compiled version first, then older 2.0.x
# releases, then newer ones). A newer runtime SDL is usually accepted
# by a pygame built against an older one, so 2.26/2.28/2.30 are tried
# too, for devices whose system SDL2 is newer. The first probe that
# passes wins.
PROBE_OK=0
TRY_SDL=""
if probe_video; then
  PROBE_OK=1
  echo "VIDEO_OK with default system SDL2"
else
  echo "Default system SDL2 did not start the app - trying versioned SDL2 files..."
  for ver in 16.0 18.2 14.1 10.0 26.5 28.2 30.0; do
    CAND=""
    for d in /usr/lib/aarch64-linux-gnu /lib/aarch64-linux-gnu /usr/local/lib /usr/lib; do
      if [ -f "$d/libSDL2-2.0.so.0.$ver" ]; then CAND="$d/libSDL2-2.0.so.0.$ver"; break; fi
    done
    [ -z "$CAND" ] && continue
    echo "Trying LD_PRELOAD=$CAND"
    if LD_PRELOAD="$CAND" probe_video; then
      TRY_SDL="$CAND"
      PROBE_OK=1
      echo "VIDEO_OK with preloaded system SDL2 $CAND"
      break
    fi
    echo "That SDL2 did not work either."
  done
fi

if [ "$PROBE_OK" -eq 0 ]; then
  echo "Video still cannot open - please send this log."
  pm_message "Video driver issue - see log.txt"
  sleep 3
  pm_finish
  exit 1
fi

if [ -n "$TRY_SDL" ]; then
  LD_PRELOAD="$TRY_SDL" python3 "$GAMEDIR/sym3ctunes/sym3ctunes.py"
else
  python3 "$GAMEDIR/sym3ctunes/sym3ctunes.py"
fi

# Put the bundled pygame folder back if it was hidden for this run,
# so the next launch starts from the known-good state.
if [ "$HIDDEN" = "1" ]; then
  mv "$GAMEDIR/sym3ctunes/pygame.bundled" "$GAMEDIR/sym3ctunes/pygame"
fi

pm_finish
