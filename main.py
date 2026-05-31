import sys
import pyray as rl
from pyray import Vector3, Vector2
import math
import asyncio
import time


from inspecting import draw_inspect_3d, update_inspect, draw_tutorial_talk
from menu import draw_menu, draw_menu_bg_into_texture
from game_context import Game_context
from state import State
from player import Player
from utils import get_scaled_rect, _screen_to_virtual
from animation import update_animations
import curses as curses

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
# SHADER HELPER
# --------------------------------------------------------------
def _set_shader_resolution(shader, loc: int, w: float, h: float):
    """Push the render-texture resolution into the painting shader."""
    res = rl.ffi.new("float[2]", [w, h])
    rl.set_shader_value(shader, loc, res, rl.SHADER_UNIFORM_VEC2)




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

    # -------------------------------------------------------------- #
    #  INVERSION CURSE TOGGLE (DEBUG)
    # -------------------------------------------------------------- #
    if rl.is_key_pressed(rl.KEY_I):
        # Initialize the variable if it doesn't exist yet, then toggle it
        if not hasattr(gc, "inversion_curse_active"):
            gc.inversion_curse_active = False
        gc.inversion_curse_active = not gc.inversion_curse_active


    # -------------------------------------------------------------- #
    #  NAUSEA CURSE TOGGLE (DEBUG)
    # -------------------------------------------------------------- #
    if rl.is_key_pressed(rl.KEY_N):
        gc.nausea_curse_active = not getattr(gc, "nausea_curse_active", False)


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
    update_animations(gc, dt)
    if not gc.transition.active or not gc.transition._fading_out:
            match gc.current_state:
                case State.MENU:
                    if rl.is_key_pressed(rl.KEY_ENTER):
                        gc.transition.start(State.INTRO)

                case State.INSPECT:
                    # Se ainda n tem gc.gs entao chama o make_scene_state
                    if not gc.created_room:
                        gc.start_new_day()
                    
                    if gc.day_intro_timer > 0:
                        gc.day_intro_timer -= dt
                        gc.day_intro_char_count += gc.day_intro_typing_speed * dt

                    if rl.is_key_pressed(rl.KEY_P):
                        if gc.gs.get("debug"):
                            gc.gs["debug"] = False
                            rl.enable_cursor()
                        gc.transition.start(State.PAUSE)
                    else:
                        update_inspect(gc, dt)

                case State.PAUSE:
                    if rl.is_key_pressed(rl.KEY_P):
                        gc.transition.start(State.INSPECT)
                    elif rl.is_key_pressed(rl.KEY_M):
                        gc.transition.start(State.MENU)
                case State.INTRO:
                    # Leia qualquer input do mouse ou teclado para pular a introdução
                    if not hasattr(gc, "gs"):
                        gc.make_scene_state()
                    # tocar som da estrofe atual ao entrar/avançar
                    if getattr(gc, 'tutorial_played_index', -1) != gc.tutorial_index and gc.tutorial_index < len(gc.tutorial_texts):
                        key = f"tutorial_{gc.tutorial_index+1}"
                        snd = None
                        if hasattr(gc, 'sounds'):
                            snd = gc.sounds.get(key)
                        if snd:
                            try:
                                rl.play_sound(snd)
                            except Exception:
                                pass
                        gc.tutorial_played_index = gc.tutorial_index

                    gc.tutorial_char_count += gc.tutorial_typing_speed * dt
                    
                    if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                        text_len = len(gc.tutorial_texts[gc.tutorial_index])
                        if gc.tutorial_char_count < text_len:
                            gc.tutorial_char_count = text_len
                        else:
                            gc.tutorial_index += 1
                            gc.tutorial_char_count = 0.0
                            if gc.tutorial_index >= len(gc.tutorial_texts):
                                gc.transition.start(State.INSPECT)


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

        case State.INTRO:
            draw_inspect_3d(gc)

    rl.end_texture_mode()

