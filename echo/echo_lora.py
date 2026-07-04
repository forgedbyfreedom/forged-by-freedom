"""
ECHO LoRa / LoRaWAN SDR sniffer — sub-GHz drone control link detector.

────────────────────────────────────────────────────────────────────────
WHY THIS MATTERS

Traditional counter-UAS RF detection (Dedrone RfPatrol, older Aerial
Armor, etc.) is heavily tuned for the crowded 2.4 GHz / 5.8 GHz ISM
bands used by DJI, Autel, Skydio and similar consumer drones. That
coverage is a known blind spot for:

  • Home-built / hobbyist "drop rigs" that use LoRa (Meshtastic-style
    rigs, ExpressLRS long-range, home-brew 915 MHz telemetry) for
    control and telemetry because it goes 5-15 km on a whip antenna
    and cuts through walls and razor wire that 2.4 GHz can't.
  • Commodity Reyax / Semtech SX126x / SX127x modules from Amazon.
    Total build cost: under $80. Encrypted with AES-128 by default
    on LoRaWAN, but the RF preamble is fixed and *the CSS chirp is
    unmistakable* even without decryption.
  • Any drone that uses LoRa strictly for a return-path telemetry beacon
    while control is on 2.4 GHz — a common cartel-adjacent build we've
    seen recovered in multiple prison-drop cases.

ECHO doesn't need to decrypt the payload. Just seeing a LoRa CSS chirp
in the 902-928 MHz band **from inside a facility that has no legitimate
LoRa traffic** is a strong signal that a drone is inbound or in progress.

────────────────────────────────────────────────────────────────────────
BAND / MODULATION QUICK REFERENCE

  Region       ISM band            Common LoRa channels
  US / CA      902-928 MHz         903.9, 904.1, ..., 914.9 MHz (64x 125 kHz)
  EU           863-870 MHz         868.1, 868.3, 868.5 (3x 125 kHz mandatory)
  AS923        920-925 MHz         various
  IN865        865-867 MHz         865.0625, 865.4025, 865.985

  Modulation: Chirp Spread Spectrum (CSS)
  Spreading factors: SF7..SF12
  Bandwidths: 125 / 250 / 500 kHz
  Preamble: 8 upchirps (fixed) → detectable in FFT waterfall without demod

  Drone-relevant sub-GHz variants:
  • ExpressLRS (ELRS): 900 MHz / 2.4 GHz — FLRC + LoRa. Sub-GHz variant
    is the one you'll see on long-range drop rigs.
  • Crossfire (TBS): 868/915 MHz — similar CSS signature.
  • Meshtastic: LoRa on 906.875-923.875 MHz US — same PHY, different LNK.
  • Raw SX126x: whatever the builder configures — usually one of the
    default LoRaWAN uplink channels.

────────────────────────────────────────────────────────────────────────
HARDWARE SPEC — for the deploy PC

Minimum viable (chirp detect only, no demod):
  RTL-SDR Blog V4 dongle                      $30
  ANT500 telescoping antenna (or similar
    900 MHz-tuned whip)                       $20
  USB extension cable, rooftop feed           $15
  → Coverage: entire 902-928 MHz band via
    tuning + FFT sweep, ~2.4 MHz instantaneous bandwidth
  → Sensitivity: -110 dBm typical; enough for a
    drone within ~1-2 km of the antenna.

Recommended for triangulation / demod:
  HackRF One                                  $320
  Discone or log-periodic antenna (300 MHz-1 GHz)   $80
  → 20 MHz instantaneous bandwidth (whole US LoRa
    band captured in one FFT frame)
  → Half-duplex so it can also transmit for TX-based
    counter-response (JAMMING IS FEDERAL FCC VIOLATION —
    do NOT enable transmit without written FCC authorization).

Professional / multi-site:
  Ettus USRP B210 (2×2 MIMO)                  $2,300
  KrakenSDR (5-channel coherent) for direction-
    finding                                   $600
  → Direction-finding the pilot's ground station is
    possible with the KrakenSDR — CSS preamble
    correlates cleanly across channels.

Install location:
  As high as practical, clear line-of-sight to the
  fence line. Sub-GHz doesn't need much elevation
  (~15 ft above ground is fine) but avoid direct
  line-of-sight to the facility's own 900 MHz gear
  (some AMR meters, some legacy paging systems).

────────────────────────────────────────────────────────────────────────
LEGAL / POLICY

  DO   passive receive.  You can lawfully receive any RF signal
       under 47 CFR § 15 unless it's an encrypted radiotelephone
       call (18 USC 2511(g)(i)) — LoRa data traffic is not covered
       by that carveout.

  DO NOT decrypt / attempt to decrypt LoRaWAN traffic without
       authorization. Even though CSS demod is legal, decrypting
       a session key you don't own likely violates CFAA and could
       violate the Wiretap Act. Store raw IQ, log preamble metadata,
       and hand ENCRYPTED PAYLOADS to a warrant-driven analyst.

  DO NOT transmit / jam on these bands without an FCC-issued
       experimental license or a specific statutory authorization
       (rare — federal prisons can get one; state facilities
       generally cannot without state legislature action).

  Retention: keep IQ recordings only long enough to correlate to a
       drone event. Purge on 24h rolling window unless flagged into
       an active case (INTEGRATION_CHECKLIST.md § LoRa retention).

────────────────────────────────────────────────────────────────────────
TO COMPLETE — committee / RF tech must provide:
  1. Hardware selection (RTL-SDR / HackRF / USRP / KrakenSDR)
  2. Antenna location + gain (dBi)
  3. Facility RF audit — list of LEGITIMATE 900 MHz emitters inside
     the fence line (AMR meters, old telemetry, staff radios). These
     get MAC/serial-whitelisted so ECHO doesn't alert on them.
  4. FCC authorization letter IF transmit-side counter-response
     is ever intended (default: NO transmit).
  5. Retention policy — how long to keep raw IQ captures
     (recommended: 24h rolling; flagged captures retained per policy).
  6. Demod stack choice:
       (a) preamble-only detection (this file's default — no external
           deps beyond pyrtlsdr + numpy)
       (b) gr-lora / gr-lora_sdr GNU Radio out-of-tree module for full
           demod (requires GNU Radio 3.10+)
       (c) sx126x_decoder / LoRa-SDR (community forks)
  7. Correlation policy: when to promote a chirp to a drone signal.
     Default: ANY LoRa chirp within ±90s of an acoustic/visual drone
     event fires drone_lora_link_detected.
────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger("echo.lora")


# ── US 902-928 MHz LoRaWAN uplink channel plan (64 x 125 kHz + 8 x 500 kHz)
US_LORAWAN_UPLINK_HZ = [
    int(902_300_000 + 200_000 * i) for i in range(64)
] + [
    int(903_000_000 + 1_600_000 * i) for i in range(8)
]

# EU 863-870 MHz mandatory 3 channels
EU_LORAWAN_UPLINK_HZ = [868_100_000, 868_300_000, 868_500_000]

# ExpressLRS 900 MHz commonly-observed hop channels (US)
ELRS_US_HZ = [
    903_500_000, 906_500_000, 909_500_000, 912_500_000,
    915_500_000, 918_500_000, 921_500_000, 924_500_000,
]

REGION_PLANS = {
    "US915":  US_LORAWAN_UPLINK_HZ + ELRS_US_HZ,
    "EU868":  EU_LORAWAN_UPLINK_HZ,
    "AS923":  [int(920_600_000 + 200_000 * i) for i in range(8)],
    "IN865":  [865_062_500, 865_402_500, 865_985_000],
}


@dataclass
class LoraDetection:
    """One observed LoRa CSS burst.

    A "detection" here is a preamble hit — 8 consecutive upchirps at a
    single center frequency with CSS-consistent bandwidth. Demod is
    OPTIONAL (committee choice above); if run, decoded_payload_hex is
    populated for LoRaWAN uplinks (encrypted — treat as opaque bytes).
    """
    timestamp: datetime
    center_freq_hz: int
    bandwidth_hz: int              # 125_000 | 250_000 | 500_000
    spreading_factor: Optional[int]        # 7..12 (None if not demodded)
    coding_rate: Optional[str]             # "4/5".."4/8" (None if not demodded)
    rssi_dbm: float
    snr_db: float
    duration_ms: float
    # Direction-finding (only with KrakenSDR / multi-antenna arrays):
    source_bearing_deg: Optional[float] = None
    source_bearing_confidence: Optional[float] = None
    # Decoded metadata (only with gr-lora / full demod):
    decoded_dev_addr: Optional[str] = None      # LoRaWAN DevAddr (uplink)
    decoded_fcnt: Optional[int] = None          # frame counter
    decoded_payload_hex: Optional[str] = None   # encrypted — do NOT store beyond retention window
    # Best-guess protocol classification:
    protocol_guess: str = "lora_unknown"        # "lorawan_us915" | "elrs_900" | "meshtastic_us" | "crossfire_868" | "lora_unknown"
    # Match against whitelisted legitimate emitters:
    matches_facility_whitelist: bool = False
    raw: dict = field(default_factory=dict)


class LoraSdrConnector:
    """
    LoRa/LoRaWAN sniffer.

    Default implementation is a PLACEHOLDER that lays out the exact
    interface ECHO expects. Committee's RF tech drops in the real
    pyrtlsdr / SoapySDR / GNU Radio hook.

    The real implementation should:
      1. Open the SDR device (rtlsdr.RtlSdr or SoapySDR.Device)
      2. Set sample rate = 2.4 Msps (RTL-SDR) or 20 Msps (HackRF)
      3. Tune to the low end of the region's LoRa band
      4. Continuously stream IQ into a rolling ring buffer
      5. Every N ms, FFT the buffer and look for CSS preambles
      6. On detect: build a LoraDetection, call self.on_detection()
      7. Sweep-tune across the band on a slow rotation if the SDR's
         instantaneous bandwidth doesn't cover it all at once.

    Preamble detection algorithm (region-agnostic):
      - CSS upchirp: instantaneous frequency ramps linearly from f_center
        - BW/2 to f_center + BW/2 over 2^SF / BW seconds.
      - Take FFT frames at 1 ms intervals.
      - Correlate each frame with a bank of ideal SF7..SF12 upchirps
        (precomputed) at the current tuning.
      - A preamble is 8+ consecutive high-correlation frames whose
        peak frequency walks the expected chirp slope.
      - Convert peak power to RSSI using the SDR's known gain +
        antenna gain calibration constant.

    False-positive suppression:
      - Facility whitelist: precomputed FFT template for known
        legitimate emitters inside the fence line (AMR meters,
        staff radios). Correlate incoming bursts against these
        first; if match > 0.9, DROP.
      - Time-of-day / day-of-week priors: some emitters run on
        cadence. Whitelist by cadence too.
    """

    def __init__(
        self,
        on_detection: Callable[[LoraDetection], None],
        *,
        region: str = "US915",
        device: str = "rtlsdr",
        device_index: int = 0,
        sample_rate_sps: int = 2_400_000,
        gain_db: float = 40.0,
        facility_whitelist_hz: Optional[list[int]] = None,
        min_rssi_dbm: float = -105.0,
        sweep_dwell_sec: float = 2.0,
    ):
        if region not in REGION_PLANS:
            raise ValueError(
                f"unknown region {region!r}; must be one of {sorted(REGION_PLANS)}"
            )
        self.on_detection = on_detection
        self.region = region
        self.channels = REGION_PLANS[region]
        self.device = device                # "rtlsdr" | "hackrf" | "usrp" | "kraken"
        self.device_index = device_index
        self.sample_rate = sample_rate_sps
        self.gain_db = gain_db
        self.facility_whitelist = set(facility_whitelist_hz or [])
        self.min_rssi_dbm = min_rssi_dbm
        self.sweep_dwell = sweep_dwell_sec

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── Lifecycle ────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="echo-lora-sdr", daemon=True
        )
        self._thread.start()
        log.info("LoRa SDR sniffer started (region=%s device=%s ch=%d)",
                 self.region, self.device, len(self.channels))

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        log.info("LoRa SDR sniffer stopped")

    # ── Main loop ────────────────────────────────────────────
    def _run(self) -> None:
        """
        PLACEHOLDER main loop. Replace with real SDR ingest per the
        committee's chosen hardware. The interface — call
        self._emit(LoraDetection(...)) whenever a preamble is confirmed
        — is stable.

        Reference wiring (RTL-SDR, preamble-only):

            from rtlsdr import RtlSdr
            sdr = RtlSdr(device_index=self.device_index)
            sdr.sample_rate = self.sample_rate
            sdr.gain = self.gain_db
            channel_idx = 0
            while not self._stop.is_set():
                sdr.center_freq = self.channels[channel_idx]
                iq = sdr.read_samples(int(self.sample_rate * self.sweep_dwell))
                bursts = self._detect_css_preambles(iq, sdr.center_freq)
                for b in bursts:
                    self._emit(b)
                channel_idx = (channel_idx + 1) % len(self.channels)
            sdr.close()
        """
        while not self._stop.is_set():
            # PLACEHOLDER — real SDR wiring lives here.
            time.sleep(self.sweep_dwell)

    def _emit(self, detection: LoraDetection) -> None:
        """Apply whitelist + threshold, then hand off to correlation."""
        if detection.center_freq_hz in self.facility_whitelist:
            detection.matches_facility_whitelist = True
            log.debug("suppressing whitelisted emitter @ %d Hz",
                      detection.center_freq_hz)
            return
        if detection.rssi_dbm < self.min_rssi_dbm:
            return
        detection.protocol_guess = self._classify(detection)
        try:
            self.on_detection(detection)
        except Exception:
            log.exception("on_detection callback failed")

    # ── Classification ────────────────────────────────────────
    def _classify(self, det: LoraDetection) -> str:
        """Best-guess protocol from center freq + bandwidth."""
        f = det.center_freq_hz
        bw = det.bandwidth_hz
        # Meshtastic uses 250 kHz BW on the LongFast preset by default
        if 906_000_000 <= f <= 924_000_000 and bw == 250_000:
            return "meshtastic_us"
        # ExpressLRS 900 uses distinctive hop pattern; if we see repeated
        # bursts at ELRS_US_HZ channels within tight time windows,
        # classify as ELRS (this hop tracking would live in a stateful
        # classifier — placeholder here).
        if f in ELRS_US_HZ:
            return "elrs_900"
        if 902_000_000 <= f <= 928_000_000 and bw == 125_000:
            return "lorawan_us915"
        if 863_000_000 <= f <= 870_000_000:
            return "lorawan_eu868"
        return "lora_unknown"


# ── Correlation-engine bridge ─────────────────────────────────────
def lora_detection_to_event(det: LoraDetection):
    """
    Turn a LoraDetection into an echo_correlation.Event with source
    'lora_detection'. Wire this up in echo_multi.py:

        lora = LoraSdrConnector(
            on_detection=lambda d: engine.ingest(lora_detection_to_event(d))
        )
        lora.start()

    The correlation engine looks for lora_detection events within ±90s
    of a drone_audio / drone_visual event and fires
    drone_lora_link_detected (see DEFAULT_WEIGHTS in echo_correlation.py).
    """
    from echo_correlation import Event
    return Event(
        source="lora_detection",
        timestamp=det.timestamp,
        payload={
            "center_freq_hz": det.center_freq_hz,
            "bandwidth_hz": det.bandwidth_hz,
            "spreading_factor": det.spreading_factor,
            "rssi_dbm": det.rssi_dbm,
            "snr_db": det.snr_db,
            "protocol_guess": det.protocol_guess,
            "source_bearing_deg": det.source_bearing_deg,
            "decoded_dev_addr": det.decoded_dev_addr,
            "duration_ms": det.duration_ms,
        },
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    def _print(d: LoraDetection) -> None:
        print(f"[LoRa] {d.timestamp.isoformat()} f={d.center_freq_hz/1e6:.3f}MHz "
              f"BW={d.bandwidth_hz//1000}kHz SF{d.spreading_factor} "
              f"RSSI={d.rssi_dbm:.1f}dBm proto={d.protocol_guess}")
    c = LoraSdrConnector(on_detection=_print, region="US915")
    c.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        c.stop()
