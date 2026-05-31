import pyray as rl
import random


# ---------------------------------------------------------------------------
# UV island analysis
# ---------------------------------------------------------------------------

def _uv_island_bboxes(mesh, tex_w: int, tex_h: int):
    """Return [(x0,y0,x1,y1), …] bounding boxes (pixels) for every contiguous
    UV island in *mesh*.  Returns [] if the mesh has no UVs or no triangles."""
    if mesh.triangleCount == 0 or not mesh.texcoords or not mesh.indices:
        return []

    vc = mesh.vertexCount
    tc = mesh.triangleCount

    uv_raw = rl.ffi.unpack(mesh.texcoords, vc * 2)
    uvs = [(uv_raw[i * 2], uv_raw[i * 2 + 1]) for i in range(vc)]

    idx_raw = rl.ffi.unpack(mesh.indices, tc * 3)
    tris = [(idx_raw[i * 3], idx_raw[i * 3 + 1], idx_raw[i * 3 + 2])
            for i in range(tc)]

    # DSU – union-find over triangles
    parent = list(range(tc))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Edge map – two triangles sharing the same UV edge are adjacent
    _EPS = 0.0001

    def _q(v):
        return round(v / _EPS)

    edge_map = {}
    for ti, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            uv0 = uvs[e[0]]
            uv1 = uvs[e[1]]
            q0 = (_q(uv0[0]), _q(uv0[1]))
            q1 = (_q(uv1[0]), _q(uv1[1]))
            key = (q0, q1) if q0 < q1 else (q1, q0)
            if key[0] == key[1]:
                continue
            edge_map.setdefault(key, []).append(ti)

    for _, tris_list in edge_map.items():
        if len(tris_list) >= 2:
            root = tris_list[0]
            for ti in tris_list[1:]:
                union(root, ti)

    # Group triangles by root
    groups = {}
    for ti in range(tc):
        r = find(ti)
        groups.setdefault(r, []).append(ti)

    # Bounding box per island (in pixel space, Y flipped for image coords)
    bboxes = []
    for g in groups.values():
        us, vs = [], []
        for ti in g:
            ai, bi, ci = tris[ti]
            us.extend((uvs[ai][0], uvs[bi][0], uvs[ci][0]))
            vs.extend((1.0 - uvs[ai][1], 1.0 - uvs[bi][1], 1.0 - uvs[ci][1]))
        bboxes.append((
            int(min(us) * tex_w), int(min(vs) * tex_h),
            int(max(us) * tex_w), int(max(vs) * tex_h),
        ))
    return bboxes


# ---------------------------------------------------------------------------
# Badge placement
# ---------------------------------------------------------------------------

def _pick_badge_position(model, mat_idx: int, bw: int, bh: int):
    """Return a random (px, py) pixel position on a UV island large enough
    to contain a badge of size *bw*×*bh*, or None if no suitable island."""
    tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture
    tex_w, tex_h = tex.width, tex.height

    islands = []
    for mi in range(model.meshCount):
        if model.meshMaterial[mi] != mat_idx:
            continue
        islands.extend(_uv_island_bboxes(model.meshes[mi], tex_w, tex_h))

    ok = [(x0, y0, x1, y1) for (x0, y0, x1, y1) in islands
          if (x1 - x0) >= bw and (y1 - y0) >= bh]
    if not ok:
        return None

    x0, y0, x1, y1 = random.choice(ok)
    x0 = max(x0, 0)
    y0 = max(y0, 0)
    x1 = min(x1, tex_w)
    y1 = min(y1, tex_h)

    if x1 - x0 < bw or y1 - y0 < bh:
        return None

    return random.randint(x0, x1 - bw), random.randint(y0, y1 - bh)


# ---------------------------------------------------------------------------
# Texture stamping
# ---------------------------------------------------------------------------