def blit_on_screen(gc: Game_context, render_tex=None, src_rect=None, painting_shader=None):
    rl.begin_drawing()
    rl.clear_background(rl.BLACK)

    dst = get_scaled_rect(gc)

    final_src_rect = curses.inversion_curse(gc, src_rect)

    if gc.painting_enabled:
        rl.begin_shader_mode(painting_shader)

    rl.draw_texture_pro(
        render_tex.texture,
        final_src_rect,
        dst,
        Vector2(0, 0),
        0.0,
        rl.WHITE,
    )

    # --- CLOSE SHADERS ---
    if gc.painting_enabled:
        rl.end_shader_mode()


    # ---- Overlays (unaffected by the painting shader) ---------------
    match gc.current_state:
        case State.MENU:
            draw_menu(gc.now, dst, gc.fonts["serif"])

        case State.INSPECT:
            gc.player.draw_hud(dst)
            if gc.day_intro_timer > 0:
                sw, sh = rl.get_screen_width(), rl.get_screen_height()
                rl.draw_rectangle(0, 0, sw, sh, rl.Color(0, 0, 0, 180)) # Filtro escuro no fundo
                
                day_text = f"Dia {gc.dia_atual}"
                chars_to_draw = int(gc.day_intro_char_count)
                if chars_to_draw > len(day_text):
                    chars_to_draw = len(day_text)
                    
                current_day_text = day_text[:chars_to_draw].encode('utf-8')
                font_size = int(sh * 0.15) # Texto bem maior e proporcional à tela
                text_width = rl.measure_text_ex(gc.fonts["serif"], current_day_text, font_size, 1).x

                rl.draw_text_ex(gc.fonts["serif"], current_day_text, rl.Vector2((sw - text_width) / 2, (sh - font_size) / 2), font_size, 1, rl.WHITE)

        case State.PAUSE:
            draw_pause(gc.fonts["serif"])
            gc.player.draw_hud(dst)

        case State.INTRO:
            gc.player.draw_hud(dst)
            draw_tutorial_talk(gc)

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
    rl.init_window(1480, 800, b"The Enigma")
    rl.set_target_fps(60)
    rl.enable_cursor()

    if sys.platform != "emscripten":
        monitor = rl.get_current_monitor()
        rl.set_window_size(rl.get_monitor_width(monitor), rl.get_monitor_height(monitor))
        rl.toggle_fullscreen()

    gc = Game_context()
    gc.player = Player(gc)
    print("Initialization complete, entering main loop...")

    gc.VIRTUAL_W, gc.VIRTUAL_H = rl.get_screen_width(), rl.get_screen_height()
    render_tex = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)
    rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
    src_rect = rl.Rectangle(0, 0, gc.VIRTUAL_W, -gc.VIRTUAL_H)

    # --- Painting shader (Kuwahara) ---
    # WebGL (pygbag/Emscripten) needs GLSL ES 1.0; desktop uses GLSL 3.3.
    _fs = b"shaders/painting_web.fs" if gc.IS_WEB else b"shaders/painting.fs"
    painting_shader  = rl.load_shader(b"", _fs)
    shader_res_loc   = rl.get_shader_location(painting_shader, b"resolution")
    _set_shader_resolution(painting_shader, shader_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)

    # --- NAUSEA SHADER INITIALIZATION ---
    nausea_shader = rl.load_shader(b"", b"shaders/nausea.fs")
    nausea_time_loc = rl.get_shader_location(nausea_shader, b"seconds")
    gc.nausea_curse_active = False # Start deactivated

    # debug
    gc.make_scene_state()

    while not rl.window_should_close():
        # dt update
        gc.now = time.time()
        dt  = gc.now - gc.prev_time
        gc.prev_time = gc.now

        current_time = gc.now - gc.start_time 
        # --- SEND TIME TO NAUSEA SHADER ---
        time_ptr = rl.ffi.new("float *", current_time)
        rl.set_shader_value(nausea_shader, nausea_time_loc, time_ptr, rl.SHADER_UNIFORM_FLOAT)

        # fullscreen resize screen
        render_tex, src_rect = resize_texture_if_needed(gc, render_tex, painting_shader, shader_res_loc, src_rect)
        
        #  UPDATE
        update(gc, dt)

        #  DRAW
        draw_on_texture(gc, render_tex)
        is_nauseous = getattr(gc, "nausea_curse_active", False)
        active_shader = nausea_shader if is_nauseous else painting_shader


        #  BLIT RENDER TEXTURE → SCREEN
        blit_on_screen(gc, render_tex, src_rect, active_shader)
        

        await asyncio.sleep(0)

    # --- Cleanup ---
    rl.unload_shader(painting_shader)
    rl.unload_render_texture(render_tex)
    gc.unload_models()
    gc.unload_textures()
    gc.unload_fonts()
    rl.close_window()


if __name__ == "__main__":
    asyncio.run(main())
