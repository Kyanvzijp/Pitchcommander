# Slagzone-detectie op Raspberry Pi 5

Een beamer projecteert een slagzone op een houten plaat. De camera op de
Pi volgt elke geworpen bal, bepaalt het exacte impactpunt op de plaat en
projecteert daar een markering. Via een webpagina op je telefoon plaats je
doelwitten waar de pitcher op moet gooien, met automatische raak/mis-telling.

---

## Stand van zaken (bijgewerkt 10 juni 2026)

**Werkt en is getest:**
- Volledige pijplijn: kalibratie, trajectvolging, projectie, telefoonbediening
- Detector v3: volgt de bal frame voor frame en legt de impact op het
  fysieke raakmoment (de knik in de baan), niet op het moment van
  verschijnen in beeld
- Camera op 640x480 @ 58 fps met vaste korte sluitertijd (6 ms) zodat de
  bal scherp blijft in plaats van een veeg
- Mobiele trainingsinterface met doelwitten en raak/mis-score
- Debugviewer met live visualisatie, live tuning en video-opname

**Morgen testen / openstaand:**
1. `fps_test.py` draaien: halen we echt ~58 fps en is het beeld licht
   genoeg met de 6 ms sluitertijd? Het script beoordeelt de helderheid nu
   zelf (te donker / werkbaar / goed / te licht). Te donker: IR-lampjes op
   de camera monteren en controleren (LDR-sensortjes afschermen of de
   potmeter bijdraaien; IR is onzichtbaar en wast de projectie niet uit),
   anders `CAM_GAIN` omhoog.
2. Beide kalibraties opnieuw doen (de cameraresolutie is gewijzigd naar
   640x480, dus oude kalibraties zijn ongeldig; de software waarschuwt zelf).
3. Echte worpen testen met `debug_view.py` + opname ('o'): klopt het
   impactpunt? Volgt de gele baan de bal netjes?
4. Zone nameten: hij is op maat gezet voor ~43,2 cm breed x ~45,7 cm hoog
   (gemeten schaal: ~13,6 px/cm horizontaal, ~14 px/cm verticaal bij de
   beamer op 2 m). Wil je de volle slagzonehoogte (55-60 cm), zet de
   beamer dan ~45-50 cm verder terug, herkalibreer de homografie, meet
   opnieuw en schaal `ZONE_W`/`ZONE_H` mee. Keystone-correctie van de
   beamer aanzetten (17 graden kanteling).

**Bekende aandachtspunten:**
- Remote desktop = beameruitgang op deze opstelling. Kalibreer en draai
  altijd in dezelfde schermconfiguratie, anders klopt de homografie niet.
- In `debug_view.py`: het Tracking-venster wordt mee geprojecteerd op de
  plaat (spiegel-lus). Verberg het met 'v' tijdens worpen of gebruik de
  opname en kijk terug.

---

## Verse start: checklist in volgorde

```bash
cd src
```

**1. Camera testen**
```bash
rpicam-hello --timeout 2000        # geeft de camera beeld?
python3 fps_test.py                # halen we ~58 fps, beeld licht genoeg?
```

**2. Lens kalibreren** (eenmalig per camera/resolutie)

Pak het geprinte 9x6 schaakbord (zit als `schaakbord_9x6.pdf` bij dit
project; print op 100%, plak vlak op karton).
```bash
python3 calibrate_lens.py
```
Houd het bord onder verschillende hoeken voor de camera. SPATIE per goed
frame (15+ stuks, bord volledig in beeld met witte rand), dan `c`.
Maakt `lens_calib.npz`.

**3. Beamer en camera koppelen** (opnieuw doen na elke verplaatsing van
beamer, camera of plaat, en na elke resolutiewijziging)

Beamer aan, gericht op de plaat, in de schermconfiguratie waarin je straks
ook draait.
```bash
python3 calibrate_homography.py
```
Wacht op "Patroon gevonden", druk `c`. Maakt `homography.npz`.

**4. Draaien**
```bash
python3 main.py        # trainingsmodus (telefoon-URL staat in de terminal)
python3 debug_view.py  # of: debugmodus met live tracking-visualisatie
```

---

## Projectstructuur

```
slagzone/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
└── src/
    ├── config.py                 # ALLE instellingen op een plek
    ├── camera.py                 # camera-abstractie (Picamera2 / OpenCV)
    ├── lens.py                   # fisheye-correctie
    ├── detector.py               # trajectvolging + impactbepaling
    ├── calibrate_lens.py         # stap 2: lens kalibreren
    ├── calibrate_homography.py   # stap 3: beamer <-> camera koppelen
    ├── fps_test.py               # meet werkelijke framerate/verwerkingstijd
    ├── debug_view.py             # live visualisatie, tuning, opname
    ├── shared.py                 # gedeelde state (detectie <-> telefoon)
    ├── webserver.py              # mobiele trainingsinterface (Flask)
    └── main.py                   # stap 4: trainingsmodus
```

## Hoe de detectie werkt (v3, trajectvolging)

De camera kijkt schuin tegen de vliegbaan aan. Een bal die in beeld
verschijnt is dus nog onderweg; pas op het moment van contact ligt hij op
het muurvlak en klopt de vertaling naar beamercoordinaten exact.