def _has_transparency(img):
    """Return True if *img* has any non-opaque pixel (alpha < 255).

    Only works with RGBA8 images; returns False for any other format
    (which implicitly have no alpha channel).
    """
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
    # Larger cells → chunkier destruction.  At 1.0 the cells are big so
    # whole pieces of the sticker are missing.
    cell = max(2, int(12 * (1.0 - degradation * 0.8)))
    gw = (bw + cell - 1) // cell
    gh = (bh + cell - 1) // cell

    destroy = [[0.0] * gw for _ in range(gh)]
    for gy in range(gh):
        for gx in range(gw):
            # Edge-wear bias
            cx = (gx + 0.5) * cell / bw
            cy = (gy + 0.5) * cell / bh
            edge = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) * 2.5
            edge = min(edge, 1.0)

            # Roughly half the cells get heavy destruction, the rest light
            destroy[gy][gx] = degradation * (0.3 + 0.5 * edge + 0.2 * random.random())

    # ---- 2. apply destruction per-pixel -----------------------------------
    for y in range(bh):
        gy = min(y // cell, gh - 1)
        for x in range(bw):
            gx = min(x // cell, gw - 1)
            d = destroy[gy][gx]

            # Add fine per-pixel jitter inside the cell
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

            # Surviving fraction (aggressive: at d=0.7 almost nothing left)
            survive = max(0.0, 1.0 - d * 1.4)
            a = int(a * survive)

            # Colour washes out proportionally
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

    # Snapshot the badge region so we blur from the pre-blur state
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


def _stamp_to_texture(tex, badge_img, px: int, py: int, degradation: float = 0.0):
    """Load *tex* to image, stamp *badge_img* at (px, py), return a new GPU
    texture.  Returns None on failure (image load, transparency, or GPU upload)."""
    model_img = rl.load_image_from_texture(tex)
    if model_img.width == 0 or model_img.height == 0:
        rl.unload_image(model_img)
        return None

    # Convert to RGBA so formats match (image_draw is a no-op on mismatched
    # formats) and _has_transparency can safely inspect alpha bytes.
    if model_img.format != rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8:
        rl.image_format(model_img, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)

    if _has_transparency(model_img):
        rl.unload_image(model_img)
        return None

    bw, bh = badge_img.width, badge_img.height
    src = rl.Rectangle(0, 0, float(bw), float(bh))
    dst = rl.Rectangle(float(px), float(py), float(bw), float(bh))
    rl.image_draw(model_img, badge_img, src, dst, rl.WHITE)

    if degradation > 0.0:
        _apply_degradation(model_img, px, py, bw, bh, degradation)

    new_tex = rl.load_texture_from_image(model_img)
    rl.unload_image(model_img)

    if new_tex.id == 0:
        return None

    rl.set_texture_filter(new_tex, rl.TEXTURE_FILTER_BILINEAR)
    return new_tex


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attach_badge(model, badge_name: str, scale: float = 0.25, degradation: float = 0.2):
    """Blend a badge image onto every real texture of *model* at a random
    position that lies *within* a contiguous UV island (so the badge is never
    cut in half by a seam).

    Textures shared by multiple materials are processed only once.

    Args:
        model:       A raylib Model.
        badge_name:  Badge filename without extension (e.g. ``'crown'``).
        scale:       Resize the badge by this factor before stamping
                     (default 0.25 → 32×32 px from the original 128×128).
        degradation: 0 = pristine sticker, 1 = nearly invisible.
                     Adds edge-wear, colour fading, grain, and flaking.

    Returns:
        The same *model* with its texture(s) modified in-place.
    """
    badge_img = rl.load_image(f"textures/badges/{badge_name}.png".encode())
    if badge_img.width == 0 or badge_img.height == 0:
        rl.unload_image(badge_img)
        return model

    if scale != 1.0:
        rl.image_resize(badge_img,
                        int(badge_img.width * scale),
                        int(badge_img.height * scale))

    bw, bh = badge_img.width, badge_img.height
    if bw == 0 or bh == 0:
        rl.unload_image(badge_img)
        return model

    processed = {}

    for mat_idx in range(model.materialCount):
        tex = model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture
        if tex.id <= 2:
            continue

        if tex.id in processed:
            model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture = processed[tex.id]
            continue

        pos = _pick_badge_position(model, mat_idx, bw, bh)
        if pos is None:
            processed[tex.id] = tex
            continue

        new_tex = _stamp_to_texture(tex, badge_img, *pos, degradation)
        if new_tex is None:
            processed[tex.id] = tex
            continue

        rl.unload_texture(tex)
        model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture = new_tex
        processed[tex.id] = new_tex

    rl.unload_image(badge_img)
    return model
