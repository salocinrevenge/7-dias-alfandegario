"""
Dynamic audio effects that respond to game state.

Music modulation (pitch/volume/pan) reacts in real time to:
- Item properties (VENENOSO = wobble, RADIOATIVO = jitter, MIMICO = warble)
- Active curses (nausea, inversion, keyhole)
- Time pressure (rising pitch as the timer runs low)

Procedural one-shot SFX are generated at init for accept/reject/error/explosion.
"""
import math
import struct
import pyray as rl
from state import State


def _make_wav_bytes(samples: list[int], sample_rate: int = 22050) -> bytes:
    """Pack signed 16-bit mono PCM into a minimal WAV in memory."""
    num_frames = len(samples)
    data = bytearray()
    for s in samples:
        data.extend(struct.pack('<h', max(-32767, min(32767, int(s)))))

    header = bytearray()
    header.extend(b'RIFF')
    header.extend(struct.pack('<I', 36 + len(data)))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend(struct.pack('<I', 16))           # chunk size
    header.extend(struct.pack('<H', 1))            # PCM
    header.extend(struct.pack('<H', 1))            # mono
    header.extend(struct.pack('<I', sample_rate))
    header.extend(struct.pack('<I', sample_rate * 2))
    header.extend(struct.pack('<H', 2))
    header.extend(struct.pack('<H', 16))
    header.extend(b'data')
    header.extend(struct.pack('<I', len(data)))
    return bytes(header) + bytes(data)


def _gen_error_buzz() -> bytes:
    """Short dissonant buzz — descending saw-ish tone."""
    sr = 22050
    dur = 0.22
    n = int(sr * dur)
    samples = []
    for i in range(n):
        t = i / sr
        env = max(0.0, 1.0 - t / dur)
        freq = 180 - 60 * (t / dur)
        phase = (freq * t) % 1.0
        val = 32767 * env * 0.45 * (phase * 2.0 - 1.0)
        samples.append(val)
    return _make_wav_bytes(samples, sr)


def _gen_accept_chime() -> bytes:
    """Two ascending sine tones — pleasant confirmation."""
    sr = 22050
    tone_ms = 110
    n_tone = int(sr * tone_ms / 1000)
    gap = int(sr * 0.025)
    samples = []
    for i in range(n_tone):
        t = i / sr
        env = 1.0 - (i / n_tone)
        samples.append(32767 * env * 0.35 * math.sin(2 * math.pi * 523 * t))
    for _ in range(gap):
        samples.append(0)
    for i in range(n_tone):
        t = i / sr
        env = 1.0 - (i / n_tone)
        samples.append(32767 * env * 0.35 * math.sin(2 * math.pi * 659 * t))
    return _make_wav_bytes(samples, sr)


def _gen_reject_thud() -> bytes:
    """Low thump — brief decaying sine."""
    sr = 22050
    dur = 0.16
    n = int(sr * dur)
    samples = []
    for i in range(n):
        t = i / sr
        env = max(0.0, 1.0 - t / dur) ** 2.5
        samples.append(32767 * env * 0.4 * math.sin(2 * math.pi * 70 * t))
    return _make_wav_bytes(samples, sr)


def _gen_explosion_rumble() -> bytes:
    """Noise burst with decaying low-frequency energy — explosion feel."""
    sr = 22050
    dur = 0.6
    n = int(sr * dur)
    samples = []
    # Simple pseudo-random noise modulated by a low-frequency envelope
    seed = 0x5EED
    for i in range(n):
        t = i / sr
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed / 0x7FFFFFFF) * 2.0 - 1.0
        # Low-pass via running average
        env = max(0.0, 1.0 - t / dur) ** 1.5
        rumble = math.sin(2 * math.pi * 55 * t) * 0.3 + noise * 0.7
        samples.append(32767 * env * 0.55 * rumble)
    return _make_wav_bytes(samples, sr)


def _gen_tick() -> bytes:
    """Very short click — time-pressure heartbeat."""
    sr = 22050
    dur = 0.025
    n = int(sr * dur)
    samples = []
    for i in range(n):
        t = i / sr
        env = max(0.0, 1.0 - t / dur) ** 4
        samples.append(32767 * env * 0.25 * math.sin(2 * math.pi * 800 * t))
    return _make_wav_bytes(samples, sr)


def _gen_eat_munch() -> bytes:
    """Quick crunchy bite sound."""
    sr = 22050
    dur = 0.18
    n = int(sr * dur)
    samples = []
    seed = 0xBEEF
    for i in range(n):
        t = i / sr
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed / 0x7FFFFFFF) * 2.0 - 1.0
        env = max(0.0, 1.0 - t / dur) ** 1.8
        crunch = noise * env * 0.35
        tone = math.sin(2 * math.pi * 300 * t) * env * 0.15
        samples.append(32767 * (crunch + tone))
    return _make_wav_bytes(samples, sr)


