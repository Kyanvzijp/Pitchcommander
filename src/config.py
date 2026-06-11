"""
Centrale configuratie voor het slagzone-systeem.
Pas deze waarden aan op jouw opstelling.
"""

# ----- Beamer / projectie -----
# Resolutie waarmee de beamer projecteert (= je HDMI output resolutie).
PROJECTOR_WIDTH = 1280
PROJECTOR_HEIGHT = 720

# Slagzone als rechthoek, in beamer-pixels.
# Gemeten schaal van deze opstelling (beamer op 2 m): 420 px = 31 cm breed,
# 560 px = 40 cm hoog, dus ~13,6 px/cm horizontaal en ~14 px/cm verticaal.
# Hieronder: breedte op de officiele 43,2 cm (thuisplaat), hoogte zo groot
# als de beamer aankan (~45,7 cm). Voor de volle slagzonehoogte (55-60 cm)
# moet de beamer ~45-50 cm verder van de plaat staan; meet daarna opnieuw
# en schaal deze waarden, en herkalibreer de homografie.
ZONE_X = 347          # linkerbovenhoek X (gecentreerd: (1280-585)/2)
ZONE_Y = 36           # linkerbovenhoek Y
ZONE_W = 585          # breedte  (~43,2 cm bij 13,6 px/cm)
ZONE_H = 640          # hoogte   (~45,7 cm bij 14 px/cm)

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
CAM_GAIN = 8.0

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
# (FRAME_DIFF_THRESHOLD vervallen: detectie werkt nu op trajectvolging.)
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
# ----- Trajectvolging (impact = omkeerpunt van de baan) -----
# De bal wordt frame voor frame gevolgd. De impact is het punt waar de
# baan omkeert (terugstuit) of abrupt stilvalt (dode klap). Pas op dat
# moment is de bal OP het muurvlak en klopt de homografie-mapping exact.
#
# Minimale snelheid in px/frame om als worp te tellen. Gemeten over het
# SNELSTE stuk van de baan (niet het begin: een bal kan traag in beeld
# komen en versnellen). Praktijkmeting op deze opstelling: een worp haalt
# ~16-30 px/frame omdat de camera vrijwel langs de werprichting kijkt;
# handen en schaduwen blijven onder de ~8. Dit is het belangrijkste
# filter tegen valse detecties.
MIN_INCOMING_SPEED = 10
# Minimale afgelegde weg (px) in beeld voordat iets als worp kan tellen.
MIN_APPROACH_PX = 40
# Een impact geeft een abrupte richtingsverandering (knik) in de baan:
# terugstuiten of omslaan naar vallen. De aanvliegbaan zelf kromt vloeiend
# (enkele graden per frame), dus een knik groter dan deze hoek markeert
# het impactmoment.
KINK_ANGLE_DEG = 45
# Of: de snelheid direct na het verste punt zakt onder deze fractie van
# de aanvliegsnelheid (dode klap die omlaag valt).
STOP_SPEED_FACTOR = 0.5
# Bal mag dit aantal frames kwijt zijn voordat de baan wordt afgesloten.
TRACK_MISSING_MAX = 2
# Veiligheidslimiet op baanlengte (frames).
TRACK_MAX_LEN = 40
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
ROI_MARGIN_PX = 200

# ----- Doelwit-training (mobiel) -----
# Poort van de webinterface voor de telefoon.
WEB_PORT = 8080
# Straal (beamer-pixels) waarbinnen een inslag als RAAK telt.
TARGET_RADIUS = 80
