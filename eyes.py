import pyray as rl
from pyray import Vector3
import random
import math


# ---------------------------------------------------------------------------
# Eye texture generation
# ---------------------------------------------------------------------------

def _generate_eye_texture():
    size = 32
    img = rl.gen_image_color(size, size, rl.Color(0, 0, 0, 0))
    rl.image_format(img, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
    data = rl.ffi.cast("unsigned char *", img.data)
    cx, cy = size / 2.0, size / 2.0
    outer_r = size / 2.0 - 1.0
    mid_r = outer_r - 2.0
    pupil_r = 3.0
    highlight_r = 2.0

    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            idx = (y * size + x) * 4

            if dist <= outer_r:
                a_val = 170
                r_val, g_val, b_val = 28, 20, 14

                if dist <= mid_r:
                    r_val, g_val, b_val = 50, 35, 22
                    a_val = 200

                if dist <= pupil_r:
                    r_val, g_val, b_val = 12, 8, 5
                    a_val = 230

                if dist <= highlight_r and dx > 0 and dy < 0:
                    r_val, g_val, b_val = 220, 210, 190
                    a_val = 240

                data[idx]     = r_val
                data[idx + 1] = g_val
                data[idx + 2] = b_val
                data[idx + 3] = a_val
            else:
                fade = max(0.0, min(1.0, outer_r + 1.5 - dist))
                if fade > 0:
                    a = int(170 * fade)
                    data[idx]     = 28
                    data[idx + 1] = 20
                    data[idx + 2] = 14
                    data[idx + 3] = a

    tex = rl.load_texture_from_image(img)
    rl.set_texture_filter(tex, rl.TEXTURE_FILTER_BILINEAR)
    rl.unload_image(img)
    return tex


# ---------------------------------------------------------------------------
# Matrix utilities
# ---------------------------------------------------------------------------

def _matrix_transform_point(mat, point):
    return Vector3(
        mat.m0 * point.x + mat.m4 * point.y + mat.m8  * point.z + mat.m12,
        mat.m1 * point.x + mat.m5 * point.y + mat.m9  * point.z + mat.m13,
        mat.m2 * point.x + mat.m6 * point.y + mat.m10 * point.z + mat.m14,
    )


# ---------------------------------------------------------------------------
# Surface position picking (model-local 3D coords)
# ---------------------------------------------------------------------------

def _weighted_random_tri(tris):
    total = sum(t["area"] for t in tris)
    if total < 1e-8:
        return random.choice(tris)
    r = random.random() * total
    accum = 0.0
    for t in tris:
        accum += t["area"]
        if accum >= r:
            return t
    return tris[-1]


def _find_eye_positions(model):
    all_tris = []

    for mi in range(model.meshCount):
        mesh = model.meshes[mi]
        if mesh.triangleCount == 0 or not mesh.indices or not mesh.vertices:
            continue

        vc = mesh.vertexCount
        tc = mesh.triangleCount
        vert_raw = rl.ffi.unpack(mesh.vertices, vc * 3)
        idx_raw = rl.ffi.unpack(mesh.indices, tc * 3)

        for ti in range(tc):
            a = idx_raw[ti * 3]
            b = idx_raw[ti * 3 + 1]
            c = idx_raw[ti * 3 + 2]

            ax, ay, az = vert_raw[a * 3], vert_raw[a * 3 + 1], vert_raw[a * 3 + 2]
            bx, by, bz = vert_raw[b * 3], vert_raw[b * 3 + 1], vert_raw[b * 3 + 2]
            cx, cy, cz = vert_raw[c * 3], vert_raw[c * 3 + 1], vert_raw[c * 3 + 2]

            nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay)
            ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az)
            nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nl < 1e-8:
                continue

            area = nl * 0.5
            normal_y = ny / nl

            if normal_y < -0.25:
                continue

            all_tris.append({
                "area": area,
                "verts": (Vector3(ax, ay, az), Vector3(bx, by, bz), Vector3(cx, cy, cz)),
                "centroid": Vector3(
                    (ax + bx + cx) / 3.0,
                    (ay + by + cy) / 3.0,
                    (az + bz + cz) / 3.0,
                ),
            })

    if not all_tris:
        return None

    def _random_point_in_tri(tri):
        A, B, C = tri["verts"]
        r1 = random.random()
        r2 = random.random()
        if r1 + r2 > 1.0:
            r1 = 1.0 - r1
            r2 = 1.0 - r2
        return Vector3(
            A.x + r1 * (B.x - A.x) + r2 * (C.x - A.x),
            A.y + r1 * (B.y - A.y) + r2 * (C.y - A.y),
            A.z + r1 * (B.z - A.z) + r2 * (C.z - A.z),
        )

    positions = []

    for eye_idx in range(2):
        for _ in range(200):
            tri = _weighted_random_tri(all_tris)
            pos = _random_point_in_tri(tri)

            if eye_idx == 0:
                positions.append(pos)
                break

            dist = math.sqrt(
                (pos.x - positions[0].x) ** 2 +
                (pos.y - positions[0].y) ** 2 +
                (pos.z - positions[0].z) ** 2
            )
            if dist > 0.006:
                positions.append(pos)
                break
        else:
            tri = all_tris[eye_idx % len(all_tris)]
            pos = tri["centroid"]
            positions.append(pos)

    return positions if len(positions) == 2 else None


