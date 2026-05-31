import sys
import pyray as rl
from pyray import Vector2, Vector3
import math
import time

import quad_text
from state import State
from transition import Transition
from item import Item
from animation import add_shake

# Lines support a leading <tag> that selects a font size (see quad_text.SIZES).
_PAPER_LINES = [
    b"<title>Propriedades",
    b"",
    b"<body>[ ] Amaldicoado?",
    b"<body>[ ] Venenoso?",
    b"<body>[ ] Radioativo?",
    b"<body>[ ] Real?",
    b"<body>[ ] Nobre?",
    b"<body>[ ] Importado?",
    b"<body>[ ] Rival?",
    b"",
    b"<small>Maldicoes:",
    b"<small>Aliados:",
    b"<small>Rivais:",
    b"",
    b"<h2>Aceitar    Rejeitar",
]

PAPER_TW, PAPER_TH = 512, 724
_PAPER_MX = PAPER_TW // 8           # 64 px left margin
_PAPER_MY = PAPER_TH // 12          # ~60 px top margin

_CHECK_EMPTY = b"[ ]"
_CHECK_FULL  = b"[x]"   # [✔]  U+2714 as UTF-8

_INK_NORMAL  = rl.Color(25,  15,   5, 220)
_INK_HOVER   = rl.Color(160, 80,  10, 255)   # warm amber for the hovered button


def _is_button_line(text: bytes) -> bool:
    return b"Aceitar" in text and b"Rejeitar" in text


def _button_rects(font: rl.Font, span: dict) -> dict:
    """Sub-rects of the two words on the Aceitar/Rejeitar span (texture coords)."""
    text, size = span["text"], span["size"]
    x, y, h    = span["x"], span["y"], span["h"]
    r_off = text.find(b"Rejeitar")
    return {
        "aceitar":  (x, y, quad_text.measure(font, b"Aceitar", size), h),
        "rejeitar": (x + quad_text.measure(font, text[:r_off], size),
                     y, quad_text.measure(font, b"Rejeitar", size), h),
    }


def parse_paper_items(layout: list[dict], font: rl.Font) -> list[dict]:
    """Interactive items (checkboxes / buttons) with texture-space rects.

    Driven by the same layout used for baking, so rects always match the text.
    """
    items: list[dict] = []
    check_idx = 0
    for span in layout:
        text = span["text"]
        if _CHECK_EMPTY in text:
            items.append({
                "type": "check",
                "key":  f"check_{check_idx}",
                "rect": (span["x"], span["y"], span["w"], span["h"]),
            })
            check_idx += 1
        elif _is_button_line(text):
            rects = _button_rects(font, span)
            items.append({"type": "button", "key": "aceitar",  "rect": rects["aceitar"]})
            items.append({"type": "button", "key": "rejeitar", "rect": rects["rejeitar"]})
    return items


