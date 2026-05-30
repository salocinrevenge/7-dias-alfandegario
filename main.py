import pyray as rl
from pyray import Vector3, Vector2
import math
import asyncio
import time
import sys

from inspecting import draw_inspect_3d
from menu import draw_menu, draw_menu_bg_into_texture

IS_WEB = sys.platform == "emscripten"

# ---------------------------------------------------------------------------
# RENDER RESOLUTION
# ---------------------------------------------------------------------------
VIRTUAL_W = 960 * 0.5
VIRTUAL_H = 720 * 0.5

# ---------------------------------------------------------------------------
# SCENE CONSTANTS
# ---------------------------------------------------------------------------
TABLE_SCALE  = 1.0
TABLE_POS    = Vector3(0, 0, 0)

OBJECT_SIZE  = 0.15
OBJECT_Y     = 0.60
OBJECT_POS   = Vector3(0, OBJECT_Y + OBJECT_SIZE * 0.5, 0.0)

CAM_POS    = Vector3(0.0, 0.8, 0.7)
CAM_TARGET = Vector3(0, 0.68, 0.0)

_OBJECT_RADIUS = OBJECT_SIZE * 0.866

# ---------------------------------------------------------------------------
# ARCBALL MATH HELPERS
# ---------------------------------------------------------------------------
def _norm3(x, y, z):
    d = math.sqrt(x*x + y*y + z*z)
    return (x/d, y/d, z/d) if d > 1e-8 else (0.0, 0.0, 1.0)

def _screen_to_virtual(pos: Vector2, dst: rl.Rectangle) -> Vector2:
    if dst.width == 0 or dst.height == 0:
        return pos
    return Vector2(
        (pos.x - dst.x) / dst.width  * VIRTUAL_W,
        (pos.y - dst.y) / dst.height * VIRTUAL_H,
    )

# ---------------------------------------------------------------------------
# GAME STATES
# ---------------------------------------------------------------------------
class State:
    MENU    = "menu"
    INSPECT = "inspect"
    PAUSE   = "pause"

# ---------------------------------------------------------------------------
# TRANSITION MANAGER
# ---------------------------------------------------------------------------
class Transition:
    SPEED = 2.5

    def __init__(self):
        self.active       = False
        self.alpha        = 0.0
        self._fading_out  = True
        self.target_state = None
        self.done         = False

    def start(self, target_state: str):
        if self.active:
            return
        self.active       = True
        self.alpha        = 0.0
        self._fading_out  = True
        self.target_state = target_state
        self.done         = False

    def update(self, dt: float) -> str | None:
        self.done = False
        if not self.active:
            return None
        if self._fading_out:
            self.alpha += self.SPEED * dt
            if self.alpha >= 1.0:
                self.alpha       = 1.0
                self._fading_out = False
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
        rl.draw_rectangle(0, 0, rl.get_screen_width(), rl.get_screen_height(),
                          rl.Color(0, 0, 0, a))

_dx, _dy, _dz = (CAM_TARGET.x - CAM_POS.x,
                 CAM_TARGET.y - CAM_POS.y,
                 CAM_TARGET.z - CAM_POS.z)
_dl = math.sqrt(_dx*_dx + _dy*_dy + _dz*_dz) or 1.0
_INIT_CAM_YAW   = math.atan2(_dx / _dl, _dz / _dl)
_INIT_CAM_PITCH = math.asin(_dy / _dl)

# ---------------------------------------------------------------------------
# SCENE STATE
# ---------------------------------------------------------------------------
def make_scene_state() -> dict:
    return {
        "object_transform": rl.matrix_identity(),
        "dragging":   False,
        "drag_dir":   None,
        "spin_axis":  (0.0, 1.0, 0.0),
        "spin_angle": 0.0,
        "debug":     False,
        "cam_yaw":   _INIT_CAM_YAW,
        "cam_pitch": _INIT_CAM_PITCH,
        "cam_pos":   Vector3(CAM_POS.x, CAM_POS.y, CAM_POS.z),
    }

# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
def update_inspect(gs: dict, camera: rl.Camera3D, dt: float):
    if rl.is_key_pressed(rl.KEY_F1):
        gs["debug"] = not gs["debug"]
        if gs["debug"]:
            rl.disable_cursor()
        else:
            rl.enable_cursor()

    if gs["debug"]:
        _update_debug_camera(gs, camera, dt)
    else:
        _update_object(gs, camera)


def _arcball_point(ray, center: Vector3, radius: float):
    ox = center.x - ray.position.x
    oy = center.y - ray.position.y
    oz = center.z - ray.position.z
    dx, dy, dz = ray.direction.x, ray.direction.y, ray.direction.z

    tca = ox*dx + oy*dy + oz*dz
    d2  = (ox*ox + oy*oy + oz*oz) - tca*tca
    r2  = radius * radius
    on_sphere = d2 <= r2

    t = (tca - math.sqrt(r2 - d2)) if on_sphere else tca
    px = ray.position.x + dx*t
    py = ray.position.y + dy*t
    pz = ray.position.z + dz*t
    return _norm3(px - center.x, py - center.y, pz - center.z), on_sphere


def _update_object(gs: dict, camera: rl.Camera3D):
    dst  = get_scaled_rect()
    vpos = _screen_to_virtual(rl.get_mouse_position(), dst)
    ray  = rl.get_screen_to_world_ray_ex(vpos, camera, VIRTUAL_W, VIRTUAL_H)

    p1, on_object = _arcball_point(ray, OBJECT_POS, _OBJECT_RADIUS)

    if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and on_object:
        gs["dragging"]   = True
        gs["spin_angle"] = 0.0
        gs["drag_dir"]   = p1

    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
        gs["dragging"] = False

    if gs["dragging"] and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
        p0 = gs["drag_dir"]
        if p0 is not None:
            ax = p0[1]*p1[2] - p0[2]*p1[1]
            ay = p0[2]*p1[0] - p0[0]*p1[2]
            az = p0[0]*p1[1] - p0[1]*p1[0]
            axis_len = math.sqrt(ax*ax + ay*ay + az*az)

            if axis_len > 1e-6:
                dot   = max(-1.0, min(1.0, p0[0]*p1[0] + p0[1]*p1[1] + p0[2]*p1[2]))
                angle = math.acos(dot)
                na    = (ax/axis_len, ay/axis_len, az/axis_len)
                rot   = rl.matrix_rotate(Vector3(*na), angle)
                gs["object_transform"] = rl.matrix_multiply(gs["object_transform"], rot)
                gs["spin_axis"]  = na
                gs["spin_angle"] = angle

            gs["drag_dir"] = p1
    else:
        if gs["spin_angle"] > 1e-5:
            rot = rl.matrix_rotate(Vector3(*gs["spin_axis"]), gs["spin_angle"])
            gs["object_transform"] = rl.matrix_multiply(gs["object_transform"], rot)
        gs["spin_angle"] *= 0.88


def _update_debug_camera(gs: dict, camera: rl.Camera3D, dt: float):
    delta = rl.get_mouse_delta()
    gs["cam_yaw"]   -= delta.x * 0.003
    gs["cam_pitch"] -= delta.y * 0.003
    gs["cam_pitch"]  = max(-1.2, min(1.2, gs["cam_pitch"]))

    yaw, pitch = gs["cam_yaw"], gs["cam_pitch"]
    dx = math.sin(yaw) * math.cos(pitch)
    dy = math.sin(pitch)
    dz = math.cos(yaw) * math.cos(pitch)
    forward = Vector3(dx, dy, dz)
    right   = Vector3(math.cos(yaw), 0.0, -math.sin(yaw))

    speed = 3.0 * dt
    p = gs["cam_pos"]
    if rl.is_key_down(rl.KEY_W): p.x += forward.x*speed; p.y += forward.y*speed; p.z += forward.z*speed
    if rl.is_key_down(rl.KEY_S): p.x -= forward.x*speed; p.y -= forward.y*speed; p.z -= forward.z*speed
    if rl.is_key_down(rl.KEY_A): p.x += right.x*speed;   p.z += right.z*speed
    if rl.is_key_down(rl.KEY_D): p.x -= right.x*speed;   p.z -= right.z*speed

    camera.position = Vector3(p.x, p.y, p.z)
    camera.target   = Vector3(p.x + dx, p.y + dy, p.z + dz)

