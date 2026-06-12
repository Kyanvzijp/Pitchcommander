"""
Impact-detectie v3: trajectvolging met omkeerpunt-analyse.

WAAROM: de camera kijkt schuin tegen de vliegbaan aan. Een bal die in beeld
verschijnt is nog onderweg; zijn beeldpositie wijst dan NIET naar de plek op
de muur (parallax). Pas op het moment van contact ligt de bal op het
muurvlak en klopt de homografie-mapping exact.

HOE: de bal wordt frame voor frame gevolgd als bewegende blob. De impact is
het punt waar de baan fysiek omkeert:
  - knik       : de bewegingsrichting verandert abrupt (> KINK_ANGLE_DEG),
                 want de bal stuit terug of slaat om naar vallen, terwijl
                 de aanvliegbaan zelf vloeiend kromt. Het knikpunt is de
                 impact. Dit is het primaire criterium.
  - instorting : vangnet voor een dode klap zonder meetbare nabeweging:
                 de snelheid langs de aanvliegas zakt blijvend onder
                 STOP_SPEED_FACTOR x de aanvliegsnelheid; de impact is dan
                 het verste punt binnen dat venster.
  - verdwijnpunt: de baan eindigt abrupt MIDDEN in de ROI terwijl de bal
                 met worpsnelheid vloog. Dan is de bal op de plaat geklapt
                 en raakte de tracker hem kwijt (stuit richting camera,
                 bewegingsonscherpte, mislukte koppeling). Impact = het
                 laatste punt plus een halve stap. Eindigt de baan aan de
                 rand van ROI of beeld, dan vloog de bal eruit: geen impact.

Bij elke afgewezen baan wordt de reden gelogd (terminal en debug-HUD).

Een baan die zonder omkeren met volle snelheid het beeld verlaat (bal die
de plaat volledig mist) levert GEEN impact op. Langzame objecten (handen,
schaduwen) halen MIN_INCOMING_SPEED niet en tellen nooit mee. Vormfilters
(rondheid, aspect ratio) en het ROI-masker blijven van kracht, net als de
onderdrukking na projectie-wijzigingen.
"""
import math
import cv2
import numpy as np
import config


