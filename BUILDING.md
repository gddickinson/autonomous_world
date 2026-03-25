# Building Autonomous World

## Requirements

- **Python**: 3.9 or higher (3.11+ recommended)
- **OS**: macOS, Windows 10+, Linux (X11 or Wayland with XWayland)

## Dependencies

Install with pip:

```bash
pip install pygame-ce numpy
```

Optional (for multiplayer AI companion):

```bash
pip install openai   # if using LLM-backed AI player
```

## Running from Source

```bash
python play.py                        # normal start
python play.py --multiplayer          # host a multiplayer server
python play.py --join 192.168.1.5:7777  # join a remote game
python play.py --ai-companion warrior   # host + AI co-player
python play.py --wizard               # cheat: high-level wizard
```

## Building a Standalone Executable

Install PyInstaller:

```bash
pip install pyinstaller
```

Build:

```bash
python build.py              # directory bundle (recommended)
python build.py --onefile     # single executable
python build.py --debug       # keep console for error output
python build.py --clean       # remove old build artifacts first
```

Or use the spec file directly:

```bash
pyinstaller build_config.spec
```

Output appears in `dist/AutonomousWorld/`.

## Platform Notes

### macOS
- Use `pygame-ce` (not legacy `pygame`) for Apple Silicon support.
- Gatekeeper may block unsigned builds. Run `xattr -cr dist/AutonomousWorld.app` to clear quarantine.
- The spec file generates a `.app` bundle automatically on macOS.

### Windows
- The `--noconsole` flag (default) hides the terminal window.
- Use `--debug` if the game closes silently on startup to see error output.
- Windows Defender may flag unsigned executables. Add an exclusion or sign the binary.

### Linux
- Requires SDL2: `sudo apt install libsdl2-2.0-0 libsdl2-mixer-2.0-0` (Debian/Ubuntu).
- Wayland: pygame uses XWayland. Set `SDL_VIDEODRIVER=x11` if needed.
- AppImage or Flatpak packaging is not included but can wrap the onedir output.

## Known Issues

- **macOS Retina**: Window may appear at 2x size on first launch. Resize or set `SDL_VIDEO_HIGHDPI_DISABLED=1`.
- **Linux PulseAudio**: Sound may crackle. Try `SDL_AUDIODRIVER=alsa`.
- **Windows onefile**: Startup is slower than onedir because it unpacks to a temp directory.
- **Large worlds**: Memory usage can exceed 1 GB with maximum world size. Ensure sufficient RAM.
