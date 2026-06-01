import pyray as rl
from pyray import Vector3
import math
import time

from .game_context import Game_context
from .utils import _arcball_point, get_scaled_rect, _screen_to_virtual


def _draw_rounded_rect(x: int, y: int, w: int, h: int, r: int, color):
    """Draw a filled rounded rectangle using rects + corner circles."""
    r = min(r, w // 2, h // 2)
    inner_x = x + r
    inner_y = y + r
    inner_w = w - 2 * r
    inner_h = h - 2 * r
    # Centre
    if inner_w > 0 and inner_h > 0:
        rl.draw_rectangle(inner_x, inner_y, inner_w, inner_h, color)
    # Four edges
    if inner_w > 0:
        rl.draw_rectangle(inner_x, y, inner_w, r, color)
        rl.draw_rectangle(inner_x, y + h - r, inner_w, r, color)
    if inner_h > 0:
        rl.draw_rectangle(x, inner_y, r, inner_h, color)
        rl.draw_rectangle(x + w - r, inner_y, r, inner_h, color)
    # Four corners
    rl.draw_circle(x + r, y + r, r, color)
    rl.draw_circle(x + w - r, y + r, r, color)
    rl.draw_circle(x + r, y + h - r, r, color)
    rl.draw_circle(x + w - r, y + h - r, r, color)


# ---------------------------------------------------------------------------
# RENDER-TEXTURE SCALING (letterbox / pillarbox)
# ---------------------------------------------------------------------------
class Player:
    def __init__(self, gc: Game_context):
        self.gc = gc

    def draw_hud(self, dst: rl.Rectangle):
        """Inspect HUD — drawn directly on screen after the shader blit."""
        bx = int(dst.x) + 8
        by = int(dst.y + dst.height) - 20
        # rl.draw_text(
            # b"[LMB] Papel   [RMB] Zoom   [P] Pause   [F] Fullscreen   [K] Painting",
            # bx, by, 11, rl.Color(120, 100, 65, 190))

        self._draw_hunger_panel(dst)
        self._draw_food_indicator(dst)
        self._draw_food_feedback(dst)

    # ------------------------------------------------------------------
    # Hunger panel (top-right)
    # ------------------------------------------------------------------

    def _draw_hunger_panel(self, dst: rl.Rectangle):
        gc = self.gc
        panel_w = int(dst.width * 0.16)
        bar_h = int(dst.height * 0.022)
        pad = int(dst.height * 0.022)
        x = int(dst.x + dst.width - panel_w - pad)
        y = int(dst.y + pad)

        ratio = gc.hunger / gc.hunger_max if gc.hunger_max > 0 else 0.0

        # Panel background — rounded rect via stacked rects + corner circles
        _draw_rounded_rect(x, y, panel_w, bar_h + 26, 8, rl.Color(8, 6, 14, 195))

        # ---- Label row ----
        icon = "FOME"
        label = f"{icon}  {int(gc.hunger)}%".encode("utf-8")
        fs = int(bar_h * 0.65)
        rl.draw_text(label, x + 10, y + 2, fs, rl.Color(200, 180, 150, 230))

        # ---- Bar ----
        bx = x + 8
        by = y + 18
        bw = panel_w - 16
        bh = bar_h

        # Bar background (dark groove)
        _draw_rounded_rect(bx, by, bw, bh, 5, rl.Color(20, 12, 10, 220))

        # Filled portion — gradient via two overlapping rects
        fill_w = int(bw * ratio)
        if fill_w > 0:
            if ratio > 0.5:
                col_hi = rl.Color(90, 200, 70, 240)
                col_lo = rl.Color(160, 210, 50, 240)
            elif ratio > 0.2:
                col_hi = rl.Color(230, 190, 40, 240)
                col_lo = rl.Color(240, 150, 30, 240)
            else:
                pulse = 0.7 + 0.3 * abs(math.sin(time.time() * 4.0))
                r = int(220 + 35 * pulse)
                g = int(40 + 20 * pulse)
                b = int(25 + 15 * pulse)
                col_hi = rl.Color(r, g, b, 240)
                col_lo = rl.Color(max(0, r - 80), max(0, g - 20), max(0, b - 10), 240)

            # Gradient: draw two halves
            half = fill_w // 2
            if half > 0:
                rl.draw_rectangle(bx, by, half, bh, col_lo)
            if fill_w - half > 0:
                rl.draw_rectangle(bx + half, by, fill_w - half, bh, col_hi)
            # Round the left cap
            rl.draw_circle(bx + 3, by + bh // 2, bh // 2, col_lo)
            rl.draw_circle(bx + fill_w - 3, by + bh // 2, bh // 2 - 1,
                           col_hi if fill_w > half else col_lo)
            # Cover corners with dark
            if fill_w < bw - 4:
                rl.draw_circle(bx + fill_w - 3, by + bh // 2, bh // 2 - 1,
                               rl.Color(20, 12, 10, 220))

        # Border over the bar for clean edges
        rl.draw_rectangle_lines(bx, by, bw, bh, rl.Color(50, 35, 25, 140))

    # ------------------------------------------------------------------
    # Food indicator (below hunger panel when item is food)
    # ------------------------------------------------------------------

    def _draw_food_indicator(self, dst: rl.Rectangle):
        gc = self.gc
        items = gc.itens_hoje.get("to evaluate", [])
        if not items:
            return
        item = items[0]
        if not item.is_food:
            return
        if gc.gs.get("object_hidden"):
            return

        panel_w = int(dst.width * 0.16)
        pad = int(dst.height * 0.022)
        x = int(dst.x + dst.width - panel_w - pad)
        y = int(dst.y + pad + dst.height * 0.022 + 26 + 8)

        # Small food tag
        tag_w = panel_w
        tag_h = int(dst.height * 0.024)
        _draw_rounded_rect(x, y, tag_w, tag_h, 6, rl.Color(30, 18, 8, 200))

        label = b"COMIDA"
        fs = int(tag_h * 0.65)
        tw = rl.measure_text(label, fs)
        rl.draw_text(label, x + (tag_w - tw) // 2, y + max(1, (tag_h - fs) // 2),
                     fs, rl.Color(255, 200, 100, 220))

    # ------------------------------------------------------------------
    # Food feedback popup
    # ------------------------------------------------------------------

    def _draw_food_feedback(self, dst: rl.Rectangle):
        """Flash the food eat feedback message."""
        gc = self.gc
        msg = gc.gs.get("food_msg", "")
        timer = gc.gs.get("food_msg_timer", 0.0)
        if not msg or timer <= 0:
            return
        cx = int(dst.x + dst.width / 2)
        cy = int(dst.y + dst.height * 0.60)
        fs = int(dst.height * 0.045)
        alpha = int(min(1.0, timer / 0.3) * 255)
        tw = rl.measure_text(msg.encode("utf-8"), fs)
        rl.draw_text(msg.encode("utf-8"), cx - tw // 2, cy, fs, rl.Color(255, 255, 255, alpha))

    # ------------------------------------------------------------------
    # Original methods
    # ------------------------------------------------------------------

    def update_object(self): # Mouse-driven arcball rotation for the inspected object.
        dst  = get_scaled_rect(self.gc)
        vpos = _screen_to_virtual(self.gc, rl.get_mouse_position(), dst)
        ray  = rl.get_screen_to_world_ray_ex(vpos, self.gc.camera, self.gc.VIRTUAL_W, self.gc.VIRTUAL_H)

        p1, on_object = _arcball_point(ray, self.gc.OBJECT_POS, self.gc._OBJECT_RADIUS)

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and on_object:
            self.gc.gs["dragging"]   = True
            self.gc.gs["spin_angle"] = 0.0
            self.gc.gs["drag_dir"]   = p1

        if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self.gc.gs["dragging"] = False

        if self.gc.gs["dragging"] and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
            p0 = self.gc.gs["drag_dir"]
            if p0 is not None:
                ax = p0[1]*p1[2] - p0[2]*p1[1]
                ay = p0[2]*p1[0] - p0[0]*p1[2]
                az = p0[0]*p1[1] - p0[1]*p1[0]
                axis_len = math.sqrt(ax*ax + ay*ay + az*az)

                if axis_len > 1e-6:
                    dot   = max(-1.0, min(1.0, p0[0]*p1[0] + p0[1]*p1[1] + p0[2]*p1[2]))
                    angle = math.acos(dot)
                    na    = (ax/axis_len, ay/axis_len, az/axis_len)
                    rot   = rl.matrix_rotate(Vector3(*na), angle)
                    self.gc.gs["object_transform"] = rl.matrix_multiply(self.gc.gs["object_transform"], rot)
                    self.gc.gs["spin_axis"]  = na
                    self.gc.gs["spin_angle"] = angle

                self.gc.gs["drag_dir"] = p1
        else:
            if self.gc.gs["spin_angle"] > 1e-5:
                rot = rl.matrix_rotate(Vector3(*self.gc.gs["spin_axis"]), self.gc.gs["spin_angle"])
                self.gc.gs["object_transform"] = rl.matrix_multiply(self.gc.gs["object_transform"], rot)
            self.gc.gs["spin_angle"] *= 0.88
