import math
import pyray as rl
from pyray import Vector2, Vector3

from game_context import Game_context, PAPER_TW, PAPER_TH
from utils import get_scaled_rect, _screen_to_virtual, wrap_text, draw_text_box
from animation import get_anim_offset


# ---------------------------------------------------------------------------
# Paper transform
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _paper_world_pos_scale(gc: Game_context, t_e: float):
    p0, p1 = gc.PAPER_POS, gc.PAPER_FRONT_POS
    pos = Vector3(
        _lerp(p0.x, p1.x, t_e),
        _lerp(p0.y, p1.y, t_e),
        _lerp(p0.z, p1.z, t_e),
    )
    return pos, _lerp(1.0, 0.6, t_e)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _tex_px_to_world(gc: Game_context, tx: float, ty: float,
                     pos: Vector3, s: float) -> Vector3:
    """
    Texture pixel → world position on the open paper.

    Plane mesh local axes after RX(90°):
      local X → world X
      local Z → world -Y   (new_y = -z for RX(90°))
    UV layout (raylib gen_mesh_plane):
      UV.x = (local_x + W/2) / W,   UV.y = (local_z + H/2) / H
    """
    uv_x    = tx / PAPER_TW
    uv_y    = ty / PAPER_TH
    local_x = (uv_x - 0.5) * gc.PAPER_W
    local_z = (uv_y - 0.5) * gc.PAPER_H
    return Vector3(
        local_x * s + pos.x,
        -local_z * s + pos.y,
        pos.z,
    )

def get_mouse_position(gc: Game_context) -> Vector2:
    """Returns the mouse position corrected for the inversion curse."""
    raw_mouse = rl.get_mouse_position()
    
    if getattr(gc, "inversion_curse_active", False):
        # 1. Grab the current scaled gameplay bounding rectangle (accounts for black bars)
        dst = get_scaled_rect(gc)
        
        # --- VERTICAL FLIP HANDLING (Upside Down) ---
        # Get mouse distance relative to the TOP of the active gameplay area
        relative_y = raw_mouse.y - dst.y
        # Mirror it from the BOTTOM of the active gameplay area
        corrected_y = (dst.y + dst.height) - relative_y
        
        # --- HORIZONTAL MIRROR HANDLING (Left-to-Right) ---
        # Get mouse distance relative to the LEFT edge of the active gameplay area
        relative_x = raw_mouse.x - dst.x
        # Mirror it from the RIGHT edge of the active gameplay area
        corrected_x = (dst.x + dst.width) - relative_x

        return rl.Vector2(corrected_x, corrected_y)
        
    return raw_mouse


def _hit_paper(gc: Game_context) -> tuple[bool, dict | None]:
    """
    Ray-plane hit test → texture pixel → item lookup.

    Returns (on_paper, item): whether the cursor ray lands anywhere on the open
    paper sheet, and the interactive item (checkbox/button) under it if any.
    """
    if gc.paper_anim.current < 0.9:
        return False, None

    t_e       = gc.paper_anim.current
    pos, s    = _paper_world_pos_scale(gc, t_e)

    dst  = get_scaled_rect(gc)
    vpos = _screen_to_virtual(gc, get_mouse_position(gc), dst)
    ray  = rl.get_screen_to_world_ray_ex(vpos, gc.camera, gc.VIRTUAL_W, gc.VIRTUAL_H)

    if abs(ray.direction.z) < 1e-6:
        return False, None
    t_hit = (pos.z - ray.position.z) / ray.direction.z
    if t_hit <= 0:
        return False, None

    hx = ray.position.x + t_hit * ray.direction.x
    hy = ray.position.y + t_hit * ray.direction.y

    hw = gc.PAPER_W / 2 * s
    hh = gc.PAPER_H / 2 * s
    if abs(hx - pos.x) > hw or abs(hy - pos.y) > hh:
        return False, None

    # World → local → UV → texture pixel
    local_x =  (hx - pos.x) / s
    local_z = -(hy - pos.y) / s
    tx = (local_x / gc.PAPER_W + 0.5) * PAPER_TW
    ty = (local_z / gc.PAPER_H + 0.5) * PAPER_TH

    for item in gc.gs.get("paper_items", []):
        ix, iy, iw, ih = item["rect"]
        if ix <= tx <= ix + iw and iy <= ty <= iy + ih:
            return True, item
    return True, None


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------

