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
# OV5647 sensormodi (libcamera): 640x480 @ ~58 fps, 1296x972 @ ~43 fps,
# 1920x1080 @ ~30 fps. Lagere resolutie = hogere framerate = betere
# baldetectie. 640x480 is de aanrader voor dit systeem.
# LET OP: na het wijzigen van de resolutie moet je calibrate_lens.py EN
# calibrate_homography.py opnieuw draaien (beide werken in camerapixels).
CAM_WIDTH = 640
CAM_HEIGHT = 480
CAM_FPS = 58

# Sluitertijd in microseconden, of None voor automatisch.
# CRUCIAAL voor scherpe ballen: bij auto-belichting kiest de camera al
# snel 15-30 ms en wordt een snelle bal een lange veeg die het
# rondheidsfilter afkeurt. 4000-8000 us (4-8 ms) geeft scherpe blobs,
# maar vraagt om voldoende licht. Begin met 6000 en kijk wat het beeld doet.
CAM_EXPOSURE_US = 6000
# Versterking (analoge gain) als CAM_EXPOSURE_US vast staat. Hoger = lichter
# beeld maar meer ruis. 4.0-8.0 is gebruikelijk bij korte sluitertijden.
CAM_GAIN = 6.0

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
# Geschaald voor 640x480; gebruik je een hogere resolutie, schaal mee
# (oppervlakte schaalt kwadratisch met de resolutie).
MIN_BLOB_AREA = 30
MAX_BLOB_AREA = 2200
# Vormfilter: rondheid van de blob (4*pi*A / omtrek^2). 1.0 = perfecte
# cirkel. Een bal-impact is rond; handen/schaduwen zijn dat niet.
MIN_CIRCULARITY = 0.45
# Maximale verhouding breedte/hoogte van de blob (armen zijn langwerpig).
MAX_ASPECT_RATIO = 2.2
# Transient-check: een echte inslag is kort. Een kandidaat-blob die langer
# dan dit aantal frames op (ongeveer) dezelfde plek blijft, is een hand,
# schaduw of object en wordt verworpen.
# Bij ~58 fps duurt een frame ~17 ms; een bal is wat meer frames zichtbaar
# dan bij 30 fps, dus deze staat iets ruimer.
TRANSIENT_MAX_FRAMES = 6
# Afstand (px) waarbinnen een blob in het volgende frame als "dezelfde
# kandidaat" geldt. Geschaald voor 640x480.
CANDIDATE_MATCH_DIST = 35
# Aantal frames dat een blob "rust" moet hebben voordat we een nieuwe
# impact accepteren (debounce, voorkomt dubbele detectie).
IMPACT_COOLDOWN_FRAMES = 25
# Detectie onderdrukken gedurende N frames nadat de projectie zelf is
# veranderd (nieuwe stip getekend). Voorkomt dat de software zijn eigen
# projectie als inslag ziet.
SUPPRESS_AFTER_DRAW_FRAMES = 15
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