class ImpactDetector:
    def __init__(self, roi_mask=None):
        """roi_mask: uint8 masker in cameraresolutie (255 = meetellen),
        of None om het hele beeld te gebruiken."""
        self.bg = None
        self.cooldown = 0
        self.suppress = 0
        self.roi_mask = roi_mask
        self._track = None       # lijst van (x, y) posities
        self._missing = 0
        self._busy_hold = 0      # poort dicht na drukte (persoon in beeld)
        # Voor visualisatie (debug_view.py): laatst gedetecteerde blobs en
        # de laatst afgesloten baan. Puur lezen, geen invloed op de logica.
        self.last_blobs = []
        self.last_track = []
        self.last_reject = None   # waarom de laatste baan geen impact gaf
        self._shape = None
        # Diagnostiek, per statusvenster uit te lezen met pop_diag():
        # waar sterft het signaal? (verschilwaarde, contourgrootte,
        # rondheid, onderdrukking)
        self.diag = {"max_diff": 0.0, "contours": 0, "max_area": 0.0,
                     "best_circ": 0.0, "suppressed": 0, "busy": 0}

    # ----- publiek -----

    def reset_background(self):
        self.bg = None
        self._track = None
        self._missing = 0
        self._busy_hold = 0
        self.last_reject = None

    def pop_diag(self):
        """Diagnostiek van het afgelopen venster teruggeven en resetten."""
        d = dict(self.diag)
        for k in self.diag:
            self.diag[k] = 0.0 if isinstance(self.diag[k], float) else 0
        return d

    def suppress_frames(self, n=None):
        """Roep dit aan direct nadat de projectie verandert."""
        self.suppress = max(self.suppress,
                            n if n is not None else
                            config.SUPPRESS_AFTER_DRAW_FRAMES)

    def process(self, frame):
        """Geeft (cx, cy) van een BEVESTIGDE impact terug, of None.
        frame mag BGR (h,w,3) of al grijswaarden (h,w) zijn."""
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        self._shape = gray.shape

        if self.bg is None:
            self.bg = gray.astype(np.float32)
            return None

        if self.suppress > 0:
            self.diag["suppressed"] += 1
        blobs, fg_mask = self._find_ball_blobs(gray)
        self.last_blobs = blobs
        if len(blobs) > config.MAX_SIMULTANEOUS_BLOBS:
            # Te veel gelijktijdige blobs = persoon/arm in beeld. Poort
            # dicht, en even dicht HOUDEN: een wegtrekkende arm zakt kort
            # onder de blobdrempel en mag dan geen valse baan starten.
            self._busy_hold = config.BUSY_HOLD_FRAMES
            self.last_reject = (f"te druk in beeld ({len(blobs)} blobs "
                                f"tegelijk): persoon of arm?")
        if self._busy_hold > 0:
            self.diag["busy"] += 1
            self._busy_hold -= 1
            self._track = None
            self._missing = 0
            impact = None
        else:
            impact = self._update_track(blobs)

        # Achtergrond bijwerken: snel na een projectie-verandering, anders
        # langzaam en niet over voorgrond-objecten heen.
        if self.suppress > 0:
            cv2.accumulateWeighted(gray, self.bg,
                                   config.BG_FAST_LEARNING_RATE)
        else:
            learn_mask = cv2.bitwise_not(fg_mask)
            cv2.accumulateWeighted(gray, self.bg,
                                   config.BG_LEARNING_RATE, mask=learn_mask)

        if self.suppress > 0:
            self.suppress -= 1
            self._track = None
            return None
        if self.cooldown > 0:
            self.cooldown -= 1
            return None
        if impact is not None:
            self.cooldown = config.IMPACT_COOLDOWN_FRAMES
        return impact

    # ----- intern: blob-detectie -----

    def _find_ball_blobs(self, gray):
        """Bal-achtige blobs (rond, juiste grootte) in de ROI.
        Geeft (lijst van zwaartepunten, voorgrondmasker) terug."""
        diff = cv2.absdiff(gray, self.bg.astype(np.uint8))
        if self.roi_mask is not None:
            diff = cv2.bitwise_and(diff, diff, mask=self.roi_mask)
        self.diag["max_diff"] = max(self.diag["max_diff"],
                                    float(diff.max()))
        _, mask = cv2.threshold(diff, config.DIFF_THRESHOLD, 255,
                                cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                np.ones((3, 3), np.uint8))
        mask = cv2.dilate(mask, None, iterations=2)

        blobs = []
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        self.diag["contours"] += len(contours)
        for c in contours:
            area = cv2.contourArea(c)
            self.diag["max_area"] = max(self.diag["max_area"], float(area))
            if not (config.MIN_BLOB_AREA <= area <= config.MAX_BLOB_AREA):
                continue
            per = cv2.arcLength(c, True)
            if per <= 0:
                continue
            circ = 4.0 * math.pi * area / (per * per)
            self.diag["best_circ"] = max(self.diag["best_circ"], circ)
            if circ < config.MIN_CIRCULARITY:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if max(w, h) / max(1, min(w, h)) > config.MAX_ASPECT_RATIO:
                continue
            M = cv2.moments(c)
            if M["m00"] > 0:
                blobs.append((M["m10"] / M["m00"], M["m01"] / M["m00"]))
        return blobs, mask

    # ----- intern: trajectvolging -----

    def _update_track(self, blobs):
        if self._track is None:
            if blobs:
                # Start een nieuwe baan op de grootste kans: eerste blob.
                self._track = [blobs[0]]
                self._missing = 0
            return None

        # Voorspel de volgende positie en zoek de dichtstbijzijnde blob
        # binnen een snelheidsafhankelijk venster.
        px, py = self._track[-1]
        if len(self._track) >= 2:
            vx = px - self._track[-2][0]
            vy = py - self._track[-2][1]
        else:
            vx = vy = 0.0
        pred = (px + vx, py + vy)
        speed = math.hypot(vx, vy)
        # Koppelvenster schaalt met de beeldbreedte: op hogere resoluties
        # verplaatst een bal meer pixels per frame. Bij een baan van 1 punt
        # is er nog geen snelheid bekend, dan extra ruim zoeken.
        base_gate = max(80.0, 0.15 * (self._shape[1] if self._shape
                                      else 640))
        if len(self._track) == 1:
            gate = 2.0 * base_gate
        else:
            gate = max(base_gate, 2.5 * speed)

        best = None
        best_d = gate
        for (bx, by) in blobs:
            # Zoek zowel rond de voorspelde als rond de laatste positie:
            # bij een terugstuit klopt de vooruit-voorspelling niet meer.
            d = min(math.hypot(bx - pred[0], by - pred[1]),
                    math.hypot(bx - px, by - py))
            if d < best_d:
                best_d = d
                best = (bx, by)

        if best is not None:
            self._track.append(best)
            self._missing = 0
            if len(self._track) > config.TRACK_MAX_LEN:
                return self._finalize(vanished=False)
            # Online-check: is de terugstuit al zichtbaar? Dan hoeven we
            # niet te wachten tot de bal uit beeld is.
            return self._check_reversal_online()
        else:
            self._missing += 1
            if self._missing > config.TRACK_MISSING_MAX:
                return self._finalize(vanished=True)
            return None

    def _incoming(self, p, disp):
        """Aanvliegrichting en snelheidsmaat van een baan.

        Snelheid: het maximum van een 2-frames lopend gemiddelde, dus het
        SNELSTE stuk van de baan telt. Een bal die traag in beeld komt en
        versnelt wordt zo niet afgekeurd op zijn eerste stapjes.
        Richting: van het eerste punt naar het midden van de baan (de
        aanvliegpoot), stabieler dan alleen de eerste paar stapjes."""
        speeds = np.hypot(disp[:, 0], disp[:, 1])
        if len(speeds) >= 2:
            roll = (speeds[:-1] + speeds[1:]) / 2.0
            speed = float(roll.max())
        else:
            speed = float(speeds.max())
        mid = max(2, min(len(p) - 1, len(p) // 2))
        v = p[mid] - p[0]
        n = float(np.hypot(*v))
        if n < 1e-6:
            v = disp[:min(3, len(disp))].mean(axis=0)
            n = float(np.hypot(*v)) or 1e-6
        return v / n, speed

    def _analyze(self, pts):
        """Geeft het impactpunt of None.

        Primair: zoek een KNIK in de baan, een abrupte richtingsverandering
        tussen twee opeenvolgende verplaatsingen. De aanvliegbaan kromt
        vloeiend; de impact (terugstuit of omslaan naar vallen) geeft een
        scherpe hoek. Het knikpunt is het impactpunt.

        Vangnet: dode klap zonder meetbare nabeweging. De snelheid langs de
        aanvliegas stort blijvend in; impact is het verste punt binnen dat
        instortingsvenster."""
        if len(pts) < 3:
            self.last_reject = f"baan te kort ({len(pts)} punten)"
            return None
        p = np.asarray(pts, dtype=np.float64)
        disp = np.diff(p, axis=0)

        u, speed_in = self._incoming(p, disp)
        if speed_in < config.MIN_INCOMING_SPEED:
            self.last_reject = (f"te traag voor worp ({speed_in:.0f} "
                                f"px/frame piek, minimum "
                                f"{config.MIN_INCOMING_SPEED})")
            return None
        s = (p - p[0]) @ u

        # --- Primair: knik in de baan ---
        cos_kink = math.cos(math.radians(config.KINK_ANGLE_DEG))
        norms = np.hypot(disp[:, 0], disp[:, 1])
        for i in range(len(disp) - 1):
            na, nb = norms[i], norms[i + 1]
            if na < 3.0 or nb < 3.0:
                continue  # jitter, geen echte beweging
            cosang = float(disp[i] @ disp[i + 1]) / (na * nb)
            if cosang < cos_kink and s[i + 1] >= config.MIN_APPROACH_PX:
                self.last_reject = None
                return (float(p[i + 1][0]), float(p[i + 1][1]))

        # --- Vangnet: blijvende snelheidsinstorting langs de aanvliegas ---
        ds = np.diff(s)
        thr = config.STOP_SPEED_FACTOR * speed_in
        # Afsluitende trage staart zoeken: de baan moet eindigen in
        # aanhoudende vertraging (een trage START die daarna versnelt is
        # juist normaal voor een binnenkomende bal).
        j = len(ds)
        while j > 0 and ds[j - 1] < thr:
            j -= 1
        if j == len(ds) or len(ds) - j < 2:
            self.last_reject = "geen knik en geen aanhoudende vertraging"
            return None
        if j == 0 or ds[:j].max() < thr:
            self.last_reject = "nooit op worpsnelheid langs de aanvliegas"
            return None
        win_end = min(j + 4, len(s))
        k = j + int(np.argmax(s[j:win_end]))
        if s[k] < config.MIN_APPROACH_PX:
            self.last_reject = (f"te korte aanloop ({s[k]:.0f} px "
                                f"langs aanvliegas)")
            return None
        self.last_reject = None
        return (float(p[k][0]), float(p[k][1]))

    def _check_reversal_online(self):
        impact = self._analyze(self._track)
        if impact is not None:
            self.last_track = list(self._track)
            self._track = None
            self._missing = 0
        return impact

    def _finalize(self, vanished=False):
        pts = self._track or []
        impact = self._analyze(pts)
        if impact is None and vanished:
            impact = self._vanish_impact(pts)
        if pts:
            self.last_track = list(pts)
        if impact is None and len(pts) >= 4 and self.last_reject:
            print(f"[detector] baan afgewezen ({len(pts)} punten): "
                  f"{self.last_reject}")
        self._track = None
        self._missing = 0
        return impact

    def _inside(self, pt, marge=10):
        """Ligt het punt binnen beeld en (indien gezet) binnen de ROI?"""
        x, y = int(round(pt[0])), int(round(pt[1]))
        if self._shape is None:
            return False
        h, w = self._shape
        if not (marge <= x < w - marge and marge <= y < h - marge):
            return False
        if self.roi_mask is not None:
            return bool(self.roi_mask[y, x])
        return True

    def _vanish_impact(self, pts):
        """Derde criterium: de baan eindigt abrupt midden in de ROI terwijl
        de bal met worpsnelheid vloog. Dan is de bal op de plaat geklapt en
        kwijtgeraakt. Impact = laatste punt + halve laatste stap. Eindigt
        de baan aan de rand (bal vloog eruit), dan geen impact."""
        if len(pts) < 3:
            return None
        p = np.asarray(pts, dtype=np.float64)
        disp = np.diff(p, axis=0)
        u, speed_in = self._incoming(p, disp)
        if speed_in < config.MIN_INCOMING_SPEED:
            self.last_reject = (f"te traag voor worp "
                                f"({speed_in:.0f} px/frame piek)")
            return None
        s = (p - p[0]) @ u
        if s[-1] < config.MIN_APPROACH_PX:
            self.last_reject = (f"te korte aanloop "
                                f"({s[-1]:.0f} px langs aanvliegas)")
            return None
        v_last = p[-1] - p[-2]
        volgend = p[-1] + v_last
        if not self._inside(p[-1]) or not self._inside(volgend):
            self.last_reject = "baan verliet ROI/beeld (misser)"
            return None
        self.last_reject = None
        imp = p[-1] + 0.5 * v_last
        return (float(imp[0]), float(imp[1]))

    @property
    def track(self):
        """Kopie van de actieve baan, voor visualisatie."""
        return list(self._track) if self._track else []


def build_roi_mask(H, cam_w, cam_h):
    """Bouwt een cameramasker van de slagzone plus marge, via de inverse
    homografie (beamer -> camera). Geeft uint8 masker (255 = meetellen)."""
    margin = config.ROI_MARGIN_PX
    zone_pts = np.array([
        [config.ZONE_X - margin, config.ZONE_Y - margin],
        [config.ZONE_X + config.ZONE_W + margin, config.ZONE_Y - margin],
        [config.ZONE_X + config.ZONE_W + margin,
         config.ZONE_Y + config.ZONE_H + margin],
        [config.ZONE_X - margin, config.ZONE_Y + config.ZONE_H + margin],
    ], dtype=np.float32).reshape(-1, 1, 2)

    H_inv = np.linalg.inv(H)
    cam_pts = cv2.perspectiveTransform(zone_pts, H_inv).reshape(-1, 2)

    mask = np.zeros((cam_h, cam_w), np.uint8)
    cv2.fillPoly(mask, [cam_pts.astype(np.int32)], 255)
    return mask
