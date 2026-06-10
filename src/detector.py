"""
Impact-detectie v2, gebouwd tegen valse positieven.

Een blob telt pas als inslag wanneer hij ALLE checks doorstaat:

1. ROI-masker      : alleen het gebied van de slagzone (plus marge) telt.
                     Alles daarbuiten in het camerabeeld wordt genegeerd.
2. Dubbele diff    : de verandering moet zichtbaar zijn t.o.v. het
                     achtergrondmodel EN t.o.v. het vorige frame. Een echte
                     inslag verschijnt plotseling; langzame veranderingen
                     (licht, schaduw die opschuift) vallen af.
3. Vormfilter      : de blob moet rond genoeg zijn (circularity) en niet
                     langwerpig (aspect ratio). Armen en schaduwen vallen af.
4. Transient-check : een inslag is kort. Een kandidaat die langer dan
                     TRANSIENT_MAX_FRAMES op dezelfde plek blijft, is een
                     hand of object en wordt verworpen. De impact wordt pas
                     bevestigd zodra de kandidaat weer VERDWENEN is.
5. Onderdrukking   : nadat de projectie zelf verandert (nieuwe stip), wordt
                     detectie kort onderdrukt en leert de achtergrond snel
                     bij, zodat de software zijn eigen projectie niet ziet
                     als inslag.

Let op: de transient-check voegt 2 a 4 frames vertraging toe (~100 ms op
30 fps). Dat is onzichtbaar voor de gebruiker maar filtert vrijwel alle ruis.
"""
import math
import cv2
import numpy as np
import config


class _Candidate:
    __slots__ = ("x", "y", "first_x", "first_y", "age", "seen_this_frame")

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.first_x = x   # impactpunt = plek van eerste verschijning
        self.first_y = y
        self.age = 1
        self.seen_this_frame = True


