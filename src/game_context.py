import sys
import pyray as rl
from pyray import Vector2, Vector3
import math
import time

from . import quad_text
from .state import State
from .transition import Transition
import random
from .item import Item, OBJECT_MODELS
from .animation import add_shake, TweenAnimation
from .audio_effects import AudioEffects
from .mimic import Mimic, unload_appendage_models
from .badge import attach_badge

# Lines support a leading <tag> that selects a font size (see quad_text.SIZES).
_PAPER_LINES = [
    b"<title>              Propriedades dos Itens",
    b"<small>",
    b"<h1>[ ] Amaldicoado ?",
    b"<h1>[ ] Venenoso ?",
    b"<h1>[ ] Radioativo ?",
    b"<h1>[ ] Real ?",
    b"<h1>[ ] Nobre ?",
    b"<h1>[ ] Aliado ?",
    b"<h1>[ ] Rival ?",
    b"<small>",
    b"",
    b"<h2>              Rejeitar   Comer             Aceitar",
]

PAPER_TW, PAPER_TH = 1024, 1448   # 2x bake resolution (see quad_text.SIZES)
_PAPER_MX = PAPER_TW // 8           # 64 px left margin
_PAPER_MY = PAPER_TH // 12          # ~60 px top margin

_CHECK_EMPTY = b"[ ]"
_CHECK_FULL  = b"[x]"   # [✔]  U+2714 as UTF-8

_INK_NORMAL  = rl.Color(25,  15,   5, 220)
_INK_HOVER   = rl.Color(160, 80,  10, 255)   # warm amber for the hovered button


def _is_button_line(text: bytes) -> bool:
    return b"Aceitar" in text and b"Rejeitar" in text


