import sys
import pyray as rl
from pyray import Vector3, Vector2
import math
import asyncio
import time


from src.inspecting import draw_inspect_3d, update_inspect, draw_tutorial_talk, get_mouse_position
from src.menu import draw_menu, draw_menu_bg_into_texture
from src.game_context import Game_context
from src.state import State
from src.player import Player
from src.utils import get_scaled_rect, _screen_to_virtual
from src.animation import update_animations
import src.curses as curses

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
    tw = _measure(title, 160)
    _draw(title, cx - tw // 2, cy - 24, 160, rl.WHITE)

    for i, text in enumerate((b"[P] Resumir", b"[M] Menu Inicial")):
        w = _measure(text, 70)
        _draw(text, cx - w // 2, cy + 190 + i * 88, 70, rl.Color(180, 180, 180, 200))



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


def resize_texture_if_needed(gc: Game_context, render_tex, src_rect):
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    if sw > 0 and sh > 0 and (sw != gc.VIRTUAL_W or sh != gc.VIRTUAL_H):
        rl.unload_render_texture(render_tex)
        rl.unload_render_texture(gc.keyhole_mask)
        gc.VIRTUAL_W, gc.VIRTUAL_H = sw, sh
        render_tex = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)
        rl.set_texture_filter(render_tex.texture, rl.TEXTURE_FILTER_BILINEAR)
        gc.keyhole_mask = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)
        src_rect = rl.Rectangle(0, 0, gc.VIRTUAL_W, -gc.VIRTUAL_H)
        # Keep both whole-screen shaders' resolution uniforms in sync.
        _set_shader_resolution(gc.painting_shader, gc.painting_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)
        _set_shader_resolution(gc.magnifier_shader, gc.magnifier_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)

    return render_tex, src_rect


def _advance_tutorial(gc: Game_context):
    """Move to the next tutorial stanza, or leave INTRO if it was the last one."""
    gc.tutorial_index += 1
    gc.tutorial_char_count = 0.0
    if gc.tutorial_index >= len(gc.tutorial_texts):
        prev = getattr(gc, 'current_tutorial_sound', None)
        if prev is not None:
            try:
                rl.stop_sound(prev)
            except Exception:
                pass
            gc.current_tutorial_sound = None
        # Tutorial done — drop straight back into day 1 (no fade); the first
        # object then arcs in.
        gc.tutorial_seen = True
        # The 'Dia X' card already played before the tutorial; go straight to
        # gameplay so it doesn't show a second time.
        gc.current_state = State.INSPECT