Daarom volgt de detector de bal frame voor frame en zoekt het fysieke
impactmoment:
- **Knik** (primair): bij impact verandert de bewegingsrichting abrupt
  (terugstuit of omslaan naar vallen), terwijl de aanvliegbaan vloeiend
  kromt. Het knikpunt is de impact.
- **Instorting** (vangnet): bij een dode klap zakt de snelheid langs de
  aanvliegas abrupt en blijvend in.
- **Verdwijnpunt** (vangnet): eindigt de baan abrupt midden in de ROI
  terwijl de bal met worpsnelheid vloog, dan is hij op de plaat geklapt en
  raakte de tracker hem kwijt (stuit richting camera, bewegingsonscherpte).
  Impact = laatste punt. Eindigt de baan aan de rand, dan was het een
  misser: geen impact.

Elke afgewezen baan wordt met reden gelogd in de terminal en getoond in de
HUD van de debugviewer ("laatste afwijzing: ..."). Zo zie je direct WAAROM
een worp niet telde en welke knop je moet bijstellen.

Filters tegen valse detecties: minimale aanvliegsnelheid (handen en
schaduwen zijn te traag), vormcontrole (rond, niet langwerpig), ROI
(alleen het gebied rond de zone telt), en onderdrukking telkens als de
projectie zelf verandert (zodat de software zijn eigen stippen nooit als
bal ziet). Een bal die de plaat mist en op volle snelheid het beeld uit
vliegt, geeft geen impact.

## Doelwit-training via je telefoon

`main.py` start automatisch een webserver. Open op een telefoon in
hetzelfde netwerk het adres dat in de terminal staat
(`http://<ip-van-de-pi>:8080`).

- Tik in de zone: de beamer projecteert daar een bullseye.
- Gooi: binnen `TARGET_RADIUS` van het doel = **RAAK** (groen), anders
  **MIS** met de afstand ernaast in procenten van de zonebreedte.
- Knoppen: *Random spot*, *Doel weg*, *Reset score*.
- Zonder doelwit werkt alles als gewone strike/ball-teller.
- De laatste inslag krijgt op de projectie een grote ring met kruisdraad.

## Debugviewer

```bash
python3 debug_view.py
```
Beamer: alleen zone + blijvende impactstippen (detectie blijft ongestoord).
Tracking-venster: camerabeeld 960x720 met actieve baan (geel), vorige baan
(oranje), blobs (cyaan), zone in cameracoordinaten (groen), ROI (blauw),
impactkruizen (rood) en een HUD.

Toetsen: `1/2` detectiedrempel, `3/4` minimum aanvliegsnelheid (live),
`o` opname naar .avi, `v` Tracking-venster aan/uit, `i` impacts wissen,
`r` achtergrond reset, `q` stop.

## Installatie (Pi 5, Raspberry Pi OS Bookworm of nieuwer)

```bash
sudo apt update
sudo apt install -y python3-opencv python3-picamera2 python3-numpy python3-flask
```

Cameratest: `rpicam-hello --timeout 2000`

## Afstellen (config.py)

| Probleem | Aanpassing |
|---|---|
| Mist zachte worpen | `MIN_INCOMING_SPEED` omlaag (snelheid = piek over de baan) |
| IR-lampjes vallen uit bij wisselend beamerlicht | tape over de LDR-sensortjes op de IR-boards |
| Triggert op snelle handbeweging | `MIN_INCOMING_SPEED` omhoog |
| Detecteert ruis / projectie | `DIFF_THRESHOLD` omhoog |
| Mist de bal als blob | `DIFF_THRESHOLD` omlaag, of belichting checken |
| Beeld te donker (6 ms sluiter) | `CAM_GAIN` omhoog of licht op de plaat |
| Impactpunt net verkeerd | `KINK_ANGLE_DEG` (45) iets omlaag = gevoeliger |
| Telt 1 inslag dubbel | `IMPACT_COOLDOWN_FRAMES` omhoog |
| Doelcirkel te streng/ruim | `TARGET_RADIUS` |
| Zone verkeerde plek/maat | `ZONE_X/Y/W/H` (verhouding 3:4 houden) |
| Beamer andere resolutie | `PROJECTOR_WIDTH/HEIGHT` + herkalibreren |

Live afstellen zonder herstart kan in `debug_view.py` met de toetsen 1 t/m 4.

## Herkalibreren: wanneer?

| Wat is er veranderd | Lens | Homografie |
|---|---|---|
| Beamer/camera/plaat verplaatst | nee | JA |
| Cameraresolutie gewijzigd | JA | JA |
| Schermconfiguratie/resolutie beamer | nee | JA |
| Zone-afmetingen in config | nee | nee |
| Detectieparameters | nee | nee |

## Bekende beperkingen

- De OV5647 haalt ~58 fps op 640x480. Voor matige worpsnelheden ruim
  voldoende; voor echte pitches (100+ km/u) is de Pi Global Shutter Camera
  de juiste upgrade.
- De beamer staat 17 graden gekanteld: zonder keystone-correctie wordt de
  zone een trapezium. Keystone op de beamer zelf aanzetten en de fysieke
  breedte nameten (~43 cm).
- Camera en beamer moeten grofweg vanuit dezelfde kant naar de plaat
  kijken voor een nauwkeurige homografie.
