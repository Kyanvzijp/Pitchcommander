"""
Debugviewer: zie live hoe de bal gevolgd wordt en waar de impact valt.

Twee vensters:
- "Beamer"   : fullscreen op de beamer. Zwart met alleen de zone en
               blijvende impactstippen. Geen live video of baan, want elke
               beamerwijziging onderdrukt de detectie kort; de beamer
               verandert dus alleen op het moment van een impact.
- "Tracking" : het volledige camerabeeld, opgeschaald naar 960x720, met
               de actieve baan (geel), de laatst afgesloten baan (oranje),
               gedetecteerde blobs (cyaan), de slagzone teruggerekend naar
               cameracoordinaten (groen), de ROI (blauw) en blijvende
               impactpunten (rood kruis). Plus een HUD met live waarden.

LET OP bij een gespiegeld scherm (remote desktop = beameruitgang): het
Tracking-venster wordt dan mee geprojecteerd op de plaat en de camera ziet
dat terug. Verberg het venster tijdens worpen met 'v', of gebruik de
opname ('o') en kijk de worp daarna terug.

Toetsen:
  1 / 2  detectiedrempel omlaag / omhoog       (DIFF_THRESHOLD)
  3 / 4  minimum aanvliegsnelheid omlaag/omhoog (MIN_INCOMING_SPEED)
  o      opname starten/stoppen (annotated video naar .avi)
  v      Tracking-venster verbergen/tonen
  i      impactstippen wissen
  r      achtergrond resetten
  q      stoppen
"""
import math
import os
import time
import cv2
import numpy as np
import config
from camera import Camera
from lens import LensCorrector
from detector import ImpactDetector, build_roi_mask

VIEW_W, VIEW_H = 960, 720          # opgeschaalde weergave (1.5x van 640x480)
SCALE = VIEW_W / config.CAM_WIDTH

KLEUR_BAAN = (0, 220, 255)         # geel: actieve baan
KLEUR_VORIGE = (0, 140, 255)       # oranje: laatst afgesloten baan
KLEUR_BLOB = (255, 220, 0)         # cyaan: blob dit frame
KLEUR_ZONE = (0, 220, 0)
KLEUR_ROI = (200, 120, 0)
KLEUR_IMPACT = (0, 0, 255)


def zone_outline_cam(H):
    """Slagzone-hoekpunten teruggerekend naar cameracoordinaten."""
    pts = np.array([
        [config.ZONE_X, config.ZONE_Y],
        [config.ZONE_X + config.ZONE_W, config.ZONE_Y],
        [config.ZONE_X + config.ZONE_W, config.ZONE_Y + config.ZONE_H],
        [config.ZONE_X, config.ZONE_Y + config.ZONE_H],
    ], dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, np.linalg.inv(H)).reshape(-1, 2)


def roi_outline_cam(H):
    m = config.ROI_MARGIN_PX
    pts = np.array([
        [config.ZONE_X - m, config.ZONE_Y - m],
        [config.ZONE_X + config.ZONE_W + m, config.ZONE_Y - m],
        [config.ZONE_X + config.ZONE_W + m, config.ZONE_Y + config.ZONE_H + m],
        [config.ZONE_X - m, config.ZONE_Y + config.ZONE_H + m],
    ], dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, np.linalg.inv(H)).reshape(-1, 2)


def _sc(p):
    """Camerapunt naar weergavecoordinaten."""
    return (int(p[0] * SCALE), int(p[1] * SCALE))


