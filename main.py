import pyray as rl
from pyray import Vector3, Vector2
import math
import asyncio
import random
import time

# ---------------------------------------------------------------------------
# VIRTUAL RESOLUTION  (the game always renders at this size, then is scaled)
# ---------------------------------------------------------------------------
VIRTUAL_W = 470
VIRTUAL_H = 360

# ---------------------------------------------------------------------------
# GAME STATES
# ---------------------------------------------------------------------------
class State:
    MENU     = "menu"
    GAMEPLAY = "gameplay"
    PAUSE    = "pause"

# ---------------------------------------------------------------------------
# TRANSITION MANAGER
# ---------------------------------------------------------------------------
class Transition:
    """Handles fade-to-black animated transitions between states.

    Usage:
        transition.start(State.GAMEPLAY)   # kicks off a fade-out → swap → fade-in
        transition.update(dt)              # call every frame
        transition.draw()                  # draws the black overlay
        transition.done                    # True once fully faded in again
    """
    SPEED = 2.5          # fade units per second (0-1 range)

    def __init__(self):
        self.active       = False
        self.alpha        = 0.0          # 0 = transparent, 1 = fully black
        self._fading_out  = True         # True = going to black, False = coming back
        self.target_state = None
        self.done         = False        # pulses True for one frame when complete

    def start(self, target_state: str):
        if self.active:
            return
        self.active       = True
        self.alpha        = 0.0
        self._fading_out  = True
        self.target_state = target_state
        self.done         = False

    def update(self, dt: float) -> str | None:
        """Returns the new state name the moment the screen is fully black,
        so the caller can swap state exactly then. Returns None otherwise."""
        self.done = False
        if not self.active:
            return None

        if self._fading_out:
            self.alpha += self.SPEED * dt
            if self.alpha >= 1.0:
                self.alpha      = 1.0
                self._fading_out = False
                # Signal caller to swap state NOW (screen is black)
                return self.target_state
        else:
            self.alpha -= self.SPEED * dt
            if self.alpha <= 0.0:
                self.alpha  = 0.0
                self.active = False
                self.done   = True

        return None

    def draw(self):
        if not self.active and self.alpha == 0.0:
            return
        a = int(self.alpha * 255)
        rl.draw_rectangle(0, 0, VIRTUAL_W, VIRTUAL_H, rl.Color(0, 0, 0, a))

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def draw_grid(size=20, spacing=1.0):
    for i in range(-size, size + 1):
        rl.draw_line_3d(Vector3(i * spacing, 0, -size * spacing),
                        Vector3(i * spacing, 0,  size * spacing), rl.GRAY)
        rl.draw_line_3d(Vector3(-size * spacing, 0, i * spacing),
                        Vector3( size * spacing, 0, i * spacing), rl.GRAY)

def check_collision(box1, box2):
    return (
        box1["min"].x <= box2["max"].x and box1["max"].x >= box2["min"].x and
        box1["min"].y <= box2["max"].y and box1["max"].y >= box2["min"].y and
        box1["min"].z <= box2["max"].z and box1["max"].z >= box2["min"].z
    )

def make_box(center, size):
    return {
        "min": Vector3(center.x - size.x/2, center.y - size.y/2, center.z - size.z/2),
        "max": Vector3(center.x + size.x/2, center.y + size.y/2, center.z + size.z/2),
    }

def normalize_v3(v: Vector3) -> Vector3:
    d = math.sqrt(v.x**2 + v.y**2 + v.z**2)
    if d == 0:
        return Vector3(0, 0, 0)
    return Vector3(v.x/d, v.y/d, v.z/d)

