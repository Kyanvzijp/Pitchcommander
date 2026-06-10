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
    ├── fps_test.py               # meet werkelijke framerate/verwerkingstijd
    ├── shared.py                 # gedeelde state (detectie <-> telefoon)
    ├── webserver.py              # mobiele trainingsinterface (Flask)
    └── main.py                   # stap 3: draaien
```

## Doelwit-training via je telefoon

Naast de detectie draait een webserver. Open op een telefoon in hetzelfde
netwerk: `http://<ip-van-de-pi>:8080` (het juiste adres staat in de
terminal als je `main.py` start).

- Tik in de zone op je telefoon: de beamer projecteert daar een bullseye.
- Gooi: binnen `TARGET_RADIUS` van het doel = **RAAK** (groen), anders
  **MIS** met de afstand ernaast in procenten van de zonebreedte.
- Knoppen: *Random spot* (willekeurig doelwit), *Doel weg*, *Reset score*.
- Zonder doelwit werkt alles als gewone strike/ball-teller.

Extra vereiste: `sudo apt install -y python3-flask`

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

## Framerate en scherpte (belangrijk voor accuratesse)

De OV5647 haalt op 640x480 zo'n 58 fps, tegen ~30 fps op 1280x720. De
standaardconfig staat daarom nu op 640x480 @ 58 fps. Minstens zo belangrijk
is de **sluitertijd**: `CAM_EXPOSURE_US = 6000` legt elke bal in 6 ms vast,
zodat hij een scherpe ronde blob is in plaats van een lange veeg die het
rondheidsfilter afkeurt. Korte sluitertijd vraagt wel licht: is het beeld
te donker, verhoog dan `CAM_GAIN` (meer ruis) of zorg voor extra verlichting
op de plaat.

Meet wat je opstelling werkelijk haalt met:

```bash
python3 fps_test.py
```

**Na elke wijziging van CAM_WIDTH/CAM_HEIGHT moet je `calibrate_lens.py`
en `calibrate_homography.py` opnieuw draaien**, omdat beide kalibraties in
camerapixels werken. De software waarschuwt en schakelt de lenscorrectie
uit als de resoluties niet overeenkomen.

## Bekende beperkingen

- De OV5647 haalt ~30 fps. Bij echt snelle pitches mis je de bal of zie je
  alleen een veeg. Voor "matige" worpen is dit prima. Wil je later opschalen,
  dan is de Pi Global Shutter Camera de juiste hardware.
- Frame-differencing reageert ook op bewegende handen/schaduwen in beeld.
  Houd het beeldveld zo schoon mogelijk en gebruik `MAX_BLOB_AREA`.
- Beamer en camera moeten vanuit ongeveer dezelfde kant kijken; staat de
  camera te schuin t.o.v. de plaat, dan wordt de homografie minder nauwkeurig.
