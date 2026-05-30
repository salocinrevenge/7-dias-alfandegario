import sys
import pyray as rl
from pyray import Vector3
import math
import time

from state import State
from transition import Transition


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
        self.models["object"] = rl.load_model(b"models/objects/mantel_clock_01_1k.gltf")

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