class ImpactDetector:
    def __init__(self, roi_mask=None):
        """roi_mask: uint8 masker in cameraresolutie (255 = meetellen),
        of None om het hele beeld te gebruiken."""
        self.bg = None
        self.prev_gray = None
        self.cooldown = 0
        self.suppress = 0
        self.roi_mask = roi_mask
        self.candidates = []

    # ----- publiek -----

    def reset_background(self):
        self.bg = None
        self.prev_gray = None
        self.candidates.clear()

    def suppress_frames(self, n=None):
        """Roep dit aan direct nadat de projectie verandert."""
        self.suppress = max(self.suppress,
                            n if n is not None else
                            config.SUPPRESS_AFTER_DRAW_FRAMES)

    def process(self, frame_bgr):
        """Geeft (cx, cy) van een BEVESTIGDE impact terug, of None."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.bg is None:
            self.bg = gray.astype(np.float32)
            self.prev_gray = gray
            return None

        new_blobs, present_mask = self._find_blobs(gray)
        impact = self._update_candidates(new_blobs, present_mask)

        # Achtergrond bijwerken, maar NIET op plekken waar nu iets voor de
        # plaat staat (anders 'leert' de achtergrond een hand of object aan
        # en geeft het weggaan daarvan een valse trigger). Na een projectie-
        # verandering juist overal snel bijleren.
        if self.suppress > 0:
            cv2.accumulateWeighted(gray, self.bg,
                                   config.BG_FAST_LEARNING_RATE)
        else:
            learn_mask = cv2.bitwise_not(present_mask)
            cv2.accumulateWeighted(gray, self.bg,
                                   config.BG_LEARNING_RATE, mask=learn_mask)
        self.prev_gray = gray

        if self.suppress > 0:
            self.suppress -= 1
            return None
        if self.cooldown > 0:
            self.cooldown -= 1
            return None
        if impact is not None:
            self.cooldown = config.IMPACT_COOLDOWN_FRAMES
        return impact

    # ----- intern -----

    def _find_blobs(self, gray):
        """Geeft (new_blobs, present_mask) terug.

        new_blobs    : zwaartepunten van blobs die plotseling EN nieuw zijn
                       (bg-diff EN frame-diff), na vormfilters. Hieruit
                       ontstaan nieuwe kandidaten.
        present_mask : uint8 masker van alles dat NU afwijkt van de
                       achtergrond (alleen bg-diff). Hiermee volgen we
                       bestaande kandidaten: een hand die stilligt beweegt
                       niet meer (geen frame-diff) maar is er nog wel."""
        diff_bg = cv2.absdiff(gray, self.bg.astype(np.uint8))
        diff_fr = cv2.absdiff(gray, self.prev_gray)

        _, m_bg = cv2.threshold(diff_bg, config.DIFF_THRESHOLD, 255,
                                cv2.THRESH_BINARY)
        _, m_fr = cv2.threshold(diff_fr, config.FRAME_DIFF_THRESHOLD, 255,
                                cv2.THRESH_BINARY)
        if self.roi_mask is not None:
            m_bg = cv2.bitwise_and(m_bg, self.roi_mask)

        m_bg = cv2.morphologyEx(m_bg, cv2.MORPH_OPEN,
                                np.ones((3, 3), np.uint8))
        m_bg = cv2.dilate(m_bg, None, iterations=2)

        # Plotseling (frame-diff) en afwijkend van achtergrond: beide nodig
        # om een NIEUWE kandidaat te starten.
        mask_new = cv2.bitwise_and(m_bg, m_fr)

        new_blobs = []
        contours, _ = cv2.findContours(mask_new, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if not (config.MIN_BLOB_AREA <= area <= config.MAX_BLOB_AREA):
                continue
            # Rondheid.
            per = cv2.arcLength(c, True)
            if per <= 0:
                continue
            circularity = 4.0 * math.pi * area / (per * per)
            if circularity < config.MIN_CIRCULARITY:
                continue
            # Aspect ratio.
            x, y, w, h = cv2.boundingRect(c)
            ratio = max(w, h) / max(1, min(w, h))
            if ratio > config.MAX_ASPECT_RATIO:
                continue
            M = cv2.moments(c)
            if M["m00"] > 0:
                new_blobs.append((M["m10"] / M["m00"], M["m01"] / M["m00"]))
        return new_blobs, m_bg

    def _update_candidates(self, new_blobs, present_mask):
        """Bestaande kandidaten blijven leven zolang het aanwezigheids-
        masker op hun plek nog 'aan' staat (ook als ze stilliggen). Nieuwe
        kandidaten ontstaan alleen uit new_blobs. Een impact wordt bevestigd
        zodra een KORTLEVENDE kandidaat weer verdwenen is."""
        h, w = present_mask.shape

        # 1. Bestaande kandidaten: nog aanwezig volgens het bg-masker?
        for cand in self.candidates:
            x = min(max(int(cand.x), 0), w - 1)
            y = min(max(int(cand.y), 0), h - 1)
            r = 8
            patch = present_mask[max(0, y - r):y + r, max(0, x - r):x + r]
            cand.seen_this_frame = bool(patch.any())
            if cand.seen_this_frame:
                cand.age += 1

        # 2. Nieuwe blobs die niet bij een bestaande kandidaat horen,
        #    worden nieuwe kandidaten.
        max_d2 = config.CANDIDATE_MATCH_DIST ** 2
        for (bx, by) in new_blobs:
            matched = False
            for cand in self.candidates:
                d2 = (cand.x - bx) ** 2 + (cand.y - by) ** 2
                if d2 < max_d2:
                    cand.x, cand.y = bx, by
                    cand.seen_this_frame = True
                    matched = True
                    break
            if not matched:
                self.candidates.append(_Candidate(bx, by))

        # 3. Verdwenen kandidaten beoordelen.
        impact = None
        survivors = []
        for cand in self.candidates:
            if cand.seen_this_frame:
                survivors.append(cand)
            else:
                # Kandidaat is weg. Kort geleefd = echte inslag (transient).
                # Lang geleefd = hand/object dat vertrok: negeren.
                if 1 <= cand.age <= config.TRANSIENT_MAX_FRAMES \
                        and impact is None:
                    impact = (cand.first_x, cand.first_y)
        self.candidates = survivors
        return impact


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
