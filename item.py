import random

class Item:
    tipos = ["relogio", "lista"]

    def __init__(self, name = None):
        if name is None:
            name = random.choice(self.tipos)
        self.name = name
        self.atributos = {
            "VENENOSO": False if random.random() < 0.65 else True,
            "RADIOATIVO": False if random.random() < 0.83 else True,
            "REAL": False if random.random() < 0.6 else True,
            "NOBRE": False if random.random() < 0.4 else True,
            "MIMICO": False if random.random() < 0.92 else True,
            "MALDIÇÕES": [],
            "ALIADOS": [],
            "RIVAIS": []
        }
