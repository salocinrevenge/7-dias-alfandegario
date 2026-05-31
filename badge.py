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


def _stamp_to_texture(tex, badge_img, px: int, py: int):
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

    new_tex = rl.load_texture_from_image(model_img)
    rl.unload_image(model_img)

    if new_tex.id == 0:
        return None

    rl.set_texture_filter(new_tex, rl.TEXTURE_FILTER_BILINEAR)
    return new_tex


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attach_badge(model, badge_name: str, scale: float = 0.25):
    """Blend a badge image onto every real texture of *model* at a random
    position that lies *within* a contiguous UV island (so the badge is never
    cut in half by a seam).

    Textures shared by multiple materials are processed only once.

    Args:
        model:      A raylib Model.
        badge_name: Badge filename without extension (e.g. ``'crown'``).
        scale:      Resize the badge by this factor before stamping
                    (default 0.25 → 32×32 px from the original 128×128).

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

        new_tex = _stamp_to_texture(tex, badge_img, *pos)
        if new_tex is None:
            processed[tex.id] = tex
            continue

        rl.unload_texture(tex)
        model.materials[mat_idx].maps[rl.MATERIAL_MAP_ALBEDO].texture = new_tex
        processed[tex.id] = new_tex

    rl.unload_image(badge_img)
    return model
