"""
Meet de werkelijk gehaalde framerate en verwerkingstijd op de Pi.

Draai dit na elke wijziging aan CAM_WIDTH/HEIGHT/FPS/EXPOSURE om te zien
wat je opstelling echt haalt. Geen vensters nodig, werkt ook via SSH.

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

    # 2. Volledige pijplijn (capture + lenscorrectie + detectie).
    proc_times = []
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < DUUR:
        ok, frame = cam.read()
        if not ok:
            continue
        t1 = time.perf_counter()
        det.process(lens.correct(frame))
        proc_times.append(time.perf_counter() - t1)
        n += 1
    fps_pipeline = n / DUUR
    cam.release()

    p = np.array(proc_times) * 1000.0
    print(f"\nCapture:   {fps_capture:5.1f} fps")
    print(f"Pijplijn:  {fps_pipeline:5.1f} fps "
          f"(verwerking {p.mean():.1f} ms gem, {p.max():.1f} ms piek)")
    print(f"Lenscorrectie actief: {'ja' if lens.enabled else 'NEE'}")

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
