import pyray as rl
from game_context import Game_context
from state import State
from utils import wrap_text, draw_text_box


def _get_end_title(state):
    if state == State.GAME_OVER_FIRED:
        return "DEMITIDO"
    elif state == State.GAME_OVER_WIN:
        return "ESTAGIO CONCLUIDO"
    elif state == State.GAME_OVER_EXPLODED:
        return "EXPLODIU TUDO"
    return ""


def _get_end_subtitle(state):
    if state == State.GAME_OVER_FIRED:
        return "Erros demais. O reino nao tolera incompetencia."
    elif state == State.GAME_OVER_WIN:
        return "Sete dias de trabalho impecavel. O reino agradece."
    elif state == State.GAME_OVER_EXPLODED:
        return "O Livro Nuclear passou. Nao sobrou nada."
    return ""


def get_end_screen_color(state):
    if state == State.GAME_OVER_FIRED:
        return rl.Color(60, 10, 10, 255)
    elif state == State.GAME_OVER_WIN:
        return rl.Color(10, 40, 20, 255)
    elif state == State.GAME_OVER_EXPLODED:
        return rl.Color(70, 5, 5, 255)
    return rl.BLACK


def update_end_state(gc: Game_context, dt: float):
    if rl.is_key_pressed(rl.KEY_ENTER):
        gc.dia_atual = 0
        gc.n_erros = 0
        gc.penalidade = 0
        gc.total_items_judged = 0
        gc.total_correct = 0
        gc.total_foods = 0
        gc.tutorial_seen = False
        gc.tutorial_index = 0
        gc.tutorial_char_count = 0
        gc.transition.start(State.MENU)


def draw_end_state(gc: Game_context):
    bg_color = get_end_screen_color(gc.current_state)
    rl.clear_background(bg_color)

    font = gc.fonts["serif"]
    sw, sh = gc.VIRTUAL_W, gc.VIRTUAL_H

    title = _get_end_title(gc.current_state)
    subtitle = _get_end_subtitle(gc.current_state)

    # Title
    title_fs = int(sh * 0.10)
    tw = rl.measure_text_ex(font, title.encode("utf-8"), title_fs, 1).x
    rl.draw_text_ex(font, title.encode("utf-8"),
                    rl.Vector2((sw - tw) / 2, sh * 0.08),
                    title_fs, 1, rl.WHITE)

    # Subtitle
    sub_fs = int(sh * 0.026)
    tw = rl.measure_text_ex(font, subtitle.encode("utf-8"), sub_fs, 1).x
    rl.draw_text_ex(font, subtitle.encode("utf-8"),
                    rl.Vector2((sw - tw) / 2, sh * 0.22),
                    sub_fs, 1, rl.Color(200, 180, 150, 230))

    # Divider line
    line_y = int(sh * 0.26)
    rl.draw_line(int(sw * 0.25), line_y, int(sw * 0.75), line_y,
                 rl.Color(120, 90, 60, 200))

    # Stats
    total = gc.total_items_judged
    correct = gc.total_correct
    errors = gc.n_erros
    penalties = gc.penalidade
    foods = gc.total_foods
    days = max(1, gc.dia_atual)

    stats_fs = int(sh * 0.030)
    lh = stats_fs * 1.8

    lines = [
        f"Dias trabalhados: {days}",
        f"Itens avaliados: {total}",
        f"Acertos: {correct}  |  Erros: {errors}",
        f"Penalidades acumuladas: {penalties}",
        f"Comidas consumidas: {foods}",
    ]

    # Grade
    if total > 0:
        pct = int(correct / total * 100)
        grade = "S" if pct >= 90 else ("A" if pct >= 70 else ("B" if pct >= 50 else "C"))
        grade_color = (rl.Color(90, 220, 80, 255) if pct >= 70 else
                       rl.Color(230, 190, 40, 255) if pct >= 50 else
                       rl.Color(220, 50, 30, 255))
        lines.append(f"Nota final: {grade} ({pct}%)")

    for i, line in enumerate(lines):
        lb = line.encode("utf-8")
        tw = rl.measure_text_ex(font, lb, stats_fs, 1).x
        cy = sh * 0.30 + i * lh
        color = grade_color if total > 0 and i == len(lines) - 1 else rl.Color(210, 190, 160, 240)
        rl.draw_text_ex(font, lb, rl.Vector2((sw - tw) / 2, cy), stats_fs, 1, color)

    # Prompt
    prompt_fs = int(sh * 0.024)
    prompt = "Pressione ENTER para voltar ao menu"
    tw = rl.measure_text_ex(font, prompt.encode("utf-8"), prompt_fs, 1).x
    rl.draw_text_ex(font, prompt.encode("utf-8"),
                    rl.Vector2((sw - tw) / 2, sh * 0.82),
                    prompt_fs, 1, rl.Color(140, 120, 90, 220))
