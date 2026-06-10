"""
Stap 4: Hoofdapplicatie.

Projecteert de slagzone, detecteert impacts via de camera, mapt die naar
beamer-coordinaten via de homografie, en tekent het raakpunt terug op de
projectie met een strike/ball-oordeel.

VEREIST: lens_calib.npz (optioneel maar aanbevolen) en homography.npz.

GEBRUIK:
  python main.py
  Toetsen:  r = achtergrond resetten   c = treffers wissen   q = stop
"""
import os
import time
import cv2
import numpy as np
import config
from camera import Camera
from lens import LensCorrector
from detector import ImpactDetector


def draw_zone(canvas):
    """Tekent de slagzone-rechthoek op het beamer-canvas."""
    x, y, w, h = config.ZONE_X, config.ZONE_Y, config.ZONE_W, config.ZONE_H
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 220, 0), 4)
    # Hulplijnen (derden), puur visueel.
    for i in (1, 2):
        cv2.line(canvas, (x + w * i // 3, y), (x + w * i // 3, y + h),
                 (0, 120, 0), 1)
        cv2.line(canvas, (x, y + h * i // 3), (x + w, y + h * i // 3),
                 (0, 120, 0), 1)
    cv2.putText(canvas, "SLAGZONE", (x, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2)


def in_zone(bx, by):
    return (config.ZONE_X <= bx <= config.ZONE_X + config.ZONE_W and
            config.ZONE_Y <= by <= config.ZONE_Y + config.ZONE_H)


def map_point(H, cx, cy):
    """Camera-pixel -> beamer-pixel via homografie."""
    pt = np.array([[[cx, cy]]], dtype=np.float32)
    out = cv2.perspectiveTransform(pt, H)
    return float(out[0, 0, 0]), float(out[0, 0, 1])


def main():
    if not os.path.exists(config.HOMOGRAPHY_FILE):
        raise SystemExit("Geen homography.npz. Run eerst calibrate_homography.py")
    data = np.load(config.HOMOGRAPHY_FILE)
    H = data["H"]

    cam = Camera()
    lens = LensCorrector()
    detector = ImpactDetector()

    cv2.namedWindow("Beamer", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Beamer", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    hits = []  # lijst van (bx, by, is_strike, timestamp)
    strikes = 0
    balls = 0

    print("r = achtergrond resetten | c = treffers wissen | q = stop")
    try:
        # Eerste frames: achtergrond leren.
        for _ in range(int(config.CAM_FPS)):
            ok, frame = cam.read()
            if ok:
                detector.process(lens.correct(frame))

        while True:
            ok, frame = cam.read()
            if not ok:
                continue
            frame = lens.correct(frame)

            impact = detector.process(frame)
            if impact is not None:
                bx, by = map_point(H, impact[0], impact[1])
                strike = in_zone(bx, by)
                hits.append((bx, by, strike, time.time()))
                if strike:
                    strikes += 1
                else:
                    balls += 1
                print(f"Impact -> beamer ({bx:.0f},{by:.0f}) "
                      f"{'STRIKE' if strike else 'BALL'}")

            # Beamer-canvas opbouwen.
            canvas = np.zeros((config.PROJECTOR_HEIGHT, config.PROJECTOR_WIDTH, 3),
                              np.uint8)
            draw_zone(canvas)
            for (bx, by, strike, _) in hits[-20:]:
                color = (0, 0, 255) if strike else (0, 180, 255)
                cv2.circle(canvas, (int(bx), int(by)), 14, color, -1)
                cv2.circle(canvas, (int(bx), int(by)), 14, (255, 255, 255), 2)
            cv2.putText(canvas, f"STRIKES: {strikes}   BALLS: {balls}",
                        (config.ZONE_X, config.ZONE_Y + config.ZONE_H + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.imshow("Beamer", canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                detector.bg = None
                print("Achtergrond gereset.")
            elif key == ord('c'):
                hits.clear()
                strikes = balls = 0
                print("Treffers gewist.")
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
