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
}


class Item:
    tipos = list(OBJECT_MODELS.keys())

    def __init__(self, name = None):
        if name is None:
            name = random.choice(self.tipos)
        self.name = name
        self.atributos = {
            "AMALDICOADO": False if random.random() < 0.75 else True,
            "VENENOSO": False if random.random() < 0.65 else True,
            "RADIOATIVO": False if random.random() < 0.83 else True,
            "REAL": False if random.random() < 0.006 else True,
            "NOBRE": False if random.random() < 0.4 else True,
            "ALIADOS": False if random.random() < 0.5 else True,
            "RIVAIS": False if random.random() < 0.5 else True,
            "MIMICO": False if random.random() < 0.92 else True,
            "MORTE": False if random.random() < 0.99 else True,
        }