def _button_rects(font: rl.Font, span: dict) -> dict:
    """Sub-rects of the three words (Rejeitar / Comer / Aceitar) in texture coords."""
    text, size = span["text"], span["size"]
    x, y, h    = span["x"], span["y"], span["h"]
    c_off = text.find(b"Comer")
    a_off = text.find(b"Aceitar")
    return {
        "rejeitar": (x, y, quad_text.measure(font, b"Rejeitar", size), h),
        "comer":    (x + quad_text.measure(font, text[:c_off], size),
                     y, quad_text.measure(font, b"Comer", size), h),
        "aceitar":  (x + quad_text.measure(font, text[:a_off], size),
                     y, quad_text.measure(font, b"Aceitar", size), h),
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
            items.append({"type": "button", "key": "rejeitar", "rect": rects["rejeitar"]})
            items.append({"type": "button", "key": "comer",    "rect": rects["comer"]})
            items.append({"type": "button", "key": "aceitar",  "rect": rects["aceitar"]})
    return items


def _bake_paper_texture(paper_tex, font: rl.Font, layout: list[dict],
                        states: dict | None = None,
                        hovered_key: str | None = None,
                        is_food: bool = False) -> rl.Texture2D:
    """Render the paper background + tagged text into a flip-corrected Texture2D.

    hovered_key: key of the button whose word is drawn in _INK_HOVER.
    is_food: if True, a third "Comer" button is drawn between Rejeitar and Aceitar.
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
            cx, cy, _, _ = r["comer"]
            # Rejeitar — always visible
            quad_text.draw_text(font, b"Rejeitar", rx, ry, span["size"],
                                _INK_HOVER if hovered_key == "rejeitar" else _INK_NORMAL)
            # Comer — only when the item is food
            if is_food:
                quad_text.draw_text(font, b"Comer", cx, cy, span["size"],
                                    _INK_HOVER if hovered_key == "comer" else _INK_NORMAL)
            # Aceitar — always visible
            quad_text.draw_text(font, b"Aceitar", ax, ay, span["size"],
                                _INK_HOVER if hovered_key == "aceitar" else _INK_NORMAL)

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
        # The scene is rendered into a render texture whose size tracks the
        # largest 16:9 rectangle that fits the current window/canvas, measured in
        # *physical* pixels (see update_render_target in main.py). That keeps the
        # framing identical desktop vs web (always 16:9, black-bar letterboxed by
        # get_scaled_rect) while rendering at the display's native resolution so
        # nothing is upscaled/blurry. All layout is expressed as fractions of
        # VIRTUAL_H, so it stays proportional at any resolution. These are just
        # the bootstrap values; the real size is set on the first frame.
        self.RENDER_ASPECT = 16.0 / 9.0
        self.VIRTUAL_W = 1280
        self.VIRTUAL_H = 720

        # ---------------------------------------------------------------------------
        # SCENE CONSTANTS
        # ---------------------------------------------------------------------------
        self.TABLE_SCALE  = 1.0
        self.TABLE_POS    = Vector3(0, 0, 0)

        self.OBJECT_SIZE  = 0.15
        self.OBJECT_Y     = 0.60
        self.OBJECT_POS   = Vector3(0, self.OBJECT_Y + self.OBJECT_SIZE * 0.5, 0.0)
        # Every inspected model is normalised so its largest dimension equals this,
        # guaranteeing the object is always framed in front of the camera no matter
        # what its native real-world size is.
        self.OBJECT_TARGET = 0.26

        self.CAM_POS    = Vector3(0.0, 0.8, 0.7)
        self.CAM_TARGET = Vector3(0, 0.68, 0.0)

        self._OBJECT_RADIUS = self.OBJECT_TARGET * 0.5

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

        self.paper_anim = TweenAnimation(duration=0.3)

        # --- Resources (fonts → textures → models; the paper bake needs the font) ---
        self.load_fonts()
        self.load_textures()
        self.load_models()
        # Top-down light + soft contact shadow (after models exist).
        self.load_lighting()
        # Floating dust motes drawn behind the 3D scene.
        self.load_particles()

        # --- Audio ---
        try:
            rl.init_audio_device()
        except Exception:
            # plataforma pode não suportar audio (web), ignore falhas
            pass
        self.sounds = {}
        self.tutorial_played_index = -1
        self.current_tutorial_sound = None   # sound currently playing in the intro
        # tenta carregar sons correspondentes às estrofes (sounds/tutorial_1.wav...)
        # consulte load_sounds() abaixo (será chamado mais abaixo, após definir os textos)

        # --- Camera ---
        self.camera            = rl.Camera3D()
        self.camera.position   = self.CAM_POS
        self.camera.target     = self.CAM_TARGET
        self.camera.up         = Vector3(0, 1, 0)
        self.camera.fovy       = 55.0
        self.camera.projection = rl.CAMERA_PERSPECTIVE

        # --- Magnifying-glass tool (hold RMB) ---
        # A screen-space lens in the post-process shader; the camera never moves.
        self.MAGNIFY     = 2.3                   # peak magnification inside the lens
        self.zoom_t      = 0.0                   # eased 0→1 activation
        self.lens_center = (0.5, 0.5)            # cursor position in texture UV
        self.lens_radius = 0.17                  # lens radius (fraction of height)
        self.lens_zoom   = 1.0                   # current magnification (1 = off)

        # --- Keyhole curse (vision mask) ---
        # The aperture is a circle (head) + a downward triangle (body). All
        # fractions of the virtual height, so it stays proportional on resize.
        self.KEYHOLE_RADIUS_FRAC = 0.08 * 0.8 # head radius
        self.KEYHOLE_CONE_W_FRAC = 0.15 * 0.8 # body half-width at the base
        self.KEYHOLE_CONE_H_FRAC = 0.25 * 0.8 # body height

        # --- Window
        self.windowed_w, self.windowed_h = 1080, 720

        self.painting_enabled = True                           # [K] toggles this

        # --- State machine ---
        self.current_state      = State.MENU
        self.prev_inspect_drawn = False
        self.transition         = Transition()
        self.start_time         = time.time()
        self.prev_time          = time.time()
        self.now                = self.prev_time
        self.player             = None
        self.n_erros = 0
        self.penalidade = 0
        # Per-day penalty allowance before the day must be redone (penalidade is
        # reset every morning, so this is "mistakes tolerated in a single day").
        self.penalidade_to_day = 10
        self.erros_to_fire = 10
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

        self.error_costs = {
            "AMALDICOADO": 4,
            "VENENOSO": 3,
            "RADIOATIVO": 1,
            "REAL": 2,
            "NOBRE": 1,
            "ALIADOS": 1,
            "RIVAIS": 1,
            "REJECT": 1,
            "MIMICO": 5,
            "MORTE": 10,
        }
        self.positive_rejects = ["REAL", "NOBRE", "ALIADOS"]
        self.negative_acept = ["AMALDICOADO", "VENENOSO", "RADIOATIVO", "RIVAIS", "MIMICO"]

        self._empty_item_properties = Item.empty_properties_on_list()

        self.reset_count_until_end_day = 100
        self.count_until_end_day = self.reset_count_until_end_day
        self.created_room = False

        # Per-day stats (reset each morning, shown in day-end summary)
        self.errors_today = 0
        self.items_judged_today = 0
        self.items_correct_today = 0
        self.foods_eaten_today = 0

        # Snapshot of the day that just ended, shown on the next "Dia X" card.
        self.last_day_items_judged  = 0
        self.last_day_items_correct = 0
        self.last_day_errors        = 0
        self.last_day_foods_eaten   = 0
        self.last_day_hunger_pct    = 0

        # Cumulative stats (never reset, shown in end-game screen)
        self.total_items_judged = 0
        self.total_correct = 0
        self.total_foods = 0

        self.MAX_TIME = 50.0
        self.item_time_max = self.MAX_TIME
        self.item_time_left = self.item_time_max

        # --- Hunger system ---
        self.hunger_max = 100.0
        self.hunger = self.hunger_max
        self.hunger_decay = 1.2          # points lost per second
        self.hunger_starve_penalty = 0.0 # accumulates when starving, triggers errors

        self.reset_tutorial_texts()

        self.day_intro_timer = 0.0
        self.day_intro_char_count = 0.0
        self.day_intro_typing_speed = 8.0

        self.animations = {}
        self.mimic_eyes = {}
        self.current_mimic_eyes = None
        # Badge-stamped model copies, keyed by id(item). Badges depend on the
        # item instance's random attributes, so the shared pristine model in
        # self.models is never touched. A value of None means "plain item, draw
        # the pristine model". Baking a copy (disk load + texture stamping) is
        # heavy and used to run synchronously mid-swap, freezing the loop long
        # enough to glitch audio; it's now prefetched during the calm inspection
        # of the previous item (see prefetch_item_model) and evicted once an item
        # has been judged.
        self.item_models = {}
        self.setup_animations()
        self.load_sounds()

        # Per-frame audio processor. Created once for the whole session (it loads
        # procedural SFX); reset_game() reuses this instance instead of leaking it.
        self.audio_effects = AudioEffects(self)

    def reset_tutorial_texts(self):
        self.tutorial_texts = [
            "Nas torres frias da escuridao,\ncomeca hoje tua missao.\nJulga os tesouros sem temor,\nanota tudo com rigor.",
            "Se houver veneno ou maldicao,\nrejeita sem hesitacao.\nSe um mimico ousar chegar,\nnao o deixes atravessar.",
            "Das terras do inimigo vil,\nnao passes nada ao teu perfil.\nE o Livro Nuclear, em ardor,\nrecusa-o sem nenhum pudor.",
            "Sete dias tens para provar\nque sabes bem fiscalizar.\nSe muitos erros cometer,\nao posto has de retornar.",
            "Mas se o fracasso florescer,\nteu cargo iras perder.\nAgora vigia o portao,\ne cumpre tua obrigacao."
        ]
        self.tutorial_index = 0
        self.tutorial_char_count = 0.0
        self.tutorial_seen = False
        self.tutorial_typing_speed = 30.0
        self.tutorial_played_index = -1
        
        # Restore original tutorial sound if needed
        if hasattr(self, "sounds") and "tutorial_1_original" in self.sounds:
            self.sounds["tutorial_1"] = self.sounds["tutorial_1_original"]

    def reset_game(self):
        """Restore all gameplay progress to a fresh start, keeping loaded
        resources (fonts/textures/models/sounds). Called whenever we return to
        the menu or finish a run so the next playthrough begins clean."""
        self.n_erros = 0
        self.penalidade = 0
        self.dia_atual = 0
        self.count_until_end_day = self.reset_count_until_end_day
        self.created_room = False
        self.itens_hoje = {'to evaluate': [], 'evaluated': []}

        self.item_time_max = self.MAX_TIME
        self.item_time_left = self.item_time_max

        self.day_intro_timer = 0.0
        self.day_intro_char_count = 0.0

        self.reset_current_item_properties()

        # Tutorial back to its day-1 state (resets index/seen/char counters too).
        self.reset_tutorial_texts()
        self.current_tutorial_sound = None

        # Per-item visual state.
        self._clear_item_models()
        self.mimic_eyes.clear()
        self.current_mimic_eyes = None

    def setup_animations(self):
        from .item import OBJECT_MODELS
        # Same idle shake for every inspectable object...
        for name in OBJECT_MODELS:
            add_shake(self, name, offset=0.001, velocity=0.3)
        # ...and the paper (only applied while it's held in front of the player).
        add_shake(self, "paper", offset=0.001, velocity=0.3)

    @property
    def current_item(self):
        items = self.itens_hoje.get('to evaluate', [])
        return items[0] if items else None

    @property
    def properties_on_list(self):
        item = self.current_item
        if item is None:
            return self._empty_item_properties
        return item.properties_on_list

    def reset_current_item_properties(self):
        item = self.current_item
        if item is None:
            for key in self._empty_item_properties:
                self._empty_item_properties[key] = False
            return
        item.reset_properties_on_list()

    def start_new_day(self):
        self.created_room = True
        self.make_scene_state()
        
        is_redo = False
        if self.penalidade >= self.penalidade_to_day:
            self.dia_atual -= 1
            self.penalidade = 0
            is_redo = True
            
        if self.n_erros >= self.erros_to_fire:
            self.transition.start(State.GAME_OVER_FIRED)
            return
        self.dia_atual += 1
        if self.dia_atual > 7:
            self.transition.start(State.GAME_OVER_WIN)
            return
            
        if is_redo:
            self.tutorial_texts = ["Nossa alfandegario, voce errou coisa pra caramba, e melhor voce trabalhar mais um dia ai denovo vamos"]
            self.tutorial_index = 0
            self.tutorial_char_count = 0.0
            self.tutorial_seen = False
            self.tutorial_played_index = -1
            self.transition.start(State.INSPECT)
            
            if hasattr(self, "sounds") and "redo" in self.sounds:
                self.sounds["tutorial_1"] = self.sounds["redo"]
        else:
            self.transition.start(State.INSPECT)
            
        self.day_intro_timer = 2.5
        self.day_intro_char_count = 0.0
        self.hunger = self.hunger_max
        self.hunger_starve_penalty = 0.0
        # penalidade is judged per-day: start each morning with a clean slate so
        # the redo threshold measures only the current day's mistakes.
        self.penalidade = 0
        # A new day wipes any curses inflicted the previous day.
        self.nausea_curse_active = False
        self.inversion_curse_active = False
        self.keyhole_curse_active = False
        # Snapshot the finished day's stats BEFORE zeroing them, so the next
        # morning's "Dia X" card can show the previous day's acertos/erros (the
        # live counters are reset below for the new day).
        self.last_day_items_judged  = self.items_judged_today
        self.last_day_items_correct = self.items_correct_today
        self.last_day_errors        = self.errors_today
        self.last_day_foods_eaten   = self.foods_eaten_today
        self.last_day_hunger_pct    = (int(self.hunger / self.hunger_max * 100)
                                       if self.hunger_max > 0 else 0)
        self.errors_today = 0
        self.items_judged_today = 0
        self.items_correct_today = 0
        self.foods_eaten_today = 0
        print(f"Starting day {self.dia_atual}...")
        # Drop any badged models cached for the previous day's items before the
        # new batch replaces them (their item objects are about to be discarded,
        # so their cache entries would otherwise leak).
        self._clear_item_models()
        self.itens_hoje['to evaluate'] = [Item() for _ in range(self.n_itens_dias.get(self.dia_atual, 15))]
        self.itens_hoje['evaluated'] = []

        self._ensure_mimic_eyes_for_current()

        self.gs["object_hidden"]       = True
        self.gs["pending_first_enter"] = True

    def mimic_view_args(self):
        """(object world-rotation, world-space object→camera direction) used by
        the mimic to keep its trait on the side facing away from the camera."""
        cp, op = self.camera.position, self.OBJECT_POS
        dx, dy, dz = cp.x - op.x, cp.y - op.y, cp.z - op.z
        length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        cam_dir = Vector3(dx / length, dy / length, dz / length)
        view_rot = self.gs.get("object_transform") if hasattr(self, "gs") else None
        if view_rot is None:
            view_rot = rl.matrix_identity()
        return view_rot, cam_dir

    def _ensure_mimic_eyes_for_current(self):
        items = self.itens_hoje.get('to evaluate', [])
        if not items:
            self.current_mimic_eyes = None
            return

        current = items[0]
        name = current.name
        is_mimic = current.atributos.get("MIMICO", False)

        if is_mimic:
            if name not in self.mimic_eyes:
                eyes = Mimic()
                eyes.setup(self.models[name], *self.mimic_view_args())
                self.mimic_eyes[name] = eyes
            self.current_mimic_eyes = self.mimic_eyes[name]
            self.current_mimic_eyes.new_object()
        else:
            self.current_mimic_eyes = None

        # The current item's badged model is normally already cached (prefetched
        # while the previous item was being inspected); this is a cheap cache hit.
        # It only bakes synchronously here as a fallback (e.g. the very first item
        # of a day, which has no previous item to prefetch behind).
        self.prefetch_item_model(current)


    # Badge images (under textures/) keyed by the Item attribute that triggers
    # them. Aliado/Inimigo have interchangeable variants; the curses are stamped
    # when the item is AMALDICOADO (a random one) and/or VENENOSO (venenoso).
    

    def _badges_for_item(self, item) -> list[str]:
        """The badge image names to stamp for *item*, per its attributes."""
        a = item.atributos
        badges: list[str] = []
        if a.get("REAL"):
            badges.append("badges/crown")
        if a.get("NOBRE"):
            badges.append("badges/shield")
        if a.get("ALIADOS"):
            badges.append(item.nation)
        if a.get("RIVAIS"):
            badges.append(item.nation)
        if a.get("AMALDICOADO"):
            badges.append(f"badges/{item.curse}")
        # Avoid stamping the same curse twice (e.g. VENENOSO + AMALDICOADO→venenoso).
        return list(dict.fromkeys(badges))

    def _bake_item_model(self, item):
        """Build a fresh, badge-stamped model copy for *item*, or None when the
        item has no badges (callers then fall back to the shared pristine model).

        A fresh copy keeps the shared model in self.models pristine; the draw
        pass reassigns the lighting/shadow shaders to it every frame. This is the
        expensive call (glTF load + per-texture stamping) — keep it off the
        gameplay-critical swap frame by prefetching ahead of time.
        """
        badges = self._badges_for_item(item)
        if not badges:
            return None
        model = rl.load_model(OBJECT_MODELS[item.name])
        for badge_name in badges:
            attach_badge(model, badge_name, degradation=0.0, target_px=140)
        return model

    def prefetch_item_model(self, item):
        """Ensure *item*'s badged model is baked and cached. Cheap (a no-op) once
        cached, so it's safe to call every frame; the heavy bake happens at most
        once per item. Call it for the NEXT item while the player inspects the
        current one so the swap itself stays smooth."""
        if item is None:
            return
        key = id(item)
        if key in self.item_models:
            return
        self.item_models[key] = self._bake_item_model(item)

    def prefetch_next_item_model(self):
        """Look-ahead: bake the item that will appear after the current one."""
        items = self.itens_hoje.get('to evaluate', [])
        if len(items) > 1:
            self.prefetch_item_model(items[1])

    def _evict_item_model(self, item):
        """Unload and forget a single item's cached model (after it's judged)."""
        if item is None:
            return
        model = self.item_models.pop(id(item), None)
        if model is not None:
            rl.unload_model(model)

    def _clear_item_models(self):
        """Unload every cached badged model (day rollover / reset / shutdown)."""
        for model in self.item_models.values():
            if model is not None:
                rl.unload_model(model)
        self.item_models.clear()

    def inspect_model(self, name):
        """The model to draw for the inspected item: its cached badged copy when
        one exists, otherwise the shared pristine model."""
        item = self.current_item
        if item is not None:
            model = self.item_models.get(id(item))
            if model is not None:
                return model
        return self.models[name]

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

        # Inspected-item models, keyed by Item.name. Each is measured at load time so
        # we can normalise its scale and recentre it on the table; object_fit maps
        # name -> (uniform scale, bbox-centre Vector3).
        from .item import OBJECT_MODELS
        self.object_fit = {}
        for name, path in OBJECT_MODELS.items():
            model = rl.load_model(path)
            self.models[name] = model
            bb = rl.get_model_bounding_box(model)
            cx = (bb.min.x + bb.max.x) * 0.5
            cy = (bb.min.y + bb.max.y) * 0.5
            cz = (bb.min.z + bb.max.z) * 0.5
            max_dim = max(bb.max.x - bb.min.x,
                          bb.max.y - bb.min.y,
                          bb.max.z - bb.min.z) or 1.0
            self.object_fit[name] = (self.OBJECT_TARGET / max_dim, Vector3(cx, cy, cz))

        # The interactive checklist paper (generated plane + baked text texture)
        paper_mesh = rl.gen_mesh_plane(self.PAPER_W, self.PAPER_H, 1, 1)
        self.models["paper"] = rl.load_model_from_mesh(paper_mesh)
        self.models["paper"].materials[0].maps[rl.MATERIAL_MAP_DIFFUSE].texture = self.textures["paper"]

        # Warm the mimic appendage model cache now so the first mimic appearance
        # mid-game doesn't stutter while loading these heavy models.
        from .mimic import preload_appendage_models
        preload_appendage_models()

    def load_lighting(self):
        """Set up a single Blinn-Phong spotlight from above plus a planar
        projected shadow cast onto the table.

        The light shader is applied to the table and every inspected object so
        their tops catch the warm cone and their undersides fall into a cool
        ambient. The paper keeps the default (unlit) shader so its baked text
        stays crisp and bright. The shadow is a second, flattened draw of the
        object using a flat dark shader — cheap and identical on desktop/web,
        no depth-texture shadow mapping required.
        """
        if self.IS_WEB:
            vs   = b"shaders/lighting_web.vs"
            fs   = b"shaders/lighting_web.fs"
            sfs  = b"shaders/shadow_web.fs"
        else:
            vs   = b"shaders/lighting.vs"
            fs   = b"shaders/lighting.fs"
            sfs  = b"shaders/shadow.fs"

        shader = rl.load_shader(vs, fs)
        self.lighting_shader = shader
        # The shadow pass reuses the same vertex shader (positions only matter).
        self.shadow_shader = rl.load_shader(vs, sfs)

        # --- Light rig --------------------------------------------------------
        # A spotlight hung above the table, slightly toward the camera, aiming
        # down at the inspection spot. Constants are set once.
        self.TABLE_TOP_Y = 0.52
        self.LIGHT_POS   = Vector3(0.30, 1.75, 0.55)
        light_target     = Vector3(0.0, self.OBJECT_Y, 0.0)
        ldir = Vector3(light_target.x - self.LIGHT_POS.x,
                       light_target.y - self.LIGHT_POS.y,
                       light_target.z - self.LIGHT_POS.z)
        _ln = math.sqrt(ldir.x**2 + ldir.y**2 + ldir.z**2) or 1.0
        ldir = Vector3(ldir.x / _ln, ldir.y / _ln, ldir.z / _ln)

        def _vec3(name, x, y, z):
            loc = rl.get_shader_location(shader, name)
            rl.set_shader_value(shader, loc, rl.ffi.new("float[3]", [x, y, z]),
                                rl.SHADER_UNIFORM_VEC3)

        def _float(name, v):
            loc = rl.get_shader_location(shader, name)
            rl.set_shader_value(shader, loc, rl.ffi.new("float *", v),
                                rl.SHADER_UNIFORM_FLOAT)

        _vec3(b"lightPos",     self.LIGHT_POS.x, self.LIGHT_POS.y, self.LIGHT_POS.z)
        _vec3(b"lightDir",     ldir.x, ldir.y, ldir.z)
        _vec3(b"lightColor",   1.10, 1.00, 0.86)        # warm key
        _vec3(b"ambientColor", 0.18, 0.20, 0.28)        # cool fill
        _float(b"spotInner",   math.cos(math.radians(26.0)))
        _float(b"spotOuter",   math.cos(math.radians(44.0)))
        _float(b"shininess",   28.0)
        _float(b"specStrength", 0.30)

        # viewPos changes with the camera, so cache its location for per-frame
        # updates in draw_inspect_3d.
        self.lighting_viewpos_loc = rl.get_shader_location(shader, b"viewPos")

        # Apply the light shader to the table and all inspectable objects.
        from .item import OBJECT_MODELS
        lit_models = ["table"] + list(OBJECT_MODELS.keys())
        for name in lit_models:
            model = self.models.get(name)
            if model is None:
                continue
            for i in range(model.materialCount):
                model.materials[i].shader = shader

        # --- Planar shadow projection matrix ---------------------------------
        # Flattens any world point onto the plane y = (TABLE_TOP_Y + lift) as
        # seen from the point light at LIGHT_POS (classic OpenGL shadow matrix).
        self.shadow_proj = self._make_planar_shadow_matrix(
            self.LIGHT_POS, self.TABLE_TOP_Y + 0.004)

        # --- Vignette ---------------------------------------------------------
        # Transparent centre → cool-dark edges, stretched over the whole view.
        # Drawn as a flat overlay so it works identically on desktop and web and
        # stays on regardless of the painting/nausea post-process toggle.
        vig = rl.gen_image_gradient_radial(256, 256, 0.55,
                                           rl.Color(0, 0, 0, 0),
                                           rl.Color(8, 6, 18, 215))
        vig_tex = rl.load_texture_from_image(vig)
        rl.unload_image(vig)
        rl.set_texture_filter(vig_tex, rl.TEXTURE_FILTER_BILINEAR)
        self.textures["vignette"] = vig_tex

    def load_particles(self):
        """Create the dust-mote field, the property auras, and their glow sprite."""
        from .particles import DustParticles, AuraParticles, RadiationParticles
        # White radial glow (opaque centre → transparent edge); tinted per mote.
        img = rl.gen_image_gradient_radial(64, 64, 0.0,
                                           rl.Color(255, 255, 255, 255),
                                           rl.Color(255, 255, 255, 0))
        glow = rl.load_texture_from_image(img)
        rl.unload_image(img)
        rl.set_texture_filter(glow, rl.TEXTURE_FILTER_BILINEAR)
        self.textures["dust_glow"] = glow
        self.particles = DustParticles(glow, count=90)

        # Subtle coloured effects hinting at hidden object properties.
        self.aura_radio  = RadiationParticles((90, 255, 110)) 
        self.aura_poison = AuraParticles((175, 80, 215))

    @staticmethod
    def _make_planar_shadow_matrix(light: Vector3, plane_y: float) -> rl.Matrix:
        """Build the projection that flattens geometry onto the horizontal plane
        y = plane_y, casting from the point light `light`.

        Plane = (0, 1, 0, -plane_y); light = (lx, ly, lz, 1). raylib's Matrix is
        column-major with field m{col*4 + row}; the matrix is consumed as
        mvp * vertex, so this is the standard glide planar-shadow matrix.
        """
        lx, ly, lz = light.x, light.y, light.z
        d = ly - plane_y          # dot(plane, light)

        m = rl.Matrix()
        m.m0,  m.m4,  m.m8,  m.m12 = d,    -lx,    0.0,  lx * plane_y
        m.m1,  m.m5,  m.m9,  m.m13 = 0.0,  d - ly, 0.0,  ly * plane_y
        m.m2,  m.m6,  m.m10, m.m14 = 0.0,  -lz,    d,    lz * plane_y
        m.m3,  m.m7,  m.m11, m.m15 = 0.0,  -1.0,   0.0,  ly
        return m

    def load_sounds(self):
        self.music = {}
        # Web (pygbag) uses the smaller, browser-friendly .ogg encodes; desktop
        # uses the full-quality .mp3 tracks. raylib's WebGL/miniaudio build does
        # not reliably decode mp3, and the mp3s would bloat the download.

        music_files = {
            "menu":     b"sounds/menu-music.ogg",
            "gameplay": b"sounds/gameplay-music.ogg",
            "derrota":  b"sounds/derrota-music.ogg",
            "vitoria":  b"sounds/vitoria-music.ogg",
        }
        for name, path in music_files.items():
            import os
            if os.path.exists(path.decode('utf-8')):
                self.music[name] = rl.load_music_stream(path)
            else:
                self.music[name] = None
        
        self.current_music_key = None
        self.current_music_stream = None

        # tenta carregar um som para cada tutorial/estrofe.
        import os
        candidates = []
        for i in range(len(self.tutorial_texts)):
            candidates.clear()
            if self.IS_WEB:
                # Browser-friendly encodes first.
                candidates.append(f"sounds/intro{i+1}-pygbag.ogg")
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

        # Pre-load the redo sound (browser-friendly encode on web).
        redo_path = b"sounds/refazer-pygbag.ogg" if self.IS_WEB else b"sounds/refazer.ogg"
        try:
            self.sounds["redo"] = rl.load_sound(redo_path)
        except Exception:
            self.sounds["redo"] = None
        # Backup original day 1 tutorial
        self.sounds["tutorial_1_original"] = self.sounds.get("tutorial_1")


    def rebake_paper(self, hovered_key: str | None = None, is_food: bool = False):
        """Re-render the paper texture (checkbox states + optional button highlight) and hot-swap on the model."""
        states  = self.gs.get("paper_states", {})
        new_tex = _bake_paper_texture(self.textures["paper_raw"], self.fonts["serif"],
                                      self.paper_layout, states, hovered_key, is_food)
        rl.unload_texture(self.textures["paper"])
        self.textures["paper"] = new_tex
        self.models["paper"].materials[0].maps[rl.MATERIAL_MAP_DIFFUSE].texture = new_tex

    def update_music(self):
        # Determine the appropriate music based on current state
        desired_music_key = None
        if self.current_state == State.MENU:
            desired_music_key = "menu"
        elif self.current_state in (State.INSPECT, State.PAUSE, State.INTRO):
            desired_music_key = "gameplay"
        elif self.current_state in (State.GAME_OVER_FIRED, State.GAME_OVER_EXPLODED):
            desired_music_key = "derrota"
        elif self.current_state == State.GAME_OVER_WIN:
            desired_music_key = "vitoria"

        # Switch music if needed
        if desired_music_key != self.current_music_key:
            if self.current_music_stream is not None:
                rl.stop_music_stream(self.current_music_stream)
            
            self.current_music_key = desired_music_key
            if desired_music_key and self.music.get(desired_music_key):
                self.current_music_stream = self.music[desired_music_key]
                rl.play_music_stream(self.current_music_stream)
            else:
                self.current_music_stream = None

        # Update the currently playing music
        if self.current_music_stream is not None:
            rl.update_music_stream(self.current_music_stream)

    def resync_music(self):
        """Restart the current music stream after a loop suspension (e.g. the
        browser tab was backgrounded). The stream underruns while no
        update_music_stream calls happen, and on some backends — notably the
        WebAudio/miniaudio build pygbag uses — it never recovers on its own and
        the audio just stays silent/stuck. Stopping and replaying re-primes the
        buffer so sound resumes."""
        stream = self.current_music_stream
        if stream is None:
            return
        try:
            rl.stop_music_stream(stream)
            rl.play_music_stream(stream)
        except Exception:
            pass
        # Any one-shot narration that was mid-play is now desynced too; drop the
        # handle so the intro logic doesn't wait forever on a sound that the
        # backend has effectively abandoned.
        self.current_tutorial_sound = None

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
                        
        if hasattr(self, 'audio_effects') and self.audio_effects:
            self.audio_effects.unload()
        if hasattr(self, 'music'):
            for m in self.music.values():
                if m is not None:
                    try:
                        rl.unload_music_stream(m)
                    except Exception:
                        pass

    def unload_models(self):
        self._clear_item_models()
        self.mimic_eyes.clear()
        unload_appendage_models()
        for model in self.models.values():
            rl.unload_model(model)
        if hasattr(self, "lighting_shader"):
            rl.unload_shader(self.lighting_shader)
        if hasattr(self, "shadow_shader"):
            rl.unload_shader(self.shadow_shader)

    # ---------------------------------------------------------------------------
    # SCENE STATE
    # ---------------------------------------------------------------------------
    def make_scene_state(self) -> dict:
        self.gs = {
            "paper_open":   False,
            "paper_states":      {},    # key → bool for checkboxes
            "paper_items":       parse_paper_items(self.paper_layout, self.fonts["serif"]),
            "paper_hovered_key": None,  # key of currently hovered button, or None
            # --- Inspected object (arcball rotation) ---
            "object_transform":  rl.matrix_identity(),
            # Positional offset (world units) driven by the swap animation
            "object_offset":     Vector3(0.0, 0.0, 0.0),
            "obj_anim":          None,  # dict while a swipe-out/parabola swap plays
            "object_hidden":     False, # True while the next object waits off-table
            "pending_first_enter": False,  # arc the first object in when the day settles
            "dragging":          False,
            "spin_angle":        0.0,
            "spin_axis":         (0.0, 1.0, 0.0),
            "drag_dir":          None,
            "food_msg":     "",
            "food_msg_timer": 0.0,
        }

    def eat_food(self, item):
        """Called when the player rejects a food item — confiscate and eat it.
        Returns a description string for HUD feedback."""
        if not item.is_food:
            return ""
        restore = item.hunger_restore
        self.hunger += restore
        if self.hunger > self.hunger_max:
            self.hunger = self.hunger_max
        if self.hunger < 0:
            self.hunger = 0

        self.apply_curses(item)
        if item.atributos.get("VENENOSO") or item.atributos.get("RADIOATIVO"):
            self.nausea_curse_active = True
        tags = []
        if item.atributos.get("VENENOSO"):
            tags.append("envenenado")
        if item.atributos.get("AMALDICOADO"):
            tags.append("amaldicoado")
        if item.atributos.get("RADIOATIVO"):
            tags.append("radioativo")
        if item.atributos.get("MIMICO"):
            tags.append("falso")

        if restore > 0:
            return f"+{int(restore)} fome"
        elif restore < 0:
            bonus = ", ".join(tags)
            return f"{int(restore)} fome" + (f" ({bonus})" if bonus else "")
        else:
            return "nem era comida..."

    def update_hunger(self, dt: float):
        """Decay hunger over time. Only when an item is actually on the table."""
        if self.current_state not in (State.INSPECT, State.INTRO):
            return
        if self.gs.get("object_hidden") or self.gs.get("pending_first_enter"):
            return
        self.hunger -= self.hunger_decay * dt
        if self.hunger <= 0:
            self.hunger = 0
            # Penalidade em erros por inanição desativada conforme solicitado
            # self.hunger_starve_penalty += dt * 1.2
            # if self.hunger_starve_penalty >= 1.0:
            #     self.hunger_starve_penalty -= 1.0
            #     self.n_erros += 1

    def apply_curses(self, item):
        """Activate the visual/audio curse effects carried by a cursed item.
        Mirrors the curse mapping used when eating tainted food."""
        if item.curse == "nausea":
            self.nausea_curse_active = True
        if item.curse == "inverter":
            self.inversion_curse_active = True
        if item.curse == "chave":
            self.keyhole_curse_active = True

    def compute_negatives(self, acao: str) -> list[str]:
        n_erros_before = self.n_erros

        item = self.current_item
        if item is None:
            return []

        result = item.compute_negatives(
            acao, self.error_costs, self.positive_rejects, self.negative_acept)
        self.penalidade += result["checklist_penalty"]
        if result["verdict_error"]:
             self.n_erros += 1

        if result["effective_action"] == "aceitar":
            # Accepting a cursed item inflicts its curse on the player. (MIMICO's
            # penalty is already covered by negative_acept above.)
            self.apply_curses(item)
            if item.atributos["MORTE"]:
                self.audio_effects.play("explosion")
                self.transition.start(State.GAME_OVER_EXPLODED)

        # Per-day tracking
        errors_this_item = self.n_erros - n_erros_before
        self.items_judged_today += 1
        self.total_items_judged += 1
        if errors_this_item == 0:
            self.items_correct_today += 1
            self.total_correct += 1
        self.errors_today += errors_this_item
        return [result["expected_action"]]

    def reset_effects(self):
        """Clear all active curses and hunger — called on restart / return to menu."""
        self.nausea_curse_active = False
        self.inversion_curse_active = False
        self.keyhole_curse_active = False
        self.hunger = self.hunger_max
        self.hunger_starve_penalty = 0.0
        self.painting_enabled = True
