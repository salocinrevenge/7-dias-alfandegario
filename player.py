import pyray as rl
from pyray import Vector3
import math

from game_context import Game_context
from utils import _arcball_point, get_scaled_rect, _screen_to_virtual


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
        if self.gc.gs.get("debug"):
            rl.draw_text(b"DEBUG CAM  [WASD] Move  [Mouse] Look  [F1] Exit",
                        bx, by, 11, rl.Color(80, 220, 80, 220))
        else:
            rl.draw_text(
                b"[LMB] Rotate   [P] Pause   [F] Fullscreen   [F1] Debug cam   [K] Painting",
                bx, by, 11, rl.Color(120, 100, 65, 190))

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


    def update_debug_camera(self, dt: float): # 
        camera = self.gc.camera
        delta = rl.get_mouse_delta()
        self.gc.gs["cam_yaw"]   -= delta.x * 0.003
        self.gc.gs["cam_pitch"] -= delta.y * 0.003
        self.gc.gs["cam_pitch"]  = max(-1.2, min(1.2, self.gc.gs["cam_pitch"]))

        yaw, pitch = self.gc.gs["cam_yaw"], self.gc.gs["cam_pitch"]
        dx = math.sin(yaw) * math.cos(pitch)
        dy = math.sin(pitch)
        dz = math.cos(yaw) * math.cos(pitch)
        forward = Vector3(dx, dy, dz)
        right   = Vector3(math.cos(yaw), 0.0, -math.sin(yaw))

        speed = 3.0 * dt
        p = self.gc.gs["cam_pos"]
        if rl.is_key_down(rl.KEY_W): p.x += forward.x*speed; p.y += forward.y*speed; p.z += forward.z*speed
        if rl.is_key_down(rl.KEY_S): p.x -= forward.x*speed; p.y -= forward.y*speed; p.z -= forward.z*speed
        if rl.is_key_down(rl.KEY_A): p.x += right.x*speed;   p.z += right.z*speed
        if rl.is_key_down(rl.KEY_D): p.x -= right.x*speed;   p.z -= right.z*speed

        camera.position = Vector3(p.x, p.y, p.z)
        camera.target   = Vector3(p.x + dx, p.y + dy, p.z + dz)