import pyray as rl
from pyray import Vector2
from pyray import Rectangle
import math

def draw_menu(now: float, dst: rl.Rectangle, font: rl.Font):
    """Menu text overlays — drawn on screen after the shader blit.

    All positions/sizes are relative to `dst` (the letterboxed scene rect) so the
    title and prompt stay glued to the menu artwork and scale with it, identically
    on desktop and web, rather than floating in the black bars.
    """
    ox, oy = dst.x, dst.y
    sw, sh = dst.width, dst.height
    cx = ox + sw / 2

    def _measure(text: bytes, size: float) -> int:
        return int(rl.measure_text_ex(font, text, size, 1).x)

    def _draw(text: bytes, x: float, y: float, size: float, color):
        rl.draw_text_ex(font, text, rl.Vector2(float(x), float(y)), size, 1, color)

    # Dark wash over the menu art so the title pops. Covers only the scene rect
    # (the surrounding bars are already black). draw_rectangle takes ints.
    rl.draw_rectangle(int(ox), int(oy), int(sw), int(sh), rl.Color(0, 0, 0, 80))

    t = now * 1.2
    offset_y = int(math.sin(t) * 4)

    # --- Title ---
    title_size = float(max(58, sh // 6))
    title = b"7 Dias de Alfandegario"
    tw = _measure(title, title_size)
    ty = oy + sh * 0.43 + offset_y
    # Subtle shadow
    _draw(title, cx - tw // 2 + 5, ty + 5, title_size, rl.Color(0, 0, 0, 120))
    _draw(title, cx - tw // 2, ty, title_size, rl.Color(220, 220, 180, 255))

    # # --- Divider line ---
    line_y = oy + sh * 0.59
    line_hw = sw // 6
    rl.draw_line_ex((cx - line_hw, line_y), (cx + line_hw, line_y), 5, rl.Color(220, 220, 180, 180))

    # # --- Prompt (pulsing) ---
    pulse = int((math.sin(now * 2.5) * 0.5 + 0.5) * 200 + 55)
    prompt_size = float(max(14, sh // 20))
    prompt = b"Clique ou aperte ENTER para jogar"
    pw = _measure(prompt, prompt_size)
    _draw(prompt, cx - pw // 2, oy + sh * 0.60, prompt_size, rl.Color(220, 220, 180, pulse))

def draw_menu_bg_into_texture(menu_bg_tex, VIRTUAL_W, VIRTUAL_H):
    """Fills the render texture with outside.png (cover-fit). Shader will paint this."""
    rl.clear_background(rl.BLACK)
    tw, th = menu_bg_tex.width, menu_bg_tex.height
    if tw == 0 or th == 0:
        return
    tex_aspect = tw / th
    virt_aspect = VIRTUAL_W / VIRTUAL_H if VIRTUAL_H > 0 else 1.0
    if virt_aspect > tex_aspect:
        dw = VIRTUAL_W
        dh = VIRTUAL_W / tex_aspect
    else:
        dh = VIRTUAL_H
        dw = VIRTUAL_H * tex_aspect
    dx = (VIRTUAL_W - dw) * 0.5
    dy = (VIRTUAL_H - dh) * 0.5
    rl.draw_texture_pro(
        menu_bg_tex,
        rl.Rectangle(0, 0, tw, th),
        rl.Rectangle(dx, dy, dw, dh),
        Vector2(0, 0), 0.0, rl.Color(245, 143, 143, 255),
    )
