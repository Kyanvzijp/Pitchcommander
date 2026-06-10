"""
Stap 1: Lenskalibratie (fisheye-correctie).

De OV5647 fisheye geeft sterke randvervorming. We bepalen de intrinsics en
distortiecoefficienten met OpenCV's fisheye-model, met een fysiek schaakbord.

GEBRUIK:
  1. Print een schaakbordpatroon (9x6 binnenste hoeken) en plak het op karton.
  2. Run dit script. Houd het bord onder verschillende hoeken/posities voor
     de camera. Druk SPATIE om een goed frame vast te leggen (>= 15 stuks).
  3. Druk 'c' om te kalibreren en op te slaan, of 'q' om te stoppen.

Output: lens_calib.npz  (K, D, dims)
"""
import cv2
import numpy as np
import config
from camera import Camera


def main():
    cols, rows = config.CHESSBOARD_COLS, config.CHESSBOARD_ROWS
    pattern_size = (cols, rows)

    # 3D-objectpunten (Z=0 vlak). Schaal is willekeurig; we hebben alleen
    # distortie nodig, niet absolute afstanden.
    objp = np.zeros((1, cols * rows, 3), np.float32)
    objp[0, :, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)

    objpoints = []
    imgpoints = []

    cam = Camera()
    print("SPATIE = frame vastleggen | c = kalibreren+opslaan | q = stop")

    captured = 0
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(
                gray, pattern_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
            )

            disp = frame.copy()
            if found:
                cv2.drawChessboardCorners(disp, pattern_size, corners, found)
            cv2.putText(disp, f"Vastgelegd: {captured}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Lenskalibratie", disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord(' ') and found:
                term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
                corners = cv2.cornerSubPix(gray, corners, (3, 3), (-1, -1), term)
                objpoints.append(objp.copy())
                imgpoints.append(corners)
                captured += 1
                print(f"Frame vastgelegd ({captured})")
            elif key == ord('c'):
                if captured < 10:
                    print("Te weinig frames, leg er minstens 10-15 vast.")
                    continue
                _calibrate_and_save(objpoints, imgpoints, gray.shape[::-1])
                break
            elif key == ord('q'):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()


def _calibrate_and_save(objpoints, imgpoints, dims):
    K = np.zeros((3, 3))
    D = np.zeros((4, 1))
    n = len(objpoints)
    rvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(n)]
    tvecs = [np.zeros((1, 1, 3), dtype=np.float64) for _ in range(n)]
    flags = (cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC +
             cv2.fisheye.CALIB_FIX_SKEW)
    term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

    rms, _, _, _, _ = cv2.fisheye.calibrate(
        objpoints, imgpoints, dims, K, D, rvecs, tvecs, flags, term)

    np.savez(config.LENS_CALIB_FILE, K=K, D=D, dims=np.array(dims))
    print(f"Kalibratie opgeslagen in {config.LENS_CALIB_FILE} (RMS-fout: {rms:.3f})")


if __name__ == "__main__":
    main()
