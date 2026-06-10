"""
Stap 3: Impact-detectie via frame-differencing.

We houden een lopend achtergrondmodel bij van de (statische) plaat met
projectie. Wanneer een bal de plaat raakt, verschijnt er kort een grote
verandering. We pakken het zwaartepunt van die verandering als impactpunt.

Een cooldown voorkomt dat dezelfde impact meerdere frames achter elkaar
als nieuwe treffer telt.
"""
import cv2
import numpy as np
import config


class ImpactDetector:
    def __init__(self):
        self.bg = None              # float32 achtergrondmodel
        self.cooldown = 0

    def reset_background(self, frame_gray):
        self.bg = frame_gray.astype(np.float32)

    def process(self, frame_bgr):
        """Geeft (cx, cy) van een nieuwe impact terug, of None."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.bg is None:
            self.reset_background(gray)
            return None

        # Verschil t.o.v. achtergrond.
        diff = cv2.absdiff(gray, self.bg.astype(np.uint8))
        _, thresh = cv2.threshold(diff, config.DIFF_THRESHOLD, 255,
                                  cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        impact = None
        if self.cooldown > 0:
            self.cooldown -= 1
        else:
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best = None
            best_area = 0
            for c in contours:
                area = cv2.contourArea(c)
                if config.MIN_BLOB_AREA <= area <= config.MAX_BLOB_AREA:
                    if area > best_area:
                        best_area = area
                        best = c
            if best is not None:
                M = cv2.moments(best)
                if M["m00"] > 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                    impact = (cx, cy)
                    self.cooldown = config.IMPACT_COOLDOWN_FRAMES

        # Achtergrond langzaam laten meelopen (lichtveranderingen e.d.),
        # maar niet tijdens een actieve impact.
        if impact is None:
            cv2.accumulateWeighted(gray, self.bg, config.BG_LEARNING_RATE)

        return impact