def _gen_stomach_growl() -> bytes:
    """Low rumbling stomach sound — 1.2 seconds."""
    sr = 22050
    dur = 1.2
    n = int(sr * dur)
    samples = []
    seed = 0xFEED
    for i in range(n):
        t = i / sr
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed / 0x7FFFFFFF) * 2.0 - 1.0
        # Pulsing low rumble
        pulse = 0.5 + 0.5 * math.sin(t * 3.7) * math.sin(t * 1.3)
        env = pulse * max(0.0, 1.0 - t / dur)
        rumble = math.sin(2 * math.pi * (45 + 20 * math.sin(t * 2.1)) * t)
        samples.append(32767 * env * 0.22 * (rumble * 0.7 + noise * 0.3))
    return _make_wav_bytes(samples, sr)


class AudioEffects:
    """Per-frame audio processing reacting to game context state."""

    def __init__(self, gc):
        self.gc = gc
        self.time = 0.0
        self._pitch_smooth = 1.0
        self._volume_smooth = 1.0
        self._pan_smooth = 0.5

        # Cooldown timers for one-shot SFX
        self._last_tick_time = -999.0
        self._tick_phase = 0  # 0=low, 1=high — alternating beats
        self._last_growl_time = -999.0

        self.sfx: dict[str, rl.Sound | None] = {}
        self._load_sfx()

    def _load_sfx(self):
        """Generate procedural SFX and store them."""
        sfx_map = {
            "error":     _gen_error_buzz,
            "accept":    _gen_accept_chime,
            "reject":    _gen_reject_thud,
            "explosion": _gen_explosion_rumble,
            "tick":      _gen_tick,
            "eat":       _gen_eat_munch,
            "growl":     _gen_stomach_growl,
        }
        for key, gen in sfx_map.items():
            try:
                wav = gen()
                wave = rl.load_wave_from_memory(b".wav", wav, len(wav))
                self.sfx[key] = rl.load_sound_from_wave(wave)
                rl.unload_wave(wave)
            except Exception:
                self.sfx[key] = None

    def unload(self):
        for snd in self.sfx.values():
            if snd is not None:
                try:
                    rl.unload_sound(snd)
                except Exception:
                    pass
        self.sfx.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, name: str):
        """Fire a one-shot SFX by key ('error', 'accept', 'reject', 'explosion')."""
        snd = self.sfx.get(name)
        if snd is not None:
            try:
                rl.play_sound(snd)
            except Exception:
                pass

    def update(self, dt: float):
        """Call once per frame. Modulates the active music stream and fires
        time-pressure ticks and hunger growls."""
        self.time += dt
        self._apply_music_modulation(dt)
        self._maybe_tick(dt)
        self._maybe_growl(dt)

    # ------------------------------------------------------------------
    # Music modulation
    # ------------------------------------------------------------------

    def _apply_music_modulation(self, dt: float):
        stream = self.gc.current_music_stream
        if stream is None:
            return

        pitch = 1.0
        volume = 1.0
        pan = 0.5

        state = self.gc.current_state

        if state in (State.INSPECT, State.PAUSE, State.INTRO):
            pitch, volume, pan = self._item_effects(pitch, volume, pan)

        pitch, volume, pan = self._curse_effects(pitch, volume, pan)
        pitch, volume = self._time_pressure(pitch, volume)
        pitch, volume = self._hunger_modulation(pitch, volume)

        pitch = max(0.2, min(2.5, pitch))
        volume = max(0.0, min(1.0, volume))
        pan = max(0.0, min(1.0, pan))

        smooth = min(1.0, 5.0 * dt)
        self._pitch_smooth += (pitch - self._pitch_smooth) * smooth
        self._volume_smooth += (volume - self._volume_smooth) * smooth
        self._pan_smooth += (pan - self._pan_smooth) * smooth

        try:
            rl.set_music_pitch(stream, self._pitch_smooth)
            rl.set_music_volume(stream, self._volume_smooth)
            rl.set_music_pan(stream, self._pan_smooth)
        except Exception:
            pass

    def _item_effects(self, pitch, volume, pan):
        item = self._current_item()
        if item is None:
            return pitch, volume, pan

        t = self.time

        # Venenoso (poison) — sick wobble, slightly muted
        if item.atributos.get("VENENOSO"):
            wobble = 0.07 * math.sin(t * 1.8 + 0.5) + 0.03 * math.sin(t * 3.1)
            pitch += wobble
            volume *= 0.82
            pan += 0.08 * math.sin(t * 1.2)

        # Radioativo — fast jitter / crackle
        if item.atributos.get("RADIOATIVO"):
            jitter = 0.025 * math.sin(t * 14.7) + 0.015 * math.sin(t * 21.3)
            pitch += jitter
            volume *= 0.92 + 0.06 * math.sin(t * 11.0)  # slight flutter

        # Mimico — uneasy subtle warble
        if item.atributos.get("MIMICO"):
            warble = 0.04 * math.sin(t * 0.7) * math.sin(t * 4.5)
            pitch += warble
            volume *= 0.88

        # Amaldicoado — deep, dark pitch drop
        if item.atributos.get("AMALDICOADO"):
            pitch -= 0.06
            volume *= 0.90

        return pitch, volume, pan

    def _curse_effects(self, pitch, volume, pan):
        t = self.time
        gc = self.gc

        # Nausea curse — deep, slow pitch wobble (matches visual distortion)
        if getattr(gc, "nausea_curse_active", False):
            wobble = 0.18 * math.sin(t * 1.1) + 0.07 * math.sin(t * 2.7)
            pitch += wobble
            volume *= 0.70

        # Inversion curse — everything sounds flipped/underwater
        if getattr(gc, "inversion_curse_active", False):
            pitch -= 0.35
            volume *= 0.78
            pan = 1.0 - pan  # mirrored stereo

        # Keyhole curse — claustrophobic muffled sound
        if getattr(gc, "keyhole_curse_active", False):
            pitch -= 0.20
            volume *= 0.55

        return pitch, volume, pan

    def _time_pressure(self, pitch, volume):
        gc = self.gc
        time_left = gc.item_time_left
        time_max = gc.item_time_max
        if time_max <= 0 or time_left <= 0:
            return pitch, volume

        ratio = time_left / time_max

        if ratio < 0.30:
            urgency = (0.30 - ratio) / 0.30
            pitch += urgency * 0.10
            # Subtle volume pulse like a racing heartbeat when very low
            if ratio < 0.15:
                pulse = 1.0 + 0.06 * math.sin(self.time * 4.5) ** 2
                volume *= pulse

        return pitch, volume

    def _hunger_modulation(self, pitch, volume):
        """Lower pitch and volume when starving."""
        gc = self.gc
        if gc.hunger_max <= 0:
            return pitch, volume
        ratio = gc.hunger / gc.hunger_max
        if ratio >= 0.30:
            return pitch, volume
        hunger_factor = (0.30 - ratio) / 0.30
        pitch -= hunger_factor * 0.12
        volume *= 1.0 - hunger_factor * 0.25
        return pitch, volume

    # ------------------------------------------------------------------
    # Time-pressure tick
    # ------------------------------------------------------------------

    def _maybe_tick(self, dt: float):
        """Emit a soft ticking sound as time runs critically low."""
        gc = self.gc
        if gc.current_state != State.INSPECT:
            return
        time_left = gc.item_time_left
        time_max = gc.item_time_max
        if time_max <= 0 or time_left > time_max * 0.20 or time_left <= 0:
            return

        interval = 0.45 if time_left > time_max * 0.10 else 0.22
        if self.time - self._last_tick_time >= interval:
            self._last_tick_time = self.time
            self._tick_phase = 1 - self._tick_phase
            snd = self.sfx.get("tick")
            if snd is not None:
                try:
                    # Alternate pitch for a heartbeat feel
                    rl.set_sound_pitch(snd, 0.9 if self._tick_phase else 1.1)
                    rl.play_sound(snd)
                except Exception:
                    pass


    # ------------------------------------------------------------------
    # Hunger growl
    # ------------------------------------------------------------------

    def _maybe_growl(self, dt: float):
        """Emit stomach growls when hunger is low."""
        gc = self.gc
        if gc.current_state != State.INSPECT:
            return
        hunger = gc.hunger
        hunger_max = gc.hunger_max
        if hunger_max <= 0:
            return

        ratio = hunger / hunger_max
        if ratio > 0.35:
            return

        # Faster growls as hunger drops
        if ratio > 0.20:
            interval = 8.0 + (0.35 - ratio) * 30
        elif ratio > 0.08:
            interval = 5.0
        else:
            interval = 3.0

        if self.time - self._last_growl_time >= interval:
            self._last_growl_time = self.time
            snd = self.sfx.get("growl")
            if snd is not None:
                try:
                    rl.set_sound_volume(snd, 0.4 + 0.6 * (1.0 - ratio))
                    rl.play_sound(snd)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_item(self):
        items = self.gc.itens_hoje.get("to evaluate", [])
        if not items:
            return None
        return items[0]
