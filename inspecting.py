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
    # Desenhe o balão de fala do tutorial
    rl.draw_text("Bem vindo ao seu primeiro dia como alfandegário. Você deve avaliar os itens que chegarem catalogando as suas características no papel e " \
    "aceitando eles. Caso suspeite de ser algum mimico, ser evenenado, radioativo, amaldiçoado ou importado de uma nação inimiga, você deve rejeitá-los. " \
    "Caso apareça o livro nuclear, o rejeite, ele pode destruir todos nós." \
    "Você tem 7 dias de trabalho. Caso erre demais, poderá ter que trabalhar novamente segundo suas cartas de reclamacões. Se errar demais, será demitido. Bom trabalho!", 60, gc.VIRTUAL_H - 130, 20, rl.WHITE)