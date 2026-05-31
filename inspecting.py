import pyray as rl
from pyray import Vector2
from pyray import Camera3D

from game_context import Game_context


def draw_inspect_3d( gc: Game_context):
    """Draws only the 3D scene into the render texture (no overlays)."""
    rl.clear_background(rl.BLACK)

    rl.draw_texture_pro(
        gc.textures["bg"],

        rl.Rectangle(0, 0, gc.textures["bg"].width, gc.textures["bg"].height),
        rl.Rectangle(0, 0, gc.VIRTUAL_W, gc.VIRTUAL_H),
        Vector2(0, 0), 0.0, rl.GRAY,
    )

    rl.begin_mode_3d(gc.camera)
    rl.draw_model(gc.models["table"], gc.TABLE_POS, gc.TABLE_SCALE, rl.WHITE)
    if len(gc.itens_hoje['to evaluate']) > 0:
        gc.models[gc.itens_hoje['to evaluate'][0].name].transform = gc.gs["object_transform"]
        rl.draw_model(gc.models[gc.itens_hoje['to evaluate'][0].name], gc.OBJECT_POS, 1.0, rl.Color(255, 255, 255, 255))
        
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
    else:
        gc.player.update_object()
    if len(gc.itens_hoje['to evaluate']) == 0:
        gc.count_until_end_day -= 1
    if gc.count_until_end_day <= 0:
        gc.count_until_end_day = gc.reset_count_until_end_day
        gc.start_new_day()

def draw_tutorial_talk(gc: Game_context):
    if gc.tutorial_index >= len(gc.tutorial_texts):
        return
    text = gc.tutorial_texts[gc.tutorial_index]
    
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    font_size = int(max(sh * 0.045, 20))
    padding = int(sw * 0.1)
    max_w = sw - padding * 2

    # Wrap text dynamically
    words = text.split(' ')
    lines = []
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