def update(gc: Game_context, dt: float):
    new_state = gc.transition.update(dt)
    if new_state is not None:
        gc.current_state = new_state

    general_inputs(gc)
    update_animations(gc, dt)
    # Dust + property auras drift continuously whenever the 3D scene is shown.
    if gc.current_state in (State.INSPECT, State.INTRO, State.PAUSE):
        gc.particles.update(dt)
        gc.aura_radio.update(dt)
        gc.aura_poison.update(dt)
    if not gc.transition.active or not gc.transition._fading_out:
            match gc.current_state:
                case State.MENU:
                    if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                        gc.reset_effects()
                        gc.transition.start(State.INSPECT)

                case State.INSPECT:
                    # Se ainda n tem gc.gs entao chama o make_scene_state
                    if not gc.created_room:
                        gc.start_new_day()

                    # The "Dia X" card types out first.
                    if gc.day_intro_timer > 0:
                        gc.day_intro_timer -= dt
                        gc.day_intro_char_count += gc.day_intro_typing_speed * dt
                        if rl.is_key_pressed(rl.KEY_ENTER):
                            gc.day_intro_timer = 0
                            gc.day_intro_char_count = 999

                    # On day 1 the tutorial plays once, right after the day card and
                    # before any gameplay / object entry. (Or on a redo day if seen is reset)
                    if not gc.tutorial_seen:
                        if gc.day_intro_timer <= 0 and not gc.transition.active:
                            gc.transition.start(State.INTRO)
                    elif rl.is_key_pressed(rl.KEY_P):
                        gc.transition.start(State.PAUSE)
                    else:
                        update_inspect(gc, dt)

                case State.PAUSE:
                    if rl.is_key_pressed(rl.KEY_P):
                        gc.transition.start(State.INSPECT)
                    elif rl.is_key_pressed(rl.KEY_M):
                        gc.reset_game()
                        gc.reset_effects()
                        gc.transition.start(State.MENU)
                case State.GAME_OVER_FIRED | State.GAME_OVER_WIN | State.GAME_OVER_EXPLODED:
                    from src.end_states import update_end_state
                    update_end_state(gc, dt)
                case State.INTRO:
                    # Leia qualquer input do mouse ou teclado para pular a introdução
                    if not hasattr(gc, "gs"):
                        gc.make_scene_state()
                    # tocar som da estrofe atual ao entrar/avançar
                    if getattr(gc, 'tutorial_played_index', -1) != gc.tutorial_index and gc.tutorial_index < len(gc.tutorial_texts):
                        # interrompe o áudio anterior antes de iniciar o novo
                        prev = getattr(gc, 'current_tutorial_sound', None)
                        if prev is not None:
                            try:
                                rl.stop_sound(prev)
                            except Exception:
                                pass
                            gc.current_tutorial_sound = None

                        key = f"tutorial_{gc.tutorial_index+1}"
                        snd = None
                        if hasattr(gc, 'sounds'):
                            snd = gc.sounds.get(key)
                        if snd:
                            try:
                                rl.play_sound(snd)
                                gc.current_tutorial_sound = snd
                            except Exception:
                                pass
                        gc.tutorial_played_index = gc.tutorial_index

                    gc.tutorial_char_count += gc.tutorial_typing_speed * dt

                    text_len = len(gc.tutorial_texts[gc.tutorial_index])
                    text_done = gc.tutorial_char_count >= text_len

                    if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                        if not text_done:
                            # First press snaps the typewriter to the end.
                            gc.tutorial_char_count = text_len
                        else:
                            _advance_tutorial(gc)
                    else:
                        # Auto-advance once the stanza's narration has finished
                        # playing (and its text is fully revealed).
                        snd = getattr(gc, 'current_tutorial_sound', None)
                        if snd is not None and text_done and not rl.is_sound_playing(snd):
                            gc.current_tutorial_sound = None
                            _advance_tutorial(gc)


def draw_on_texture(gc: Game_context, render_tex):
    rl.begin_texture_mode(render_tex)

    match gc.current_state:
        case State.MENU:
            # Paint the menu backdrop with the Kuwahara shader, same as the
            # in-game background.
            if gc.painting_enabled:
                rl.begin_shader_mode(gc.painting_shader)
            draw_menu_bg_into_texture(gc.textures["menu_bg"], gc.VIRTUAL_W, gc.VIRTUAL_H)
            if gc.painting_enabled:
                rl.end_shader_mode()

        case State.INSPECT:
            draw_inspect_3d(gc)
            gc.prev_inspect_drawn = True

        case State.PAUSE:
            # Keep the 3D scene visible under the pause overlay
            if gc.prev_inspect_drawn:
                draw_inspect_3d(gc)
            else:
                rl.clear_background(rl.BLACK)

        case State.INTRO:
            draw_inspect_3d(gc)
            draw_tutorial_talk(gc)

        case State.GAME_OVER_FIRED | State.GAME_OVER_WIN | State.GAME_OVER_EXPLODED:
            from src.end_states import draw_end_state
            draw_end_state(gc)

    # Composite the keyhole mask over the finished scene (multiply blend).
    composite_keyhole(gc)

    rl.end_texture_mode()