def _draw_paper(gc: Game_context):
    t_e    = gc.paper_anim.current
    pos, s = _paper_world_pos_scale(gc, t_e)

    rx = math.radians(_lerp(gc.PAPER_REST_ROT_X, gc.PAPER_OPEN_ROT_X, t_e))
    ry = math.radians(_lerp(gc.PAPER_REST_ROT_Y, gc.PAPER_OPEN_ROT_Y, t_e))

    # Shake only while the paper is lifted toward the player (faded in by t_e); it
    # stays perfectly still resting on the table.
    shake = get_anim_offset(gc, "paper")
    pos = Vector3(pos.x + shake.x * t_e, pos.y + shake.y * t_e, pos.z + shake.z * t_e)

    mat = rl.matrix_scale(s, s, s)
    mat = rl.matrix_multiply(mat, rl.matrix_rotate_x(rx))
    mat = rl.matrix_multiply(mat, rl.matrix_rotate_y(ry))
    mat = rl.matrix_multiply(mat, rl.matrix_translate(pos.x, pos.y, pos.z))

    gc.models["paper"].transform = mat
    rl.draw_model(gc.models["paper"], Vector3(0, 0, 0), 1.0, rl.WHITE)
    gc.models["paper"].transform = rl.matrix_identity()


def draw_inspect_3d(gc: Game_context):
    rl.clear_background(rl.BLACK)
    rl.draw_texture_pro(
        gc.textures["bg"],
        rl.Rectangle(0, 0, gc.textures["bg"].width, gc.textures["bg"].height),
        rl.Rectangle(0, 0, gc.VIRTUAL_W, gc.VIRTUAL_H),
        Vector2(0, 0), 0.0, rl.Color(245, 185, 185, 255),
    )
    rl.begin_mode_3d(gc.camera)

    table_offset = get_anim_offset(gc, "table")
    table_pos = Vector3(
        gc.TABLE_POS.x + table_offset.x,
        gc.TABLE_POS.y + table_offset.y,
        gc.TABLE_POS.z + table_offset.z,
    )
    rl.draw_model(gc.models["table"], table_pos, gc.TABLE_SCALE, rl.WHITE)

    # Current item under evaluation, recentred on its bbox, normalised to a common
    # size and rotated by the accumulated arcball transform.
    if len(gc.itens_hoje['to evaluate']) > 0 and not gc.gs.get("object_hidden"):
        name = gc.itens_hoje['to evaluate'][0].name
        item_model = gc.models[name]
        scale, center = gc.object_fit[name]

        # local order: recentre to origin → arcball-rotate → scale to target size
        mat = rl.matrix_translate(-center.x, -center.y, -center.z)
        mat = rl.matrix_multiply(mat, gc.gs["object_transform"])
        mat = rl.matrix_multiply(mat, rl.matrix_scale(scale, scale, scale))
        item_model.transform = mat

        obj_offset = get_anim_offset(gc, name)
        swap = gc.gs.get("object_offset") or Vector3(0.0, 0.0, 0.0)
        obj_pos = Vector3(
            gc.OBJECT_POS.x + obj_offset.x + swap.x,
            gc.OBJECT_POS.y + obj_offset.y + swap.y,
            gc.OBJECT_POS.z + obj_offset.z + swap.z,
        )
        rl.draw_model(item_model, obj_pos, 1.0, rl.WHITE)
        item_model.transform = rl.matrix_identity()

    # Paper is always drawn on top of the table (depth test off avoids z-fighting).
    rl.rl_draw_render_batch_active()
    rl.rl_disable_depth_test()
    _draw_paper(gc)
    rl.rl_draw_render_batch_active()
    rl.rl_enable_depth_test()
    rl.end_mode_3d()

    # --- Draw HUD for Errors and Penalties ---
    # Draw simple text overlay
    text = f"Erros: {gc.n_erros}   Penalidade: {gc.penalidade}".encode('utf-8')
    rl.draw_text(text, 20, 20, 20, rl.WHITE)


def send_item(gc: Game_context):
    gc.itens_hoje['evaluated'].append(gc.itens_hoje['to evaluate'].pop(0))
    


# ---------------------------------------------------------------------------
# Object swap animation (swipe-out → parabolic entry)
# ---------------------------------------------------------------------------

