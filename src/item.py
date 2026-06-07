import random

# Inspectable object types → their glTF model file (relative to the working dir).
# Add new entries here and they automatically join the rotation of items shown
# on the table; game_context loads every model listed and normalises its scale.
OBJECT_MODELS = {
    "relogio":              b"models/objects/mantel_clock/mantel_clock_01_1k.gltf",
    "metal_jug":            b"models/objects/metal_jug/metal_jug_1k.gltf",
    "treasure_chest":       b"models/objects/treasure_chest/treasure_chest_1k.gltf",
    "wooden_axe":           b"models/objects/wooden_axe/wooden_axe_03_1k.gltf",
    "brass_pot":            b"models/objects/brass_pot/brass_pot_02_1k.gltf",
    "brass_pan":            b"models/objects/brass_pan/brass_pan_01_1k.gltf",
    "antique_ceramic_vase": b"models/objects/antique_ceramic_vase/antique_ceramic_vase_01_1k.gltf",
    "wooden_bowl":          b"models/objects/wooden_bowl/wooden_bowl_02_1k.gltf",
    "garden_gnome":         b"models/objects/garden_gnome/garden_gnome_1k.gltf",
    "concrete_cat_statue":  b"models/objects/concrete_cat_statue/concrete_cat_statue_1k.gltf",
    "lambis_shell":         b"models/objects/lambis_shell/lambis_shell_1k.gltf",
    # --- Foods (hunger system) ---
    "maca":             b"models/objects/food_apple/food_apple_01_1k.gltf",
    "lichia":           b"models/objects/food_lychee/food_lychee_01_1k.gltf",
    "limao":            b"models/objects/lemon/lemon_1k.gltf",
    "bolo":             b"models/objects/strawberry_chocolate_cake/strawberry_chocolate_cake_1k.gltf",
    "cebola":           b"models/objects/yellow_onion/yellow_onion_1k.gltf",
}
# OBJECT_MODELS = {
#     "metal_jug":            b"models/objects/metal_jug/metal_jug_1k.gltf",
# }

FOOD_NAMES = {"maca", "lichia", "limao", "bolo", "cebola"}


class Item:
    tipos = list(OBJECT_MODELS.keys())
    CURSE_VARIANTS = ("nausea", "chave", "inverter")
    ALIADO_VARIANTS = ("Aliado1", "Aliado2", "Aliado3")
    INIMIGO_VARIANTS = ("Inimigo1", "Inimigo2", "Inimigo3")

    def __init__(self, name=None):
        if name is None:
            name = random.choice(self.tipos)
        self.name = name
        self.is_food = name in FOOD_NAMES

        if self.is_food:
            self._init_food_attrs()
        else:
            self._init_normal_attrs()
        
        self.curse = None
        self.nation = None
        if self.atributos["AMALDICOADO"]:
            self.curse = random.choice(self.CURSE_VARIANTS)

        if self.atributos["ALIADOS"]:
            self.nation = random.choice(self.ALIADO_VARIANTS)
        elif self.atributos["RIVAIS"]:
            self.nation = random.choice(self.INIMIGO_VARIANTS)

    @staticmethod
    def _roll_faction(ally_chance: float, rival_chance: float) -> tuple[bool, bool]:
        """ALIADOS and RIVAIS are mutually exclusive: an item belongs to one
        faction, the other, or neither — never both."""
        r = random.random()
        if r < ally_chance:
            return True, False
        if r < ally_chance + rival_chance:
            return False, True
        return False, False

    def _init_normal_attrs(self):
        aliados, rivais = self._roll_faction(0.20, 0.20)
        self.atributos = {
            "AMALDICOADO": random.random() < 0.18,
            "VENENOSO":    random.random() < 0.20,
            "RADIOATIVO":  random.random() < 0.18,
            "REAL":        random.random() < 0.16,
            "NOBRE":       random.random() < 0.20,
            "ALIADOS":     aliados,
            "RIVAIS":      rivais,
            "MIMICO":      random.random() < 0.15,
            "MORTE":       random.random() < 0.00,
        }

        

        


    def _init_food_attrs(self):
        aliados, rivais = self._roll_faction(0.05, 0.20)
        self.atributos = {
            "AMALDICOADO": random.random() < 0.20,
            "VENENOSO":    random.random() < 0.10,
            "RADIOATIVO":  random.random() < 0.08,
            "REAL":        random.random() < 0.00,
            "NOBRE":       random.random() < 0.00,
            "ALIADOS":     aliados,
            "RIVAIS":      rivais,
            "MIMICO":      random.random() < 0.04,
            "MORTE":       False,
        }

    @property
    def hunger_restore(self) -> float:
        """How much hunger this food restores when eaten (only meaningful for foods)."""
        if not self.is_food:
            return 0.0
        base = 35.0
        if self.atributos.get("VENENOSO"):
            base = -15.0
        if self.atributos.get("AMALDICOADO"):
            base += -10.0
        if self.atributos.get("RADIOATIVO"):
            base += -8.0
        if self.atributos.get("MIMICO"):
            base = 0.0
        return base

    @property
    def hunger_penalty(self) -> float:
        """Extra hunger lost from eating bad food (absolute value, always >= 0)."""
        r = self.hunger_restore
        return max(0.0, -r)