def render_keyhole_mask(gc):
    """Render the keyhole aperture into gc.keyhole_mask: an opaque black field
    with the keyhole drawn WHITE (a circle for the head + a downward triangle
    for the body). Composited later with multiply blending, white keeps the
    scene and black hides it — so tuning the keyhole is just tuning these two
    shapes. Must be called outside any other texture-mode pass.
    """
    if not getattr(gc, "keyhole_curse_active", False):
        return

    # Cursor → virtual (render-texture) space so it lines up with the scene.
    # get_mouse_position() returns the inversion-corrected cursor, i.e. the
    # render-texture point that sits under the physical cursor once the
    # inversion-curse blit mirrors everything — so the aperture stays on the
    # mouse whether or not the curse is active.
    dst   = get_scaled_rect(gc)
    mouse = _screen_to_virtual(gc, get_mouse_position(gc), dst)
    mx, my = mouse.x, mouse.y

    # Dimensions as fractions of the virtual height → resize-stable.
    vh = gc.VIRTUAL_H
    R  = gc.KEYHOLE_RADIUS_FRAC * vh   # head radius
    CW = gc.KEYHOLE_CONE_W_FRAC * vh   # body half-width at the base
    CH = gc.KEYHOLE_CONE_H_FRAC * vh   # body height

    rl.begin_texture_mode(gc.keyhole_mask)
    rl.clear_background(rl.BLACK)                       # opaque black surround

    rl.draw_circle(int(mx), int(my), R, rl.WHITE)      # head
    # Body: a downward triangle (apex at the head, wide base below). Drawn with
    # both windings so it fills regardless of back-face culling.
    apex = rl.Vector2(mx, my)
    bl   = rl.Vector2(mx - CW, my + CH)
    br   = rl.Vector2(mx + CW, my + CH)
    rl.draw_triangle(apex, bl, br, rl.WHITE)
    rl.draw_triangle(apex, br, bl, rl.WHITE)

    rl.end_texture_mode()


def composite_keyhole(gc):
    """Multiply the scene by the keyhole mask (white aperture → scene, black
    surround → darkness). Called inside the scene's texture-mode pass."""
    if not getattr(gc, "keyhole_curse_active", False):
        return

    rl.begin_blend_mode(rl.BLEND_MULTIPLIED)
    # Negative source height flips the mask FBO upright into the scene's logical
    # space (same convention as the final screen blit), so the aperture lands
    # under the cursor and aligns with the scene.
    rl.draw_texture_pro(
        gc.keyhole_mask.texture,
        rl.Rectangle(0, 0, gc.VIRTUAL_W, -gc.VIRTUAL_H),
        rl.Rectangle(0, 0, gc.VIRTUAL_W, gc.VIRTUAL_H),
        rl.Vector2(0, 0), 0.0, rl.WHITE,
    )
    rl.end_blend_mode()