# ---------------------------------------------------------------------------
# GAME DATA  (plain dict, easy to reset)
# ---------------------------------------------------------------------------
def make_game_state():
    enemies = []
    for _ in range(3):
        enemies.append({
            "pos":      Vector3(random.uniform(-10, 10), 1, random.uniform(-10, 10)),
            "dir":      random.uniform(0, math.tau),
            "speed":    0.05,
            "cooldown": time.time() + random.uniform(1, 3),
        })
    return {
        "player_pos":        Vector3(0, 1, 0),
        "player_size":       Vector3(1, 2, 1),
        "player_speed":      0.2,
        "player_vel_y":      0.0,
        "on_ground":         True,
        "lives":             5,
        "invulnerable_until":0.0,
        "camera_pitch":      -0.3,
        "camera_yaw":        0.0,
        "third_person":      False,
        "camera_distance":   6.0,
        "sword_rotation_x":  0.0,
        "sword_rotation_y":  0.0,
        "enemies":           enemies,
        "projectiles":       [],
    }

# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
def update_gameplay(gs: dict, camera: rl.Camera3D, dt: float):
    now = time.time()

    # --- Camera toggle ---
    if rl.is_key_pressed(rl.KEY_F5):
        gs["third_person"] = not gs["third_person"]

    mouse_delta = rl.get_mouse_delta()

    # --- Sword / camera rotation ---
    if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT):
        gs["sword_rotation_y"] -= mouse_delta.x * 0.01
        gs["sword_rotation_x"] -= mouse_delta.y * 0.01
    else:
        gs["camera_yaw"]   -= mouse_delta.x * 0.003
        gs["camera_pitch"] -= mouse_delta.y * 0.003
    gs["camera_pitch"] = max(-1.2, min(1.2, gs["camera_pitch"]))

    yaw, pitch = gs["camera_yaw"], gs["camera_pitch"]
    dir_x = math.sin(yaw) * math.cos(pitch)
    dir_y = math.sin(pitch)
    dir_z = math.cos(yaw) * math.cos(pitch)
    forward = Vector3(dir_x, dir_y, dir_z)
    right   = Vector3(math.cos(yaw), 0, -math.sin(yaw))

    # Store for draw step
    gs["_dir"]     = (dir_x, dir_y, dir_z)
    gs["_forward"] = forward
    gs["_right"]   = right

    # --- Player movement ---
    move = Vector3(0, 0, 0)
    if rl.is_key_down(rl.KEY_W): move.x += forward.x; move.z += forward.z
    if rl.is_key_down(rl.KEY_S): move.x -= forward.x; move.z -= forward.z
    if rl.is_key_down(rl.KEY_A): move.x += right.x;   move.z += right.z
    if rl.is_key_down(rl.KEY_D): move.x -= right.x;   move.z -= right.z

    length = math.sqrt(move.x**2 + move.z**2)
    if length:
        move.x /= length
        move.z /= length

    gs["player_pos"].x += move.x * gs["player_speed"]
    gs["player_pos"].z += move.z * gs["player_speed"]

    # --- Jump ---
    if rl.is_key_pressed(rl.KEY_SPACE) and gs["on_ground"]:
        gs["player_vel_y"] = 0.35
        gs["on_ground"]    = False

    gs["player_vel_y"] -= 0.02
    gs["player_pos"].y += gs["player_vel_y"]
    if gs["player_pos"].y <= 1:
        gs["player_pos"].y = 1
        gs["player_vel_y"] = 0
        gs["on_ground"]    = True

    # --- Enemies ---
    for enemy in gs["enemies"]:
        enemy["pos"].x += math.cos(enemy["dir"]) * enemy["speed"]
        enemy["pos"].z += math.sin(enemy["dir"]) * enemy["speed"]
        if abs(enemy["pos"].x) > 19 or abs(enemy["pos"].z) > 19:
            enemy["dir"] += math.pi / 2
        if now >= enemy["cooldown"]:
            dp = Vector3(gs["player_pos"].x - enemy["pos"].x,
                         0,
                         gs["player_pos"].z - enemy["pos"].z)
            d = math.sqrt(dp.x**2 + dp.z**2)
            if d:
                dp.x /= d; dp.z /= d
            gs["projectiles"].append({
                "pos":   Vector3(enemy["pos"].x, 1.5, enemy["pos"].z),
                "vel":   Vector3(dp.x * 0.3, 0, dp.z * 0.3),
                "spawn": now,
            })
            enemy["cooldown"] = now + random.uniform(2, 5)

    # --- Projectiles ---
    live = []
    for p in gs["projectiles"]:
        p["pos"].x += p["vel"].x
        p["pos"].y += p["vel"].y
        p["pos"].z += p["vel"].z
        if now - p["spawn"] < 5:
            live.append(p)
    gs["projectiles"] = live

    # --- Collisions ---
    player_box = make_box(gs["player_pos"], gs["player_size"])
    if now > gs["invulnerable_until"]:
        for enemy in gs["enemies"]:
            if check_collision(player_box, make_box(enemy["pos"], Vector3(1, 2, 1))):
                gs["lives"] -= 1
                gs["invulnerable_until"] = now + 3
                break
        live2 = []
        for p in gs["projectiles"]:
            if check_collision(player_box, make_box(p["pos"], Vector3(0.5, 0.5, 0.5))):
                gs["lives"] -= 1
                gs["invulnerable_until"] = now + 3
            else:
                live2.append(p)
        gs["projectiles"] = live2

    # --- Update camera struct ---
    pp    = gs["player_pos"]
    dx, dy, dz = gs["_dir"]
    if gs["third_person"]:
        dist = gs["camera_distance"]
        camera.position = Vector3(pp.x - dx*dist, pp.y + 2 - dy*dist, pp.z - dz*dist)
    else:
        camera.position = Vector3(pp.x, pp.y + 1.5, pp.z)
    camera.target = Vector3(pp.x + dx, pp.y + 1.5 + dy, pp.z + dz)

