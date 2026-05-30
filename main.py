import pyray as rl
from pyray import Vector3, Vector2
import math
import asyncio
import time


from inspecting import draw_inspect_3d, update_inspect
from menu import draw_menu, draw_menu_bg_into_texture
from game_context import Game_context
from state import State



# ---------------------------------------------------------------------------
# ARCBALL MATH HELPERS
# ---------------------------------------------------------------------------
def _norm3(x, y, z):
    d = math.sqrt(x*x + y*y + z*z)
    return (x/d, y/d, z/d) if d > 1e-8 else (0.0, 0.0, 1.0)

def _screen_to_virtual(gc: Game_context, pos: Vector2, dst: rl.Rectangle) -> Vector2:
    if dst.width == 0 or dst.height == 0:
        return pos
    return Vector2(
        (pos.x - dst.x) / dst.width  * gc.VIRTUAL_W,
        (pos.y - dst.y) / dst.height * gc.VIRTUAL_H,
    )

# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------



def _arcball_point(ray, center: Vector3, radius: float): # Given a ray from the camera through the mouse position, find the point on the arcball sphere (centered on the inspected object) that it intersects. Returns a normalized vector from the center to that point, and whether the ray is actually hitting the sphere or just grazing it.
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


def _update_object(gc: Game_context): # Mouse-driven arcball rotation for the inspected object.
    dst  = get_scaled_rect(gc)
    vpos = _screen_to_virtual(gc, rl.get_mouse_position(), dst)
    ray  = rl.get_screen_to_world_ray_ex(vpos, gc.camera, gc.VIRTUAL_W, gc.VIRTUAL_H)

    p1, on_object = _arcball_point(ray, gc.OBJECT_POS, gc._OBJECT_RADIUS)

    if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and on_object:
        gc.gs["dragging"]   = True
        gc.gs["spin_angle"] = 0.0
        gc.gs["drag_dir"]   = p1

    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
        gc.gs["dragging"] = False

    if gc.gs["dragging"] and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
        p0 = gc.gs["drag_dir"]
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
                gc.gs["object_transform"] = rl.matrix_multiply(gc.gs["object_transform"], rot)
                gc.gs["spin_axis"]  = na
                gc.gs["spin_angle"] = angle

            gc.gs["drag_dir"] = p1
    else:
        if gc.gs["spin_angle"] > 1e-5:
            rot = rl.matrix_rotate(Vector3(*gc.gs["spin_axis"]), gc.gs["spin_angle"])
            gc.gs["object_transform"] = rl.matrix_multiply(gc.gs["object_transform"], rot)
        gc.gs["spin_angle"] *= 0.88


def _update_debug_camera(gc: Game_context, camera: rl.Camera3D, dt: float): # 
    # return
    delta = rl.get_mouse_delta()
    gc.gs["cam_yaw"]   -= delta.x * 0.003
    gc.gs["cam_pitch"] -= delta.y * 0.003
    gc.gs["cam_pitch"]  = max(-1.2, min(1.2, gc.gs["cam_pitch"]))

    yaw, pitch = gc.gs["cam_yaw"], gc.gs["cam_pitch"]
    dx = math.sin(yaw) * math.cos(pitch)
    dy = math.sin(pitch)
    dz = math.cos(yaw) * math.cos(pitch)
    forward = Vector3(dx, dy, dz)
    right   = Vector3(math.cos(yaw), 0.0, -math.sin(yaw))

    speed = 3.0 * dt
    p = gc.gs["cam_pos"]
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

def get_scaled_rect(gc: Game_context) -> rl.Rectangle:
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    scale  = min(sw / gc.VIRTUAL_W, sh / gc.VIRTUAL_H)
    dw, dh = gc.VIRTUAL_W * scale, gc.VIRTUAL_H * scale
    return rl.Rectangle((sw - dw) / 2, (sh - dh) / 2, dw, dh)

# ---------------------------------------------------------------------------
# SHADER HELPER
# --------------------------------------------------------------
def _set_shader_resolution(shader, loc: int, w: float, h: float):
    """Push the render-texture resolution into the painting shader."""
    res = rl.ffi.new("float[2]", [w, h])
    rl.set_shader_value(shader, loc, res, rl.SHADER_UNIFORM_VEC2)



def unload_textures(textures: dict):
    rl.unload_texture(textures["bg"])
    rl.unload_texture(textures["menu_bg"])
    rl.unload_font(textures["tropiland_font"])

def unload_models(models: dict):
    rl.unload_model(models["table"])
    rl.unload_model(models["object"])

def general_inputs(gc: Game_context): # Essa funcao mostra q era pra ter uma classe aqui, mas n to botando pq lucas pediu pra n usar
    # -------------------------------------------------------------- #
    #  FULLSCREEN TOGGLE                                               #
    # -------------------------------------------------------------- #
    if rl.is_key_pressed(rl.KEY_F):
        if rl.is_window_fullscreen():
            rl.toggle_fullscreen()
            rl.set_window_size(gc.windowed_w, gc.windowed_h)
        else:
            gc.windowed_w = rl.get_screen_width()
            gc.windowed_h = rl.get_screen_height()
            monitor   = rl.get_current_monitor()
            rl.set_window_size(rl.get_monitor_width(monitor),
                                rl.get_monitor_height(monitor))
            rl.toggle_fullscreen()

    # -------------------------------------------------------------- #
    #  PAINTING SHADER TOGGLE                                          #
    # -------------------------------------------------------------- #
    if rl.is_key_pressed(rl.KEY_K):
        gc.painting_enabled = not gc.painting_enabled