def _bake_paper_texture(paper_tex, font: rl.Font, layout: list[dict],
                        states: dict | None = None,
                        hovered_key: str | None = None) -> rl.Texture2D:
    """Render the paper background + tagged text into a flip-corrected Texture2D.

    hovered_key: key of the button whose word is drawn in _INK_HOVER.
    """
    if states is None:
        states = {}

    rt = rl.load_render_texture(PAPER_TW, PAPER_TH)
    rl.begin_texture_mode(rt)
    rl.clear_background(rl.WHITE)
    rl.draw_texture_pro(
        paper_tex,
        rl.Rectangle(0, 0, float(paper_tex.width), float(paper_tex.height)),
        rl.Rectangle(0, 0, float(PAPER_TW), float(PAPER_TH)),
        Vector2(0, 0), 0.0, rl.WHITE,
    )

    check_idx = 0
    for span in layout:
        text = span["text"]

        if _CHECK_EMPTY in text:
            if states.get(f"check_{check_idx}", False):
                text = text.replace(_CHECK_EMPTY, _CHECK_FULL)
            check_idx += 1
            quad_text.draw_text(font, text, span["x"], span["y"], span["size"], _INK_NORMAL)

        elif _is_button_line(text):
            r = _button_rects(font, span)
            ax, ay, _, _ = r["aceitar"]
            rx, ry, _, _ = r["rejeitar"]
            quad_text.draw_text(font, b"Aceitar",  ax, ay, span["size"],
                                _INK_HOVER if hovered_key == "aceitar"  else _INK_NORMAL)
            quad_text.draw_text(font, b"Rejeitar", rx, ry, span["size"],
                                _INK_HOVER if hovered_key == "rejeitar" else _INK_NORMAL)

        elif text:
            quad_text.draw_span(font, span, _INK_NORMAL)

    rl.end_texture_mode()

    # Render textures are stored flipped; export → flip → reload so it reads right on the mesh
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
        self.VIRTUAL_W = int(960 * 0.5)
        self.VIRTUAL_H = int(720 * 0.5)

        # ---------------------------------------------------------------------------
        # SCENE CONSTANTS
        # ---------------------------------------------------------------------------
        self.TABLE_SCALE  = 1.0
        self.TABLE_POS    = Vector3(0, 0, 0)

        self.OBJECT_SIZE  = 0.15
        self.OBJECT_Y     = 0.60
        self.OBJECT_POS   = Vector3(0, self.OBJECT_Y + self.OBJECT_SIZE * 0.5, 0.0)
        self.OBJECT_SCALE = 1.0   # tune to fit the inspected model on the table

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

        # --- Resources (fonts → textures → models; the paper bake needs the font) ---
        self.load_fonts()
        self.load_textures()
        self.load_models()

        # --- Audio ---
        try:
            rl.init_audio_device()
        except Exception:
            # plataforma pode não suportar audio (web), ignore falhas
            pass
        self.sounds = {}
        self.tutorial_played_index = -1
        # tenta carregar sons correspondentes às estrofes (sounds/tutorial_1.wav...)
        # consulte load_sounds() abaixo (será chamado mais abaixo, após definir os textos)

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
        self.start_time         = time.time()
        self.prev_time          = time.time()
        self.now                = self.prev_time
        self.player             = None
        self.player_cartas_odio = 0
        self.odio_to_day = 5
        self.dia_atual = 0
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
        self.properties_on_list = {
            "VENENOSO": False,
            "RADIOATIVO": False,
            "REAL": False,
            "NOBRE": False,
            "ALIADOS": [],
            "RIVAL": [],
            "MIMICO": False
        }

        self.error_costs = {
            "VENENOSO": 4,
            "RADIOATIVO": 1,
            "REAL": 3,
            "NOBRE": 2,
            "MIMICO": 7,
            "MALDIÇÕES": 5,
            "ALIADOS": 1,
            "RIVAIS": 2,
            "REJECT": 1
        }
        self.positive_rejects = ["REAL", "NOBRE", "ALIADOS"]

        self.reset_count_until_end_day = 100
        self.count_until_end_day = self.reset_count_until_end_day
        self.created_room = False

        self.tutorial_texts = [
            "Nas torres frias da escuridão,\ncomeça hoje tua missão.\nJulga os tesouros sem temor,\nanota tudo com rigor.",
            "Se houver veneno ou maldição,\nrejeita sem hesitação.\nSe um mímico ousar chegar,\nnão o deixes atravessar.",
            "Das terras do inimigo vil,\nnão passes nada ao teu perfil.\nE o Livro Nuclear, em ardor,\nrecusa-o sem nenhum pudor.",
            "Sete dias tens para provar\nque sabes bem fiscalizar.\nSe muitos erros cometer,\nao posto hás de retornar.",
            "Mas se o fracasso florescer,\nteu cargo irás perder.\nAgora vigia o portão,\ne cumpre tua obrigação."
        ]

        self.tutorial_index = 0
        self.tutorial_char_count = 0.0
        self.tutorial_typing_speed = 30.0

        self.day_intro_timer = 0.0
        self.day_intro_char_count = 0.0
        self.day_intro_typing_speed = 8.0

        self.animations = {}
        self.setup_animations()
        # Agora que os textos existem, tente carregar os sons do tutorial
        try:
            self.load_sounds()
        except Exception:
            pass

    def setup_animations(self):
        add_shake(self, "relogio", offset=0.001, velocity=0.3)

    def start_new_day(self):
        self.created_room = True
        self.make_scene_state()
        self.transition.start(State.INSPECT)
        self.dia_atual += 1
        self.day_intro_timer = 2.5
        self.day_intro_char_count = 0.0
        print(f"Starting day {self.dia_atual}...")
        self.itens_hoje['to evaluate'] = [Item() for _ in range(self.n_itens_dias.get(self.dia_atual, 15))]
        self.itens_hoje['evaluated'] = []

    def load_fonts(self):
        """Load fonts once into self.fonts. The serif atlas includes the ✔ glyph
        and is baked at high resolution so it scales cleanly to any quad/HUD size."""
        self.fonts = {}
        cps = list(range(32, 127)) + [0x2714]   # ASCII + checkmark
        buf = rl.ffi.new(f"int[{len(cps)}]", cps)
        serif = rl.load_font_ex(b"fonts/Enchanted Land.otf", 96,
                                rl.ffi.cast("int *", buf), len(cps))
        rl.set_texture_filter(serif.texture, rl.TEXTURE_FILTER_BILINEAR)
        self.fonts["serif"] = serif

    def load_textures(self):
        self.textures = {}
        self.textures["bg"]   = rl.load_texture(b"models/env/wizard_room.jpg")
        self.textures["menu_bg"] = rl.load_texture(b"models/env/outside.png")
        self.textures["paper_raw"] = rl.load_texture(b"textures/paper-texture.jpg")
        rl.set_texture_filter(self.textures["bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["menu_bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["paper_raw"], rl.TEXTURE_FILTER_BILINEAR)
        # Layout is computed once; both baking and hit-testing reference it.
        self.paper_layout = quad_text.layout_lines(_PAPER_LINES, self.fonts["serif"], _PAPER_MX, _PAPER_MY)
        self.textures["paper"] = _bake_paper_texture(
            self.textures["paper_raw"], self.fonts["serif"], self.paper_layout)

    def load_models(self):
        self.models = {}
        self.models["table"]   = rl.load_model(b"models/env/chinese_tea_table_2k.gltf")
        # Inspected-item models, keyed by Item.name ("relogio" / "lista")
        self.models["relogio"] = rl.load_model(b"models/objects/mantel_clock/mantel_clock_01_1k.gltf")
        self.models["lista"]   = rl.load_model(b"models/objects/papel/papel.gltf")
        # The interactive checklist paper (generated plane + baked text texture)
        paper_mesh = rl.gen_mesh_plane(self.PAPER_W, self.PAPER_H, 1, 1)
        self.models["paper"] = rl.load_model_from_mesh(paper_mesh)
        self.models["paper"].materials[0].maps[rl.MATERIAL_MAP_DIFFUSE].texture = self.textures["paper"]

    def load_sounds(self):
        # tenta carregar um som para cada tutorial/estrofe.
        import os
        candidates = []
        for i in range(len(self.tutorial_texts)):
            candidates.clear()
            candidates.extend([
                f"sounds/intro{i+1}.ogg",
                f"sounds/intro{i+1}.mp3",
                f"sounds/intro{i+1}.wav",
                f"sounds/tutorial_{i+1}.ogg",
                f"sounds/tutorial_{i+1}.mp3",
                f"sounds/tutorial_{i+1}.wav",
            ])

            sound_obj = None
            for path in candidates:
                if not os.path.exists(path):
                    continue
                try:
                    # Prefer load_sound for compressed formats (ogg/mp3)
                    if path.lower().endswith('.ogg') or path.lower().endswith('.mp3'):
                        try:
                            sound_obj = rl.load_sound(path.encode('utf-8'))
                        except Exception:
                            # fallback to loading wave then sound
                            try:
                                wave = rl.load_wave(path.encode('utf-8'))
                                sound_obj = rl.load_sound_from_wave(wave)
                                try:
                                    rl.unload_wave(wave)
                                except Exception:
                                    pass
                            except Exception:
                                sound_obj = None
                    else:
                        # WAV: prefer load_wave -> load_sound_from_wave
                        try:
                            wave = rl.load_wave(path.encode('utf-8'))
                            sound_obj = rl.load_sound_from_wave(wave)
                            try:
                                rl.unload_wave(wave)
                            except Exception:
                                pass
                        except Exception:
                            try:
                                sound_obj = rl.load_sound(path.encode('utf-8'))
                            except Exception:
                                sound_obj = None
                except Exception:
                    sound_obj = None

                if sound_obj:
                    break

            self.sounds[f"tutorial_{i+1}"] = sound_obj


    def rebake_paper(self, hovered_key: str | None = None):
        """Re-render the paper texture (checkbox states + optional button highlight) and hot-swap on the model."""
        states  = self.gs.get("paper_states", {})
        new_tex = _bake_paper_texture(self.textures["paper_raw"], self.fonts["serif"],
                                      self.paper_layout, states, hovered_key)
        rl.unload_texture(self.textures["paper"])
        self.textures["paper"] = new_tex
        self.models["paper"].materials[0].maps[rl.MATERIAL_MAP_DIFFUSE].texture = new_tex

    def unload_fonts(self):
        for font in self.fonts.values():
            rl.unload_font(font)

    def unload_textures(self):
        for key, tex in self.textures.items():
            try:
                rl.unload_texture(tex)
            except Exception:
                # pode ser uma Font ou outro objeto; tente descarregar como fonte
                try:
                    rl.unload_font(tex)
                except Exception:
                    pass
        # descarrega sons caso existam
        if hasattr(self, 'sounds'):
            for s in self.sounds.values():
                if s is not None:
                    try:
                        rl.unload_sound(s)
                    except Exception:
                        pass

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
            "paper_states":      {},    # key → bool for checkboxes
            "paper_items":       parse_paper_items(self.paper_layout, self.fonts["serif"]),
            "paper_hovered_key": None,  # key of currently hovered button, or None
            # --- Inspected object (arcball rotation) ---
            "object_transform":  rl.matrix_identity(),
            "dragging":          False,
            "spin_angle":        0.0,
            "spin_axis":         (0.0, 1.0, 0.0),
            "drag_dir":          None,
            "debug":        False,
            "cam_yaw":      self._INIT_CAM_YAW,
            "cam_pitch":    self._INIT_CAM_PITCH,
            "cam_pos":      Vector3(self.CAM_POS.x, self.CAM_POS.y, self.CAM_POS.z),
        }
