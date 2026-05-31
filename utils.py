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





def wrap_text(font, text: str, font_size: int, spacing: int, max_width: float) -> list[str]:
    """Wrap text to max_width, preserving explicit newlines (poem stanzas/verses)."""
    lines = []
    for raw_line in text.split('\n'):
        words = raw_line.split(' ')
        current = []
        for word in words:
            test = " ".join(current + [word])
            w = rl.measure_text_ex(font, test.encode('utf-8'), font_size, spacing).x
            if w > max_width and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        # Keep blank lines (empty raw_line) so poem spacing survives.
        lines.append(" ".join(current))
    return lines


def draw_text_box(font, text: str, center: Vector2, font_size: int, *,
                  spacing: int = 1, line_spacing: float = 1.5,
                  align: str = "center", color=None, shadow_color=None,
                  shadow_offset: int = 2):
    """Draw multi-line text centered on `center` (the block's middle point).

    Each line is aligned (`center` or `left`) and gets a fake drop shadow,
    a second darker copy drawn a few pixels down-right.
    """
    color = rl.WHITE if color is None else color
    shadow_color = rl.BLACK if shadow_color is None else shadow_color

    drawn_lines = text.split('\n')
    line_height = int(font_size * line_spacing)
    total_h = line_height * len(drawn_lines)
    start_y = center.y - total_h / 2.0

    for i, line in enumerate(drawn_lines):
        line_w = rl.measure_text_ex(font, line.encode('utf-8'), font_size, spacing).x
        if align == "left":
            x = center.x
        else:  # center
            x = center.x - line_w / 2.0
        y = start_y + i * line_height

        encoded = line.encode('utf-8')
        # Fake shadow first, then the foreground text on top.
        rl.draw_text_ex(font, encoded,
                        Vector2(x + shadow_offset, y + shadow_offset),
                        font_size, spacing, shadow_color)
        rl.draw_text_ex(font, encoded, Vector2(x, y), font_size, spacing, color)


def get_scaled_rect(gc: Game_context) -> rl.Rectangle:
    sw, sh = rl.get_screen_width(), rl.get_screen_height()
    scale  = min(sw / gc.VIRTUAL_W, sh / gc.VIRTUAL_H)
    dw, dh = gc.VIRTUAL_W * scale, gc.VIRTUAL_H * scale
    return rl.Rectangle((sw - dw) / 2, (sh - dh) / 2, dw, dh)