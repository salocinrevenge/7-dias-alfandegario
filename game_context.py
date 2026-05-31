import sys
import pyray as rl
from pyray import Vector2, Vector3
import math
import time

from state import State
from transition import Transition

_PAPER_LINES = [
    b"PROPRIEDADES DO PRODUTO",
    b"",
    b"[ ]  ITEM AMALDICADO?",
    b"[ ]  ITEM VENENOSO?",
    b"[ ]  ITEM RADIOATIVO?",
    b"[ ]  ITEM REAL?",
    b"[ ]  ITEM NOBRE?",
    b"[ ]  ITEM IMPORTADO?",
    b"[ ]  ITEM RIVAL?",
    b"",
    b"MALDICOES:",
    b"ALIADOS:",
    b"RIVAIS:",
    b"",
    b"ACEITAR      REJEITAR",
    b"",
]


def _bake_paper_texture(paper_tex) -> rl.Texture2D:
    """Render paper texture + text lines into a corrected Texture2D."""
    TW, TH = 512, 724
    rt = rl.load_render_texture(TW, TH)
    rl.begin_texture_mode(rt)
    rl.clear_background(rl.WHITE)
    rl.draw_texture_pro(
        paper_tex,
        rl.Rectangle(0, 0, float(paper_tex.width), float(paper_tex.height)),
        rl.Rectangle(0, 0, float(TW), float(TH)),
        Vector2(0, 0), 0.0, rl.WHITE,
    )
    font_size = TH // 32
    line_h    = font_size + font_size // 3
    mx = TW // 8
    my = TH // 10
    ink = rl.Color(25, 15, 5, 220)
    for i, line in enumerate(_PAPER_LINES):
        rl.draw_text(line, mx, my + i * line_h, font_size, ink)
    rl.end_texture_mode()
    # Render textures are stored flipped; export → flip → reload so it looks right on the mesh
    img = rl.load_image_from_texture(rt.texture)
    rl.image_flip_vertical(img)
    tex = rl.load_texture_from_image(img)
    rl.unload_image(img)
    rl.unload_render_texture(rt)
    rl.set_texture_filter(tex, rl.TEXTURE_FILTER_BILINEAR)
    return tex