def blit_on_screen(gc: Game_context, render_tex=None, src_rect=None, screen_shader=None):
    rl.begin_drawing()
    rl.clear_background(rl.BLACK)

    dst = get_scaled_rect(gc)

    final_src_rect = curses.inversion_curse(gc, src_rect)

    # The blit always runs through a whole-screen shader (magnifier lens, or the
    # nausea curse when active). The painting filter is applied earlier, only to
    # the background texture inside the scene draw.
    rl.begin_shader_mode(screen_shader)

    rl.draw_texture_pro(
        render_tex.texture,
        final_src_rect,
        dst,
        Vector2(0, 0),
        0.0,
        rl.WHITE,
    )

    rl.end_shader_mode()

    # ---- Vignette (cool edge darkening, atmosphere) -----------------
    # Only over the live 3D scene, not the menu's own artwork.
    if gc.current_state in (State.INSPECT, State.PAUSE, State.INTRO):
        vig = gc.textures["vignette"]
        rl.draw_texture_pro(
            vig,
            rl.Rectangle(0, 0, float(vig.width), float(vig.height)),
            dst,
            Vector2(0, 0), 0.0, rl.WHITE,
        )

        # ---- Hunger vignette (reddish edge pulse when starving) ------
        hunger_ratio = gc.hunger / gc.hunger_max if gc.hunger_max > 0 else 1.0
        if hunger_ratio < 0.30:
            alpha = int((1.0 - hunger_ratio / 0.30) * 90)
            rl.draw_texture_pro(
                vig,
                rl.Rectangle(0, 0, float(vig.width), float(vig.height)),
                dst,
                Vector2(0, 0), 0.0, rl.Color(180, 20, 10, alpha),
            )

        # ---- Starvation: gray desaturation + heartbeat pulse ----------
        if hunger_ratio <= 0:
            pulse = 0.5 + 0.5 * math.sin(gc.now * 3.3)  # ~100 BPM
            gray_alpha = int(50 + 35 * pulse)
            rl.draw_rectangle(
                int(dst.x), int(dst.y),
                int(dst.width), int(dst.height),
                rl.Color(30, 28, 35, gray_alpha),
            )

    # ---- Overlays (unaffected by the painting shader) ---------------
    match gc.current_state:
        case State.MENU:
            draw_menu(gc.now, dst, gc.fonts["serif"])

        case State.INSPECT:
            gc.player.draw_hud(dst)
            if gc.day_intro_timer > 0:
                sw, sh = rl.get_screen_width(), rl.get_screen_height()
                font = gc.fonts["serif"]
                
                day_text = f"Dia {gc.dia_atual}"
                chars_to_draw = int(gc.day_intro_char_count)
                if chars_to_draw > len(day_text):
                    chars_to_draw = len(day_text)
                    
                current_day_text = day_text[:chars_to_draw].encode('utf-8')
                font_size = int(sh * 0.14)
                text_width = rl.measure_text_ex(font, current_day_text, font_size, 1).x

                rl.draw_text_ex(font, current_day_text,
                                rl.Vector2((sw - text_width) / 2, sh * 0.38),
                                font_size, 1, rl.WHITE)

                # Day summary stats (after title is fully typed, only day 2+).
                # Shows the day that JUST ENDED — the live counters were already
                # reset for the new day, so read the snapshot taken at rollover.
                if chars_to_draw >= len(day_text) and gc.dia_atual > 1:
                    total = gc.last_day_items_judged
                    correct = gc.last_day_items_correct
                    errors = gc.last_day_errors
                    ate = gc.last_day_foods_eaten
                    hunger_pct = gc.last_day_hunger_pct

                    lines = [
                        f"Itens avaliados: {total}",
                        f"Acertos: {correct}  |  Erros: {errors}",
                        f"Comidas: {ate}  |  Fome restante: {hunger_pct}%",
                    ]
                    grade_color = rl.Color(200, 180, 150, 230)  # default
                    if total > 0:
                        pct = int(correct / total * 100)
                        grade = "S" if pct >= 90 else ("A" if pct >= 70 else ("B" if pct >= 50 else "C"))
                        grade_color = (rl.Color(90, 200, 70, 255) if pct >= 70 else
                                       rl.Color(220, 180, 30, 255) if pct >= 50 else
                                       rl.Color(200, 60, 40, 255))
                        lines.append(f"Nota: {grade} ({pct}%)")

                    stats_fs = int(sh * 0.032)
                    for i, line in enumerate(lines):
                        lb = line.encode("utf-8")
                        tw = rl.measure_text_ex(font, lb, stats_fs, 1).x
                        cy = sh * 0.52 + i * (stats_fs * 1.6)
                        rl.draw_text_ex(font, lb,
                                        rl.Vector2((sw - tw) / 2, cy),
                                        stats_fs, 1, grade_color if i == len(lines) - 1 and total > 0
                                        else rl.Color(200, 180, 150, 230))

                rl.draw_text_ex(font, b"[ENTER] para pular",
                                rl.Vector2(sw * 0.42, sh * 0.72),
                                int(sh * 0.022), 1, rl.Color(120, 100, 70, 200))

        case State.PAUSE:
            draw_pause(gc.fonts["serif"])
            gc.player.draw_hud(dst)

        case State.INTRO:
            gc.player.draw_hud(dst)

    # Transition fade drawn on top of everything
    gc.transition.draw()

    # Shader toggle indicator
    # label = b"[K] Painting: ON " if gc.painting_enabled else b"[K] Painting: OFF"
    # col   = rl.Color(220, 175, 70, 200) if gc.painting_enabled else rl.Color(100, 90, 70, 140)
    # rl.draw_text(label, 8, 8, 11, col)

    rl.end_drawing()


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
async def main():

    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
    rl.set_trace_log_level(rl.LOG_NONE)
    rl.init_window(1480, 800, b"7 Dias de Alfandegario")
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

    # Offscreen mask for the keyhole curse (black surround, white aperture).
    gc.keyhole_mask = rl.load_render_texture(gc.VIRTUAL_W, gc.VIRTUAL_H)

    # WebGL (pygbag/Emscripten) needs GLSL ES 1.0; desktop uses GLSL 3.3.

    # --- Painting shader (Kuwahara) — applied ONLY to the background texture
    # inside the scene draw (see draw_inspect_3d). Stored on gc so the draw
    # code can reach it; [K] toggles gc.painting_enabled.
    _pfs = b"shaders/painting_web.fs" if gc.IS_WEB else b"shaders/painting.fs"
    gc.painting_shader   = rl.load_shader(b"", _pfs)
    gc.painting_res_loc  = rl.get_shader_location(gc.painting_shader, b"resolution")
    _set_shader_resolution(gc.painting_shader, gc.painting_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)

    # --- Magnifier lens shader — applied to the WHOLE render texture at blit.
    _mfs = b"shaders/magnifier_web.fs" if gc.IS_WEB else b"shaders/magnifier.fs"
    gc.magnifier_shader  = rl.load_shader(b"", _mfs)
    gc.magnifier_res_loc = rl.get_shader_location(gc.magnifier_shader, b"resolution")
    _set_shader_resolution(gc.magnifier_shader, gc.magnifier_res_loc, gc.VIRTUAL_W, gc.VIRTUAL_H)
    lens_center_loc = rl.get_shader_location(gc.magnifier_shader, b"lensCenter")
    lens_radius_loc = rl.get_shader_location(gc.magnifier_shader, b"lensRadius")
    lens_zoom_loc   = rl.get_shader_location(gc.magnifier_shader, b"lensZoom")

    # --- Nausea curse shader — applied to the WHOLE render texture at blit.
    _nfs = b"shaders/nausea_web.fs" if gc.IS_WEB else b"shaders/nausea.fs"
    nausea_shader = rl.load_shader(b"", _nfs)
    nausea_time_loc = rl.get_shader_location(nausea_shader, b"seconds")
    gc.nausea_curse_active = False # Start deactivated

    # debug
    gc.make_scene_state()

    while not rl.window_should_close():
        # dt update
        gc.now = time.time()
        dt  = gc.now - gc.prev_time

        # slow curse ?
        # dt = (1/10)*dt

        gc.prev_time = gc.now

        current_time = gc.now - gc.start_time 
        # --- SEND TIME TO NAUSEA SHADER ---
        time_ptr = rl.ffi.new("float *", current_time)
        rl.set_shader_value(nausea_shader, nausea_time_loc, time_ptr, rl.SHADER_UNIFORM_FLOAT)

        # fullscreen resize screen
        render_tex, src_rect = resize_texture_if_needed(gc, render_tex, src_rect)

        # MUSIC
        gc.update_music()
        # AUDIO EFFECTS (poison wobble, curse distortion, time pressure, etc.)
        gc.audio_effects.update(dt)
        # HUNGER DECAY
        gc.update_hunger(dt)

        #  UPDATE
        update(gc, dt)

        # Push magnifier lens state into the lens shader (used at blit).
        rl.set_shader_value(gc.magnifier_shader, lens_center_loc,
                            rl.ffi.new("float[2]", list(gc.lens_center)), rl.SHADER_UNIFORM_VEC2)
        rl.set_shader_value(gc.magnifier_shader, lens_radius_loc,
                            rl.ffi.new("float *", gc.lens_radius), rl.SHADER_UNIFORM_FLOAT)
        rl.set_shader_value(gc.magnifier_shader, lens_zoom_loc,
                            rl.ffi.new("float *", gc.lens_zoom), rl.SHADER_UNIFORM_FLOAT)

        #  DRAW
        # Build the keyhole mask first (its own offscreen pass), then the scene
        # multiplies itself by it at the end of draw_on_texture.
        render_keyhole_mask(gc)
        draw_on_texture(gc, render_tex)

        # Whole-render-texture blit pass: nausea curse takes over when active,
        # otherwise the magnifier lens (a passthrough unless RMB is held).
        is_nauseous = getattr(gc, "nausea_curse_active", False)
        active_shader = nausea_shader if is_nauseous else gc.magnifier_shader

        #  BLIT RENDER TEXTURE → SCREEN
        blit_on_screen(gc, render_tex, src_rect, active_shader)
        

        await asyncio.sleep(0)

    # --- Cleanup ---
    rl.unload_shader(gc.painting_shader)
    rl.unload_shader(gc.magnifier_shader)
    rl.unload_shader(nausea_shader)
    rl.unload_render_texture(render_tex)
    rl.unload_render_texture(gc.keyhole_mask)
    gc.unload_models()
    gc.unload_textures()
    gc.unload_fonts()
    rl.close_window()


if __name__ == "__main__":
    asyncio.run(main())
