"""
Gedeelde, thread-veilige state tussen de Flask-webserver (telefoon) en de
detectielus (main.py).

De telefoon zet een doelwit (genormaliseerd binnen de slagzone, 0..1).
De detectielus leest dat, projecteert het, en schrijft worpresultaten terug.
"""
import threading
import time
import config


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._target = None        # (bx, by) in beamer-pixels, of None
        self._dirty = False        # projectie moet opnieuw getekend worden
        self._results = []         # dicts per worp
        self._hits = 0
        self._misses = 0

    # ----- doelwit (vanaf telefoon) -----

    def set_target_normalized(self, nx, ny):
        """nx, ny in 0..1 binnen de slagzone."""
        nx = min(max(nx, 0.0), 1.0)
        ny = min(max(ny, 0.0), 1.0)
        bx = config.ZONE_X + nx * config.ZONE_W
        by = config.ZONE_Y + ny * config.ZONE_H
        with self._lock:
            self._target = (bx, by)
            self._dirty = True

    def clear_target(self):
        with self._lock:
            self._target = None
            self._dirty = True

    def get_target(self):
        with self._lock:
            return self._target

    # ----- projectie-synchronisatie (detectielus) -----

    def consume_dirty(self):
        """True als de projectie opnieuw getekend moet worden (en reset)."""
        with self._lock:
            d = self._dirty
            self._dirty = False
            return d

    # ----- resultaten (detectielus schrijft, telefoon leest) -----

    def add_result(self, bx, by, strike, hit, dist_px):
        nx = (bx - config.ZONE_X) / config.ZONE_W
        ny = (by - config.ZONE_Y) / config.ZONE_H
        with self._lock:
            self._results.append({
                "t": time.time(),
                "nx": round(nx, 4), "ny": round(ny, 4),
                "strike": bool(strike),
                "hit": hit,                      # True/False/None (geen doel)
                "dist_pct": (round(100.0 * dist_px / config.ZONE_W, 1)
                             if dist_px is not None else None),
            })
            self._results = self._results[-50:]
            if hit is True:
                self._hits += 1
            elif hit is False:
                self._misses += 1

    def reset_results(self):
        with self._lock:
            self._results.clear()
            self._hits = 0
            self._misses = 0
            self._dirty = True

    def snapshot(self):
        with self._lock:
            target_norm = None
            if self._target is not None:
                target_norm = {
                    "nx": (self._target[0] - config.ZONE_X) / config.ZONE_W,
                    "ny": (self._target[1] - config.ZONE_Y) / config.ZONE_H,
                }
            return {
                "target": target_norm,
                "results": list(self._results[-10:]),
                "hits": self._hits,
                "misses": self._misses,
            }


STATE = SharedState()
