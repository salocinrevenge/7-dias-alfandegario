import pyray as rl
from pyray import Vector3, Vector2
from pyray import Camera3D


def draw_inspect_3d(gs: dict, camera: Camera3D, models, textures, VIRTUAL_W, VIRTUAL_H, TABLE_POS, TABLE_SCALE, OBJECT_POS):
    """Draws only the 3D scene into the render texture (no overlays)."""
    rl.clear_background(rl.BLACK)

    rl.draw_texture_pro(
        textures["bg"],

        rl.Rectangle(0, 0, textures["bg"].width, textures["bg"].height),
        rl.Rectangle(0, 0, VIRTUAL_W, VIRTUAL_H),
        Vector2(0, 0), 0.0, rl.GRAY,
    )

    rl.begin_mode_3d(camera)
    rl.draw_model(models["table"], TABLE_POS, TABLE_SCALE, rl.WHITE)
    models["object"].transform = gs["object_transform"]
    rl.draw_model(models["object"], OBJECT_POS, 1.0, rl.Color(255, 255, 255, 255))
    rl.end_mode_3d()