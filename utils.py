import math
import pyray as rl
from pyray import Vector3, Vector2

from game_context import Game_context


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





def get_scaled_rect(gc: Game_context) -> rl.Rectangle:
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    scale  = min(sw / gc.VIRTUAL_W, sh / gc.VIRTUAL_H)
    dw, dh = gc.VIRTUAL_W * scale, gc.VIRTUAL_H * scale
    return rl.Rectangle((sw - dw) / 2, (sh - dh) / 2, dw, dh)