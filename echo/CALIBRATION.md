# ECHO Field Calibration Guide

Every tunable in ECHO lives in [`config.yaml`](./config.yaml). This guide
explains what each knob does, safe ranges, common false-positive causes
(helicopters, HVAC, lawn equipment, mains hum), and a step-by-step
procedure to tune a fresh install without chasing your tail.

Read the whole thing once before touching anything — knobs interact.

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

## Emergency: turn off the noisy alerts

If ECHO is falsely paging staff at 3 AM:

1. Immediate: raise `harmonic_snr_db` to `12` and `min_harmonics` to `4`.
   This dramatically reduces false positives at the cost of some real
   detections. Buys you the sleep to tune properly the next day.
2. Then work through Steps 1-6 above.

Do NOT disable the pipeline entirely — false positives are a tuning
issue, not a fundamental flaw.
