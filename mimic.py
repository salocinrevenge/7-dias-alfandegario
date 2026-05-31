import pyray as rl
from pyray import Vector3
import random
import math


# ---------------------------------------------------------------------------
# Appendage models
# ---------------------------------------------------------------------------
# Instead of a flat painted eye, a mimic now grows a single 3D appendage out of
# the object's surface: an eye, a mouth, or a tentacle. The behaviour is the
# same as the old eyes (it appears, retracts, blinks and repositions itself),
# but it is rendered with a real model placed on the surface and aligned to the
# local surface normal.

APPENDAGE_MODELS = {
    "eye":      b"models/objects/monster_eye_lowpoly_animated/scene.gltf",
    "tentacle": b"models/objects/tentacle/scene.gltf",
}

# Target world-space "diameter" each appendage is scaled to (objects are fit to
# OBJECT_TARGET = 0.26, so these stay small relative to the host object).
APPENDAGE_SIZE = {
    "eye":      0.018,
    "tentacle": 0.030,
}

# Per-model base rotation (Euler X, Y, Z in degrees), applied to the model in
# its own local space BEFORE anything else. Tune these so each model's "base"
# sits at the bottom and it grows upward along +Y; the draw step then rotates
# that +Y onto the host surface normal. (All zero = use the model as authored.)
APPENDAGE_ROTATION = {
    "eye":      (0.0, 0.0, 0.0),
    "tentacle": (0.0, 0.0, 0.0),
}

# Shared, lazily-loaded model cache: kind -> (model, unit_scale, base_transform).
# Models are GPU resources, so every Mimic instance reuses the same handles;
# base_transform is the model's authored transform captured once (raylib mutates
# model.transform when drawing, so we keep a pristine copy to compose against).
_MODEL_CACHE = {}


def _load_appendage_models():
    if _MODEL_CACHE:
        return
    for kind, path in APPENDAGE_MODELS.items():
        model = rl.load_model(path)
        bb = rl.get_model_bounding_box(model)
        max_dim = max(bb.max.x - bb.min.x,
                      bb.max.y - bb.min.y,
                      bb.max.z - bb.min.z) or 1.0
        rx, ry, rz = APPENDAGE_ROTATION[kind]
        base_rot = rl.matrix_rotate_xyz(Vector3(math.radians(rx),
                                                math.radians(ry),
                                                math.radians(rz)))
        # Fold the chosen base rotation into the model's authored transform so
        # the +Y axis becomes the growth axis we align to the surface normal.
        base_transform = rl.matrix_multiply(model.transform, base_rot)
        _MODEL_CACHE[kind] = (model, 1.0 / max_dim, base_transform)


def preload_appendage_models():
    """Load every appendage model up front (at startup, with a GL context). The
    models are heavy, so loading them lazily mid-game causes a frame hitch the
    first time a mimic appears; warming the cache here avoids that stutter."""
    _load_appendage_models()


def unload_appendage_models():
    for model, _ in _MODEL_CACHE.values():
        rl.unload_model(model)
    _MODEL_CACHE.clear()


# ---------------------------------------------------------------------------
# Matrix / vector utilities
# ---------------------------------------------------------------------------

def _matrix_transform_point(mat, point):
    return Vector3(
        mat.m0 * point.x + mat.m4 * point.y + mat.m8  * point.z + mat.m12,
        mat.m1 * point.x + mat.m5 * point.y + mat.m9  * point.z + mat.m13,
        mat.m2 * point.x + mat.m6 * point.y + mat.m10 * point.z + mat.m14,
    )


def _matrix_transform_dir(mat, d):
    # Rotate a direction by the matrix's upper 3x3 (ignores translation).
    return Vector3(
        mat.m0 * d.x + mat.m4 * d.y + mat.m8  * d.z,
        mat.m1 * d.x + mat.m5 * d.y + mat.m9  * d.z,
        mat.m2 * d.x + mat.m6 * d.y + mat.m10 * d.z,
    )


def _normalize(v):
    l = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if l < 1e-8:
        return Vector3(0.0, 1.0, 0.0)
    return Vector3(v.x / l, v.y / l, v.z / l)


