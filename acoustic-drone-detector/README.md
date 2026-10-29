# Acoustic Drone Detector

Passive, multi-layer acoustic detection of drones — no transmissions of its own.
Designed to run on a laptop or Raspberry Pi and to fuse with a separate RF
detection system.

## What it does

Detects a drone by its **acoustic structure**, not just "sound in a band." Five
cooperating layers reject everyday confusers (fans, leaf blowers, RC planes,
HVAC, traffic, insects):

1. **Harmonic stack** — blade-pass fundamental (50–700 Hz) plus its overtones.
2. **Persistence** — the signature must hold for ~3 seconds before alerting.
3. **Multi-rotor beat** — two fundamentals a few Hz apart = multiple props
   slightly out of sync (heavy-lift hexa/octo cue). Reliable as a yes/no flag.
4. **RPM modulation** — the small rapid "wobble" of a hovering drone. Steady
   tones (a fan held at constant speed) do not wobble. Strong confuser filter.
5. **Direction of arrival (DOA)** — with a mic array, estimates a bearing.

It also reports the implied rotor RPM (`BPF = RPM ÷ 60 × blades`, inverted).

## Quick start

```bash
pip install -r requirements.txt        # numpy (+ sounddevice for live mic)

# 1) Validate for FREE on a recording — no hardware needed:
#    grab a drone flyby clip, export to 16-bit PCM WAV, then:
python3 drone_detect.py --wav clip.wav

# 2) Live, single USB mic:
python3 drone_detect.py

# 3) Live, 4-mic array with bearing:
python3 drone_detect.py --channels 4 --geometry respeaker
```

## Useful options

| Flag | Default | Meaning |
|------|---------|---------|
| `--wav FILE` | — | Analyze a 16-bit PCM WAV instead of the live mic |
| `--channels N` | 1 | Live input channels (use 4 with an array) |
| `--geometry respeaker\|stereo15cm` | none | Mic array geometry, enables DOA |
| `--min-harmonics N` | 3 | Overtones required to count as a candidate |
| `--persist-sec S` | 3.0 | Seconds the signature must persist before alerting |

## Reading the output

```
[DETECT] BPF= 110.4 Hz | harm=6 | SNR=40.3dB | RPM≈3311(2bl)/2207(3bl)
         | MULTI-ROTOR beat=6.0Hz (110/116Hz)
         | wobble=2.10% @ 1.8Hz [DRONE-LIKE]
         | bearing= 92.0° (conf 0.74)
```

- `BPF` — detected blade-pass fundamental
- `harm` — number of harmonics found
- `MULTI-ROTOR` — two desynced rotors detected (heavy-lift signature)
- `wobble … [DRONE-LIKE]` — RPM modulation consistent with a hovering drone
- `bearing` — direction of arrival (array only; coarse at low frequency)

## Capabilities & limits (honest)

- **Strongest target:** heavy-lift electric multirotors with payload — loud,
  low fundamental that carries far, rich multi-rotor signature.
- **Indicative range (night/quiet):** small drone ~150–300 m rural; heavy-lift
  ~0.8–2 km rural. Suburban and wind cut these significantly.
- **Acoustic is a close-in layer**, not perimeter radar. Pair with RF for
  long-range early warning and to confirm before acting.
- **Bearing is coarse** on a small array at low frequency (physics, not a bug).
  A larger baseline or high-harmonic steering improves it.
- **No make/model classification yet** — that's a future ML phase.

## Hardware to prove the concept

- **$0** — your laptop + recorded clips (validate the DSP first).
- **~$40–95** — one USB measurement mic (e.g. Dayton iMM-6) + furry windscreen.
- **~$90–110** — ReSpeaker 4-Mic Array for live bearing.
- Outdoors: a **furry windscreen (dead-cat) is mandatory** — wind swamps the
  low band.

## Files

- `drone_detect.py` — the detector (pure-numpy WAV path; sounddevice for live).
- `requirements.txt` — dependencies.
- `make_deck.py` — regenerates the capabilities slide deck.

## Note

Passive detection / situational-awareness tool. Operate it in compliance with
local laws on recording and monitoring.
