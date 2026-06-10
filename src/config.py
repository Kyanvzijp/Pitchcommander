"""
Centrale configuratie voor het slagzone-systeem.
Pas deze waarden aan op jouw opstelling.
"""

# ----- Beamer / projectie -----
# Resolutie waarmee de beamer projecteert (= je HDMI output resolutie).
PROJECTOR_WIDTH = 1280
PROJECTOR_HEIGHT = 720

# Slagzone als rechthoek, in beamer-pixels.
# Gecentreerd, met marge eromheen zodat het kalibratiepatroon ook past.
ZONE_X = 340          # linkerbovenhoek X
ZONE_Y = 120          # linkerbovenhoek Y
ZONE_W = 600          # breedte
ZONE_H = 480          # hoogte

# ----- Camera -----
# OV5647: rolling shutter, praktisch ~30 fps. Houd resolutie laag voor snelheid.
CAM_WIDTH = 1280
CAM_HEIGHT = 720
CAM_FPS = 30

# Zet op True als je libcamera/picamera2 gebruikt (Pi 5 aanrader).
# False = OpenCV VideoCapture (USB / oudere setups).
USE_PICAMERA2 = True

# ----- Fisheye / lensvervorming -----
# Pad naar opgeslagen camera-kalibratie (intrinsics + distortie).
# Wordt gemaakt door calibrate_lens.py
LENS_CALIB_FILE = "lens_calib.npz"

# ----- Homografie (camera <-> beamer) -----
HOMOGRAPHY_FILE = "homography.npz"

# Schaakbord voor automatische kalibratie (binnenste hoeken).
CHESSBOARD_COLS = 9
CHESSBOARD_ROWS = 6

# ----- Impact-detectie -----
# Drempel voor frame-differencing (0-255). Hoger = minder gevoelig.
DIFF_THRESHOLD = 30
# Minimale/maximale oppervlakte van een impact-blob (in camera-pixels).
MIN_BLOB_AREA = 80
MAX_BLOB_AREA = 8000
# Aantal frames dat een blob "rust" moet hebben voordat we hem als nieuwe
# impact accepteren (debounce, voorkomt dubbele detectie).
IMPACT_COOLDOWN_FRAMES = 15
# Achtergrond-leersnelheid voor de differencing (0-1). Laag = stabiel.
BG_LEARNING_RATE = 0.02