# ---------------------------------------------------------------------------
# Surface position picking (model-local 3D coords + outward normal)
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


def _collect_surface_tris(model):
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
            normal = Vector3(nx / nl, ny / nl, nz / nl)

            all_tris.append({
                "area": area,
                "verts": (Vector3(ax, ay, az), Vector3(bx, by, bz), Vector3(cx, cy, cz)),
                "normal": normal,
                "centroid": Vector3(
                    (ax + bx + cx) / 3.0,
                    (ay + by + cy) / 3.0,
                    (az + bz + cz) / 3.0,
                ),
            })

    return all_tris


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


def _find_appendage_spot(model, view_rot=None, cam_dir=None):
    """Pick one surface point on the object and the outward normal there,
    returned as (local_position, local_normal). None if the mesh is unusable.

    When *view_rot* (the object's current world rotation) and *cam_dir* (the
    world-space object→camera direction) are given, prefer faces that point
    AWAY from the camera, so the mimic trait hides on the far side and the
    player has to rotate the object to catch it."""
    tris = _collect_surface_tris(model)
    if not tris:
        return None

    candidates = tris
    if view_rot is not None and cam_dir is not None:
        hidden = []
        for t in tris:
            wn = _normalize(_matrix_transform_dir(view_rot, t["normal"]))
            facing = wn.x * cam_dir.x + wn.y * cam_dir.y + wn.z * cam_dir.z
            # Pointing away from the camera, and not straight down into the table.
            if facing < 0.1 and wn.y > -0.6:
                hidden.append(t)
        if hidden:
            candidates = hidden
    else:
        # No camera info: fall back to upward/outward faces (visible side).
        upward = [t for t in tris if t["normal"].y >= -0.25]
        if upward:
            candidates = upward

    tri = _weighted_random_tri(candidates)
    return _random_point_in_tri(tri), tri["normal"]


# ---------------------------------------------------------------------------
# Mimic class
# ---------------------------------------------------------------------------

