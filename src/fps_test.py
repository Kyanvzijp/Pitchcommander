"""
Meet de werkelijk gehaalde framerate, verwerkingstijd EN beeldhelderheid.

Draai dit na elke wijziging aan CAM_WIDTH/HEIGHT/FPS/EXPOSURE of aan de
belichting (IR-lampjes, kamerlicht) om te zien wat je opstelling echt
haalt. Geen vensters nodig, werkt ook via SSH.

  python3 fps_test.py
"""
import time
import numpy as np
import config
from camera import Camera
from lens import LensCorrector
from detector import ImpactDetector

DUUR = 5.0  # seconden meten


def main():
    print(f"Config: {config.CAM_WIDTH}x{config.CAM_HEIGHT} @ "
          f"{config.CAM_FPS} fps gevraagd, sluitertijd "
          f"{config.CAM_EXPOSURE_US or 'auto'} us")

    cam = Camera(gray=True)
    lens = LensCorrector()
    det = ImpactDetector()

    # Opwarmen.
    for _ in range(10):
        cam.read()

    # 1. Pure capture-snelheid.
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < DUUR:
        ok, frame = cam.read()
        if ok:
            n += 1
    fps_capture = n / DUUR

    # 2. Volledige pijplijn (capture + lenscorrectie + detectie),
    #    en ondertussen de beeldhelderheid bemonsteren.
    proc_times = []
    helderheden = []
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < DUUR:
        ok, frame = cam.read()
        if not ok:
            continue
        t1 = time.perf_counter()
        det.process(lens.correct(frame))
        proc_times.append(time.perf_counter() - t1)
        helderheden.append(float(frame.mean()))
        n += 1
    fps_pipeline = n / DUUR
    laatste = frame
    cam.release()

    p = np.array(proc_times) * 1000.0
    print(f"\nCapture:   {fps_capture:5.1f} fps")
    print(f"Pijplijn:  {fps_pipeline:5.1f} fps "
          f"(verwerking {p.mean():.1f} ms gem, {p.max():.1f} ms piek)")
    print(f"Lenscorrectie actief: {'ja' if lens.enabled else 'NEE'}")

    # --- Helderheidsbeoordeling ---
    gem = float(np.mean(helderheden))
    # Donkerste en lichtste 1% van het laatste frame: zicht op contrast
    # en overbelichting.
    p1, p99 = np.percentile(laatste, (1, 99))
    print(f"\nHelderheid: gemiddeld {gem:.0f}/255 "
          f"(donkerste 1%: {p1:.0f}, lichtste 1%: {p99:.0f})")
    if gem < 35:
        print("  -> TE DONKER voor betrouwbare detectie. Opties: IR-lampjes"
              "\n     monteren/controleren (LDR-sensortjes afschermen of"
              "\n     potmeter bijdraaien), CAM_GAIN omhoog (max ~10), of"
              "\n     als laatste CAM_EXPOSURE_US naar 8000.")
    elif gem < 60:
        print("  -> Aan de donkere kant maar werkbaar. Test met"
              "\n     debug_view.py of de bal als blob wordt opgepikt;"
              "\n     IR-verlichting geeft hier nog duidelijke winst.")
    elif gem <= 170:
        print("  -> GOED. Ruim voldoende licht voor de detectie.")
    else:
        print("  -> Erg licht; check of de lichtste delen niet dichtslaan"
              f"\n     (lichtste 1% = {p99:.0f}; bij 255 verdwijnt de bal"
              "\n     in overbelichting). Zo ja: CAM_GAIN omlaag.")
    if p99 - p1 < 30:
        print("  -> LET OP: weinig contrast in beeld; detectie kan moeite"
              "\n     krijgen de bal van de plaat te onderscheiden.")

    budget = 1000.0 / config.CAM_FPS
    if p.mean() > budget * 0.8:
        print(f"\nLet op: verwerking ({p.mean():.1f} ms) nadert het "
              f"framebudget ({budget:.1f} ms). Overweeg een lagere "
              f"resolutie of minder zware filters.")
    else:
        print(f"\nVerwerking past ruim binnen het framebudget "
              f"({budget:.1f} ms per frame). De camera is de beperkende "
              f"factor, niet de software.")


if __name__ == "__main__":
    main()