def resize_texture_if_needed(gc: Game_context, render_tex, painting_shader, shader_res_loc, src_rect):
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    if sw > 0 and sh > 0 and (sw != gc.VIRTUAL_W or sh != gc.VIRTUAL_H):
        rl.unload_render_texture(render_tex)
        gc.VIRTUAL_W, gc.VIRTUAL_H = sw, sh
        render_tex = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)
        rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
        src_rect = rl.Rectangle(0, 0, gc.VIRTUAL_W, -gc.VIRTUAL_H)
        # Keep shader resolution uniform in sync
        _set_shader_resolution(painting_shader, shader_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)
    return render_tex, src_rect


def update(gc: Game_context, dt: float):
    new_state = gc.transition.update(dt)
    if new_state is not None:
        gc.current_state = new_state

    general_inputs(gc)
    if not gc.transition.active or not gc.transition._fading_out:
            if gc.current_state == State.MENU:
                if rl.is_key_pressed(rl.KEY_ENTER):
                    gc.make_scene_state()
                    gc.transition.start(State.INSPECT)

            elif gc.current_state == State.INSPECT:
                if rl.is_key_pressed(rl.KEY_P):
                    if gc.gs.get("debug"):
                        gc.gs["debug"] = False
                        rl.enable_cursor()
                    gc.transition.start(State.PAUSE)
                else:
                    update_inspect(gc, dt, _update_debug_camera, _update_object)

            elif gc.current_state == State.PAUSE:
                if rl.is_key_pressed(rl.KEY_P):
                    gc.transition.start(State.INSPECT)
                elif rl.is_key_pressed(rl.KEY_M):
                    gc.transition.start(State.MENU)

def draw_on_texture(gc: Game_context, render_tex):
    rl.begin_texture_mode(render_tex)

    match gc.current_state:
        case State.MENU:
            draw_menu_bg_into_texture(gc.textures["menu_bg"], gc.VIRTUAL_W, gc.VIRTUAL_H)

        case State.INSPECT:
            draw_inspect_3d(gc)
            gc.prev_inspect_drawn = True

        case State.PAUSE:
            # Keep the 3D scene visible under the pause overlay
            if gc.prev_inspect_drawn:
                print("Drawing paused scene into texture...")
                draw_inspect_3d(gc)
            else:
                rl.clear_background(rl.BLACK)

    rl.end_texture_mode()

def blit_on_screen(gc: Game_context, render_tex=None, src_rect=None, painting_shader=None):
    rl.begin_drawing()
    rl.clear_background(rl.BLACK)

    dst = get_scaled_rect(gc)

    if gc.painting_enabled:
        rl.begin_shader_mode(painting_shader)

    rl.draw_texture_pro(
        render_tex.texture,
        src_rect,
        dst,
        Vector2(0, 0),
        0.0,
        rl.WHITE,
    )

    if gc.painting_enabled:
        rl.end_shader_mode()

    # ---- Overlays (unaffected by the painting shader) ---------------
    match gc.current_state:
        case State.MENU:
            draw_menu(gc.now, dst, gc.textures["tropiland_font"])
            
        case State.INSPECT:
            draw_inspect_hud(gc.gs, dst)

        case State.PAUSE:
            draw_pause(gc.textures["tropiland_font"])
            draw_inspect_hud(gc.gs, dst)

    # Transition fade drawn on top of everything
    gc.transition.draw()

    # Shader toggle indicator
    label = b"[K] Painting: ON " if gc.painting_enabled else b"[K] Painting: OFF"
    col   = rl.Color(220, 175, 70, 200) if gc.painting_enabled else rl.Color(100, 90, 70, 140)
    rl.draw_text(label, 8, 8, 11, col)

    rl.end_drawing()


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
async def main():

    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
    rl.init_window(1000, 700, b"The Enigma")
    rl.set_target_fps(60)
    rl.enable_cursor()

    gc = Game_context()
    print("Initialization complete, entering main loop...")

    gc.VIRTUAL_W, gc.VIRTUAL_H = rl.get_screen_width(), rl.get_screen_height()
    render_tex = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)
    rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
    src_rect = rl.Rectangle(0, 0, gc.VIRTUAL_W, -gc.VIRTUAL_H)

    # --- Painting shader (Kuwahara) ---
    # WebGL (pygbag/Emscripten) needs GLSL ES 1.0; desktop uses GLSL 3.3.
    _fs = b"textures/shaders/painting_web.fs" if gc.IS_WEB else b"textures/shaders/painting.fs"
    painting_shader  = rl.load_shader(b"", _fs)
    shader_res_loc   = rl.get_shader_location(painting_shader, b"resolution")
    _set_shader_resolution(painting_shader, shader_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)


    while not rl.window_should_close():
        # dt update
        gc.now = time.time()
        dt  = gc.now - gc.prev_time
        gc.prev_time = gc.now

        # fullscreen resize screen
        render_tex, src_rect = resize_texture_if_needed(gc, render_tex, painting_shader, shader_res_loc, src_rect)
        
        #  UPDATE
        update(gc, dt)

        #  DRAW
        draw_on_texture(gc, render_tex)

        #  BLIT RENDER TEXTURE → SCREEN
        blit_on_screen(gc, render_tex, src_rect, painting_shader)
        

        await asyncio.sleep(0)

    # --- Cleanup ---
    rl.unload_shader(painting_shader)
    rl.unload_render_texture(render_tex)
    unload_models(gc.models)
    unload_textures(gc.textures)
    rl.close_window()


if __name__ == "__main__":
    asyncio.run(main())
