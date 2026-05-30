# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cover-Jam** is a 3D game built with Python using `raylib` for graphics and `pygbag` for web deployment. It's a dodging game where the player controls a character, avoids enemies and projectiles, and can wield a sword. The game features a state machine with menu, gameplay, and pause states with smooth fade transitions.

## Build & Run Commands

### Setup
```bash
uv sync  # Install dependencies from lock file
```

### Run Desktop
```bash
uv run python main.py
```

### Run on Web
```bash
uv run python -m pygbag .
```

### Install Script
The `install.sh` script in the root performs initial setup (equivalent to running `uv sync`).

## Project Structure

- **main.py** – Single-file game implementation (~500 lines)
  - `State` enum: Game states (MENU, GAMEPLAY, PAUSE)
  - `Transition` class: Fade-to-black animation manager for state transitions
  - Helper functions: collision detection, vector math, grid rendering
  - Game data: `make_game_state()` creates player/enemy/projectile state as plain dicts
  - Update logic: `update_gameplay()` handles input, physics, enemies, collisions
  - Draw functions: `draw_menu()`, `draw_gameplay()`, `draw_pause()`
  - Main loop: Async loop using `raylib` (via `pyray` binding) with render-to-texture for scaling

- **Assets:**
  - `sword_2handed.gltf` / `sword_2handed.bin` – 3D sword model
  - `Mage.glb` – Enemy model
  - `cube.glb` – Unused model asset
  - `knight_texture.png` – Texture file

- **Web deployment:**
  - `web.tmpl` – Jinja2 template for pygbag (generates loader HTML)
  - `uv.lock` – Locked dependency versions

- **Config:**
  - `pyproject.toml` – Project metadata and dependencies (raylib >=5.5.0.4, pygbag >=0.9.3, Python >=3.14)
  - `.python-version` – Python 3.14

## Architecture Notes

### State Machine with Transitions
The game uses a three-state machine (menu → gameplay ↔ pause) with animated `Transition` objects that fade to black before swapping state. This happens at the peak black fade, ensuring smooth visual transitions.

### Render-to-Texture Scaling
Game renders to a virtual resolution (470×360) inside a render texture, then scales and letterboxes it to fit the screen. This maintains consistent gameplay appearance across different window sizes.

### Game Data as Dicts
All game state (player position/velocity, enemies, projectiles, camera) is stored in plain Python dicts initialized by `make_game_state()`, making state reset trivial. No classes for game objects.

### Async Loop
Main loop is async using `asyncio`, required for pygbag web compatibility. Frame timing uses `time.time()` and delta-time calculations.

### Input Handling
- **WASD**: Movement (relative to camera forward/right)
- **SPACE**: Jump
- **Right Mouse**: Rotate sword (when held)
- **Mouse (free)**: Rotate camera (unless RMB held)
- **P**: Pause/Resume
- **M**: Return to menu from pause
- **F**: Fullscreen toggle
- **F5**: Toggle 3rd person camera
- **ENTER** (menu only): Start game

### Collision System
Simple axis-aligned bounding box (AABB) checks with dict-based collision boxes (`{"min": Vector3, "max": Vector3}`). Player takes damage on enemy or projectile collision with invulnerability cooldown.

### Camera System
First-person by default; F5 toggles to third-person. Camera follows player with pitch/yaw clamped. Sword rotates independently of camera via mouse RMB.

## Testing & Debugging

There are no automated tests in this repository. Manual testing via `uv run python main.py` is the standard approach. The game logs no debug output; use print statements or a debugger for troubleshooting.

## Dependencies

- **raylib (5.5.0.4+)** – 3D graphics and input
- **pygbag (0.9.3+)** – Python-to-web compiler (Pyodide-based)
- **pyray** – Python bindings for raylib (installed as dependency of raylib)

## Notes for Development

- Game is single-file; keep physics, rendering, and state management cohesive
- Virtual resolution (470×360) is hardcoded; changing requires updating `VIRTUAL_W`/`VIRTUAL_H` and render texture size
- Asset loading happens at startup; model/texture paths are relative to the working directory
- Fullscreen toggle preserves windowed dimensions on toggle-back
- Pause state freezes gameplay but re-renders the scene; uses `prev_gameplay_drawn` to cache the last drawn frame
