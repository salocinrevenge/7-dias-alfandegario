import math
import random
from pyray import Vector3


class ShakeAnimation:
    def __init__(self, intensity=0.05):
        self.intensity = intensity
        self.offset = Vector3(0.0, 0.0, 0.0)
        self._time = 0.0
        self._fx = random.uniform(7.0, 13.0)
        self._fy = random.uniform(7.0, 13.0)
        self._fz = random.uniform(7.0, 13.0)
        self._px = random.uniform(0.0, math.pi * 2.0)
        self._py = random.uniform(0.0, math.pi * 2.0)
        self._pz = random.uniform(0.0, math.pi * 2.0)

    def update(self, dt: float):
        self._time += dt
        t = self._time
        self.offset = Vector3(
            math.sin(t * self._fx + self._px) * self.intensity,
            math.sin(t * self._fy + self._py) * self.intensity,
            math.sin(t * self._fz + self._pz) * self.intensity,
        )


def update_animations(gc, dt: float):
    if not hasattr(gc, "animations") or not gc.animations:
        return
    for anim in gc.animations.values():
        anim.update(dt)


def get_anim_offset(gc, model_name: str) -> Vector3:
    if hasattr(gc, "animations") and model_name in gc.animations:
        return gc.animations[model_name].offset
    return Vector3(0.0, 0.0, 0.0)


def add_shake(gc, model_name: str, intensity=0.05):
    if not hasattr(gc, "animations"):
        gc.animations = {}
    gc.animations[model_name] = ShakeAnimation(intensity)


def remove_animation(gc, model_name: str):
    if hasattr(gc, "animations") and model_name in gc.animations:
        del gc.animations[model_name]