_OBJ_EXIT_DUR   = 0.45   # seconds to swipe the judged object off-screen
_OBJ_ENTER_DUR  = 0.55   # seconds for the next object to arc into place
_OBJ_SWIPE_X    = 0.9    # how far (world X) the object slides out

# New object starts low and toward the camera (front edge of the table), then
# arcs up onto its inspection spot.
_OBJ_ENTER_START = Vector3(0.0, -0.28, 0.5)
_OBJ_ENTER_ARC   = 0.18  # peak extra height of the parabola


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _start_object_transition(gc: Game_context, direction: int):
    """Queue an object swap (direction: -1 left, +1 right).

    Starts in the 'wait' phase: nothing moves until the paper has finished
    returning to the table, then the object swipes out and the next arcs in.
    """
    gc.gs["obj_anim"] = {"phase": "wait", "dir": direction, "t": 0.0}


def _start_object_enter(gc: Game_context):
    """Arc the current first object onto the table (used at the start of a day)."""
    gc.gs["object_hidden"]    = False
    gc.gs["object_transform"] = rl.matrix_identity()
    gc.gs["spin_angle"]       = 0.0
    gc.gs["obj_anim"]         = {"phase": "enter", "dir": 0, "t": 0.0}
    s = _OBJ_ENTER_START
    gc.gs["object_offset"]    = Vector3(s.x, s.y, s.z)


def _apply_enter(gc: Game_context, t: float):
    e   = _smooth(t)
    s   = _OBJ_ENTER_START
    arc = _OBJ_ENTER_ARC * 4.0 * t * (1.0 - t)   # 0 at ends, peak at midpoint
    gc.gs["object_offset"] = Vector3(
        s.x * (1.0 - e),
        s.y * (1.0 - e) + arc,
        s.z * (1.0 - e),
    )


