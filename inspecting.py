import math
import pyray as rl
from pyray import Vector2, Vector3

from game_context import Game_context
from utils import get_scaled_rect, _screen_to_virtual


def _elastic_out(t: float) -> float:
    """Overshoots slightly then settles — gives the paper a springy pop."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    p = 0.35
    return pow(2.0, -10.0 * t) * math.sin((t - p / 4.0) * (2.0 * math.pi) / p) + 1.0


def _elastic_in(t: float) -> float:
    """Reverse of elastic_out — snaps back quickly."""
    return 1.0 - _elastic_out(1.0 - t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _draw_paper(gc: Game_context, t_raw: float):
    """Draw the paper model with a fully interpolated transform (position + two rotation axes + scale)."""
    opening = gc.gs["paper_open"]
    # Use elastic-out when opening (spring into place), elastic-in when closing (snap away)
    t_e = _elastic_out(t_raw) if opening else _elastic_in(t_raw)

    # --- Interpolate position ---
    p0 = gc.PAPER_POS
    p1 = gc.PAPER_FRONT_POS
    px = _lerp(p0.x, p1.x, t_e)
    py = _lerp(p0.y, p1.y, t_e)
    pz = _lerp(p0.z, p1.z, t_e)

    # --- Interpolate rotation angles ---
    rx_deg = _lerp(gc.PAPER_REST_ROT_X, gc.PAPER_OPEN_ROT_X, t_e)
    ry_deg = _lerp(gc.PAPER_REST_ROT_Y, gc.PAPER_OPEN_ROT_Y, t_e)

    # --- Interpolate scale ---
    s = _lerp(1.0, 0.6, t_e)

    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)

    # Build transform: scale → rotateX → rotateY → translate
    mat = rl.matrix_scale(s, s, s)
    mat = rl.matrix_multiply(mat, rl.matrix_rotate_x(rx))
    mat = rl.matrix_multiply(mat, rl.matrix_rotate_y(ry))
    mat = rl.matrix_multiply(mat, rl.matrix_translate(px, py, pz))

    gc.models["paper"].transform = mat
    rl.draw_model(gc.models["paper"], Vector3(0, 0, 0), 1.0, rl.WHITE)
    # Reset transform so the bounding-box raycast still works against PAPER_POS
    gc.models["paper"].transform = rl.matrix_identity()


def draw_inspect_3d(gc: Game_context):
    """Draws the 3D scene into the render texture (no overlays)."""
    rl.clear_background(rl.BLACK)

    rl.draw_texture_pro(
        gc.textures["bg"],
        rl.Rectangle(0, 0, gc.textures["bg"].width, gc.textures["bg"].height),
        rl.Rectangle(0, 0, gc.VIRTUAL_W, gc.VIRTUAL_H),
        Vector2(0, 0), 0.0, rl.Color(255, 185, 185, 255),
    )

    rl.begin_mode_3d(gc.camera)
    rl.draw_model(gc.models["table"], gc.TABLE_POS, gc.TABLE_SCALE, rl.WHITE)
    _draw_paper(gc, gc.gs.get("paper_anim_t", 0.0))
    rl.end_mode_3d()


def update_inspect(gc: Game_context, dt: float):
    if rl.is_key_pressed(rl.KEY_F1):
        gc.gs["debug"] = not gc.gs["debug"]
        if gc.gs["debug"]:
            rl.disable_cursor()
        else:
            rl.enable_cursor()

    if gc.gs["debug"]:
        gc.player.update_debug_camera(dt)
        return

    # Drive animation t toward 1 (opening) or 0 (closing)
    target = 1.0 if gc.gs["paper_open"] else 0.0
    current = gc.gs["paper_anim_t"]
    if current != target:
        step = gc.PAPER_ANIM_SPEED * dt
        if target > current:
            gc.gs["paper_anim_t"] = min(target, current + step)
        else:
            gc.gs["paper_anim_t"] = max(target, current - step)

    # While open, clicking or pressing E starts the close animation
    if gc.gs["paper_open"]:
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) or rl.is_key_pressed(rl.KEY_E):
            gc.gs["paper_open"] = False
        return

    # Raycast against the rest-position bounding box to open
    dst  = get_scaled_rect(gc)
    vpos = _screen_to_virtual(gc, rl.get_mouse_position(), dst)
    ray  = rl.get_screen_to_world_ray_ex(vpos, gc.camera, gc.VIRTUAL_W, gc.VIRTUAL_H)

    hw, hh = gc.PAPER_W / 2, gc.PAPER_H / 2
    p = gc.PAPER_POS
    paper_box = rl.BoundingBox(
        Vector3(p.x - hw, p.y - 0.01, p.z - hh),
        Vector3(p.x + hw, p.y + 0.02, p.z + hh),
    )
    col = rl.get_ray_collision_box(ray, paper_box)
    if col.hit and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
        gc.gs["paper_open"] = True
