import math
import random
from pyray import Vector3


class ShakeAnimation:
    def __init__(self, offset=0.05, velocity=1.0):
        self.velocity = velocity
        self.amplitude = offset
        self.current = Vector3(0.0, 0.0, 0.0)
        self._time = 0.0
        self._fx = random.uniform(7.0, 13.0)
        self._fy = random.uniform(7.0, 13.0)
        self._fz = random.uniform(7.0, 13.0)
        self._px = random.uniform(0.0, math.pi * 2.0)
        self._py = random.uniform(0.0, math.pi * 2.0)
        self._pz = random.uniform(0.0, math.pi * 2.0)

    def update(self, dt: float):
        self._time += dt * self.velocity
        t = self._time
        self.current = Vector3(
            math.sin(t * self._fx + self._px) * self.amplitude,
            math.sin(t * self._fy + self._py) * self.amplitude,
            math.sin(t * self._fz + self._pz) * self.amplitude,
        )


class TweenAnimation:
    def __init__(self, duration=1.0):
        self.duration = duration
        self.current = 0.0
        self._raw = 0.0
        self._playing = False
        self._forward = True

    def open(self):
        self._forward = True
        self._playing = True

    def close(self):
        self._forward = False
        self._playing = True

    def update(self, dt: float):
        if not self._playing:
            return
        step = dt / self.duration
        if self._forward:
            self._raw = min(1.0, self._raw + step)
        else:
            self._raw = max(0.0, self._raw - step)
        self.current = self._ease(self._raw)
        if self._raw <= 0.0 or self._raw >= 1.0:
            self._playing = False

    @staticmethod
    def _ease(t: float) -> float:
        return t * t * (3.0 - 2.0 * t)

    @property
    def done(self) -> bool:
        return not self._playing


def update_animations(gc, dt: float):
    if not hasattr(gc, "animations") or not gc.animations:
        return
    for anim in gc.animations.values():
        anim.update(dt)


def get_anim_offset(gc, model_name: str) -> Vector3:
    if hasattr(gc, "animations") and model_name in gc.animations:
        return gc.animations[model_name].current
    return Vector3(0.0, 0.0, 0.0)


def add_shake(gc, model_name: str, offset=0.05, velocity=1.0):
    if not hasattr(gc, "animations"):
        gc.animations = {}
    gc.animations[model_name] = ShakeAnimation(offset, velocity)


def remove_animation(gc, model_name: str):
    if hasattr(gc, "animations") and model_name in gc.animations:
        del gc.animations[model_name]
