import math
import pyray as rl
from pyray import Vector2, Vector3

from game_context import Game_context, PAPER_TW, PAPER_TH
from utils import get_scaled_rect, _screen_to_virtual
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


def _hit_paper_item(gc: Game_context) -> dict | None:
    """
    Ray-plane hit test → texture pixel → item lookup.
    Returns the interactive item under the cursor, or None.
    """
    if gc.paper_anim.current < 0.9:
        return None

    t_e       = gc.paper_anim.current
    pos, s    = _paper_world_pos_scale(gc, t_e)

    dst  = get_scaled_rect(gc)
    vpos = _screen_to_virtual(gc, rl.get_mouse_position(), dst)
    ray  = rl.get_screen_to_world_ray_ex(vpos, gc.camera, gc.VIRTUAL_W, gc.VIRTUAL_H)

    if abs(ray.direction.z) < 1e-6:
        return None
    t_hit = (pos.z - ray.position.z) / ray.direction.z
    if t_hit <= 0:
        return None

    hx = ray.position.x + t_hit * ray.direction.x
    hy = ray.position.y + t_hit * ray.direction.y

    hw = gc.PAPER_W / 2 * s
    hh = gc.PAPER_H / 2 * s
    if abs(hx - pos.x) > hw or abs(hy - pos.y) > hh:
        return None

    # World → local → UV → texture pixel
    local_x =  (hx - pos.x) / s
    local_z = -(hy - pos.y) / s
    tx = (local_x / gc.PAPER_W + 0.5) * PAPER_TW
    ty = (local_z / gc.PAPER_H + 0.5) * PAPER_TH

    for item in gc.gs.get("paper_items", []):
        ix, iy, iw, ih = item["rect"]
        if ix <= tx <= ix + iw and iy <= ty <= iy + ih:
            return item
    return None


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------

def _draw_paper(gc: Game_context):
    t_e    = gc.paper_anim.current
    pos, s = _paper_world_pos_scale(gc, t_e)

    rx = math.radians(_lerp(gc.PAPER_REST_ROT_X, gc.PAPER_OPEN_ROT_X, t_e))
    ry = math.radians(_lerp(gc.PAPER_REST_ROT_Y, gc.PAPER_OPEN_ROT_Y, t_e))

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
        Vector2(0, 0), 0.0, rl.Color(255, 185, 185, 255),
    )
    rl.begin_mode_3d(gc.camera)

    table_offset = get_anim_offset(gc, "table")
    table_pos = Vector3(
        gc.TABLE_POS.x + table_offset.x,
        gc.TABLE_POS.y + table_offset.y,
        gc.TABLE_POS.z + table_offset.z,
    )
    rl.draw_model(gc.models["table"], table_pos, gc.TABLE_SCALE, rl.WHITE)

    # Current item under evaluation, rotated by the accumulated arcball transform.
    if len(gc.itens_hoje['to evaluate']) > 0:
        name = gc.itens_hoje['to evaluate'][0].name
        item_model = gc.models[name]
        item_model.transform = gc.gs["object_transform"]
        obj_offset = get_anim_offset(gc, name)
        obj_pos = Vector3(
            gc.OBJECT_POS.x + obj_offset.x,
            gc.OBJECT_POS.y + obj_offset.y,
            gc.OBJECT_POS.z + obj_offset.z,
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


def send_item(gc: Game_context):
    gc.itens_hoje['evaluated'].append(gc.itens_hoje['to evaluate'].pop(0))
    penalidade = 0
    n_erros = 0
    for atributo, valor in gc.itens_hoje['evaluated'][-1].atributos.items():
        if type(valor) != list:
            if gc.properties_on_list[atributo] != valor:
                n_erros += 1
                penalidade += gc.error_costs[atributo]
    gc.player_cartas_odio += n_erros


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

    if rl.is_key_pressed(rl.KEY_S):
        if len(gc.itens_hoje['to evaluate']) > 0:
            send_item(gc)

    if gc.gs["debug"]:
        gc.player.update_debug_camera(dt)
        return

    # End-of-day countdown: advance once every item has been evaluated.
    if len(gc.itens_hoje['to evaluate']) == 0:
        gc.count_until_end_day -= 1
    if gc.count_until_end_day <= 0:
        gc.count_until_end_day = gc.reset_count_until_end_day
        gc.start_new_day()
        return

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

    if gc.gs["paper_open"]:
        item = _hit_paper_item(gc)
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
            if item is None:
                gc.gs["paper_open"] = False
                gc.gs["paper_hovered_key"] = None
                gc.rebake_paper()
            elif item["type"] == "check":
                states = gc.gs["paper_states"]
                states[item["key"]] = not states.get(item["key"], False)
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


def draw_tutorial_talk(gc: Game_context):
    if gc.tutorial_index >= len(gc.tutorial_texts):
        return
    text = gc.tutorial_texts[gc.tutorial_index]
    
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    font_size = int(max(sh * 0.045, 20))
    padding = int(sw * 0.2)
    max_w = sw - padding * 2

    # Wrap text dynamically
    raw_lines = text.split('\n')
    lines = []
    
    for raw_line in raw_lines:
        words = raw_line.split(' ')
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            w = rl.measure_text(test_line.encode('utf-8'), font_size)
            if w > max_w and len(current_line) > 0:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        if current_line:
            lines.append(" ".join(current_line))
        
    wrapped_full_text = "\n".join(lines)

    chars_to_draw = int(gc.tutorial_char_count)
    if chars_to_draw > len(wrapped_full_text):
        chars_to_draw = len(wrapped_full_text)
    
    current_text = wrapped_full_text[:chars_to_draw]
    # Desenhe o balão de fala do tutorial
    text_y = sh - int(sh * 0.25)
    rl.draw_text(current_text.encode('utf-8'), padding, text_y, font_size, rl.WHITE)


def _on_button(gc: Game_context, key: str):
    print(f"[paper] {key.upper()} clicked")
    gc.gs["paper_open"] = False
    gc.gs["paper_hovered_item"] = None
