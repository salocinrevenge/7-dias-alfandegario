import math
import random

import pyray as rl


class AuraParticles:
    """A faint cloud of coloured motes orbiting and rising around an inspected
    object — used to hint at hidden properties (e.g. green = radioactive, purple
    = poisonous). Drawn as additive 3D billboards so it reads as a subtle glow
    clinging to the model rather than flat sprites.
    """

    def __init__(self, color, count: int = 5, radius: float = 0.06,
                 rise: float = 0.13):
        self.color  = color          # (r, g, b)
        self.radius = radius         # orbit radius around the object centre
        self.rise   = rise           # how far motes drift upward before respawning
        self.t = 0.0
        self.particles = [self._spawn(initial=True) for _ in range(count)]

    def _spawn(self, initial: bool = False) -> dict:
        return {
            "ang":   random.random() * math.tau,
            "rad":   self.radius * (0.30 + 0.70 * random.random()),
            "y":     (random.random() if initial else 0.0) * self.rise,
            "vy":    -1 * random.uniform(0.2, 0.3),       # rise speed (× rise)
            "orbit": random.uniform(-0.7, 0.7),      # angular drift (rad/s)
            "size":  random.uniform(0.012, 0.020),   # billboard size (world units)
            "life":  random.random() if initial else 0.0,
            "lifespeed": random.uniform(0.45, 1.05),
        }

    def update(self, dt: float):
        self.t += dt
        for q in self.particles:
            q["life"] += q["lifespeed"] * dt
            if q["life"] >= 1.0:
                q.update(self._spawn())
            q["ang"] += q["orbit"] * dt
            q["y"]   += q["vy"] * self.rise * dt

    def draw(self, center, glow_tex, cam):
        r, g, b = self.color
        base_y = center.y - self.radius          # start a touch below the centre
        rl.begin_blend_mode(rl.BLEND_ADDITIVE)
        for q in self.particles:
            fade = math.sin(q["life"] * math.pi)  # 0 at birth/death, 1 mid-life
            if fade <= 0.0:
                continue
            alpha = int(fade * 80)                # deliberately faint
            x = center.x + math.cos(q["ang"]) * q["rad"]
            z = center.z + math.sin(q["ang"]) * q["rad"]
            pos = rl.Vector3(x, base_y + q["y"], z)
            sz  = q["size"] * (0.2 + 0.3 * fade)
            rl.draw_billboard(cam, glow_tex, pos, sz, rl.Color(r, g, b, alpha))
        rl.end_blend_mode()


class RadiationParticles:
    """Motes that shoot outward from an object's centre in all directions and
    fade as they travel — a subtle radiating burst. Same draw/update interface
    as AuraParticles. Rendered as additive 3D billboards.
    """

    def __init__(self, color, count: int = 3, reach: float = 0.40):
        self.color = color           # (r, g, b)
        self.reach = reach           # max distance travelled from the centre
        self.particles = [self._spawn(initial=True) for _ in range(count)]

    def _spawn(self, initial: bool = False) -> dict:
        # Uniformly random direction on the unit sphere.
        t = random.random() * math.tau
        y = random.uniform(-1.0, 1.0)
        r = math.sqrt(max(0.0, 1.0 - y * y))
        return {
            "dx": r * math.cos(t),
            "dy": y,
            "dz": r * math.sin(t),
            "life":      random.random() if initial else 0.0,
            "lifespeed": random.uniform(0.6, 1.3),     # how fast it flies out
            "size":      random.uniform(0.010, 0.014),
        }

    def update(self, dt: float):
        for q in self.particles:
            q["life"] += q["lifespeed"] * dt
            if q["life"] >= 1.0:
                q.update(self._spawn())

    def draw(self, center, glow_tex, cam):
        r, g, b = self.color
        rl.begin_blend_mode(rl.BLEND_ADDITIVE)
        for q in self.particles:
            life = q["life"]
            # Quick fade-in near the centre, then fade out as it travels.
            fade = (1.0 - life) * min(1.0, life * 6.0)
            if fade <= 0.0:
                continue
            dist  = life * self.reach
            pos   = rl.Vector3(center.x + q["dx"] * dist,
                               center.y + q["dy"] * dist,
                               center.z + q["dz"] * dist)
            alpha = int(fade * 90)
            sz    = q["size"] * (0.3 + 0.5 * fade)
            rl.draw_billboard(cam, glow_tex, pos, sz, rl.Color(r, g, b, alpha))
        rl.end_blend_mode()


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
