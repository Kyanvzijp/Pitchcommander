"""
Laadt de lenskalibratie en levert een snelle undistort-functie.
Pre-computet de remap-tabellen, zodat het per frame goedkoop is.
"""
import os
import cv2
import numpy as np
import config


class LensCorrector:
    def __init__(self):
        self.enabled = False
        self.map1 = None
        self.map2 = None
        if os.path.exists(config.LENS_CALIB_FILE):
            self._load()

    def _load(self):
        data = np.load(config.LENS_CALIB_FILE)
        K = data["K"]
        D = data["D"]
        dims = tuple(int(x) for x in data["dims"])
        # Oude kalibratiebestanden hebben geen modelveld: die zijn fisheye.
        model = str(data["model"]) if "model" in data else "fisheye"
        if model != config.LENS_MODEL:
            print(f"WAARSCHUWING: lens_calib.npz is een {model}-kalibratie "
                  f"maar config.LENS_MODEL = {config.LENS_MODEL}. "
                  f"Correctie staat UIT; draai calibrate_lens.py opnieuw.")
            return
        if dims != (config.CAM_WIDTH, config.CAM_HEIGHT):
            # De kalibratie is op een andere resolutie gemaakt. Domweg
            # schalen is riskant: verschillende sensormodi van de OV5647
            # hebben een ander beeldveld (1280x720 is een 16:9 crop,
            # 640x480 gebruikt de volle 4:3 sensor). Correctie wordt dan
            # uitgeschakeld; draai calibrate_lens.py opnieuw op de
            # huidige resolutie.
            print(f"WAARSCHUWING: lens_calib.npz is gemaakt op {dims}, "
                  f"maar de camera staat op "
                  f"{(config.CAM_WIDTH, config.CAM_HEIGHT)}. "
                  f"Fisheye-correctie staat UIT. Draai calibrate_lens.py "
                  f"opnieuw op deze resolutie.")
            return
        # Nieuwe cameramatrix die zoveel mogelijk beeld behoudt.
        if model == "fisheye":
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D, dims, np.eye(3), balance=0.0)
            self.map1, self.map2 = cv2.fisheye.initUndistortRectifyMap(
                K, D, np.eye(3), new_K, dims, cv2.CV_16SC2)
        else:  # standaard (rectilineair) model, b.v. de 6 mm GS-lens
            new_K, _ = cv2.getOptimalNewCameraMatrix(K, D, dims, 0, dims)
            self.map1, self.map2 = cv2.initUndistortRectifyMap(
                K, D, None, new_K, dims, cv2.CV_16SC2)
        self.enabled = True

    def correct(self, frame):
        if not self.enabled:
            return frame
        return cv2.remap(frame, self.map1, self.map2,
                         interpolation=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT)
