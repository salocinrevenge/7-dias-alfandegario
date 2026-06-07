import pyray as rl
from pyray import Vector3
import random
import math


# ---------------------------------------------------------------------------
# Image rotation helper
# ---------------------------------------------------------------------------

def _rotate_image(src_img, angle_deg):
    """Rotate an RGBA8 image by *angle_deg* (counter-clockwise).
    Background is fully transparent. Returns a new Image."""
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    sw, sh = src_img.width, src_img.height
    # Bounding box of rotated image
    corners = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2),
               (-sw / 2,  sh / 2), (sw / 2,  sh / 2)]
    rot = [(x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in corners]
    min_x = min(c[0] for c in rot)
    max_x = max(c[0] for c in rot)
    min_y = min(c[1] for c in rot)
    max_y = max(c[1] for c in rot)

    dw = int(max_x - min_x + 1)
    dh = int(max_y - min_y + 1)

    # Transparent destination
    dst = rl.gen_image_color(dw, dh, rl.Color(0, 0, 0, 0))

    src_data = rl.ffi.cast("unsigned char *", src_img.data)
    dst_data = rl.ffi.cast("unsigned char *", dst.data)
    src_stride = sw * 4
    dst_stride = dw * 4

    cx = dw / 2.0
    cy = dh / 2.0
    scx = sw / 2.0
    scy = sh / 2.0

    for dy in range(dh):
        for dx in range(dw):
            # Map dest pixel back to source (inverse rotation)
            x = dx - cx
            y = dy - cy
            sx = x * cos_a + y * sin_a + scx
            sy = -x * sin_a + y * cos_a + scy

            if 0 <= sx < sw - 1 and 0 <= sy < sh - 1:
                ix = int(sx)
                iy = int(sy)
                si = iy * src_stride + ix * 4
                di = dy * dst_stride + dx * 4
                dst_data[di]     = src_data[si]
                dst_data[di + 1] = src_data[si + 1]
                dst_data[di + 2] = src_data[si + 2]
                dst_data[di + 3] = src_data[si + 3]

    return dst


# ---------------------------------------------------------------------------
# Degradation helpers
# ---------------------------------------------------------------------------

def _has_transparency(img):
    """Return True if *img* has any non-opaque pixel (alpha < 255).
    Only works with RGBA8 images; returns False for any other format."""
    if img.format != rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8:
        return False
    size = img.width * img.height * 4
    data = rl.ffi.unpack(rl.ffi.cast("unsigned char *", img.data), size)
    return any(data[i] < 255 for i in range(3, size, 4))


def _apply_degradation(img, px: int, py: int, bw: int, bh: int, degradation: float):
    """Destroy the badge region to look like a heavily aged, cracked,
    torn sticker.

    *degradation*: 0 = pristine, 1 = barely recognisable fragments.
    """
    if degradation <= 0.0:
        return

    data = rl.ffi.cast("unsigned char *", img.data)
    stride = img.width * 4

    # ---- 1. destruction map (cell grid) -----------------------------------
    cell = max(2, int(12 * (1.0 - degradation * 0.8)))
    gw = (bw + cell - 1) // cell
    gh = (bh + cell - 1) // cell

    destroy = [[0.0] * gw for _ in range(gh)]
    for gy in range(gh):
        for gx in range(gw):
            cx = (gx + 0.5) * cell / bw
            cy = (gy + 0.5) * cell / bh
            edge = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) * 2.5
            edge = min(edge, 1.0)
            destroy[gy][gx] = degradation * (0.3 + 0.5 * edge + 0.2 * random.random())

    # ---- 2. apply destruction per-pixel -----------------------------------
    for y in range(bh):
        gy = min(y // cell, gh - 1)
        for x in range(bw):
            gx = min(x // cell, gw - 1)
            d = destroy[gy][gx]
            d = d + random.uniform(-0.12, 0.12) * degradation
            if d < 0.0:
                d = 0.0
            if d > 1.0:
                d = 1.0

            idx = (py + y) * stride + (px + x) * 4
            a = data[idx + 3]
            if a == 0:
                continue

            r, g, b, a = data[idx], data[idx + 1], data[idx + 2], data[idx + 3]
            survive = max(0.0, 1.0 - d * 1.4)
            a = int(a * survive)
            grey = (r + g + b) // 3
            wash = 0.2 + d * 0.8
            r = int(r * (1.0 - wash) + grey * wash)
            g = int(g * (1.0 - wash) + grey * wash)
            b = int(b * (1.0 - wash) + grey * wash)

            data[idx] = r
            data[idx + 1] = g
            data[idx + 2] = b
            data[idx + 3] = a

    # ---- 3. box blur (age / wear softness) --------------------------------
    blur_radius = int(degradation * 5)
    if blur_radius < 1:
        return

    region = []
    for y in range(bh):
        row = []
        for x in range(bw):
            i = (py + y) * stride + (px + x) * 4
            row.append((data[i], data[i + 1], data[i + 2], data[i + 3]))
        region.append(row)

    for y in range(bh):
        for x in range(bw):
            r_sum = g_sum = b_sum = a_sum = 0
            count = 0
            for dy in range(-blur_radius, blur_radius + 1):
                for dx in range(-blur_radius, blur_radius + 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < bh and 0 <= nx < bw:
                        pr, pg, pb, pa = region[ny][nx]
                        r_sum += pr
                        g_sum += pg
                        b_sum += pb
                        a_sum += pa
                        count += 1

            idx = (py + y) * stride + (px + x) * 4
            data[idx] = r_sum // count
            data[idx + 1] = g_sum // count
            data[idx + 2] = b_sum // count
            data[idx + 3] = a_sum // count


# ---------------------------------------------------------------------------
# Manual alpha blending
# ---------------------------------------------------------------------------

def _blend_badge_onto_image(dst_img, badge_img, px: int, py: int):
    """Alpha-blend *badge_img* onto *dst_img* at (px, py).
    Both images must be RGBA8."""
    bw, bh = badge_img.width, badge_img.height
    dw, dh = dst_img.width, dst_img.height

    dst_data = rl.ffi.cast("unsigned char *", dst_img.data)
    src_data = rl.ffi.cast("unsigned char *", badge_img.data)
    dst_stride = dw * 4
    src_stride = bw * 4

    for y in range(bh):
        sy = py + y
        if sy < 0 or sy >= dh:
            continue
        for x in range(bw):
            sx = px + x
            if sx < 0 or sx >= dw:
                continue

            si = y * src_stride + x * 4
            sa = src_data[si + 3]
            if sa == 0:
                continue

            di = sy * dst_stride + sx * 4

            if sa == 255:
                dst_data[di]     = src_data[si]
                dst_data[di + 1] = src_data[si + 1]
                dst_data[di + 2] = src_data[si + 2]
                dst_data[di + 3] = 255
            else:
                a = sa / 255.0
                inv = 1.0 - a
                dst_data[di]     = int(src_data[si]     * a + dst_data[di]     * inv)
                dst_data[di + 1] = int(src_data[si + 1] * a + dst_data[di + 1] * inv)
                dst_data[di + 2] = int(src_data[si + 2] * a + dst_data[di + 2] * inv)
                dst_data[di + 3] = min(255, int(255 * a + dst_data[di + 3] * inv))


# ---------------------------------------------------------------------------
# Matte the badge on ARM (roughness/metallic) texture
# ---------------------------------------------------------------------------

def _matte_badge_on_arm(arm_img, px: int, py: int, bw: int, bh: int):
    """Increase roughness (green) and reduce metallic (blue) in badge area
    so the sticker looks matte instead of glossy.

    ARM layout: R = AO, G = Roughness, B = Metallic.
    """
    if arm_img.format != rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8:
        rl.image_format(arm_img, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)

    data = rl.ffi.cast("unsigned char *", arm_img.data)
    stride = arm_img.width * 4
    aw, ah = arm_img.width, arm_img.height

    for y in range(bh):
        sy = py + y
        if sy < 0 or sy >= ah:
            continue
        for x in range(bw):
            sx = px + x
            if sx < 0 or sx >= aw:
                continue
            idx = sy * stride + sx * 4
            # Increase roughness (matte) — blend toward 240
            data[idx + 1] = int(data[idx + 1] * 0.2 + 240 * 0.8)
            # Reduce metallic
            data[idx + 2] = int(data[idx + 2] * 0.3 + 0 * 0.7)


# ---------------------------------------------------------------------------
# Texture stamping (returns new albedo tex + new ARM tex)
# ---------------------------------------------------------------------------

def _stamp_to_texture(tex, badge_img, px: int, py: int,
                      arm_tex=None, arm_scale_x=1.0, arm_scale_y=1.0):
    """Load *tex* to image, stamp *badge_img* at (px, py), optionally also
    matte the corresponding region on *arm_tex*, and return
    (new_albedo_tex, new_arm_tex) or (None, None) on failure."""
    model_img = rl.load_image_from_texture(tex)
    if model_img.width == 0 or model_img.height == 0:
        rl.unload_image(model_img)
        return None, None

    if model_img.format != rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8:
        rl.image_format(model_img, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)

    if _has_transparency(model_img):
        rl.unload_image(model_img)
        return None, None

    _blend_badge_onto_image(model_img, badge_img, px, py)

    new_tex = rl.load_texture_from_image(model_img)
    rl.unload_image(model_img)

    if new_tex.id == 0:
        return None, None

    rl.set_texture_filter(new_tex, rl.TEXTURE_FILTER_BILINEAR)

    new_arm_tex = None
    if arm_tex is not None and arm_tex.id > 2:
        arm_img = rl.load_image_from_texture(arm_tex)
        if arm_img.width > 0 and arm_img.height > 0:
            arm_px = int(px * arm_scale_x)
            arm_py = int(py * arm_scale_y)
            arm_bw = max(1, int(badge_img.width * arm_scale_x))
            arm_bh = max(1, int(badge_img.height * arm_scale_y))
            _matte_badge_on_arm(arm_img, arm_px, arm_py, arm_bw, arm_bh)
            new_arm_tex = rl.load_texture_from_image(arm_img)
            if new_arm_tex.id != 0:
                rl.set_texture_filter(new_arm_tex, rl.TEXTURE_FILTER_BILINEAR)
            rl.unload_image(arm_img)

    return new_tex, new_arm_tex


# ---------------------------------------------------------------------------
# Visible-surface picking
# ---------------------------------------------------------------------------

def _get_mesh_data(mesh):
    """Read mesh vertex positions, UVs, and indices. Returns tuple or None."""
    if mesh.triangleCount == 0 or not mesh.indices or not mesh.texcoords or not mesh.vertices:
        return None

    vc = mesh.vertexCount
    tc = mesh.triangleCount

    vert_raw = rl.ffi.unpack(mesh.vertices, vc * 3)
    uv_raw = rl.ffi.unpack(mesh.texcoords, vc * 2)
    idx_raw = rl.ffi.unpack(mesh.indices, tc * 3)

    return (vert_raw, uv_raw, idx_raw, vc, tc)


def _model_local_center(model):
    """Compute the axis-aligned bounding box center of *model* (all meshes)."""
    mins = [float('inf'), float('inf'), float('inf')]
    maxs = [float('-inf'), float('-inf'), float('-inf')]

    for mi in range(model.meshCount):
        mesh = model.meshes[mi]
        if mesh.vertexCount == 0 or not mesh.vertices:
            continue
        vert_raw = rl.ffi.unpack(mesh.vertices, mesh.vertexCount * 3)
        for i in range(mesh.vertexCount):
            x = vert_raw[i * 3]
            y = vert_raw[i * 3 + 1]
            z = vert_raw[i * 3 + 2]
            mins[0] = min(mins[0], x)
            mins[1] = min(mins[1], y)
            mins[2] = min(mins[2], z)
            maxs[0] = max(maxs[0], x)
            maxs[1] = max(maxs[1], y)
            maxs[2] = max(maxs[2], z)

    if mins[0] == float('inf'):
        return Vector3(0.0, 0.0, 0.0)

    return Vector3(
        (mins[0] + maxs[0]) * 0.5,
        (mins[1] + maxs[1]) * 0.5,
        (mins[2] + maxs[2]) * 0.5,
    )


def _build_main_camera(center):
    """Single front-above inspect camera."""
    cam = rl.Camera3D()
    cam.position = Vector3(center.x, center.y + 0.125, center.z + 0.7)
    cam.target = Vector3(center.x, center.y + 0.005, center.z)
    cam.up = Vector3(0.0, 1.0, 0.0)
    cam.fovy = 55.0
    cam.projection = rl.CAMERA_PERSPECTIVE
    return cam


def _collect_triangles(mesh_data):
    """Return a list of triangle records for the mesh.
    Each record: (uva, uvb, uvc, area, normal, centroid, is_not_bottom)"""
    vert_raw, uv_raw, idx_raw, vc, tc = mesh_data
    tris = []

    for ti in range(tc):
        a = idx_raw[ti * 3]
        b = idx_raw[ti * 3 + 1]
        c = idx_raw[ti * 3 + 2]

        ax = vert_raw[a * 3]
        ay = vert_raw[a * 3 + 1]
        az = vert_raw[a * 3 + 2]

        bx = vert_raw[b * 3]
        by = vert_raw[b * 3 + 1]
        bz = vert_raw[b * 3 + 2]

        cx_ = vert_raw[c * 3]
        cy_ = vert_raw[c * 3 + 1]
        cz_ = vert_raw[c * 3 + 2]

        nx = (by - ay) * (cz_ - az) - (bz - az) * (cy_ - ay)
        ny = (bz - az) * (cx_ - ax) - (bx - ax) * (cz_ - az)
        nz = (bx - ax) * (cy_ - ay) - (by - ay) * (cx_ - ax)
        nl = math.sqrt(nx * nx + ny * ny + nz * nz)
        if nl < 1e-8:
            continue

        area = nl * 0.5
        uva = (uv_raw[a * 2], uv_raw[a * 2 + 1])
        uvb = (uv_raw[b * 2], uv_raw[b * 2 + 1])
        uvc = (uv_raw[c * 2], uv_raw[c * 2 + 1])

        centroid = ((ax + bx + cx_) / 3.0, (ay + by + cy_) / 3.0, (az + bz + cz_) / 3.0)
        normal = (nx / nl, ny / nl, nz / nl)
        is_not_bottom = normal[1] > -0.2

        tris.append((uva, uvb, uvc, area, normal, centroid, is_not_bottom))

    return tris


def _is_triangle_visible(tri, camera):
    """Return True if the triangle faces the camera and is in front of it."""
    _, _, _, _, normal, centroid, _ = tri
    nx, ny, nz = normal
    cx, cy, cz = centroid

    # Vector from triangle center to camera
    to_cam_x = camera.position.x - cx
    to_cam_y = camera.position.y - cy
    to_cam_z = camera.position.z - cz
    to_cam_len = math.sqrt(to_cam_x**2 + to_cam_y**2 + to_cam_z**2)
    if to_cam_len < 1e-8:
        return False

    # Must face camera (reject back faces and some edge faces)
    dot = (nx * to_cam_x + ny * to_cam_y + nz * to_cam_z) / to_cam_len
    if dot < 0.15:
        return False

    # Must be in front of the camera
    cam_dir_x = camera.target.x - camera.position.x
    cam_dir_y = camera.target.y - camera.position.y
    cam_dir_z = camera.target.z - camera.position.z
    dlen = math.sqrt(cam_dir_x**2 + cam_dir_y**2 + cam_dir_z**2)
    if dlen < 1e-8:
        return False
    cam_dir_x /= dlen
    cam_dir_y /= dlen
    cam_dir_z /= dlen

    to_target_x = cx - camera.position.x
    to_target_y = cy - camera.position.y
    to_target_z = cz - camera.position.z
    dot2 = to_target_x * cam_dir_x + to_target_y * cam_dir_y + to_target_z * cam_dir_z
    if dot2 < 0.02:
        return False

    return True


def _barycentric(pxx, pyy, ax, ay, bx, by, cx, cy):
    denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denom) < 1e-10:
        return False
    a = ((by - cy) * (pxx - cx) + (cx - bx) * (pyy - cy)) / denom
    b = ((cy - ay) * (pxx - cx) + (ax - cx) * (pyy - cy)) / denom
    c = 1.0 - a - b
    return a >= -1e-4 and b >= -1e-4 and c >= -1e-4


def _point_in_visible_tri(u, v, visible_tris):
    """Return True if (u,v) lies inside any of *visible_tris*."""
    for tri in visible_tris:
        uva, uvb, uvc = tri[0], tri[1], tri[2]
        if _barycentric(u, v, uva[0], uva[1], uvb[0], uvb[1], uvc[0], uvc[1]):
            return True
    return False


def _uv_to_pixel(u, v, tex_w, tex_h, bw, bh):
    """Convert UV to top-left pixel coord, clamped so the whole badge fits."""
    px = int(u * tex_w) - bw // 2
    py = int((1.0 - v) * tex_h) - bh // 2
    if px < 0:
        px = 0
    if py < 0:
        py = 0
    if px + bw > tex_w:
        px = tex_w - bw
    if py + bh > tex_h:
        py = tex_h - bh
    return px, py


def _pick_badge_position(model, mat_idx, bw, bh):
    """Return a random (px, py) pixel position on a visible surface.

    Strategy:
      1. Use a single front-above inspect camera.
      2. Collect visible triangles (face camera, in front of camera).
      3. Try many random positions with footprint validation.
      4. Fall back to non-bottom, then any triangle.
    """
    tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture
    tex_w, tex_h = tex.width, tex.height
    if tex_w == 0 or tex_h == 0:
        return None

    center = _model_local_center(model)
    camera = _build_main_camera(center)

    # Gather all triangles for this material
    all_tris = []
    for mi in range(model.meshCount):
        if model.meshMaterial[mi] != mat_idx:
            continue
        mesh_data = _get_mesh_data(model.meshes[mi])
        if mesh_data is None:
            continue
        all_tris.extend(_collect_triangles(mesh_data))

    if not all_tris:
        return None

    # Build visibility pools
    visible = [tri for tri in all_tris if _is_triangle_visible(tri, camera)]
    if not visible:
        visible = [tri for tri in all_tris if tri[6]]   # is_not_bottom
    if not visible:
        visible = all_tris

    areas = [tri[3] for tri in visible]
    total = sum(areas)
    if total < 1e-8:
        return None

    # Footprint sample offsets (inset to avoid rotated-image transparent corners)
    inset_x = max(1, bw // 6)
    inset_y = max(1, bh // 6)

    # Try a bounded number of times with footprint validation. Kept modest
    # because this runs in pure Python (slow under Pyodide on the web build); the
    # centroid fallback below covers the rare miss.
    for _ in range(100):
        # Weighted random triangle
        r = random.random() * total
        accum = 0.0
        chosen = visible[0]
        for tri, area in zip(visible, areas):
            accum += area
            if accum >= r:
                chosen = tri
                break

        uva, uvb, uvc = chosen[0], chosen[1], chosen[2]

        # Random barycentric point inside chosen triangle
        r1 = random.random()
        r2 = random.random()
        if r1 + r2 > 1.0:
            r1 = 1.0 - r1
            r2 = 1.0 - r2

        cu = (1.0 - r1 - r2) * uva[0] + r1 * uvb[0] + r2 * uvc[0]
        cv = (1.0 - r1 - r2) * uva[1] + r1 * uvb[1] + r2 * uvc[1]
        cu = max(0.0, min(1.0, cu))
        cv = max(0.0, min(1.0, cv))

        px, py = _uv_to_pixel(cu, cv, tex_w, tex_h, bw, bh)

        # Sample points: center + 4 inset corners of badge bounding box
        samples = [
            (px + bw // 2,          py + bh // 2),
            (px + inset_x,          py + inset_y),
            (px + bw - inset_x,     py + inset_y),
            (px + inset_x,          py + bh - inset_y),
            (px + bw - inset_x,     py + bh - inset_y),
        ]

        valid = True
        for sx, sy in samples:
            su = sx / tex_w
            sv = 1.0 - sy / tex_h
            if not _point_in_visible_tri(su, sv, visible):
                valid = False
                break

        if valid:
            return (px, py)

    # Fallback: centroid of the largest visible triangle
    largest = max(visible, key=lambda t: t[3])
    uva, uvb, uvc = largest[0], largest[1], largest[2]
    cu = (uva[0] + uvb[0] + uvc[0]) / 3.0
    cv = (uva[1] + uvb[1] + uvc[1]) / 3.0
    return _uv_to_pixel(cu, cv, tex_w, tex_h, bw, bh)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attach_badge(model, badge_name: str = "badges/crown", scale: float = 0.25,
                 degradation: float = 0.6, target_px: int | None = None):
    """Blend a badge image onto every real texture of *model* at a random
    position that lies on a visible surface.

    Args:
        model:       A raylib Model.
        badge_name:  Badge path under ``textures/`` without extension
                     (e.g. ``'venenoso'`` → ``textures/venenoso.png``,
                     ``'badges/crown'`` → ``textures/badges/crown.png``).
        scale:       Resize the badge by this factor before stamping (ignored
                     when *target_px* is given).
        degradation: 0 = pristine sticker, 1 = nearly invisible.
        target_px:   If set, resize the badge so its largest dimension equals
                     this many pixels — keeps badges a consistent on-object size
                     regardless of their differing source resolutions.

    Returns:
        The same *model* with its texture(s) modified in-place.
    """
    badge_img = rl.load_image(f"textures/{badge_name}.png".encode())
    if badge_img.width == 0 or badge_img.height == 0:
        rl.unload_image(badge_img)
        return model

    # Ensure RGBA so we can safely blend and degrade
    if badge_img.format != rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8:
        rl.image_format(badge_img, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)

    if target_px is not None:
        longest = max(badge_img.width, badge_img.height)
        if longest > 0:
            scale = target_px / longest

    if scale != 1.0:
        rl.image_resize(badge_img,
                        int(badge_img.width * scale),
                        int(badge_img.height * scale))

    bw, bh = badge_img.width, badge_img.height
    if bw == 0 or bh == 0:
        rl.unload_image(badge_img)
        return model

    # Pre-apply degradation to the badge image itself
    if degradation > 0.0:
        _apply_degradation(badge_img, 0, 0, bw, bh, degradation)

    # Random rotation (±35°)
    angle = random.uniform(-35.0, 35.0)
    rotated_badge = _rotate_image(badge_img, angle)
    rl.unload_image(badge_img)

    rbw, rbh = rotated_badge.width, rotated_badge.height

    processed_albedo = {}
    processed_arm = {}

    for mat_idx in range(model.materialCount):
        # ---- Skip transparent materials (glass, etc.) --------------------
        albedo_map = model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO]
        if hasattr(albedo_map, 'color') and albedo_map.color.a < 240:
            continue

        tex = albedo_map.texture
        if tex.id <= 2:
            continue

        if tex.id in processed_albedo:
            model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture = processed_albedo[tex.id]
            arm_tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_METALNESS].texture
            if arm_tex.id in processed_arm:
                model.materials[mat_idx].maps[rl.MATERIAL_MAP_METALNESS].texture = processed_arm[arm_tex.id]
                model.materials[mat_idx].maps[rl.MATERIAL_MAP_ROUGHNESS].texture = processed_arm[arm_tex.id]
            continue

        pos = _pick_badge_position(model, mat_idx, rbw, rbh)
        if pos is None:
            processed_albedo[tex.id] = tex
            continue

        # glTF metallic-roughness is usually loaded into METALNESS map in raylib
        arm_tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_METALNESS].texture
        if arm_tex.id <= 2:
            arm_tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_ROUGHNESS].texture
            if arm_tex.id <= 2:
                arm_tex = None

        arm_scale_x = 1.0
        arm_scale_y = 1.0
        if arm_tex is not None and arm_tex.width > 0 and tex.width > 0:
            arm_scale_x = arm_tex.width / tex.width
            arm_scale_y = arm_tex.height / tex.height

        new_tex, new_arm_tex = _stamp_to_texture(
            tex, rotated_badge, *pos, arm_tex=arm_tex,
            arm_scale_x=arm_scale_x, arm_scale_y=arm_scale_y
        )

        if new_tex is None:
            processed_albedo[tex.id] = tex
            continue

        rl.unload_texture(tex)
        model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture = new_tex
        processed_albedo[tex.id] = new_tex

        if new_arm_tex is not None and new_arm_tex.id != 0:
            if arm_tex is not None:
                processed_arm[arm_tex.id] = new_arm_tex
                rl.unload_texture(arm_tex)
            model.materials[mat_idx].maps[rl.MATERIAL_MAP_METALNESS].texture = new_arm_tex
            model.materials[mat_idx].maps[rl.MATERIAL_MAP_ROUGHNESS].texture = new_arm_tex

    rl.unload_image(rotated_badge)
    return model