def _update_object_transition(gc: Game_context, dt: float):
    a = gc.gs["obj_anim"]

    if a["phase"] == "wait":
        # Hold still until the paper is fully back at rest on the table.
        gc.gs["object_offset"] = Vector3(0.0, 0.0, 0.0)
        if gc.paper_anim.done and gc.paper_anim.current <= 0.001:
            a["phase"] = "exit"
            a["t"]     = 0.0
        return

    a["t"] += dt

    if a["phase"] == "exit":
        t = min(1.0, a["t"] / _OBJ_EXIT_DUR)
        e = _smooth(t)
        gc.gs["object_offset"] = Vector3(a["dir"] * _OBJ_SWIPE_X * e, -0.1 * e, 0.0)

        if t >= 1.0:
            send_item(gc)
            if len(gc.itens_hoje["to evaluate"]) > 0:
                # Next object arcs in.
                gc.gs["object_transform"] = rl.matrix_identity()
                gc.gs["spin_angle"]       = 0.0
                a["phase"] = "enter"
                a["t"]     = 0.0
                _apply_enter(gc, 0.0)
            else:
                # Day is over: roll straight into the next day (no extra delay).
                gc.gs["obj_anim"]      = None
                gc.gs["object_offset"] = Vector3(0.0, 0.0, 0.0)
                gc.start_new_day()

    elif a["phase"] == "enter":
        t = min(1.0, a["t"] / _OBJ_ENTER_DUR)
        _apply_enter(gc, t)
        if t >= 1.0:
            gc.gs["obj_anim"]      = None
            gc.gs["object_offset"] = Vector3(0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

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

    # Arc the first object in only once the day transition has settled AND the
    # "Dia X" title animation has finished playing.
    if (gc.gs.get("pending_first_enter")
            and not gc.transition.active
            and gc.day_intro_timer <= 0):
        gc.gs["pending_first_enter"] = False
        _start_object_enter(gc)

    # Advance paper open/close animation
    was_open = gc.gs.get("paper_open_prev", False)
    is_open = gc.gs["paper_open"]
    if is_open != was_open:
        if is_open:
            gc.paper_anim.open()
        else:
            gc.paper_anim.close()
        gc.gs["paper_open_prev"] = is_open

    gc.paper_anim.update(dt)

    # A swap animation owns the scene until it finishes (no paper/arcball input).
    if gc.gs.get("obj_anim"):
        _update_object_transition(gc, dt)
        return

    if gc.gs["paper_open"]:
        on_paper, item = _hit_paper(gc)
        gc.gs["paper_hovered_item"] = item

        # Rebake only when the hovered button changes (avoids per-frame rebakes)
        new_hk = item["key"] if (item and item["type"] == "button") else None
        if new_hk != gc.gs.get("paper_hovered_key"):
            gc.gs["paper_hovered_key"] = new_hk
            gc.rebake_paper(hovered_key=new_hk)

        if rl.is_key_pressed(rl.KEY_E):
            gc.gs["paper_open"] = False
            gc.gs["paper_hovered_key"] = None
            gc.rebake_paper()
            return

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if not on_paper:
                # Only put the paper down when the click misses the sheet entirely.
                gc.gs["paper_open"] = False
                gc.gs["paper_hovered_key"] = None
                gc.rebake_paper()
            elif item is None:
                pass  # clicked the paper but not an interactive element — keep it up
            elif item["type"] == "check":
                states = gc.gs["paper_states"]
                states[item["key"]] = not states.get(item["key"], False)
                
                # Mapeamento do check_idx para a propriedade correspondente
                prop_map = {
                    "check_0": "AMALDICOADO",
                    "check_1": "VENENOSO",
                    "check_2": "RADIOATIVO",
                    "check_3": "REAL",
                    "check_4": "NOBRE",
                    "check_5": "ALIADOS",
                    "check_6": "RIVAIS",
                }
                if item["key"] in prop_map:
                    gc.properties_on_list[prop_map[item["key"]]] = states[item["key"]]
                print(f"Updated paper state: {item['key']} is now {states[item['key']]}, list: {gc.properties_on_list}")
                    
                gc.rebake_paper(hovered_key=new_hk)
            elif item["type"] == "button":
                _on_button(gc, item["key"])
        return

    gc.gs["paper_hovered_item"] = None

    # Paper closed: arcball-rotate the inspected object. It only grabs when the
    # click lands on the object, so a click elsewhere stays free for the paper.
    gc.player.update_object()
    if gc.gs["dragging"]:
        return

    # Raycast to open the paper from the table
    dst  = get_scaled_rect(gc)
    vpos = _screen_to_virtual(gc, get_mouse_position(gc), dst)
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


def draw_tutorial_talk(gc: Game_context):
    if gc.tutorial_index >= len(gc.tutorial_texts):
        return
    text = gc.tutorial_texts[gc.tutorial_index]

    # Draw into the render texture, so use the virtual resolution and the same
    # serif font used by the rest of the UI text.
    font = gc.fonts["serif"]
    sw, sh = gc.VIRTUAL_W, gc.VIRTUAL_H
    font_size = int(max(sh * 0.045, 20))
    spacing = 1
    padding = int(sw * 0.2)
    max_w = sw - padding * 2

    # Wrap to the box width but keep the poem's own line breaks.
    lines = wrap_text(font, text, font_size, spacing, max_w)
    wrapped_full_text = "\n".join(lines)

    # Typewriter reveal.
    chars_to_draw = min(int(gc.tutorial_char_count), len(wrapped_full_text))
    current_text = wrapped_full_text[:chars_to_draw]

    # Centered on screen, poem-style, with a fake drop shadow.
    draw_text_box(
        font,
        current_text,
        rl.Vector2(sw / 2.0, sh / 2.0),
        font_size,
        spacing=spacing,
        line_spacing=1.5,
        align="center",
        shadow_offset=max(2, int(font_size * 0.08)),
    )


def _on_button(gc: Game_context, key: str):
    print(f"[paper] {key.upper()} clicked")

    # Kick off the swap: Aceitar swipes the object left, Rejeitar swipes it right.
    # The actual item advance (send_item) is deferred until the swipe completes and
    # the paper has settled back down — see _update_object_transition.
    if len(gc.itens_hoje['to evaluate']) > 0:
        _start_object_transition(gc, 1 if key == "aceitar" else -1)
        neg = gc.compute_negatives(key)
        

    # Put the paper down and reset every checkbox back to its unchecked version.
    gc.gs["paper_open"] = False
    gc.gs["paper_hovered_item"] = None
    gc.gs["paper_hovered_key"] = None
    gc.gs["paper_states"] = {}
    
    # Also reset the properties tracking correctly
    for prop in gc.properties_on_list.keys():
        gc.properties_on_list[prop] = False
        
    gc.rebake_paper()
