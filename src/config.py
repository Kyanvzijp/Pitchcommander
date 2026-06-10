"""
Centrale configuratie voor het slagzone-systeem.
Pas deze waarden aan op jouw opstelling.
"""

# ----- Beamer / projectie -----
# Resolutie waarmee de beamer projecteert (= je HDMI output resolutie).
PROJECTOR_WIDTH = 1280
PROJECTOR_HEIGHT = 720

# Slagzone als rechthoek, in beamer-pixels.
# Een echte slagzone is STAAND: de thuisplaat is 43 cm breed en de zone
# loopt verticaal van knieholte tot halverwege de romp. Verhouding hier
# 3:4 (420x560). Meet na projectie de fysieke breedte op de plaat na en
# schaal ZONE_W/ZONE_H tot die ~43 cm is.
ZONE_X = 430          # linkerbovenhoek X (gecentreerd: (1280-420)/2)
ZONE_Y = 80           # linkerbovenhoek Y (gecentreerd: (720-560)/2)
ZONE_W = 420          # breedte
ZONE_H = 560          # hoogte

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
# Drempel t.o.v. het achtergrondmodel (0-255). Hoger = minder gevoelig.
DIFF_THRESHOLD = 35
# Drempel t.o.v. het VORIGE frame. Een echte inslag verschijnt plotseling,
# dus moet ook in de frame-naar-frame diff zichtbaar zijn.
FRAME_DIFF_THRESHOLD = 30
# Minimale/maximale oppervlakte van een impact-blob (in camera-pixels).
MIN_BLOB_AREA = 80
MAX_BLOB_AREA = 6000
# Vormfilter: rondheid van de blob (4*pi*A / omtrek^2). 1.0 = perfecte
# cirkel. Een bal-impact is rond; handen/schaduwen zijn dat niet.
MIN_CIRCULARITY = 0.45
# Maximale verhouding breedte/hoogte van de blob (armen zijn langwerpig).
MAX_ASPECT_RATIO = 2.2
# Transient-check: een echte inslag is kort. Een kandidaat-blob die langer
# dan dit aantal frames op (ongeveer) dezelfde plek blijft, is een hand,
# schaduw of object en wordt verworpen.
TRANSIENT_MAX_FRAMES = 4
# Afstand (px) waarbinnen een blob in het volgende frame als "dezelfde
# kandidaat" geldt.
CANDIDATE_MATCH_DIST = 60
# Aantal frames dat een blob "rust" moet hebben voordat we een nieuwe
# impact accepteren (debounce, voorkomt dubbele detectie).
IMPACT_COOLDOWN_FRAMES = 15
# Detectie onderdrukken gedurende N frames nadat de projectie zelf is
# veranderd (nieuwe stip getekend). Voorkomt dat de software zijn eigen
# projectie als inslag ziet.
SUPPRESS_AFTER_DRAW_FRAMES = 10
# Achtergrond-leersnelheid (0-1). Laag = stabiel.
BG_LEARNING_RATE = 0.02
# Snelle leersnelheid direct na een projectie-verandering, zodat de nieuwe
# stip snel in het achtergrondmodel wordt opgenomen.
BG_FAST_LEARNING_RATE = 0.35
# ----- ROI -----
# ROI: marge (in beamer-pixels) rond de slagzone die nog meetelt. Alles
# daarbuiten in het camerabeeld wordt volledig genegeerd.
ROI_MARGIN_PX = 120

# ----- Doelwit-training (mobiel) -----
# Poort van de webinterface voor de telefoon.
WEB_PORT = 8080
# Straal (beamer-pixels) waarbinnen een inslag als RAAK telt.
TARGET_RADIUS = 80
