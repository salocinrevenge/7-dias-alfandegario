import sys
import pyray as rl
from pyray import Vector3
import math
import time

from state import State
from transition import Transition
from item import Item

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

        # --- Models & textures ---
        self.load_models()
        self.load_textures()

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
        self.windowed_w, self.windowed_h = 1000, 700



        self.painting_enabled = True                           # [K] toggles this

        # --- State machine ---
        self.current_state      = State.MENU
        self.prev_inspect_drawn = False
        self.transition         = Transition()
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
        # Agora que os textos existem, tente carregar os sons do tutorial
        try:
            self.load_sounds()
        except Exception:
            pass

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

    def load_textures(self):
        self.textures = {}
        self.textures["bg"]   = rl.load_texture(b"models/env/wizard_room.jpg")
        self.textures["menu_bg"] = rl.load_texture(b"models/env/outside2.jpg")
        self.textures["tropiland_font"] = rl.load_font_ex(b"fonts/TropiLand.ttf", 128, None, 0)
        rl.set_texture_filter(self.textures["bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["menu_bg"], rl.TEXTURE_FILTER_BILINEAR)
        rl.set_texture_filter(self.textures["tropiland_font"].texture, rl.TEXTURE_FILTER_BILINEAR)

    def load_models(self):
        self.models = {}
        self.models["table"]  = rl.load_model(b"models/env/chinese_tea_table_2k.gltf")
        self.models["relogio"] = rl.load_model(b"models/objects/mantel_clock_01_1k.gltf")
        self.models["lista"] = rl.load_model(b"models/objects/papel.gltf")

    def load_sounds(self):
        # tenta carregar um som para cada tutorial/estrofe.
        for i in range(len(self.tutorial_texts)):
            key = f"intro{i+1}"
            path = f"sounds/{key}.ogg"
            try:
                self.sounds[key] = rl.load_sound(path.encode('utf-8'))
            except Exception:
                self.sounds[key] = None


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
            "object_transform": rl.matrix_identity(),
            "dragging":   False,
            "drag_dir":   None,
            "spin_axis":  (0.0, 1.0, 0.0),
            "spin_angle": 0.0,
            "debug":     False,
            "cam_yaw":   self._INIT_CAM_YAW,
            "cam_pitch": self._INIT_CAM_PITCH,
            "cam_pos":   Vector3(self.CAM_POS.x, self.CAM_POS.y, self.CAM_POS.z),
        }