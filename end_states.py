import pyray as rl
from game_context import Game_context
from state import State
from utils import wrap_text, draw_text_box

def get_end_screen_text(state):
    if state == State.GAME_OVER_FIRED:
        return "Voce cometeu erros demais e foi demitido"
    elif state == State.GAME_OVER_WIN:
        return "Parabens voce concluiu o seu estagio de alfandegario, agora esta preparado para uma vida toda fazendo isso! Por enquanto voce pode sair e curtir a vida enquanto seu chefe nao percebe que voce ja acabou"
    elif state == State.GAME_OVER_EXPLODED:
        return "Voce passou o livro NUCLEAR?!! Ele Explodiu e todos morreram!!! Incluindo voce. Esta feliz???"
    return ""

def get_end_screen_color(state):
    if state == State.GAME_OVER_FIRED:
        return rl.Color(139, 0, 0, 255) # Dark Red
    elif state == State.GAME_OVER_WIN:
        return rl.Color(0, 100, 0, 255) # Dark Green
    elif state == State.GAME_OVER_EXPLODED:
        return rl.Color(139, 0, 0, 255) # Dark Red
    return rl.BLACK

def update_end_state(gc: Game_context, dt: float):
    # Wait for enter to restart the game
    if rl.is_key_pressed(rl.KEY_ENTER):
        # Reset game variables
        gc.dia_atual = 0
        gc.n_erros = 0
        gc.penalidade = 0
        gc.reset_tutorial_texts()
        gc.tutorial_seen = False
        gc.tutorial_index = 0
        gc.tutorial_char_count = 0
        gc.transition.start(State.MENU)

def draw_end_state(gc: Game_context):
    bg_color = get_end_screen_color(gc.current_state)
    rl.clear_background(bg_color)
    
    font = gc.fonts["serif"]
    sw, sh = gc.VIRTUAL_W, gc.VIRTUAL_H
    
    text = get_end_screen_text(gc.current_state)
    lines = wrap_text(font, text, 48, 1, sw * 0.8)
    wrapped_text = "\n".join(lines)
    
    # Draw main text in the center
    draw_text_box(
        font,
        wrapped_text,
        rl.Vector2(sw / 2.0, sh / 2.0 - 50.0),
        48,
        spacing=0,
        line_spacing=1.5,
        align="center",
        shadow_offset=max(2, int(48 * 0.08)),
    )
    
    # Draw stats and prompt to restart
    stats_text = f"Erros: {gc.n_erros}   Dia alcancado: {max(1, gc.dia_atual)}"
    prompt_text = "Pressione ENTER para voltar ao menu inicial"
    
    draw_text_box(
        font,
        stats_text,
        rl.Vector2(sw / 2.0, sh / 2.0 + 50.0),
        36,
        spacing=0,
        line_spacing=1.5,
        align="center",
        shadow_offset=2,
    )
    
    draw_text_box(
        font,
        prompt_text,
        rl.Vector2(sw / 2.0, sh / 2.0 + 100.0),
        36,
        spacing=0,
        line_spacing=1.5,
        align="center",
        shadow_offset=2,
    )
