"""
Hoofdapplicatie v3: slagzone + doelwit-training via de telefoon.

Naast de detectielus draait een webserver (webserver.py). Op een telefoon
in hetzelfde netwerk open je http://<pi-ip>:8080, tikt een plek aan, en de
beamer projecteert daar een bullseye. Elke inslag wordt beoordeeld:
binnen TARGET_RADIUS van het doelwit = RAAK (groen), anders MIS (geel),
en zonder doelwit gewoon strike/ball zoals voorheen.

VEREIST: homography.npz (en bij voorkeur lens_calib.npz).
         Flask:  sudo apt install -y python3-flask

GEBRUIK:
  python3 main.py
  Toetsen:  r = achtergrond resetten   c = treffers wissen   q = stop
"""
import math
import os
import socket
import time
import cv2
import numpy as np
import config
from camera import Camera
from lens import LensCorrector
from detector import ImpactDetector, build_roi_mask
from shared import STATE
import webserver


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "ip-van-de-pi"


def draw_zone(canvas):
    x, y, w, h = config.ZONE_X, config.ZONE_Y, config.ZONE_W, config.ZONE_H
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 220, 0), 4)
    for i in (1, 2):
        cv2.line(canvas, (x + w * i // 3, y), (x + w * i // 3, y + h),
                 (0, 120, 0), 1)
        cv2.line(canvas, (x, y + h * i // 3), (x + w, y + h * i // 3),
                 (0, 120, 0), 1)
    cv2.putText(canvas, "SLAGZONE", (x, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2)


def draw_target(canvas, target):
    """Bullseye op de doelplek."""
    if target is None:
        return
    tx, ty = int(target[0]), int(target[1])
    r = config.TARGET_RADIUS
    cv2.circle(canvas, (tx, ty), r, (0, 200, 255), 3)            # buitenring
    cv2.circle(canvas, (tx, ty), int(r * 0.55), (0, 200, 255), 2)
    cv2.circle(canvas, (tx, ty), int(r * 0.18), (0, 200, 255), -1)  # roos


def in_zone(bx, by):
    return (config.ZONE_X <= bx <= config.ZONE_X + config.ZONE_W and
            config.ZONE_Y <= by <= config.ZONE_Y + config.ZONE_H)


def map_point(H, cx, cy):
    pt = np.array([[[cx, cy]]], dtype=np.float32)
    out = cv2.perspectiveTransform(pt, H)
    return float(out[0, 0, 0]), float(out[0, 0, 1])


def render(hits, strikes, balls, target, hit_count, miss_count):
    canvas = np.zeros((config.PROJECTOR_HEIGHT, config.PROJECTOR_WIDTH, 3),
                      np.uint8)
    draw_zone(canvas)
    draw_target(canvas, target)
    for idx, (bx, by, strike, was_hit, _) in enumerate(hits[-20:]):
        if was_hit is True:
            color = (0, 220, 0)        # raak: groen
        elif was_hit is False:
            color = (0, 200, 255)      # mis (wel doelwit): geel/oranje
        else:
            color = (0, 0, 255) if strike else (0, 180, 255)
        cv2.circle(canvas, (int(bx), int(by)), 14, color, -1)
        cv2.circle(canvas, (int(bx), int(by)), 14, (255, 255, 255), 2)
    # De LAATSTE inslag extra markeren: grote ring + kruisdraad, zodat de
    # pitcher vanaf de werpplek direct ziet waar de impact zat.
    if hits:
        bx, by, strike, was_hit, _ = hits[-1]
        bx, by = int(bx), int(by)
        c = ((0, 220, 0) if was_hit is True else
             (0, 200, 255) if was_hit is False else
             (0, 0, 255) if strike else (0, 180, 255))
        cv2.circle(canvas, (bx, by), 34, (255, 255, 255), 3)
        cv2.circle(canvas, (bx, by), 34, c, 1)
        cv2.line(canvas, (bx - 52, by), (bx - 22, by), (255, 255, 255), 2)
        cv2.line(canvas, (bx + 22, by), (bx + 52, by), (255, 255, 255), 2)
        cv2.line(canvas, (bx, by - 52), (bx, by - 22), (255, 255, 255), 2)
        cv2.line(canvas, (bx, by + 22), (bx, by + 52), (255, 255, 255), 2)
    label = (f"RAAK: {hit_count}   MIS: {miss_count}" if target is not None
             or hit_count or miss_count
             else f"STRIKES: {strikes}   BALLS: {balls}")
    cv2.putText(canvas, label,
                (config.ZONE_X, config.ZONE_Y + config.ZONE_H + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    return canvas


def main():
    if not os.path.exists(config.HOMOGRAPHY_FILE):
        raise SystemExit("Geen homography.npz. Run eerst calibrate_homography.py")
    H = np.load(config.HOMOGRAPHY_FILE)["H"]

    cam = Camera(gray=True)   # Y-vlak direct: geen kleurconversie per frame
    lens = LensCorrector()
    roi = build_roi_mask(H, config.CAM_WIDTH, config.CAM_HEIGHT)
    detector = ImpactDetector(roi_mask=roi)

    webserver.start_in_background()
    print(f"Telefoon: open http://{get_ip()}:{config.WEB_PORT} "
          f"(zelfde wifi als de Pi)")

    cv2.namedWindow("Beamer", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Beamer", cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN)

    hits = []          # (bx, by, strike, was_hit, t)
    strikes = balls = 0
    hit_count = miss_count = 0
    target = None

    def redraw():
        cv2.imshow("Beamer", render(hits, strikes, balls, target,
                                    hit_count, miss_count))
        detector.suppress_frames()

    redraw()
    cv2.waitKey(300)
    print("Achtergrond leren, houd de plaat 2 seconden vrij...")
    for _ in range(int(config.CAM_FPS * 2)):
        ok, frame = cam.read()
        if ok:
            detector.process(lens.correct(frame))
        cv2.waitKey(1)
    print("Klaar. r = reset achtergrond | c = wissen | q = stop")

    try:
        while True:
            # Wijzigingen vanaf de telefoon (nieuw doelwit, reset)?
            if STATE.consume_dirty():
                target = STATE.get_target()
                redraw()

            ok, frame = cam.read()
            if not ok:
                continue
            frame = lens.correct(frame)

            impact = detector.process(frame)
            if impact is not None:
                bx, by = map_point(H, impact[0], impact[1])
                strike = in_zone(bx, by)
                was_hit = None
                dist = None
                if target is not None:
                    dist = math.hypot(bx - target[0], by - target[1])
                    was_hit = dist <= config.TARGET_RADIUS
                    if was_hit:
                        hit_count += 1
                    else:
                        miss_count += 1
                if strike:
                    strikes += 1
                else:
                    balls += 1
                hits.append((bx, by, strike, was_hit, time.time()))
                STATE.add_result(bx, by, strike, was_hit, dist)
                msg = ("RAAK" if was_hit is True else
                       "MIS" if was_hit is False else
                       ("STRIKE" if strike else "BALL"))
                print(f"Impact -> beamer ({bx:.0f},{by:.0f}) {msg}")
                redraw()

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                detector.reset_background()
                print("Achtergrond gereset.")
            elif key == ord('c'):
                hits.clear()
                strikes = balls = hit_count = miss_count = 0
                STATE.reset_results()
                redraw()
                print("Treffers gewist.")
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
