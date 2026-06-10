"""
Camera-abstractie. Werkt met Picamera2 (Pi 5 aanrader) of OpenCV VideoCapture.
Geeft in beide gevallen frames terug als BGR numpy-arrays (OpenCV-formaat).
"""
import time
import numpy as np
import config


class Camera:
    def __init__(self):
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
        cfg = self._picam.create_video_configuration(
            main={"size": (config.CAM_WIDTH, config.CAM_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": config.CAM_FPS},
        )
        self._picam.configure(cfg)
        self._picam.start()
        time.sleep(1.0)  # laat de auto-exposure even settelen
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
        """Geeft (ok, frame) terug. frame is BGR uint8."""
        import cv2
        if self._backend == "picamera2":
            rgb = self._picam.capture_array()
            # Picamera2 RGB888 -> OpenCV verwacht BGR
            frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return True, frame
        else:
            return self._cap.read()

    def release(self):
        if self._backend == "picamera2" and self._picam is not None:
            self._picam.stop()
        elif self._cap is not None:
            self._cap.release()