class Mimic:
    """A single appendage (eye / mouth / tentacle) that grows out of a mimic
    object, then retracts and resurfaces elsewhere. Drop-in replacement for the
    old MimicEyes: same setup/update/draw/unload contract."""

    def __init__(self):
        self.kind = random.choice(list(APPENDAGE_MODELS.keys()))
        self.position = None        # model-local surface point
        self.normal = Vector3(0.0, 1.0, 0.0)
        self.alpha = 0.0            # 0 = fully retracted (shrunk into base), 1 = fully out
        self.target_alpha = 0.0
        self.hidden = True
        self._models_found = False

        self._blink_timer = random.uniform(1.0, 3.0)
        self._next_blink = random.uniform(2.0, 5.0)
        self._close_timer = 0.0
        self._close_duration = 0.0

        self._reposition_timer = random.uniform(4.0, 10.0)
        self._next_reposition = random.uniform(8.0, 20.0)
        self._needs_reposition = False
        self._hidden_wait = 0.0
        self._hidden_target = 0.0

        self._tremoring = False
        self._tremor_timer = 0.0
        self._next_tremor = random.uniform(5.0, 20.0)
        self._tremor_duration = 0.0

        # Latest object rotation + camera direction, so repositions keep landing
        # on the far (hidden-from-camera) side of the object.
        self._view_rot = None
        self._cam_dir = None

    def setup(self, model, view_rot=None, cam_dir=None):
        _load_appendage_models()
        self._view_rot = view_rot
        self._cam_dir = cam_dir
        spot = _find_appendage_spot(model, view_rot, cam_dir)
        if spot:
            self.position, self.normal = spot
            self._models_found = True
            self.target_alpha = 1.0
            self.hidden = False
            self.alpha = 0.0

    def new_object(self):
        """Called when this appendage's host object is freshly presented (after
        ACEITAR / REJEITAR). The kind only mutates here — never mid-inspection."""
        self.kind = random.choice(list(APPENDAGE_MODELS.keys()))

    def _reposition(self, model):
        # Surface somewhere new on the SAME object; the kind stays put. Only
        # the location drifts on its own timer while the object is inspected.
        spot = _find_appendage_spot(model, self._view_rot, self._cam_dir)
        if spot:
            self.position, self.normal = spot

    def update(self, dt, model, anim=None, view_rot=None, cam_dir=None):
        if not self._models_found:
            return

        if view_rot is not None:
            self._view_rot = view_rot
        if cam_dir is not None:
            self._cam_dir = cam_dir

        # Occasional nervous shake of the whole object (drives the host's idle
        # animation amplitude, same as the old eyes did).
        if anim is not None:
            self._tremor_timer += dt
            if self._tremoring:
                if self._tremor_timer >= self._tremor_duration:
                    self._tremoring = False
                    anim.amplitude = 0.001
                    anim.velocity = 0.3
            else:
                if self._tremor_timer >= self._next_tremor:
                    self._tremor_timer = 0.0
                    self._next_tremor = random.uniform(5.0, 20.0)
                    self._tremor_duration = random.uniform(0.06, 0.18)
                    self._tremoring = True
                    anim.amplitude = 0.0015
                    anim.velocity = 5.0

        # Retract → wait → resurface elsewhere as a (possibly different) appendage.
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
                self._reposition(model)
                self.target_alpha = 1.0
                self.hidden = False
                self._needs_reposition = False
                self._blink_timer = 0.0
                self._next_blink = random.uniform(1.5, 3.0)

        # Quick blink / mouth-snap / tentacle-flinch: retract then pop back.
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

        # Smoothly grow/retract toward the target.
        fade_speed = 12.0 if self.target_alpha == 0.0 else 8.0
        if self.alpha < self.target_alpha:
            self.alpha = min(self.target_alpha, self.alpha + fade_speed * dt)
        elif self.alpha > self.target_alpha:
            self.alpha = max(self.target_alpha, self.alpha - fade_speed * dt)

    def draw(self, camera, model_transform, draw_offset):
        if self.alpha < 0.01 or not self._models_found:
            return

        cached = _MODEL_CACHE.get(self.kind)
        if cached is None:
            return
        model, unit_scale, base_transform = cached

        # Surface point and outward normal in world space (these stay fixed for
        # the whole appearance, so the appendage is rock-steady on the surface).
        world_pos = _matrix_transform_point(model_transform, self.position)
        world_pos.x += draw_offset.x
        world_pos.y += draw_offset.y
        world_pos.z += draw_offset.z
        normal = _normalize(_matrix_transform_dir(model_transform, self.normal))

        size = APPENDAGE_SIZE[self.kind] * unit_scale

        # Disappearing = shrinking toward the base: only the growth axis (+Y in
        # the base-corrected frame) scales by alpha, so the tip retracts down
        # into the surface instead of fading in mid-air. X/Z keep full size.
        scale = rl.matrix_scale(size, size * self.alpha, size)

        # Rotation that takes the model's local +Y onto the world surface normal.
        up = Vector3(0.0, 1.0, 0.0)
        dot = max(-1.0, min(1.0, up.x * normal.x + up.y * normal.y + up.z * normal.z))
        if dot > 0.9999:
            tilt = rl.matrix_identity()
        elif dot < -0.9999:
            tilt = rl.matrix_rotate(Vector3(1.0, 0.0, 0.0), math.pi)
        else:
            axis = _normalize(Vector3(
                up.y * normal.z - up.z * normal.y,
                up.z * normal.x - up.x * normal.z,
                up.x * normal.y - up.y * normal.x,
            ))
            tilt = rl.matrix_rotate(axis, math.acos(dot))

        translate = rl.matrix_translate(world_pos.x, world_pos.y, world_pos.z)

        # Compose (raylib's matrix_multiply(A, B) applies A then B):
        #   authored+base rotation -> shrink-along-Y -> tilt onto normal -> place
        m = rl.matrix_multiply(base_transform, scale)
        m = rl.matrix_multiply(m, tilt)
        m = rl.matrix_multiply(m, translate)

        old = model.transform
        model.transform = m
        rl.draw_model(model, Vector3(0.0, 0.0, 0.0), 1.0, rl.WHITE)
        model.transform = old

    def unload(self):
        # Appendage models are shared in the module cache; freed once via
        # unload_appendage_models() rather than per-instance.
        pass
