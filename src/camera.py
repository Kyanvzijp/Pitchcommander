"""
Camera-abstractie. Werkt met Picamera2 (Pi 5 aanrader) of OpenCV VideoCapture.

Twee modi:
- Camera()           : kleurenframes (BGR), voor de kalibratiescripts.
- Camera(gray=True)  : grijswaardenframes rechtstreeks uit het Y-vlak van
                       YUV420. Geen kleurconversie per frame nodig, dus
                       sneller. Voor de detectielus (main.py).

Stelt ook framerate en (optioneel) een vaste korte sluitertijd in, wat
essentieel is om snelle ballen scherp vast te leggen.
"""
import time
import numpy as np
import config


class Camera:
    def __init__(self, gray=False):
        self.gray = gray
        self._backend = None
        self._cap = None
        self._picam = None

        if config.USE_PICAMERA2:
            self._init_picamera2()
        else:
            self._init_opencv()

    def _init_picamera2(self):
        from picamera2 import Picamera2
        self._picam = Picamera2()

        frame_us = int(1_000_000 / config.CAM_FPS)
        controls = {"FrameDurationLimits": (frame_us, frame_us)}
        if config.CAM_EXPOSURE_US:
            # Vaste korte sluitertijd: scherpe ballen, geen veegsporen.
            # Sluitertijd kan nooit langer zijn dan de frameduur.
            controls["AeEnable"] = False
            controls["ExposureTime"] = min(config.CAM_EXPOSURE_US,
                                           frame_us - 200)
            controls["AnalogueGain"] = float(config.CAM_GAIN or 6.0)

        fmt = "YUV420" if self.gray else "RGB888"
        cfg = self._picam.create_video_configuration(
            main={"size": (config.CAM_WIDTH, config.CAM_HEIGHT),
                  "format": fmt},
            controls=controls,
            buffer_count=6,
        )
        self._picam.configure(cfg)
        self._picam.start()
        time.sleep(1.0)  # sensor laten settelen
        self._backend = "picamera2"

    def _init_opencv(self):
        import cv2
        self._cap = cv2.VideoCapture(0)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAM_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAM_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.CAM_FPS)
        if not self._cap.isOpened():
            raise RuntimeError("Kon de camera niet openen via OpenCV.")
        self._backend = "opencv"

    def read(self):
        """Geeft (ok, frame) terug.
        gray=False: frame is BGR uint8 (h, w, 3).
        gray=True : frame is grijswaarden uint8 (h, w)."""
        import cv2
        if self._backend == "picamera2":
            arr = self._picam.capture_array()
            if self.gray:
                # YUV420: array is (h*1.5, w); het Y-vlak is de eerste h rijen.
                return True, arr[:config.CAM_HEIGHT, :config.CAM_WIDTH]
            return True, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            ok, frame = self._cap.read()
            if ok and self.gray and frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return ok, frame

    def release(self):
        if self._backend == "picamera2" and self._picam is not None:
            self._picam.stop()
        elif self._cap is not None:
            self._cap.release()
