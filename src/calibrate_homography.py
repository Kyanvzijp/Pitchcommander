"""
Stap 2: Automatische camera<->beamer kalibratie.

De beamer projecteert een schaakbord op de houten plaat. De camera ziet dat
patroon. Omdat we exact weten waar de hoeken in BEAMER-pixels staan (we tekenen
ze immers zelf) en waar de camera ze ziet, kunnen we een homografie H berekenen
die camera-pixels omzet naar beamer-pixels.

Zo weet je later: "impact gezien op camera-pixel (cx, cy)" -> "beamer-pixel
(bx, by)" -> ligt dat binnen de slagzone-rechthoek?

GEBRUIK:
  Run dit script terwijl de beamer aan staat en op de plaat projecteert.
  Het venster 'Beamer' moet je naar het beamer-scherm slepen (of zet de beamer
  als primair/gespiegeld scherm). Druk 'c' om te kalibreren, 'q' om te stoppen.

Output: homography.npz  (H, plus de slagzone-rechthoek ter referentie)
"""
import cv2
import numpy as np
import config
from camera import Camera
from lens import LensCorrector


def make_chessboard_image():
    """Tekent een schaakbord in beamer-resolutie, binnen de slagzone-rechthoek,
    en geeft ook de exacte beamer-pixelcoordinaten van de binnenste hoeken terug."""
    cols, rows = config.CHESSBOARD_COLS, config.CHESSBOARD_ROWS
    img = np.full((config.PROJECTOR_HEIGHT, config.PROJECTOR_WIDTH, 3),
                  255, np.uint8)

    # Vakgrootte zo kiezen dat (cols+1) x (rows+1) vakken in de zone passen.
    sq_w = config.ZONE_W // (cols + 1)
    sq_h = config.ZONE_H // (rows + 1)
    sq = min(sq_w, sq_h)

    board_w = sq * (cols + 1)
    board_h = sq * (rows + 1)
    ox = config.ZONE_X + (config.ZONE_W - board_w) // 2
    oy = config.ZONE_Y + (config.ZONE_H - board_h) // 2

    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                x0 = ox + c * sq
                y0 = oy + r * sq
                cv2.rectangle(img, (x0, y0), (x0 + sq, y0 + sq), (0, 0, 0), -1)

    # Binnenste hoeken in beamer-pixels (zelfde volgorde als findChessboardCorners).
    beamer_pts = []
    for r in range(rows):
        for c in range(cols):
            bx = ox + (c + 1) * sq
            by = oy + (r + 1) * sq
            beamer_pts.append([bx, by])
    beamer_pts = np.array(beamer_pts, dtype=np.float32)
    return img, beamer_pts


def main():
    pattern_size = (config.CHESSBOARD_COLS, config.CHESSBOARD_ROWS)
    board_img, beamer_pts = make_chessboard_image()

    cv2.namedWindow("Beamer", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Beamer", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("Beamer", board_img)
    cv2.waitKey(500)

    cam = Camera()
    lens = LensCorrector()
    if not lens.enabled:
        print("WAARSCHUWING: geen lens_calib.npz gevonden. Fisheye wordt NIET "
              "gecorrigeerd; de kalibratie wordt minder nauwkeurig.")

    print("Richt de beamer op de plaat. 'c' = kalibreren, 'q' = stop.")
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue
            frame = lens.correct(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(
                gray, pattern_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

            disp = frame.copy()
            if found:
                cv2.drawChessboardCorners(disp, pattern_size, corners, found)
                cv2.putText(disp, "Patroon gevonden - druk 'c'", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(disp, "Geen patroon...", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.imshow("Camera", disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('c') and found:
                term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
                corners = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), term)
                cam_pts = corners.reshape(-1, 2).astype(np.float32)

                # H: camera-pixel -> beamer-pixel
                H, mask = cv2.findHomography(cam_pts, beamer_pts, cv2.RANSAC, 3.0)
                if H is None:
                    print("Homografie mislukt, probeer opnieuw.")
                    continue
                zone = np.array([config.ZONE_X, config.ZONE_Y,
                                 config.ZONE_W, config.ZONE_H])
                np.savez(config.HOMOGRAPHY_FILE, H=H, zone=zone)
                inliers = int(mask.sum()) if mask is not None else 0
                print(f"Homografie opgeslagen ({inliers} inliers) -> "
                      f"{config.HOMOGRAPHY_FILE}")
                break
            elif key == ord('q'):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