# ---------------------------------------------------------------------------
# DRAW FUNCTIONS
# ---------------------------------------------------------------------------



def draw_pause(font: rl.Font):
    """Pause overlay — solid black screen with centered PAUSED text."""
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    cx, cy = sw // 2, sh // 2
    rl.draw_rectangle(0, 0, sw, sh, rl.BLACK)

    def _measure(text: bytes, size: float) -> int:
        return int(rl.measure_text_ex(font, text, size, 1).x)

    def _draw(text: bytes, x: int, y: int, size: float, color):
        rl.draw_text_ex(font, text, rl.Vector2(float(x), float(y)), size, 1, color)

    title = b"PAUSADO"
    tw = _measure(title, 80)
    _draw(title, cx - tw // 2, cy - 24, 80, rl.WHITE)

    for i, text in enumerate((b"[P] Resumir", b"[M] Menu Inicial")):
        w = _measure(text, 40)
        _draw(text, cx - w // 2, cy + 62 + i * 38, 40, rl.Color(180, 180, 180, 200))

# ---------------------------------------------------------------------------
# RENDER-TEXTURE SCALING (letterbox / pillarbox)
# ---------------------------------------------------------------------------

def draw_inspect_hud(gs: dict, dst: rl.Rectangle):
    """Inspect HUD — drawn directly on screen after the shader blit."""
    bx = int(dst.x) + 8
    by = int(dst.y + dst.height) - 20
    if gs.get("debug"):
        rl.draw_text(b"DEBUG CAM  [WASD] Move  [Mouse] Look  [F1] Exit",
                     bx, by, 11, rl.Color(80, 220, 80, 220))
    else:
        rl.draw_text(
            b"[LMB] Rotate   [P] Pause   [F] Fullscreen   [F1] Debug cam   [K] Painting",
            bx, by, 11, rl.Color(120, 100, 65, 190))

def get_scaled_rect() -> rl.Rectangle:
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    scale  = min(sw / VIRTUAL_W, sh / VIRTUAL_H)
    dw, dh = VIRTUAL_W * scale, VIRTUAL_H * scale
    return rl.Rectangle((sw - dw) / 2, (sh - dh) / 2, dw, dh)

# ---------------------------------------------------------------------------
# SHADER HELPER
# --------------------------------------------------------------
def _set_shader_resolution(shader, loc: int, w: float, h: float):
    """Push the render-texture resolution into the painting shader."""
    res = rl.ffi.new("float[2]", [w, h])
    rl.set_shader_value(shader, loc, res, rl.SHADER_UNIFORM_VEC2)

def load_textures(textures: dict):
    textures["bg"]   = rl.load_texture(b"models/env/wizard_room.jpg")
    textures["menu_bg"] = rl.load_texture(b"models/env/outside2.jpg")
    textures["tropiland_font"] = rl.load_font_ex(b"fonts/TropiLand.ttf", 128, None, 0)
    rl.set_texture_filter(textures["bg"], rl.TEXTURE_FILTER_BILINEAR)
    rl.set_texture_filter(textures["menu_bg"], rl.TEXTURE_FILTER_BILINEAR)
    rl.set_texture_filter(textures["tropiland_font"].texture, rl.TEXTURE_FILTER_BILINEAR)

def load_models(models: dict):
    models["table"]  = rl.load_model(b"models/env/chinese_tea_table_2k.gltf")
    models["object"] = rl.load_model(b"models/objects/mantel_clock_01_1k.gltf")

def unload_textures(textures: dict):
    rl.unload_texture(textures["bg"])
    rl.unload_texture(textures["menu_bg"])
    rl.unload_font(textures["tropiland_font"])

def unload_models(models: dict):
    rl.unload_model(models["table"])
    rl.unload_model(models["object"])

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
async def main():
    global VIRTUAL_W, VIRTUAL_H

    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
    rl.init_window(1000, 700, b"The Enigma")
    rl.set_target_fps(60)
    rl.enable_cursor()

    windowed_w, windowed_h = 1000, 700

    VIRTUAL_W, VIRTUAL_H = rl.get_screen_width(), rl.get_screen_height()
    render_tex = rl.load_render_texture(VIRTUAL_W, VIRTUAL_H)
    rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
    src_rect = rl.Rectangle(0, 0, VIRTUAL_W, -VIRTUAL_H)

    # --- Models & textures ---
    models: dict = {}
    textures: dict = {}
    load_models(models)
    load_textures(textures)

    # --- Painting shader (Kuwahara) ---
    # WebGL (pygbag/Emscripten) needs GLSL ES 1.0; desktop uses GLSL 3.3.
    _fs = b"textures/shaders/painting_web.fs" if IS_WEB else b"textures/shaders/painting.fs"
    painting_shader  = rl.load_shader(b"", _fs)
    shader_res_loc   = rl.get_shader_location(painting_shader, b"resolution")
    painting_enabled = True                          # [K] toggles this
    _set_shader_resolution(painting_shader, shader_res_loc, VIRTUAL_W, VIRTUAL_H)

    # --- Camera ---
    camera            = rl.Camera3D()
    camera.position   = CAM_POS
    camera.target     = CAM_TARGET
    camera.up         = Vector3(0, 1, 0)
    camera.fovy       = 55.0
    camera.projection = rl.CAMERA_PERSPECTIVE

    # --- State machine ---
    current_state      = State.MENU
    prev_inspect_drawn = False
    gs: dict           = {}
    transition         = Transition()
    prev_time          = time.time()

    while not rl.window_should_close():
        now = time.time()
        dt  = now - prev_time
        prev_time = now

        # -------------------------------------------------------------- #
        #  RENDER TEXTURE RESIZE                                           #
        # -------------------------------------------------------------- #
        sw, sh = rl.get_screen_width(), rl.get_screen_height()
        if sw > 0 and sh > 0 and (sw != VIRTUAL_W or sh != VIRTUAL_H):
            rl.unload_render_texture(render_tex)
            VIRTUAL_W, VIRTUAL_H = sw, sh
            render_tex = rl.load_render_texture(VIRTUAL_W, VIRTUAL_H)
            rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
            src_rect = rl.Rectangle(0, 0, VIRTUAL_W, -VIRTUAL_H)
            # Keep shader resolution uniform in sync
            _set_shader_resolution(painting_shader, shader_res_loc, VIRTUAL_W, VIRTUAL_H)

        # -------------------------------------------------------------- #
        #  FULLSCREEN TOGGLE                                               #
        # -------------------------------------------------------------- #
        if rl.is_key_pressed(rl.KEY_F):
            if rl.is_window_fullscreen():
                rl.toggle_fullscreen()
                rl.set_window_size(windowed_w, windowed_h)
            else:
                windowed_w = rl.get_screen_width()
                windowed_h = rl.get_screen_height()
                monitor   = rl.get_current_monitor()
                rl.set_window_size(rl.get_monitor_width(monitor),
                                   rl.get_monitor_height(monitor))
                rl.toggle_fullscreen()

        # -------------------------------------------------------------- #
        #  PAINTING SHADER TOGGLE                                          #
        # -------------------------------------------------------------- #
        if rl.is_key_pressed(rl.KEY_K):
            painting_enabled = not painting_enabled

        # -------------------------------------------------------------- #
        #  TRANSITION UPDATE                                               #
        # -------------------------------------------------------------- #
        new_state = transition.update(dt)
        if new_state is not None:
            current_state = new_state

        # -------------------------------------------------------------- #
        #  INPUT / UPDATE                                                  #
        # -------------------------------------------------------------- #
        if not transition.active or not transition._fading_out:
            if current_state == State.MENU:
                if rl.is_key_pressed(rl.KEY_ENTER):
                    gs = make_scene_state()
                    transition.start(State.INSPECT)

            elif current_state == State.INSPECT:
                if rl.is_key_pressed(rl.KEY_P):
                    if gs.get("debug"):
                        gs["debug"] = False
                        rl.enable_cursor()
                    transition.start(State.PAUSE)
                else:
                    update_inspect(gs, camera, dt)

            elif current_state == State.PAUSE:
                if rl.is_key_pressed(rl.KEY_P):
                    transition.start(State.INSPECT)
                elif rl.is_key_pressed(rl.KEY_M):
                    transition.start(State.MENU)

        # -------------------------------------------------------------- #
        #  DRAW INTO RENDER TEXTURE  (3D scene only — no overlays)         #
        # -------------------------------------------------------------- #
        rl.begin_texture_mode(render_tex)

        if current_state == State.MENU:
            draw_menu_bg_into_texture(textures["menu_bg"], VIRTUAL_W, VIRTUAL_H)

        elif current_state == State.INSPECT:
            draw_inspect_3d(gs, camera, models, textures, VIRTUAL_W, VIRTUAL_H, TABLE_POS, TABLE_SCALE, OBJECT_POS)
            prev_inspect_drawn = True

        elif current_state == State.PAUSE:
            # Keep the 3D scene visible under the pause overlay
            if prev_inspect_drawn:
                print("Drawing paused scene into texture...")
                draw_inspect_3d(gs, camera, models, textures, VIRTUAL_W, VIRTUAL_H, TABLE_POS, TABLE_SCALE, OBJECT_POS)
            else:
                rl.clear_background(rl.BLACK)

        rl.end_texture_mode()

        # -------------------------------------------------------------- #
        #  BLIT RENDER TEXTURE → SCREEN  (with optional painting shader)  #
        # -------------------------------------------------------------- #
        rl.begin_drawing()
        rl.clear_background(rl.BLACK)

        dst = get_scaled_rect()

        if painting_enabled:
            rl.begin_shader_mode(painting_shader)

        rl.draw_texture_pro(
            render_tex.texture,
            src_rect,
            dst,
            Vector2(0, 0),
            0.0,
            rl.WHITE,
        )

        if painting_enabled:
            rl.end_shader_mode()

        # ---- Overlays (unaffected by the painting shader) ---------------
        if current_state == State.MENU:
            draw_menu(now, dst, textures["tropiland_font"])

        elif current_state == State.INSPECT:
            draw_inspect_hud(gs, dst)

        elif current_state == State.PAUSE:
            draw_pause(textures["tropiland_font"])
            draw_inspect_hud(gs, dst)

        # Transition fade drawn on top of everything
        transition.draw()

        # Shader toggle indicator
        label = b"[K] Painting: ON " if painting_enabled else b"[K] Painting: OFF"
        col   = rl.Color(220, 175, 70, 200) if painting_enabled else rl.Color(100, 90, 70, 140)
        rl.draw_text(label, 8, 8, 11, col)

        rl.end_drawing()

        await asyncio.sleep(0)

    # --- Cleanup ---
    rl.unload_shader(painting_shader)
    rl.unload_render_texture(render_tex)
    unload_models(models)
    unload_textures(textures)
    rl.close_window()


if __name__ == "__main__":
    asyncio.run(main())
