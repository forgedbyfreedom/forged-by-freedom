# ECHO Field Calibration Guide

Every tunable in ECHO lives in [`config.yaml`](./config.yaml). This guide
explains what each knob does, safe ranges, common false-positive causes
(helicopters, HVAC, lawn equipment, mains hum), and a step-by-step
procedure to tune a fresh install without chasing your tail.

Read the whole thing once before touching anything — knobs interact.

---

## Contents

1. [Quick reference — precedence](#quick-reference--precedence)
2. [Quick diagnostic decision tree](#quick-diagnostic-decision-tree)
3. [The acoustic detector — `detector:`](#the-acoustic-detector--detector)
4. [Reference drone acoustic signatures](#reference-drone-acoustic-signatures)
5. [Correlation engine — `correlation:`](#correlation-engine--correlation)
6. [LoRa / LoRaWAN SDR — `lora:`](#lora--lorawan-sdr--lora)
7. [Acoustic Lily Pads — `lily_pads:`](#acoustic-lily-pads--lily_pads)
8. [Step-by-step field-tuning procedure](#the-step-by-step-field-tuning-procedure)
9. [Diagnostic recipes — grep, curl, tail](#diagnostic-recipes--grep-curl-tail)
10. [Microphone placement, wind, weather](#microphone-placement-wind-weather)
11. [Environment-variable overrides](#environment-variable-overrides--the-field-debug-pattern)
12. [Verifying a change is actually live](#verifying-a-change-is-actually-live)
13. [Fault tolerance & health — `health:`](#fault-tolerance--health--health--fusion-behavior)
14. [Pipeline state machine — `state_machine:`](#pipeline-state-machine--state_machine)
15. [Correlation weight retuning workflow](#correlation-weight-retuning-workflow)
16. [Multi-site fleet tuning](#multi-site-fleet-tuning)
17. [Emergency: turn off the noisy alerts](#emergency-turn-off-the-noisy-alerts)
18. [Troubleshooting matrix](#troubleshooting-matrix)
19. [Appendix — reference numbers](#appendix--reference-numbers)

---

## Quick diagnostic decision tree

Fresh install acting weird? Follow this **before** touching any knob.
Every question has a concrete check next to it.

```
Is ECHO producing detections at all?
├── NO  → check /health (or `ps` for the process) → check /subsystems
│         → is 'acoustic' OK? if not, check echo_rtsp.py error log
│         → is min_level_db gating everything? tail the log for gate events
│
└── YES → How many per hour?
    ├── 0-2/hr (typical baseline)  → healthy. Move to real-drone verify.
    ├── 3-5/hr                      → mild FP. Raise harmonic_snr_db 2 dB.
    ├── 5-20/hr                     → significant FP. Run § "Diagnostic recipes"
    │                                 to identify source (helicopters? mowers?
    │                                 HVAC? sirens?) before touching knobs.
    └── 20+/hr                      → broken. Do NOT tune — investigate first.
                                      Common causes: mic ungrounded (60 Hz
                                      smear), mic in HVAC path, sample rate
                                      mismatched to hardware.
```

If ECHO IS producing detections but they're not correlating:

```
Correlation report says decision_declined=True?
├── YES → check `dropped_subsystems` — those are DOWN. Fix them, or
│         lower `correlation.min_viable_sensors`.
│
└── NO  → check correlation weights. If top candidate scores ~0.05-0.15
          across the board, your weights are too flat. See § "Correlation
          weight retuning workflow" for the A/B loop.
```

---

## Quick reference — precedence

Later overrides earlier:

1. Baked defaults in `echo_config.py` (`DEFAULTS`)
2. `config.yaml` next to the code
3. `ECHO_*` environment variables (nested with `__`, e.g.
   `ECHO_DETECTOR__MIN_LEVEL_DB=-42`)
4. Per-run overrides passed to `echo_config.load(overrides={...})`

The API reports the effective detector config at `GET /status`.

---

## The acoustic detector — `detector:`

### `sample_rate_hz` (default `44100`)
Standard audio rate. Don't change unless your capture card requires it
(RTSP-decoded audio from `echo_rtsp.py` gets forcibly resampled to 44100
anyway).

### `block_samples` (default `16384`, ~370 ms @ 44.1 kHz)
FFT window size. **Bigger = better frequency resolution but slower
response.** Halving to 8192 doubles temporal resolution at the cost of
frequency-bin width (~5.4 Hz → ~10.8 Hz). Larger drone rotors (Mavic 3,
Autel) benefit from bigger blocks (harmonics further apart); micro
quads want smaller blocks.

Safe range: `4096` → `32768` (power of 2 only).

### `harmonics` (default `[1, 2, 3, 4, 5, 6]`)
Which harmonic multiples of the blade-pass fundamental to look for.
Adding harmonic 7 or 8 catches fewer drones (energy drops off) but is
more specific if false positives from vehicles are a problem.

### `harmonic_snr_db` (default `8.0`)
Each harmonic must be this many dB above the local noise floor to count.

- **Raise to 10-12 dB** if lawn equipment / HVAC gives false positives.
- **Lower to 5-6 dB** if you're missing quiet distant quads (accept
  more false positives).

This is the single most important detector knob. Only move it in ±2 dB
steps and re-run the calibration procedure after each change.

### `mains_hz` / `mains_width_hz` (default `60` / `5`)
Notches out the mains hum. Use `50` in Europe / most of Asia, `60` in
North America. Widen (`mains_width_hz: 10`) if the site has bad
grounding and you see 55-65 Hz smearing in the spectrogram.

### `min_level_db` (default `-45.0`)
Absolute audio level gate. Anything quieter is treated as silence and
skipped (no CPU spent, no false alarm risk).

- **Raise to -40** in loud environments (freeway near facility, prison
  yard PA system) to reject spurious low-level ringing.
- **Lower to -50** for very quiet rural / lab installs where you want
  to hear whispers of distant drones.

### `max_drift_hz` (default `6.0`)
How far a harmonic can drift between adjacent blocks and still be
considered "the same harmonic." Drones under wind or maneuvering drift;
raise for windy sites (`8.0`). Lower for static labs (`4.0`) to reject
sirens/vehicles that drift more freely.

### `min_continuity` (default `0.85`)
Fraction of the persist window that must contain a valid harmonic
stack. `0.85` = 85% of blocks must hit. **Raise to 0.9** to reduce
false positives; **lower to 0.75** to catch drones that pass through
gaps in coverage.

### `min_harmonics` (default `2`)
Minimum number of harmonics that must line up. `2` is aggressive (catches
distant drones but false-positives on any two-tone hum); `3` is the
safe production value; `4` is very strict (misses distant quads).

### `persist_sec` (default `2.0`)
How long a continuous detection must last before ECHO declares a drone.
Short (`1.0`) catches fast passes but false-alarms on transient noise
(vehicle horns). Long (`4.0`) is very robust but misses fast flyovers.

### `ml_confidence_floor` (default `0.55`)
Second-stage confirmation: numpy-MLP classifier output must exceed this
to promote a candidate to a confirmed detection. `0.55` is the trained
balance point. Raise to `0.7` for extremely conservative deployments;
lower to `0.4` only during a false-negative debug session.

---

## Reference drone acoustic signatures

Blade-pass frequency (BPF) is the fundamental ECHO looks for. It's
`RPM × blade_count / 60` Hz. The harmonic stack is BPF × [1, 2, 3, 4,
5, 6]. Approximate BPFs for drones you're likely to encounter in a
corrections context:

| Drone class | Typical BPF | Harmonic 2 | Harmonic 3 | Notes |
|---|---:|---:|---:|---|
| DJI Mini / micro quad (2-3" props) | 220-280 Hz | 440-560 | 660-840 | Highest BPF; hardest to catch at range because energy falls off fast |
| DJI Mavic 3 / Air 3 (7-9" props) | 130-170 Hz | 260-340 | 390-510 | The single most common drone-drop platform. Well within default detector range. |
| DJI Matrice / Autel EVO Max (13-15" props) | 80-110 Hz | 160-220 | 240-330 | Heavy-lifter. LOUD. Detects at 500 m+. |
| Home-built quad (3D-printed, mystery props) | 100-200 Hz | 200-400 | 300-600 | The variable one. Tune `min_harmonics` up when these are the target — more harmonics means fewer FPs on the wild BPF. |
| Fixed-wing (VTOL cargo, ExpressLRS builds) | 40-90 Hz | 80-180 | 120-270 | Overlaps with vehicle rumble — use vision to disambiguate. |
| Helicopter (R-22, Bell 206) | 5-15 Hz | 10-30 | 15-45 | ECHO's default `harmonics: [1..6]` picks these up sometimes; the ML layer (`echo_ml.py`) is trained to reject them. If they still slip through, raise `ml_confidence_floor`. |

**How to read this table:**
- If your facility's threat model is DJI drops, defaults are already
  tuned for you.
- If a specific incident recovers a home-built or fixed-wing, log its
  RPM (from flight-log or a bench test with a tach); adjust
  `harmonics` and `max_drift_hz` for that class specifically in a
  challenger config.
- Micro quads (DJI Mini class) are genuinely harder — they're quiet and
  their BPF is high enough that atmospheric absorption kills range past
  100 m. Accept that or add lily pads to the perimeter.

### Reading the spectrogram

Every detection log line includes a `feature_summary` field like:

```
peak_freqs=[148.2, 296.4, 444.7, 592.9] snr=[14.2, 11.8, 9.4, 7.1]
persist=0.92 ml_score=0.71
```

Sanity check when triaging a report:

- Are the peaks integer multiples of the first one? (Real drone: yes.
  Mower / vehicle: usually no.)
- Do the peaks drift together across blocks? (Real drone: yes, tightly.
  Sirens: yes but too fast — trips `max_drift_hz`. Vehicle: no,
  independent.)
- Is `persist` above 0.85? Below that suggests transient noise.
- Is `ml_score` above 0.55? Below that means the MLP disagreed with
  the harmonic stack.

---

## Correlation engine — `correlation:`

### `window_hours` (default `4`)
How far back the rolling event log holds evidence. `4` matches the
typical drone-drop investigation timeline (call/visit → drop → recovery).
Raise to `24` for cases where deposit anomalies and prior visits matter
more; lower to `1` for real-time-only ops.

### `top_n_report` (default `10`)
How many candidate inmates and external contacts to include per report.
Rarely needs tuning.

### `weights.*`
Per-signal weights. **Do not tune these blind** — retune only after:

1. A period (≥ 30 days) of live correlation reports has accumulated
2. You've labeled each report's actual investigative outcome (real /
   false / unresolved)
3. You've measured the correlation between each signal firing and a
   real outcome

Then increase weights on signals that predict truth and decrease those
that fire on false positives. Recommended: keep two copies of
`config.yaml` — production and challenger — and A/B them.

The strongest signals (currently `drone_serial_matches_recovery`,
`contact_msisdn_matches_mas`, `drone_serial_known`) should never drop
below 0.30 — they're near-deterministic.

---

## LoRa / LoRaWAN SDR — `lora:`

### `enabled`
Flip to `true` only after the SDR hardware is physically installed and
the antenna is properly grounded.

### `region`
`US915` for the Americas, `EU868` for Europe, `AS923` for most of Asia,
`IN865` for India. Wrong region = you'll miss local traffic and waste
CPU on empty channels.

### `min_rssi_dbm` (default `-105.0`)
Threshold for what counts as a real chirp. RTL-SDR floor is around
`-110 dBm`; HackRF around `-115 dBm`; anything below the SDR's floor is
noise.

- **Raise to -100** if you're getting false positives from thermal
  noise or nearby ISM device jitter.
- **Lower to -110** only after facility RF audit is complete and the
  whitelist is populated.

### `facility_whitelist_hz`
List of frequencies known to belong to legitimate emitters inside the
fence line (AMR meters, staff radios, telemetry). Populate this from
the facility RF audit (see INTEGRATION_CHECKLIST.md § 5g). Each entry
suppresses all detections whose center frequency exactly matches.

### `correlation_window_sec` (default `90`)
± seconds around a drone event within which a LoRa chirp triggers
`drone_lora_link_detected`. **90 s** is the default because a real
drop pass is preceded by 30-60 seconds of control-link chatter.
Shortening below 60 misses real associations; extending beyond 180
starts producing false positives from unrelated 900 MHz noise.

---

## Acoustic Lily Pads — `lily_pads:`

### `tdoa_group_window_ms` (default `800`)
Time window within which detections from different nodes are considered
part of the same event. **Set to (facility_diameter_m / 343) × 3** as a
starting point — a drone at one corner takes about
`facility_diameter / 343` seconds for its sound to reach the far
corner; 3× that gives room for detection latency slop.

- 200 m facility → `600` ms
- 500 m facility → `1500` ms

Too small → nodes miss the group; too large → distinct events fuse.

### `min_nodes_for_fix` (default `3`)
`3` = 2D fix (needs known altitude assumption); `4` = full 3D fix.
Prefer `4` if you have enough nodes to guarantee it — altitude fixes
distinguish "drone over yard" from "drone over housing roof."

### `speed_of_sound_mps` (default `343.0`)
Adjust for climate: subtract ~0.6 m/s per °C below 20 °C, add ~0.6
per °C above. At 35 °C summer heat, use `352`; at -5 °C winter, use
`328`. Wrong value biases the fix but doesn't blow it up.

### `clock_sync_error_penalty_ms` (default `5`)
Nodes reporting worse than this clock-sync error get downweighted in
the fusion. Leave alone unless most nodes are on NTP (raise to 15).

---

## The step-by-step field-tuning procedure

Follow this in order. **Do not skip steps** — one wrong tune upstream
cascades through everything downstream.

### Step 1 — Establish the noise floor (30 min, no drone)

1. Deploy the sensor(s) in the target location.
2. Start ECHO with defaults, `logging.level: DEBUG`.
3. Let it run for 30 minutes with NO drone activity.
4. Watch the debug log for `min_level_db` gate triggers. If it's
   gating everything → the location is too quiet, LOWER `min_level_db`
   until ~10-30% of blocks pass the gate.
5. If it's NEVER gating → the location is loud enough that thermal
   noise is above `-45 dB`; RAISE `min_level_db` until ~30% of blocks
   pass.

### Step 2 — Baseline false-positive rate (24 h, no drone)

1. Leave defaults otherwise. Run 24 h at target install location.
2. Count detections per hour. Expected: 0-2/hour is fine; 5+/hour is
   too many.
3. If too many, RAISE `harmonic_snr_db` by 2 dB. Re-run 24 h. Repeat
   until FP rate ≤ 2/hour.
4. If NO detections at all → LOWER `harmonic_snr_db` by 2 dB and
   re-check with a real drone in Step 3.

### Step 3 — Real-drone detection distance

1. Fly a known drone (Mavic 3 is a good reference) in concentric arcs
   at 50 m, 100 m, 200 m, 300 m from the sensor.
2. At each arc, hover 30 s then translate 30 s.
3. Note the distance at which ECHO stops detecting reliably.
4. Compare to your operational requirement (typically ≥ 200 m for
   corrections).
5. If range is insufficient:
   - LOWER `harmonic_snr_db` by 2 dB
   - LOWER `min_harmonics` from 3 → 2 (if raised)
   - Re-run Steps 2 and 3

**Trade-off is direct:** longer detection range = more false positives.
Pick the range/FP balance the site can operate with.

### Step 4 — Distinguish helicopters and lawn equipment

These are the two most common false-positive sources:

**Helicopters**
- Blade fundamental: 5-15 Hz (very low), harmonics up to 200 Hz.
- ECHO's default harmonics search will pick some up as "drones with
  low fundamentals." The ML confirmation layer (`echo_ml.py`) is
  specifically trained to reject them.
- If helicopters are still slipping through, RAISE
  `ml_confidence_floor` to `0.65`.

**Lawn equipment (mowers, blowers, string trimmers)**
- Broadband noise + one or two engine harmonics.
- Usually caught by `min_harmonics: 3` — a mower has 2 harmonics max.
- If they slip through, RAISE `min_harmonics` to `3`. Trade-off: some
  distant micro-quads become undetectable.

**HVAC / cooling towers**
- Constant low hum, no true harmonics.
- `mains_hz` notch catches 60 Hz stuff; widen `mains_width_hz` to `10`
  for cooling towers that hum around 55-65 Hz.

**PA / siren tests**
- Sirens sweep in frequency (they'll trip `max_drift_hz`).
- Lower `max_drift_hz` to `4.0` to reject them (may reject drones
  under high wind).

### Step 5 — Persistence tuning

If you're getting brief detections that don't correlate to actual
drone events, RAISE `persist_sec` to `3.0` or `4.0`.

If you're missing fast flyovers (< 2 s), LOWER `persist_sec` to `1.5`
and accept more false alarms.

### Step 6 — Once live, log the outcomes

Every detection that fires should be logged with the outcome:

- **REAL** — confirmed drone / drop / attempt
- **FALSE** — investigated, no drone
- **UNRESOLVED** — cannot determine

After 30 days:
- If REAL:FALSE ratio < 1:5, LOWER thresholds (raise sensitivity)
- If REAL:FALSE ratio > 1:1, RAISE thresholds
- Ideal target: 1:2 (one real per two investigations)

### Step 7 — LoRa calibration (only if `lora.enabled=true`)

1. With SDR installed, run 24 h with `min_rssi_dbm: -105`.
2. Note every detection: log the center frequency.
3. Any frequency that fires > 5 times in 24 h with no drone activity is
   likely a legitimate emitter → add it to `facility_whitelist_hz`.
4. Repeat until 24 h produces zero unwhitelisted detections during
   drone-free periods.
5. Verify with a real LoRa transmitter (any $30 Meshtastic node makes
   a good test source) — ECHO should detect it and correlate to a
   simultaneous drone-audio simulation.

### Step 8 — Lily Pads calibration (only if `lily_pads.enabled=true`)

1. Survey and record every node's ENU (x, y, z) in meters. GPS-tag
   each install location; convert to facility-local ENU relative to
   the origin.
2. Verify clock sync at every node (`chronyc tracking` for NTP, or
   PPS status LED for GPS).
3. Launch a drone at a KNOWN GPS location within the array.
4. Compare ECHO's fused fix to ground truth.
5. Iterate on `tdoa_group_window_ms` — if the hub reports
   "detection from unknown node" or dropped stragglers, the window
   is too tight.
6. Residual error > 20 m on a 200 m array → check clock sync first,
   antenna heights second, node survey accuracy third.

---

## Diagnostic recipes — grep, curl, tail

Concrete commands for common triage tasks. All assume you're in the
`echo/` directory, the log file is at `echo/logs/echo.log` (default),
and the API is up on `127.0.0.1:5058`.

### "Are we detecting anything?"

```bash
# Detections in the last hour
tail -n 5000 echo/logs/echo.log | grep -E 'DRONE DETECTED|detected=True'

# Or via API — last N events, drone-audio only:
curl -s 'http://127.0.0.1:5058/detections?source=drone_audio&limit=50' | jq .
```

### "Which subsystem is DOWN?"

```bash
curl -s http://127.0.0.1:5058/subsystems | jq '.counts, .subsystems[] | select(.status != "OK") | {name, status, last_error, last_error_at}'
```

If the API isn't up, hit the log directly:

```bash
grep -E 'health: .* → (DEGRADED|DOWN)' echo/logs/echo.log | tail -30
```

### "Where is the pipeline stuck?"

```bash
curl -s 'http://127.0.0.1:5058/state?history_limit=30' | jq .
```

State stuck in `SCANNING` for hours means signals are arriving but
none reach the alert floor. Check top correlation-report scores:

```bash
curl -s 'http://127.0.0.1:5058/reports/recent?limit=10' | \
  jq '.reports[] | {ts: .generated_at, top_score: (.inmate_candidates[0].score // 0), declined: .decision_declined}'
```

### "What false-positive source is dominating?"

Pull the feature summaries for the noisiest hour:

```bash
grep 'DRONE DETECTED' echo/logs/echo.log | tail -50 | \
  grep -oE 'peak_freqs=\[[^\]]*\]' | sort | uniq -c | sort -rn | head
```

Then map each peak set to a source:
- `[59-61 Hz, 118-122, …]` → mains hum leaking past the notch. Widen
  `mains_width_hz`.
- `[100-140, 200-280, …]` with `persist < 0.7` → passing vehicle.
  Raise `min_continuity` to 0.9.
- `[5-15, 10-30, …]` → helicopter. Raise `ml_confidence_floor` to 0.65.
- `[190-260, …]` matching drone table above → real drone. Investigate.

### "Is a specific camera the culprit?"

```bash
# Count DEGRADED events per camera in the log
grep -oE 'camera:[^ ]+ .* → DEGRADED' echo/logs/echo.log | \
  awk '{print $1}' | sort | uniq -c | sort -rn
```

Rebooting a chronically DEGRADED camera almost always fixes it —
usually a stalled RTSP session ffmpeg can't recover from.

### "Which subsystem's data drove the last alert?"

```bash
curl -s 'http://127.0.0.1:5058/reports/recent?limit=1' | \
  jq '.reports[0] | {contributing_subsystems, dropped_subsystems, subsystem_health}'
```

Post-mortem gold — tells you which sensors were live when the alert
fired.

### "Prove ECHO is running with the config I edited"

```bash
curl -s http://127.0.0.1:5058/status | jq .config.detector
```

Compare against the value in `config.yaml`. If they differ, you either
edited the wrong file or an `ECHO_*` env var is overriding you:

```bash
env | grep ^ECHO_
```

### "Show me the last 5 state transitions with reasons"

```bash
curl -s 'http://127.0.0.1:5058/state?history_limit=5' | jq '.history'
```

Common patterns:
- `IDLE → SCANNING → IDLE → SCANNING → IDLE` — noise floor too low;
  raise `min_level_db` by 3-5 dB.
- `SCANNING → TRACKING → SCANNING → TRACKING` (never reaches ALERT) —
  signals present but scores stay below `alert_score_floor`; either
  lower the floor or (better) the correlation weights need tuning.
- Long stretches in `ALERT` without ack — dashboard operator is not
  ack-ing; set `state_machine.alert_auto_ack_sec` to 1800 to prevent
  stuck-alert desensitization.

---

## Microphone placement, wind, weather

The single biggest source of FP that no threshold will fix is a badly
placed mic. Get the physical install right first.

### Placement rules

1. **Height** — 3-5 m off the ground. Higher = more sky, less ground
   reflection. Above 8 m you start picking up more distant traffic than
   local drone activity. Don't go rooftop unless you have to.
2. **Line of sight to the sky** — nothing directly overhead within 30°.
   Under an eave is the classic mistake — the eave reflects the drone's
   own sound back and doubles the effective signal (good) while also
   channeling every other reflection into the mic (bad, dominates FPs).
3. **Away from HVAC / rooftop equipment** — 10 m minimum. HVAC hum
   directly under the mic is the second-biggest install failure.
4. **Away from mains transformers** — 5 m minimum. Ungrounded mic +
   nearby transformer = 60 Hz smear that no `mains_width_hz` widening
   fixes.
5. **Facing outward, not into the yard** — the mic should look toward
   where drones come FROM (perimeter, tree line, road) — not toward
   the target yard. This gives you more warning time.

### Windscreens

**Non-negotiable for outdoor installs.** Bare mics in even 5 mph wind
produce broadband low-frequency noise that:
- Cracks the `min_level_db` gate constantly (all your CPU goes into
  processing wind)
- Occasionally forms accidental harmonic stacks (rare but real FP source)

Use a **foam windscreen** (Rycote-style, $10-30) for USB electrets; a
**dead-cat furry cover** for professional mics if the site is very
exposed. Both cut wind noise by 15-25 dB at low frequencies without
affecting drone frequencies.

### Temperature

Detection range varies with air temperature because the speed of sound
does. Cold air (denser) = slightly better sensitivity; hot air =
slightly worse. The difference between 0 °C and 35 °C at 300 m is
about 6% range loss — usually irrelevant.

BUT: temperature also inverts sound propagation on some evenings —
warmer air aloft over cooler air near the ground can channel drone
sound farther than usual, and boost your range dramatically. If you
see spontaneous long-range detections on cool evenings, that's why.

### Rain

Rain adds broadband noise (raindrops on the windscreen, on nearby
surfaces). Options:

- Do nothing — the wet windscreen is worse than dry but usable.
- Install a small **rain shield** above the mic (an inverted disc,
  15 cm above the mic, transparent to sound but blocks direct drops).
- Add a "rain suppression" flag to your ops runbook: during heavy
  rain, raise `harmonic_snr_db` by 3 dB, accept range loss for FP
  reduction.

Don't try to auto-detect rain from the signal — it's more trouble than
it's worth. Use a real weather station or facility HVAC data.

### Fog / humidity

Increases high-frequency absorption slightly. Effect on drone
detection is negligible below 1 km. Don't tune for it.

### Net-pole perimeter arrays (SC-DOC preferred install)

The single best acoustic install ECHO supports at a modern correctional
facility isn't a purpose-built pole — it's the netting poles the
facility already has.

Why this pattern wins:

- **Height** — 30-60 ft is well above the ground boundary layer where
  most wind noise lives. Detection range at the same drone is 30-50%
  better than a 3 m pole install for the same mic hardware.
- **Density** — 20-40 ft pole spacing = TDOA baselines of 6-12 m,
  which is tighter than any budgeted array would be. Sub-meter
  position accuracy against a Mavic-class drone within 300 m is
  realistic (bench-simulated at 0 m error with 54 nodes; expect a
  few meters of real-world error from residual clock jitter and
  survey imprecision, still excellent).
- **Direction** — poles are *outside* the containment wall. Mics face
  outward and catch drones on approach 15-30 seconds before they
  reach airspace over the yard. That warning window is where CORTEX
  correlation actually pays off — it can pre-fetch inmate location,
  active-call, and Tecore MAS context so the operator alert lands
  with a candidate list attached, not "unknown drone."
- **Utility** — perimeter lighting is already run to the poles. PoE
  drop is often just tapping the existing lighting conduit.

Deployment call:

```python
from echo_lily_pads import net_pole_perimeter_array, LilyPadHub

# Surveyed perimeter in facility ENU meters (WGS84 anchored elsewhere):
polygon = [(0, 0), (152, 0), (152, 98), (0, 98)]
nodes = net_pole_perimeter_array(
    site_id="broad-river",
    perimeter_polygon_m=polygon,
    pole_spacing_m=9.0,           # 30 ft
    pole_height_m=12.0,           # ~40 ft mic height
    clock_source="ptp",           # perimeter switches support PTP
    mic_type="mems_array",        # ReSpeaker 6-mic HAT
    outward_facing=True,
    windscreen=True,
    vibration_isolated=True,
)
hub = LilyPadHub(nodes=nodes, on_track=..., min_nodes_for_fix=4)
```

Install-time checklist specific to this pattern:

1. **Survey each pole.** Do NOT trust "9 m spacing" as ground truth —
   surveyors put poles ~9 m apart. Actual placements can vary by
   0.5-1 m. Get the real (x, y) for each pole with a total station
   or RTK GPS. That surveyed list overrides whatever the perimeter
   generator produced.
2. **Confirm the mount height.** The pole top is not where the mic
   goes; the mic mounts 1-2 m below the top for practical access.
   Record the real mic height per pole (typically 90% of pole
   height).
3. **PTP over a wired perimeter.** GPS PPS is fine as a fallback but
   PTP on the same perimeter switch is easier to manage. If the
   perimeter switches don't support PTP, most Cisco / Aruba enterprise
   switches now do — check firmware first.
4. **Windscreens on every pole, no exceptions.** Dead-cat furry
   covers, not foam. A tall pole in even 10 mph wind produces enough
   low-frequency rumble to trip the detector constantly if bare.
5. **Vibration isolation.** Mount the mic on a rubber grommet or
   simple spring assembly so pole sway doesn't couple as a 1-5 Hz
   rumble the harmonic tracker misinterprets as a fundamental.
6. **Lightning protection.** A metal pole 40 ft in the air is a
   lightning rod. Every enclosure needs a gas discharge tube on the
   PoE line, and the pole must be bonded to facility ground. Skipping
   this ends with fried Pis after the first summer storm.
7. **Net acoustic reflection test.** After install, walk the interior
   with a known noise source (a small drone at low altitude works).
   The netting will produce a mild acoustic shadow inside the fence
   and slight harmonic doubling at some angles. If FP rate spikes,
   raise `detector.min_harmonics` to 3 site-wide.

Signage: perimeter mics WILL pick up voices on adjacent public
sidewalks or visitor parking. SC is one-party-consent for audio, but
DOC policy generally requires posted signage at any perimeter with
audio surveillance. Get that signage up before the array goes live.

### Nearby vegetation

Deciduous trees within 20 m of the mic add rustle noise on windy days
and cut effective range in leaf-out season. Evergreens do the same but
year-round. Not fixable in config — clear the sight-line if possible,
or plan around a 20% range loss during leaf-out.

---

## Environment-variable overrides — the field-debug pattern

You don't need to edit `config.yaml` in the field to try a tweak.
Every value has an env override:

```
ECHO_DETECTOR__HARMONIC_SNR_DB=10 \
ECHO_DETECTOR__MIN_HARMONICS=3 \
python echo_multi.py --config echo/echo_cameras.yaml
```

Nesting uses double-underscore. Booleans accept `true`/`false`/`yes`/`no`.
`null` empties a value. Numbers are auto-coerced.

---

## Verifying a change is actually live

Every module logs the effective config it's using at startup. Grep
the log:

```
grep -E "loaded config|using baked defaults" echo/logs/echo.log
```

Or query the API (if `api.enabled=true`):

```
curl -s http://127.0.0.1:5058/status | jq .config.detector
```

If the value you set doesn't appear, you're either editing the wrong
file, or your env var name has a typo. Env override examples
[echo_config.py](./echo_config.py).

---

## Fault tolerance & health — `health:` + fusion behavior

Every subsystem in ECHO — cameras, LoRa SDR, Lily-Pad hub, ViaPath /
Tecore / Dedrone / Flock / DMV / Cellebrite connectors, face
recognizer, drone forensics — reports one of four statuses to the
shared registry (`echo_health.HealthRegistry`):

| Status    | Meaning                                          | CORTEX fusion behavior           |
|-----------|--------------------------------------------------|----------------------------------|
| OK        | Producing valid data, no recent errors           | Full weight                      |
| DEGRADED  | Producing data with warnings / retries / partial | Full weight, flagged in report   |
| DOWN      | Not producing data — errors, crashed, disconnected | Signals **dropped** from scoring |
| UNKNOWN   | Never came up (subsystem disabled)               | Signals dropped                  |

### `health.stale_timeout_sec` (default `60`)
A subsystem that hasn't reported OK for this long auto-demotes to
DOWN. Raise for slow-cadence pollers (SFTP every 5 min = set to
`600`). Lower for critical realtime paths (cameras: 30 s is stricter).

### `health.safe_loop_max_consecutive_errors` (default `10`)
Number of consecutive iteration errors inside `safe_loop()` before the
subsystem is marked DOWN. Below the ceiling and above 3 it goes
DEGRADED and keeps retrying with backoff.

### `health.safe_loop_backoff_sec` (default `5.0`)
Seconds between retries after a failing tick. Exponential scaling
kicks in as consecutive errors accumulate (capped at 4× this value).

### `correlation.min_viable_sensors` (default `2`)
CORTEX declines to decide when fewer than this many distinct
subsystems have contributed OK/DEGRADED events in the current
correlation window. The report still comes back, but with
`decision_declined: true` and a reason string like
`"only 1 viable sensor(s) (need ≥ 2); dropped: ['face']"`.

- **Raise to 3** for high-stakes production. Requires audio + at
  least two of {vision, ViaPath, MAS, LoRa, Lily Pads, Dedrone,
  Flock, DMV, Cellebrite} to be alive.
- **Lower to 1** ONLY for isolated single-sensor deployments (a
  bare acoustic install), where declining every event would silence
  the entire pipeline.

Never set to 0 — that removes the guard entirely and lets CORTEX
guess from an empty log.

---

## Pipeline state machine — `state_machine:`

ECHO uses an explicit four-state pipeline:

    IDLE → SCANNING → TRACKING → ALERT → (back to SCANNING, TRACKING, or IDLE)

Legal transitions (from `echo_state.TRANSITIONS`):

| From      | Allowed → |
|-----------|-----------|
| IDLE      | SCANNING |
| SCANNING  | IDLE, TRACKING, ALERT |
| TRACKING  | SCANNING, ALERT |
| ALERT     | TRACKING, SCANNING, IDLE |

Every transition logs: `state: FROM → TO trigger=…  event_id=…  detail=…`.
Invalid transitions raise `InvalidTransition` — the caller decides
whether to swallow. The `bind_to_correlation_engine()` helper uses
`try_transition()` which swallows on invalid rather than crashing.

### `state_machine.alert_auto_ack_sec` (default `0`)
Seconds after entering ALERT that ECHO auto-transitions back
without an operator acknowledgment. `0` = never (require manual
ack from dashboard or `/state` PATCH). Set to `1800` (30 min) to
avoid ALERT sticking when a shift-change happens mid-event.

### `state_machine.history_cap` (default `256`)
Ring-buffer size for the transition history surfaced at
`GET /state?history_limit=…`. Rarely needs tuning.

### Tuning the SCANNING → ALERT threshold
Set `correlation.alert_score_floor` (default `0.5`). Anything below
this stays in SCANNING/TRACKING. Anything at or above transitions
to ALERT and pages SIU (via `alert:drone_with_correlated_inmate`).

- **Raise to 0.6-0.7** if operators are getting alert fatigue.
- **Lower to 0.35** in the first month of a new deployment while
  weights are still being tuned — accept more alerts to build
  labeling data faster.

---

## Correlation weight retuning workflow

The 25 CORTEX signal weights in `config.yaml correlation.weights` are
starting values. They will drift wrong as the site's threat model
evolves. Here's the disciplined loop for keeping them calibrated.

### 1. Label every alert

For 30-90 days after go-live, tag every `drone_with_correlated_inmate`
alert with its investigative outcome:

- **REAL** — confirmed drone / drop / attempt
- **FALSE** — investigated, no drone
- **UNRESOLVED** — cannot determine
- **PARTIAL** — drone was real but the top candidate was wrong

Store the labels in whatever incident-management system the DOC uses;
the specific fields to keep are:

```
alert_id, drone_event_ts, top_inmate, top_contact, actual_outcome,
which_signals_fired, notes
```

Under 30 days = you're guessing. Do not adjust weights.

### 2. Compute per-signal precision

For each of the 25 signals, compute:

```
precision(signal) = REAL alerts where signal fired / all alerts where signal fired
```

Rank signals by precision. Anything below **0.4 precision** is
actively harmful — it's contributing to false alerts. Anything above
**0.7** is your goldenweights.

```bash
# Rough SQL sketch of the query:
SELECT
  signal,
  COUNT(*) FILTER (WHERE outcome = 'REAL')     AS true_pos,
  COUNT(*) FILTER (WHERE outcome != 'REAL')    AS false_pos,
  1.0 * COUNT(*) FILTER (WHERE outcome = 'REAL') / COUNT(*) AS precision
FROM alert_signal_fires
WHERE alert_ts BETWEEN 'yesterday' - '30 days'::interval AND 'yesterday'
GROUP BY signal
ORDER BY precision DESC;
```

### 3. Build a challenger config

Copy `config.yaml` to `config-challenger.yaml`. Adjust weights:

- Signals with precision < 0.4 → cut weight by 50%
- Signals with precision > 0.7 → raise weight by 25%
- Middle band → leave alone

DO NOT change more than 5 weights in one iteration. You lose the
ability to attribute cause.

### 4. A/B compare

Two options:

**A. Fleet-partitioned A/B** — if you deploy at multiple facilities,
put half on production config and half on challenger for 30 days.
Compare alert precision aggregated across each cohort.

**B. Time-partitioned A/B** — one facility only. Run production for
30 days, challenger for 30 days. Compare against a slow-changing
baseline metric (weekly drone-drop attempt count from investigation
records).

### 5. Promote or rollback

If challenger precision is > production precision by ≥ 5 percentage
points, promote. Otherwise rollback and try a different adjustment
in the next iteration.

### 6. Never touch these

Two signals are near-deterministic and should never drop below 0.30:

- `drone_serial_matches_recovery` (0.50 default) — same physical
  airframe used in a prior incident. If this fires, it's real.
- `contact_msisdn_matches_mas` (0.20 default) — Tecore captured
  this exact phone number inside the facility. Only false in the
  extremely rare case of spoofed MSISDN.

Lower them and you're throwing away the strongest evidence you have.

### 7. Anti-pattern — don't do this

- ❌ Adjust weights based on ONE alert's outcome. Statistical noise.
- ❌ Adjust weights on the same week you introduced a new data source.
  You can't tell whether the source or the weights explain any change.
- ❌ Adjust weights to fix a KNOWN sensor problem. Fix the sensor.
  Weights compensate for real limitations, not broken installs.

---

## Multi-site fleet tuning

Running ECHO at 5+ facilities creates a coordination problem:

- Each site has different noise floors, RF environments, drone traffic
- Weights tuned per-site diverge and become hard to maintain
- Central compliance / policy wants ONE canonical config for auditability

Recommended pattern:

### Layered config for fleet

```
config/
├── global.yaml              # canonical defaults for the fleet
├── sites/
│   ├── broad-river.yaml     # local overrides for one facility
│   ├── kirkland.yaml
│   └── perry.yaml
└── env/
    ├── prod.yaml            # production-wide overrides
    └── canary.yaml          # single-facility challenger overrides
```

Load with:

```bash
python echo_multi.py \
  --config config/global.yaml \
  --config-overlay config/sites/broad-river.yaml \
  --config-overlay config/env/prod.yaml
```

(Overlay support is a small addition to `echo_config.load()` — deep-merge
each overlay in the order supplied.)

### Per-site knobs (leave in site file)

- `detector.harmonic_snr_db` — noise floor varies by site
- `detector.min_level_db` — depends on ambient
- `lora.facility_whitelist_hz` — different legitimate emitters per site
- `lily_pads.nodes` — always per-site
- `paths.*` — different disk layouts

### Fleet-wide knobs (leave in global file)

- `correlation.weights` — fleet-wide, tuned via the workflow above
- `correlation.min_viable_sensors`
- `correlation.alert_score_floor`
- `state_machine.alert_auto_ack_sec`
- `health.stale_timeout_sec`
- Detector defaults NOT overridden per-site

### Canary a change

When you retune a fleet-wide weight, canary at ONE site first:

```bash
# On the canary site's deploy PC, add the challenger overlay:
python echo_multi.py \
  --config config/global.yaml \
  --config-overlay config/sites/broad-river.yaml \
  --config-overlay config/env/canary.yaml   # <-- challenger weights here
```

If canary precision improves for 30 days, roll the change into
`config/env/prod.yaml` fleet-wide.

---

## Emergency: turn off the noisy alerts

If ECHO is falsely paging staff at 3 AM:

1. Immediate: raise `harmonic_snr_db` to `12` and `min_harmonics` to `4`.
   This dramatically reduces false positives at the cost of some real
   detections. Buys you the sleep to tune properly the next day.
2. Then work through Steps 1-6 above.

Do NOT disable the pipeline entirely — false positives are a tuning
issue, not a fundamental flaw.

If you need a live-off-switch that doesn't lose signal capture, set
`state_machine.alert_auto_ack_sec: 1800` (auto-clear ALERT after 30
min) and `correlation.alert_score_floor: 0.7` (require stronger
correlation before paging). ECHO still detects, still correlates,
still logs — but it stops paging until you turn the sensitivity back
up.

---

## Troubleshooting matrix

Grouped by symptom. Each row: what you observe → most likely cause →
first thing to try.

### Detector-level

| Symptom | Likely cause | First try |
|---|---|---|
| No detections at all, all-zero scores | mic not producing audio | Check `min_level_db` gate (raise it should suppress; if raising it changes nothing, hardware is silent). `ls /dev/snd` on Linux; check RTSP URL with `ffplay`. |
| Detections stuck at score 0.1 forever | mains hum overwhelming everything | Widen `mains_width_hz` to 10; check mic grounding. |
| Sudden burst of 50+ detections in a minute | siren / vehicle horn cluster | Nothing to fix in config; wait it out. If chronic, raise `max_drift_hz` window OR restrict operating hours. |
| Only certain cameras detect ever, others always miss real drones | Mic-level mismatch between cameras | Set per-camera `detector_overrides` in `echo_cameras.yaml` with a lower `harmonic_snr_db` for the deaf cameras (they may just be quieter). |
| Detections but ALL have `ml_score < 0.4` | Model rejecting everything | Confirm the model file exists at `paths.ml_model_path`. If missing, ECHO falls back to a pass-through score — that's the bug. |

### Correlation-level

| Symptom | Likely cause | First try |
|---|---|---|
| `decision_declined=True` on every report | Not enough subsystems live | Check `/subsystems`; fix DOWN ones, or lower `correlation.min_viable_sensors`. |
| All candidate scores under 0.1 | Time window too short OR weights too flat | Check `correlation.window_hours` (raise to 4-8); run weight-tuning workflow. |
| Same inmate topping every report | Real (habitual offender) OR weights favor whatever signal they always trigger | Look at their signals — if one is 1.00 across 20 reports and it's not `msisdn_matches_mas` or `serial_matches_recovery`, that signal is over-weighted. |
| Correlation report has `contributing_subsystems: []` | Nothing OK-status is producing events | Registry not being reported into. Verify subsystems call `report_ok()` on healthy ticks. |

### State-machine-level

| Symptom | Likely cause | First try |
|---|---|---|
| Stuck in IDLE despite obvious drone detections | Correlation engine not wired to state machine | Check `echo_multi.py.__init__` — should call `bind_to_correlation_engine`. |
| Stuck in ALERT for hours | No one is ack-ing | Set `state_machine.alert_auto_ack_sec: 1800`. Also train operators. |
| Bounces IDLE ↔ SCANNING dozens of times per minute | Noise floor too low; every quiet moment triggers | Raise `min_level_db` by 5 dB. |
| Reaches TRACKING but never ALERT | Correlation score always below `alert_score_floor` | Either lower the floor (start with 0.4) OR run weight-tuning workflow. |

### Subsystem-level

| Symptom | Likely cause | First try |
|---|---|---|
| Camera keeps flipping OK ↔ DEGRADED | RTSP stream unstable — network or camera-side | Check `ffmpeg` logs; often solved by reducing camera bitrate on the switch. |
| LoRa never OK, always UNKNOWN | SDR device not connected OR pyrtlsdr not installed | `lsusb | grep -i rtl` (or SoapySDR probe); `pip show pyrtlsdr`. |
| LoRa OK but ZERO detections ever | Threshold too high OR wrong region | Try `min_rssi_dbm: -110` temporarily. If still nothing, `region: US915` vs `EU868` mix-up. |
| Lily pads never OK, stays UNKNOWN | Hub started but no nodes reporting | Check node → hub network path (MQTT / gRPC / HTTP endpoint). |
| Lily pad fixes wildly wrong (200 m off) | Clock sync bad OR node coordinates wrong | Check node clock sync errors (`clock_sync_error_ms`); re-survey positions. |
| ViaPath / Tecore / Dedrone connector goes DOWN in the middle of the night | Vendor API on maintenance window | Contact vendor NOC. ECHO recovers automatically. |

### Fleet-level

| Symptom | Likely cause | First try |
|---|---|---|
| Precision (REAL alerts / all alerts) drops across the fleet after a config change | The change was wrong for some sites | Rollback via `git checkout` on the config repo. Investigate per-site before re-trying. |
| One site's precision much worse than others | Site-specific tuning needed | Move that site's `detector.*` overrides into `config/sites/<site>.yaml`. |
| Alert fatigue reported by operators | Floor too low OR too many low-value signals firing | Raise `alert_score_floor` first (fast). Longer-term: retune weights. |

---

## Appendix — reference numbers

### Speed of sound in air (m/s)

| Temp (°C) | Speed |
|---|---:|
| -10 | 325.4 |
| 0   | 331.3 |
| 10  | 337.3 |
| 20  | 343.2 (default) |
| 25  | 346.1 |
| 30  | 349.0 |
| 35  | 351.9 |

Use for tuning `lily_pads.speed_of_sound_mps` per climate. In humid
air, speed rises another ~0.5% — not usually worth accounting for.

### Attenuation with distance (approximate, calm dry air)

Sound level drops **6 dB per doubling of distance** in free field.
Practical numbers for a drone that produces 65 dB SPL @ 1 m:

| Distance | Approx SPL |
|---:|---:|
| 1 m | 65 dB |
| 10 m | 45 dB |
| 100 m | 25 dB |
| 300 m | 15 dB |
| 500 m | 11 dB |
| 1 km | 5 dB |

The noise floor of a typical outdoor mic in a suburban environment is
around 30-35 dB SPL. That's why 200-300 m is the realistic ECHO
detection range for a single mic on a Mavic-class drone.

### LoRa channel plan quick reference

**US915 uplink (64 × 125 kHz + 8 × 500 kHz):**

| First 8 channels (MHz) | Notes |
|---|---|
| 902.3, 902.5, 902.7, 902.9, 903.1, 903.3, 903.5, 903.7 | LoRaWAN 125 kHz sub-band 1 |
| 903.0, 904.6, 906.2, 907.8, 909.4, 911.0, 912.6, 914.2 | LoRaWAN 500 kHz uplink (join) |

**ExpressLRS-900 US common hop frequencies:**

`903.5, 906.5, 909.5, 912.5, 915.5, 918.5, 921.5, 924.5` MHz

If a chirp is on one of these AND repeats on a hop pattern → high
probability of an ELRS drone control link. Not proof of a drone (any
long-range RC controller uses the same protocol), but strong
correlator signal within ±90 s of an acoustic drone event.

### Detection score → severity table (default weights)

| Top candidate score | Interpretation | Suggested alert severity |
|---|---|---|
| 0.00 - 0.15 | Noise / spurious | none |
| 0.15 - 0.30 | Weak correlation, single signal | log-only |
| 0.30 - 0.50 | Moderate — multi-signal but no strong ones | notify |
| 0.50 - 0.75 | Strong — includes at least one 0.20+ weight signal | alert (SIU pager) |
| 0.75 - 1.00 | Very strong — likely serial match, MAS match, or Cellebrite | critical (warden + FBI) |

Adjust `alert_score_floor` for the boundary between "notify" and
"alert" per your operator staffing model.

### Rule-of-thumb detection ranges (single-mic install, good placement)

| Drone class | Calm night | Windy day | Rain |
|---|---:|---:|---:|
| DJI Mini class | 100-150 m | 40-80 m | 20-50 m |
| DJI Mavic 3 class | 250-350 m | 150-200 m | 80-150 m |
| DJI Matrice class | 500-800 m | 300-500 m | 200-300 m |

If your site's numbers are half of these, you have an installation
problem (mic placement, wind exposure, HVAC noise). Fix the physical
install before touching thresholds — no config tuning recovers a bad
placement.

### Common LoRa emitter fingerprints (whitelist candidates)

Populate `lora.facility_whitelist_hz` from a site RF audit; typical
legitimate emitters inside a fence line:

| Emitter class | Typical freqs (MHz) |
|---|---|
| Elster / Itron AMR water meters (US) | 902-904 (upstream), 912-928 (return) |
| Sensus AMI electric | 902-928 (freq-hopping) |
| Motorola staff radios (900 MHz trunked) | 935-940 |
| Legacy pager transmitters | 929-932 |
| Building automation LoRaWAN | site-specific — get from facilities team |

Whitelist by exact center frequency, not by range — you don't want to
suppress a real drone control link that happens to fall inside an
emitter band.

---

**End of guide.** Any tunable not covered here is either baked into
the detection algorithm (see `ACOUSTIC_DETECTION_RESEARCH.md`) or lives
in `echo_cameras.yaml` (see the sample file's comments).

