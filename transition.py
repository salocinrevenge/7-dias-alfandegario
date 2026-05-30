import pyray as rl

# ---------------------------------------------------------------------------
# TRANSITION MANAGER
# ---------------------------------------------------------------------------
class Transition:
    SPEED = 2.5

    def __init__(self):
        self.active       = False
        self.alpha        = 0.0
        self._fading_out  = True
        self.target_state = None
        self.done         = False

    def start(self, target_state: str):
        if self.active:
            return
        self.active       = True
        self.alpha        = 0.0
        self._fading_out  = True
        self.target_state = target_state
        self.done         = False

    def update(self, dt: float) -> str | None:
        self.done = False
        if not self.active:
            return None
        if self._fading_out:
            self.alpha += self.SPEED * dt
            if self.alpha >= 1.0:
                self.alpha       = 1.0
                self._fading_out = False
                return self.target_state
        else:
            self.alpha -= self.SPEED * dt
            if self.alpha <= 0.0:
                self.alpha  = 0.0
                self.active = False
                self.done   = True
        return None

    def draw(self):
        if not self.active and self.alpha == 0.0:
            return
        a = int(self.alpha * 255)
        rl.draw_rectangle(0, 0, rl.get_screen_width(), rl.get_screen_height(),
                          rl.Color(0, 0, 0, a))
