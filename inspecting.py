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
        Vector2(0, 0), 0.0, rl.Color(255, 185, 185, 255),
    )

    rl.begin_mode_3d(gc.camera)
    rl.draw_model(gc.models["table"], gc.TABLE_POS, gc.TABLE_SCALE, rl.WHITE)
    gc.models["object"].transform = gc.gs["object_transform"]
    rl.draw_model(gc.models["object"], gc.OBJECT_POS, 1.0, rl.Color(255, 255, 255, 255))
    rl.end_mode_3d()

def update_inspect(gc: Game_context, dt: float):
    if rl.is_key_pressed(rl.KEY_F1):
        gc.gs["debug"] = not gc.gs["debug"]
        if gc.gs["debug"]:
            rl.disable_cursor()
        else:
            rl.enable_cursor()

    if gc.gs["debug"]:
        gc.player.update_debug_camera(dt)
    else:
        gc.player.update_object()
