import math
import random

import pyray as rl


class DustParticles:
    """Slow-drifting dust motes with a faux-bloom look.

    Each mote is a soft radial glow sprite drawn with additive blending, so
    overlapping motes accumulate into bright cores that read as bloom — no
    bright-pass/blur post-process needed (which keeps it WebGL1-friendly).

    Positions are stored in normalised [0, 1] screen space so the field is
    resolution-independent and survives window resizes; sizes are a fraction of
    the screen height. The system is drawn behind the 3D scene.
    """

    def __init__(self, glow_tex: rl.Texture2D, count: int = 90):
        self.tex = glow_tex
        self.t = 0.0
        self.particles = [self._spawn(initial=True) for _ in range(count)]

    def _spawn(self, initial: bool = False) -> dict:
        return {
            "x":     random.random(),
            # Fresh motes enter from just below the bottom edge and drift up.
            "y":     random.random() if initial else 1.05,
            "vx":    random.uniform(-0.010, 0.010),   # gentle lateral drift
            "vy":    random.uniform(-0.045, -0.012),  # slow rise (toward y=0)
            "size":  random.uniform(0.006, 0.024),    # fraction of screen height
            "base":  random.uniform(0.10, 0.45),      # peak alpha
            "tw_sp": random.uniform(0.5, 1.8),        # twinkle speed
            "sway":  random.uniform(0.0003, 0.0010),  # horizontal sway amount
            "phase": random.uniform(0.0, math.tau),
            "warm":  random.random() < 0.7,           # mostly warm, some cool
        }

    def update(self, dt: float):
        self.t += dt
        for q in self.particles:
            q["x"] += q["vx"] * dt + math.sin(self.t * 0.5 + q["phase"]) * q["sway"]
            q["y"] += q["vy"] * dt

            if q["y"] < -0.05:               # left the top → respawn at the bottom
                q.update(self._spawn())
            elif q["x"] < -0.05:             # wrap horizontally
                q["x"] = 1.05
            elif q["x"] > 1.05:
                q["x"] = -0.05

    def draw(self, vw: int, vh: int):
        tw, th = float(self.tex.width), float(self.tex.height)
        src = rl.Rectangle(0, 0, tw, th)

        rl.begin_blend_mode(rl.BLEND_ADDITIVE)
        for q in self.particles:
            # Twinkle: alpha breathes between ~0 and the mote's peak.
            a = q["base"] * (0.45 + 0.55 * math.sin(self.t * q["tw_sp"] + q["phase"]))
            if a <= 0.0:
                continue

            sz = q["size"] * vh
            px = q["x"] * vw - sz * 0.5
            py = q["y"] * vh - sz * 0.5
            alpha = int(max(0.0, min(1.0, a)) * 255)

            col = (rl.Color(255, 226, 180, alpha) if q["warm"]
                   else rl.Color(190, 205, 255, alpha))
            rl.draw_texture_pro(self.tex, src, rl.Rectangle(px, py, sz, sz),
                                rl.Vector2(0, 0), 0.0, col)
        rl.end_blend_mode()
