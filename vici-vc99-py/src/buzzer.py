import math
import os
import struct
import tempfile
import wave

try:
    import winsound
    _HAS_WINSOUND = True
except Exception:
    _HAS_WINSOUND = False


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _write_wav(path, frames, rate=44100):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def _generate_tone(path, freq, volume=0.5, rate=44100, ms=250):
    n = int(rate * ms / 1000)
    amp = int(32767 * _clamp(volume))
    frames = bytearray()
    two_pi_f = 2.0 * math.pi * freq
    for i in range(n):
        frames += struct.pack("<h", int(amp * math.sin(two_pi_f * i / rate)))
    _write_wav(path, frames, rate)


def _generate_pattern(path, freq, volume=0.5, beeps=1, beep_ms=60,
                      gap_ms=120, period_ms=1500, rate=44100):
    """Buduje WAV dlugosci period_ms z 'beeps' piknieciami (petla = powtarzanie)."""
    total = max(1, int(rate * period_ms / 1000))
    buf = bytearray(2 * total)
    amp = int(32767 * _clamp(volume))
    two_pi_f = 2.0 * math.pi * freq
    beep_n = max(1, int(rate * beep_ms / 1000))
    for b in range(max(1, beeps)):
        start = int(rate * (b * (beep_ms + gap_ms)) / 1000)
        for i in range(beep_n):
            idx = start + i
            if idx >= total:
                break
            struct.pack_into("<h", buf, 2 * idx, int(amp * math.sin(two_pi_f * i / rate)))
    _write_wav(path, buf, rate)


class Buzzer:
    """Odtwarza ton ciagly lub wzorzec pikniec (petla) dopoki aktywny."""

    def __init__(self):
        self._playing = False
        self._key = None
        self._path = None

    def _play(self, key, path, builder):
        if not _HAS_WINSOUND:
            return
        if self._playing and self._key == key:
            return
        self.stop()
        try:
            builder(path)
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
            self._playing = True
            self._key = key
            self._path = path
        except Exception:
            self._playing = False
            self._key = None

    def play_tone(self, freq, volume=0.5):
        key = ("tone", int(freq), round(volume, 2))
        path = os.path.join(
            tempfile.gettempdir(),
            f"vici_vc99_tone_{int(freq)}_{int(volume * 100)}.wav",
        )
        self._play(key, path, lambda p: _generate_tone(p, freq, volume))

    def play_pattern(self, freq, volume, beeps, beep_ms, gap_ms, period_ms):
        key = ("pat", int(freq), round(volume, 2), int(beeps),
               int(beep_ms), int(gap_ms), int(period_ms))
        path = os.path.join(
            tempfile.gettempdir(),
            "vici_vc99_pat_{}_{}_{}_{}_{}_{}.wav".format(
                int(freq), int(volume * 100), int(beeps),
                int(beep_ms), int(gap_ms), int(period_ms)),
        )
        self._play(
            key, path,
            lambda p: _generate_pattern(
                p, freq, volume, beeps, beep_ms, gap_ms, period_ms
            ),
        )

    def stop(self):
        if not _HAS_WINSOUND:
            return
        if self._playing:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            self._playing = False
            self._key = None