def build_tracking_frame(gray, detector, zone_pts, roi_pts,
                         impacts_cam, fps, recording):
    """Bouwt het geannoteerde Tracking-beeld (VIEW_W x VIEW_H, BGR)."""
    frame = cv2.resize(gray, (VIEW_W, VIEW_H),
                       interpolation=cv2.INTER_NEAREST)
    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    # ROI en zone.
    cv2.polylines(frame, [np.array([_sc(p) for p in roi_pts])],
                  True, KLEUR_ROI, 1)
    cv2.polylines(frame, [np.array([_sc(p) for p in zone_pts])],
                  True, KLEUR_ZONE, 2)

    # Laatst afgesloten baan (oranje) en actieve baan (geel).
    for pts, kleur in ((detector.last_track, KLEUR_VORIGE),
                       (detector.track, KLEUR_BAAN)):
        if len(pts) >= 2:
            cv2.polylines(frame,
                          [np.array([_sc(p) for p in pts])],
                          False, kleur, 2)
        for p in pts:
            cv2.circle(frame, _sc(p), 3, kleur, -1)

    # Blobs van dit frame.
    for b in detector.last_blobs:
        cv2.circle(frame, _sc(b), 12, KLEUR_BLOB, 2)

    # Blijvende impactpunten.
    for p in impacts_cam:
        x, y = _sc(p)
        cv2.circle(frame, (x, y), 8, KLEUR_IMPACT, -1)
        cv2.line(frame, (x - 18, y), (x + 18, y), (255, 255, 255), 2)
        cv2.line(frame, (x, y - 18), (x, y + 18), (255, 255, 255), 2)

    # HUD.
    hud = (f"fps {fps:4.1f}  drempel[1/2] {config.DIFF_THRESHOLD}  "
           f"minsnelheid[3/4] {config.MIN_INCOMING_SPEED}  "
           f"baan {len(detector.track)}  impacts {len(impacts_cam)}")
    cv2.putText(frame, hud, (10, 26), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (255, 255, 255), 1)
    if detector.last_reject:
        cv2.putText(frame, f"laatste afwijzing: {detector.last_reject}",
                    (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 140, 255), 1)
    if recording:
        cv2.circle(frame, (VIEW_W - 24, 22), 9, (0, 0, 255), -1)
        cv2.putText(frame, "REC", (VIEW_W - 78, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return frame


def build_beamer_canvas(impacts_beamer):
    """Zwart beamerbeeld met zone en blijvende impactstippen."""
    canvas = np.zeros((config.PROJECTOR_HEIGHT, config.PROJECTOR_WIDTH, 3),
                      np.uint8)
    x, y, w, h = config.ZONE_X, config.ZONE_Y, config.ZONE_W, config.ZONE_H
    cv2.rectangle(canvas, (x, y), (x + w, y + h), KLEUR_ZONE, 3)
    for (bx, by) in impacts_beamer:
        bx, by = int(bx), int(by)
        cv2.circle(canvas, (bx, by), 12, KLEUR_IMPACT, -1)
        cv2.circle(canvas, (bx, by), 26, (255, 255, 255), 2)
    cv2.putText(canvas, f"DEBUG  impacts: {len(impacts_beamer)}",
                (x + w + 24, y + 40), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2)
    return canvas


def main():
    if not os.path.exists(config.HOMOGRAPHY_FILE):
        raise SystemExit("Geen homography.npz. Run eerst calibrate_homography.py")
    H = np.load(config.HOMOGRAPHY_FILE)["H"]

    cam = Camera(gray=True)
    lens = LensCorrector()
    roi = build_roi_mask(H, config.CAM_WIDTH, config.CAM_HEIGHT)
    detector = ImpactDetector(roi_mask=roi)
    zone_pts = zone_outline_cam(H)
    roi_pts = roi_outline_cam(H)

    cv2.namedWindow("Beamer", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Beamer", cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN)
    cv2.namedWindow("Tracking", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Tracking", VIEW_W, VIEW_H)
    tracking_zichtbaar = True

    impacts_cam = []
    impacts_beamer = []
    writer = None
    tijden = []

    def redraw_beamer():
        cv2.imshow("Beamer", build_beamer_canvas(impacts_beamer))
        detector.suppress_frames()

    redraw_beamer()
    cv2.waitKey(300)
    print("Achtergrond leren, houd de plaat 2 seconden vrij...")
    for _ in range(int(config.CAM_FPS * 2)):
        ok, frame = cam.read()
        if ok:
            detector.process(lens.correct(frame))
        cv2.waitKey(1)
    print(__doc__)

    try:
        while True:
            ok, gray = cam.read()
            if not ok:
                continue
            gray = lens.correct(gray)

            nu = time.perf_counter()
            tijden.append(nu)
            tijden[:] = [t for t in tijden if nu - t < 1.0]
            fps = len(tijden)

            impact = detector.process(gray)
            if impact is not None:
                impacts_cam.append(impact)
                pt = np.array([[[impact[0], impact[1]]]], dtype=np.float32)
                bx, by = cv2.perspectiveTransform(pt, H)[0, 0]
                impacts_beamer.append((float(bx), float(by)))
                print(f"Impact: camera ({impact[0]:.0f},{impact[1]:.0f}) "
                      f"-> beamer ({bx:.0f},{by:.0f})")
                redraw_beamer()

            # Annoteren kost ~5-8 ms per frame; alleen doen als iemand
            # kijkt of de opname loopt, anders zakt de framerate onnodig.
            if tracking_zichtbaar or writer is not None:
                view = build_tracking_frame(gray, detector, zone_pts,
                                            roi_pts, impacts_cam, fps,
                                            writer is not None)
                if writer is not None:
                    writer.write(view)
                if tracking_zichtbaar:
                    cv2.imshow("Tracking", view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('1'):
                config.DIFF_THRESHOLD = max(5, config.DIFF_THRESHOLD - 5)
            elif key == ord('2'):
                config.DIFF_THRESHOLD = min(120, config.DIFF_THRESHOLD + 5)
            elif key == ord('3'):
                config.MIN_INCOMING_SPEED = max(4,
                                                config.MIN_INCOMING_SPEED - 2)
            elif key == ord('4'):
                config.MIN_INCOMING_SPEED = min(80,
                                                config.MIN_INCOMING_SPEED + 2)
            elif key == ord('i'):
                impacts_cam.clear()
                impacts_beamer.clear()
                redraw_beamer()
            elif key == ord('r'):
                detector.reset_background()
                print("Achtergrond gereset.")
            elif key == ord('v'):
                tracking_zichtbaar = not tracking_zichtbaar
                if not tracking_zichtbaar:
                    cv2.destroyWindow("Tracking")
                else:
                    cv2.namedWindow("Tracking", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("Tracking", VIEW_W, VIEW_H)
            elif key == ord('o'):
                if writer is None:
                    naam = time.strftime("debug_%Y%m%d_%H%M%S.avi")
                    writer = cv2.VideoWriter(
                        naam, cv2.VideoWriter_fourcc(*"MJPG"),
                        config.CAM_FPS, (VIEW_W, VIEW_H))
                    print(f"Opname gestart: {naam}")
                else:
                    writer.release()
                    writer = None
                    print("Opname gestopt.")
    finally:
        if writer is not None:
            writer.release()
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