# ---------------------------------------------------------------------------
# DRAW  (always called inside begin_texture_mode / end_texture_mode)
# ---------------------------------------------------------------------------
def draw_menu(now: float):
    """Menu screen drawn into the virtual render texture."""
    rl.clear_background(rl.Color(15, 15, 25, 255))

    # Animated title
    t = now * 1.5
    offset_y = int(math.sin(t) * 4)

    title = b"Cover-Jam 2026"
    tw = rl.measure_text(title, 52)
    rl.draw_text(title, VIRTUAL_W//2 - tw//2, 90 + offset_y, 52, rl.Color(255, 80, 60, 255))

    # Subtitle
    sub = b"Don't judge a book by its cover"
    sw = rl.measure_text(sub, 18)
    rl.draw_text(sub, VIRTUAL_W//2 - sw//2, 155, 18, rl.Color(180, 180, 200, 220))

    # Pulsing ENTER prompt
    pulse = int((math.sin(now * 3) * 0.5 + 0.5) * 200 + 55)
    prompt = b"Press ENTER to Play"
    pw = rl.measure_text(prompt, 22)
    rl.draw_text(prompt, VIRTUAL_W//2 - pw//2, 230, 22, rl.Color(255, 220, 80, pulse))

    # Controls hint
    hints = b"[F] Fullscreen   [F5] Toggle camera"
    hw = rl.measure_text(hints, 14)
    rl.draw_text(hints, VIRTUAL_W//2 - hw//2, VIRTUAL_H - 30, 14, rl.Color(120, 120, 140, 200))


def draw_gameplay(gs: dict, camera: rl.Camera3D, model, enemy_model, cube_pos):
    now = time.time()
    rl.clear_background(rl.RAYWHITE)

    rl.begin_mode_3d(camera)
    draw_grid(20, 1.0)

    # Player (blink when invulnerable)
    blink = (now * 10) % 2 < 1
    if now < gs["invulnerable_until"]:
        if blink:
            rl.draw_cube(gs["player_pos"], 1, 2, 1, rl.BLUE)
    else:
        rl.draw_cube(gs["player_pos"], 1, 2, 1, rl.BLUE)

    for enemy in gs["enemies"]:
        rl.draw_model(enemy_model, enemy["pos"], 1.0, rl.WHITE)

    for p in gs["projectiles"]:
        rl.draw_sphere(p["pos"], 0.3, rl.ORANGE)

    # Sword
    model.transform = rl.matrix_multiply(
        rl.matrix_scale(1.0, 1.0, 1.0),
        rl.matrix_rotate_xyz(Vector3(gs["sword_rotation_x"], gs["sword_rotation_y"], 0.0))
    )
    rl.draw_model(model, cube_pos, 1.0, rl.WHITE)

    rl.end_mode_3d()

    # HUD — lives
    for i in range(gs["lives"]):
        rl.draw_rectangle(10 + i * 28, 10, 22, 22, rl.RED)

    if now < gs["invulnerable_until"]:
        rl.draw_text(b"INVULNERAVEL", 10, 40, 20, rl.GOLD)

    rl.draw_text(b"[P] Pause  [F] Fullscreen  [F5] Camera  [RMB] Sword", 10, VIRTUAL_H - 22, 13, rl.GRAY)


def draw_pause(gs: dict):
    # Simple semi-transparent dim over the frozen gameplay
    rl.draw_rectangle(0, 0, VIRTUAL_W, VIRTUAL_H, rl.Color(0, 0, 0, 120))

    title = b"PAUSED"
    tw = rl.measure_text(title, 40)
    rl.draw_text(title, VIRTUAL_W//2 - tw//2, VIRTUAL_H//2 - 40, 40, rl.WHITE)

    hint1 = b"[P] Resume"
    h1w = rl.measure_text(hint1, 18)
    rl.draw_text(hint1, VIRTUAL_W//2 - h1w//2, VIRTUAL_H//2 + 10, 18, rl.Color(200, 200, 200, 230))

    hint2 = b"[M] Main Menu"
    h2w = rl.measure_text(hint2, 18)
    rl.draw_text(hint2, VIRTUAL_W//2 - h2w//2, VIRTUAL_H//2 + 34, 18, rl.Color(200, 200, 200, 230))

# ---------------------------------------------------------------------------
# SCALE RENDER TEXTURE TO SCREEN  (letterbox + pillarbox — always centred)
# ---------------------------------------------------------------------------
def get_scaled_rect() -> rl.Rectangle:
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    scale  = min(sw / VIRTUAL_W, sh / VIRTUAL_H)   # fit inside the window
    dw, dh = VIRTUAL_W * scale, VIRTUAL_H * scale
    ox     = (sw - dw) / 2   # centre horizontally
    oy     = (sh - dh) / 2   # centre vertically
    return rl.Rectangle(ox, oy, dw, dh)

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
async def main():
    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
    rl.init_window(1000, 700, b"Cube Dodge 3D")
    rl.set_target_fps(60)
    rl.disable_cursor()

    # --- Windowed size (saved so fullscreen can restore it) ---
    windowed_w, windowed_h = 1000, 700

    # --- Render texture (virtual canvas) ---
    render_tex = rl.load_render_texture(VIRTUAL_W, VIRTUAL_H)
    rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)

    # Source rect for the render texture (Y is flipped in OpenGL)
    src_rect = rl.Rectangle(0, 0, VIRTUAL_W, -VIRTUAL_H)

    # --- Models & shared assets ---
    model       = rl.load_model(b"sword_2handed.gltf")
    enemy_model = rl.load_model(b"Mage.glb")
    cube_pos    = Vector3(0.0, 0.5, 0.0)

    # --- Camera ---
    camera       = rl.Camera3D()
    camera.up    = Vector3(0, 1, 0)
    camera.fovy  = 90
    camera.projection = rl.CAMERA_PERSPECTIVE

    # --- State machine ---
    current_state = State.MENU
    prev_gameplay_drawn = False  # lets pause show a frozen gameplay background

    # --- Game data ---
    gs: dict = {}

    # --- Transition ---
    transition = Transition()

    prev_time = time.time()

    while not rl.window_should_close():
        now = time.time()
        dt  = now - prev_time
        prev_time = now

        # ------------------------------------------------------------------ #
        #  GLOBAL HOTKEYS  (active in all states)                             #
        # ------------------------------------------------------------------ #
        if rl.is_key_pressed(rl.KEY_F):
            if rl.is_window_fullscreen():
                # Leaving fullscreen — restore saved windowed size
                rl.toggle_fullscreen()
                rl.set_window_size(windowed_w, windowed_h)
            else:
                # Entering fullscreen — save current size, resize to monitor
                windowed_w = rl.get_screen_width()
                windowed_h = rl.get_screen_height()
                monitor = rl.get_current_monitor()
                mon_w    = rl.get_monitor_width(monitor)
                mon_h    = rl.get_monitor_height(monitor)
                rl.set_window_size(mon_w, mon_h)
                rl.toggle_fullscreen()

        # ------------------------------------------------------------------ #
        #  TRANSITION UPDATE  (swap state at blackout peak)                   #
        # ------------------------------------------------------------------ #
        new_state = transition.update(dt)
        if new_state is not None:
            current_state = new_state
            # Re-enable/disable cursor as needed
            if current_state == State.GAMEPLAY:
                rl.disable_cursor()
            else:
                rl.enable_cursor()

        # ------------------------------------------------------------------ #
        #  INPUT / UPDATE  (only when not mid-transition)                     #
        # ------------------------------------------------------------------ #
        if not transition.active or not transition._fading_out:
            if current_state == State.MENU:
                if rl.is_key_pressed(rl.KEY_ENTER):
                    gs = make_game_state()
                    transition.start(State.GAMEPLAY)

            elif current_state == State.GAMEPLAY:
                if rl.is_key_pressed(rl.KEY_P):
                    transition.start(State.PAUSE)
                else:
                    update_gameplay(gs, camera, dt)

            elif current_state == State.PAUSE:
                if rl.is_key_pressed(rl.KEY_P):
                    transition.start(State.GAMEPLAY)
                elif rl.is_key_pressed(rl.KEY_M):
                    transition.start(State.MENU)

        # ------------------------------------------------------------------ #
        #  DRAW INTO RENDER TEXTURE                                           #
        # ------------------------------------------------------------------ #
        rl.begin_texture_mode(render_tex)

        if current_state == State.MENU:
            draw_menu(now)

        elif current_state == State.GAMEPLAY:
            draw_gameplay(gs, camera, model, enemy_model, cube_pos)
            prev_gameplay_drawn = True

        elif current_state == State.PAUSE:
            # Draw the frozen gameplay underneath the pause overlay
            if prev_gameplay_drawn:
                draw_gameplay(gs, camera, model, enemy_model, cube_pos)
            draw_pause(gs)

        # Transition overlay (black fade)
        transition.draw()

        rl.end_texture_mode()

        # ------------------------------------------------------------------ #
        #  BLIT RENDER TEXTURE → SCREEN  (scaled, letterboxed)               #
        # ------------------------------------------------------------------ #
        dst_rect = get_scaled_rect()

        rl.begin_drawing()
        rl.clear_background(rl.BLACK)   # letterbox / pillarbox bars
        rl.draw_texture_pro(
            render_tex.texture,
            src_rect,
            dst_rect,
            Vector2(0, 0),
            0.0,
            rl.WHITE
        )
        rl.end_drawing()

        await asyncio.sleep(0)

    # Cleanup
    rl.unload_render_texture(render_tex)
    rl.unload_model(model)
    rl.unload_model(enemy_model)
    rl.close_window()


if __name__ == "__main__":
    asyncio.run(main())
