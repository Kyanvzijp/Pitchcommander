# Slagzone-detectie op Raspberry Pi 5

Beamer projecteert een rechthoekige slagzone op een houten plaat. De
OV5647-fisheyecamera kijkt naar diezelfde plaat en detecteert waar de bal
inslaat. Het raakpunt wordt teruggeprojecteerd als rode (strike) of oranje
(ball) stip.

## Projectstructuur

```
slagzone/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
└── src/
    ├── config.py                 # alle instellingen op een plek
    ├── camera.py                 # camera-abstractie (Picamera2 / OpenCV)
    ├── lens.py                   # fisheye-correctie
    ├── detector.py               # impact-detectie (frame-differencing)
    ├── calibrate_lens.py         # stap 1: lens kalibreren
    ├── calibrate_homography.py   # stap 2: beamer <-> camera koppelen
    └── main.py                   # stap 3: draaien
```

## Hoe het werkt

1. **Lenskalibratie** (`calibrate_lens.py`) corrigeert de fisheye-vervorming.
2. **Homografie-kalibratie** (`calibrate_homography.py`) projecteert een
   schaakbord en koppelt camera-pixels aan beamer-pixels.
3. **Impact-detectie** (`detector.py`) gebruikt frame-differencing: het zoekt
   naar een plotselinge verandering op de plaat = de inslag.
4. **Hoofdapp** (`main.py`) brengt alles samen.

De detectie zoekt bewust niet "de bal" maar de *verandering op de plaat*. Dat
is veel robuuster met een trage fisheyecamera dan kleur-tracking.

## Installatie (op de Pi 5, Raspberry Pi OS Bookworm)

```bash
sudo apt update
sudo apt install -y python3-opencv python3-picamera2 python3-numpy
```

Picamera2 zit standaard in Bookworm. Test of de camera werkt:

```bash
libcamera-hello --timeout 2000
```

## Gebruik

Doorloop de stappen in volgorde. Beamer en plaat moeten vast staan; verschuif
je de opstelling, dan moet je opnieuw kalibreren.

### Stap 1 - Lens kalibreren (eenmalig per camera)

Print een 9x6 schaakbord op papier, plak op karton.

```bash
cd src
python3 calibrate_lens.py
```

Houd het bord onder verschillende hoeken voor de camera, druk SPATIE per goed
frame (15+), dan `c` om op te slaan. Maakt `lens_calib.npz`.

### Stap 2 - Beamer en camera koppelen

Beamer aan, projecteert op de plaat. Camera ziet de hele projectie.

```bash
python3 calibrate_homography.py
```

Wacht tot "Patroon gevonden", druk `c`. Maakt `homography.npz`.

### Stap 3 - Draaien

```bash
python3 main.py
```

Toetsen: `r` achtergrond resetten, `c` treffers wissen, `q` stoppen.

## Afstellen (config.py)

| Probleem | Aanpassing |
|---|---|
| Detecteert te veel/ruis | `DIFF_THRESHOLD` omhoog |
| Mist zachte treffers | `DIFF_THRESHOLD` omlaag |
| Pakt schaduw/hand op als treffer | `MAX_BLOB_AREA` omlaag |
| Telt 1 inslag dubbel | `IMPACT_COOLDOWN_FRAMES` omhoog |
| Slagzone verkeerde plek/grootte | `ZONE_X/Y/W/H` |
| Beamer andere resolutie | `PROJECTOR_WIDTH/HEIGHT` |

## Bekende beperkingen

- De OV5647 haalt ~30 fps. Bij echt snelle pitches mis je de bal of zie je
  alleen een veeg. Voor "matige" worpen is dit prima. Wil je later opschalen,
  dan is de Pi Global Shutter Camera de juiste hardware.
- Frame-differencing reageert ook op bewegende handen/schaduwen in beeld.
  Houd het beeldveld zo schoon mogelijk en gebruik `MAX_BLOB_AREA`.
- Beamer en camera moeten vanuit ongeveer dezelfde kant kijken; staat de
  camera te schuin t.o.v. de plaat, dan wordt de homografie minder nauwkeurig.