# ---------------------------------------------------------------------------
# MimicEyes class
# ---------------------------------------------------------------------------

class MimicEyes:
    def __init__(self):
        self.eye_tex = None
        self.positions = []
        self.alpha = 0.0
        self.target_alpha = 0.0
        self.hidden = True
        self._blink_timer = random.uniform(1.0, 3.0)
        self._next_blink = random.uniform(2.0, 5.0)
        self._close_timer = 0.0
        self._close_duration = 0.0
        self._reposition_timer = random.uniform(4.0, 10.0)
        self._next_reposition = random.uniform(8.0, 20.0)
        self._models_found = False
        self._needs_reposition = False
        self._tremoring = False
        self._tremor_timer = 0.0
        self._next_tremor = random.uniform(5.0, 20.0)
        self._tremor_duration = 0.0
        self._hidden_wait = 0.0
        self._hidden_target = 0.0

    def setup(self, model):
        if self.eye_tex is None:
            self.eye_tex = _generate_eye_texture()
        positions = _find_eye_positions(model)
        if positions:
            self.positions = positions
            self._models_found = True
            self.target_alpha = 1.0
            self.hidden = False
            self.alpha = 0.0

    def update(self, dt, model, anim=None):
        if not self._models_found:
            return

        if anim is not None:
            if self._tremoring:
                self._tremor_timer += dt
                if self._tremor_timer >= self._tremor_duration:
                    self._tremoring = False
                    anim.amplitude = 0.001
                    anim.velocity = 0.3
            else:
                self._tremor_timer += dt
                if self._tremor_timer >= self._next_tremor:
                    self._tremor_timer = 0.0
                    self._next_tremor = random.uniform(5.0, 20.0)
                    self._tremor_duration = random.uniform(0.06, 0.18)
                    self._tremoring = True
                    anim.amplitude = 0.0015
                    anim.velocity = 5.0

        self._reposition_timer += dt
        if self._reposition_timer >= self._next_reposition and not self.hidden:
            self._reposition_timer = 0.0
            self._next_reposition = random.uniform(8.0, 20.0)
            self._hidden_target = random.uniform(0.5, 3.0)
            self._hidden_wait = 0.0
            self.target_alpha = 0.0
            self.hidden = True
            self._needs_reposition = True

        if self._needs_reposition and self.alpha < 0.05:
            self._hidden_wait += dt
            if self._hidden_wait >= self._hidden_target:
                positions = _find_eye_positions(model)
                if positions:
                    self.positions = positions
                self.target_alpha = 1.0
                self.hidden = False
                self._needs_reposition = False
                self._blink_timer = 0.0
                self._next_blink = random.uniform(1.5, 3.0)

        self._blink_timer += dt
        if not self.hidden and self.target_alpha > 0.5 and self._blink_timer >= self._next_blink:
            self._blink_timer = 0.0
            self._next_blink = random.uniform(0.08, 0.15)
            self.target_alpha = 0.0

        if not self.hidden and self.target_alpha < 0.1 and self.alpha < 0.05:
            if self._close_timer <= 0:
                self._close_duration = random.uniform(0.08, 0.2)
            self._close_timer += dt
            if self._close_timer >= self._close_duration:
                self._close_timer = 0.0
                self._next_blink = random.uniform(2.0, 5.0)
                self._blink_timer = 0.0
                self.target_alpha = 1.0

        fade_speed = 12.0 if self.target_alpha == 0.0 else 8.0
        if self.alpha < self.target_alpha:
            self.alpha = min(self.target_alpha, self.alpha + fade_speed * dt)
        elif self.alpha > self.target_alpha:
            self.alpha = max(self.target_alpha, self.alpha - fade_speed * dt)

    def draw(self, camera, model_transform, draw_offset):
        if self.alpha < 0.01 or not self._models_found:
            return

        alpha_byte = int(self.alpha * 180)
        tint = rl.Color(255, 255, 255, alpha_byte)
        eye_size = 0.010

        for pos in self.positions:
            world_pos = _matrix_transform_point(model_transform, pos)
            world_pos.x += draw_offset.x
            world_pos.y += draw_offset.y
            world_pos.z += draw_offset.z

            rl.draw_billboard(camera, self.eye_tex, world_pos, eye_size, tint)

    def unload(self):
        if self.eye_tex is not None:
            rl.unload_texture(self.eye_tex)
            self.eye_tex = None