class Game_context:
    def __init__(self):
        self.IS_WEB = sys.platform == "emscripten"

        # ---------------------------------------------------------------------------
        # RENDER RESOLUTION
        # ---------------------------------------------------------------------------
        self.VIRTUAL_W = 960 * 0.5
        self.VIRTUAL_H = 720 * 0.5

        # ---------------------------------------------------------------------------
        # SCENE CONSTANTS
        # ---------------------------------------------------------------------------
        self.TABLE_SCALE  = 1.0
        self.TABLE_POS    = Vector3(0, 0, 0)

        self.OBJECT_SIZE  = 0.15
        self.OBJECT_Y     = 0.60
        self.OBJECT_POS   = Vector3(0, self.OBJECT_Y + self.OBJECT_SIZE * 0.5, 0.0)

        self.CAM_POS    = Vector3(0.0, 0.8, 0.7)
        self.CAM_TARGET = Vector3(0, 0.68, 0.0)

        self._OBJECT_RADIUS = self.OBJECT_SIZE * 0.866

        # --- Paper dimensions (3D world units) ---
        self.PAPER_W        = 0.28
        self.PAPER_H        = 0.40
        # Rest: right side of table, lying flat with a casual Y tilt
        self.PAPER_POS      = Vector3(0.35, 0.52, 0.20)
        self.PAPER_REST_ROT_X = 0.0    # flat
        self.PAPER_REST_ROT_Y = 20.0   # casual angle in degrees
        # Open: centred in front of camera, upright and facing forward
        self.PAPER_FRONT_POS  = Vector3(0.0, 0.74, 0.4)
        self.PAPER_OPEN_ROT_X = 90.0
        self.PAPER_OPEN_ROT_Y = 0.0
        self.PAPER_ANIM_SPEED = 1.0

        # --- Models & textures (textures first — paper model references paper tex) ---
        self.load_textures()
        self.load_models()

        # --- Camera ---
        self.camera            = rl.Camera3D()
        self.camera.position   = self.CAM_POS
        self.camera.target     = self.CAM_TARGET
        self.camera.up         = Vector3(0, 1, 0)
        self.camera.fovy       = 55.0
        self.camera.projection = rl.CAMERA_PERSPECTIVE

        # --- Window
        self.windowed_w, self.windowed_h = 1080, 720

        self.painting_enabled = True                           # [K] toggles this

        # --- State machine ---
        self.current_state      = State.INSPECT
        self.prev_inspect_drawn = False
        self.transition         = Transition()
        self.prev_time          = time.time()
        self.now                = self.prev_time
        self.player             = None
        self.player_cartas_odio = 0
        self.odio_to_day = 5
        self.dia_atual = 1
        self.n_itens_dias = {
            1: 3,
            2: 5,
            3: 7,
            4: 9,
            5: 11,
            6: 13,
            7: 15
        }
        self.itens_hoje= {
            'to evaluate': [],
            'evaluated': []
        }

    def start_day(self):
        self.itens_hoje['to evaluate'] = list(range(1, self.n_itens_dias[self.dia_atual]+1))
        self.itens_hoje['evaluated'] = []

    def load_textures(self):
        self.textures = {}
        self.textures["bg"]   = rl.load_texture(b"models/env/wizard_room.jpg")
        self.textures["menu_bg"] = rl.load_texture(b"models/env/outside.png")
        self.textures["paper_raw"] = rl.load_texture(b"textures/paper-texture.jpg")
        self.textures["tropiland_font"] = rl.load_font_ex(b"fonts/TropiLand.ttf", 128, None, 0)
        rl.set_texture_filter(self.textures["bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["menu_bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["paper_raw"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["tropiland_font"].texture, rl.TEXTURE_FILTER_BILINEAR)
        # Bake text onto paper — stored separately so unload_textures handles it
        self.textures["paper"] = _bake_paper_texture(self.textures["paper_raw"])

    def load_models(self):
        self.models = {}
        self.models["table"]  = rl.load_model(b"models/env/chinese_tea_table_2k.gltf")
        self.models["relogio"] = rl.load_model(b"models/objects/mantel_clock_01_1k.gltf")
        paper_mesh = rl.gen_mesh_plane(self.PAPER_W, self.PAPER_H, 1, 1)
        self.models["paper"] = rl.load_model_from_mesh(paper_mesh)
        # Use the baked texture (paper + text) as the diffuse map
        self.models["paper"].materials[0].maps[rl.MATERIAL_MAP_DIFFUSE].texture = self.textures["paper"]


    def unload_textures(self):
        for tex in self.textures.values():
            rl.unload_texture(tex)

    def unload_models(self):
        for model in self.models.values():
            rl.unload_model(model)

    # ---------------------------------------------------------------------------
    # SCENE STATE
    # ---------------------------------------------------------------------------
    def make_scene_state(self) -> dict:
        # ----------------------------------------------------------------------------
        # CAMERA INITIAL ORIENTATION (pointing at the table center)
        # ----------------------------------------------------------------------------
        _dx, _dy, _dz = (self.CAM_TARGET.x - self.CAM_POS.x,
                    self.CAM_TARGET.y - self.CAM_POS.y,
                    self.CAM_TARGET.z - self.CAM_POS.z)
        

        _dl = math.sqrt(_dx*_dx + _dy*_dy + _dz*_dz) or 1.0
        self._INIT_CAM_YAW   = math.atan2(_dx / _dl, _dz / _dl)
        self._INIT_CAM_PITCH = math.asin(_dy / _dl)
        self.gs = {
            "paper_open":   False,
            "paper_anim_t": 0.0,   # 0 = flat on table, 1 = upright in front of camera
            "debug":        False,
            "cam_yaw":      self._INIT_CAM_YAW,
            "cam_pitch":    self._INIT_CAM_PITCH,
            "cam_pos":      Vector3(self.CAM_POS.x, self.CAM_POS.y, self.CAM_POS.z),
        }
