# Acoustic Drone Detection & Identification — Knowledge Base

A curated, cited reference compiled from peer-reviewed papers, datasets, and
technical reports. Purpose: ground ECHO's detection parameters in published
research, guide the ML-classifier build, and reduce false alarms / misses.

Compiled 2026-05-23. This is a living document — append new findings with citations.

---

## 1. The acoustic signature of a drone

A drone's sound is dominated by **propeller blade-pass tones** plus motor/ESC whine.

- **Blade-pass frequency (BPF) = RPM/60 x number_of_blades** (the fundamental).
- A DJI Mavic-class quad hovering ~5,000 RPM with 2-blade props => fundamental **~166 Hz**.
- **Commercial drone fundamentals typically 150-400 Hz** (large/heavy-lift run lower, ~60-250 Hz; small fast props higher, ~300-600 Hz).
- The signature is a **harmonic stack**: fundamental + integer-multiple harmonics. Harmonic energy extends to **~16 kHz**, with some models showing ultrasonic content at **35-45 kHz**. **Primary energy is concentrated below ~2.5 kHz.**
- Energy distribution across harmonics varies with **blade geometry, loading, and flight state** (hover vs. maneuver vs. climb), which is why a moving drone's spectrum shifts.

**Implication for ECHO:** the harmonic-stack + blade-pass approach is the correct physical model. The 50-700 Hz fundamental search window matches the commercial range. The low band (below ~2.5 kHz) carries the most reliable energy.

## 2. Feature extraction methods (ranked by relevance)

| Feature | What it captures | Notes |
|---|---|---|
| **FFT harmonic peaks / blade-pass** | Fundamental + harmonics directly | What ECHO uses now. Interpretable, real-time, but rule-based. |
| **Mel-spectrogram** | Time-frequency energy on perceptual scale | **Standard input for CNN classifiers.** Best for deep learning. |
| **MFCC** | Spectral envelope / timbre ("buzz" vs "chirp") | Great for distinguishing drone timbre from birds; **noise-sensitive**. |
| **GFCC** (Gammatone) | Auditory-model cepstrum | **More noise-robust than MFCC** outdoors. |
| **Wavelet transform** | Multi-resolution transients | Good for **sudden RPM changes during maneuvers**. |

**Implication for ECHO:** the ML classifier (Phase B) should use **mel-spectrograms** as input (the field standard), optionally fused with MFCC/GFCC for noise robustness.

## 3. Detection & classification methods

Progression from classical to modern:
- **Rule-based / template** (harmonic stack, thresholds) — what ECHO uses. Interpretable, fast, but overlaps with voice/confusers.
- **Classical ML** — Random Forest, SVM, k-NN, Hidden Markov Models (HMM) + MFCC. Robust, interpretable.
- **Deep learning (state of the art):**
  - **CNN on spectrograms** — implicitly learns to suppress reverberation/noise; the dominant approach.
  - **CRNN** (CNN + recurrent) — adds temporal modeling.
  - **AUDRON** (hybrid MFCC + STFT-CNN + recurrent + autoencoder): **98.51% binary / 97.11% multiclass** drone-type recognition.
  - **GAN augmentation** (Al-Emadi et al.) — synthesize UAV audio to enlarge training sets; improved generalization for CNN/RNN/CRNN.

**Key insight:** CNNs distinguish drone *timbre* from voice/fans/birds far better than any threshold rule — they solve the voice false-alarm problem rules can't.

## 4. Datasets (for training the ML classifier)

| Dataset | Contents | Use |
|---|---|---|
| **DroneAudioDataset** (Sara Al-Emadi, GitHub) | Bebop/Mambo quad recordings + noise classes | Binary + multiclass; what ECHO validated against. |
| **Multiclass UAV acoustic dataset (2025)** | **3,200 recordings, 32 UAVs, 16,000 s** (28 quads, 1 tri, 2 hexa, 1 tail-sitter) | Drone-*type* identification. |
| **DroneDetect** (IEEE DataPort) | RF (not acoustic) UAS signals | For RF-side / fusion work. |
| **GAN-augmented corpora** | Synthetic UAV audio | Augmentation to fight small-data overfit. |

## 5. Localization & direction-finding (validates ECHO's DOA)

- Methods: **TOA, TDOA, AOA**; solve hyperbolic equations across a spatially distributed array to triangulate position.
- **GCC-PHAT** — phase-transform cross-correlation; emphasizes phase, **reduces noise influence**, improves time-delay estimation. (This is exactly what ECHO's DOA uses.)
- **Tetrahedral 4-mic arrays** — enable real-time 3D localization from a compact arrangement.
- **Beamforming:** Steered-Response Power (**SRP-PHAT**) and **MVDR** spatially filter to find energy peaks. (ECHO uses SRP-PHAT.)
- **Distributed arrays** (multiple nodes) significantly improve localization vs. a single compact array — confirms ECHO's Phase-3 multi-node plan.

## 6. Range & environmental factors

- **Detection range scales with acoustic output:**
  - Quiet quadcopters: **~200-300 m**.
  - Loud / fixed-wing: **several km** (e.g., Microflown SkySentry: 2 kg fixed-wing at ~1 km, manned helicopter ~10 km).
  - Acoustic + optical fusion: **>500 m with <1.5% 3D positioning error**.
- **Wind is the single biggest environmental problem.** A windshield (e.g., RODE NTG-2 + WS6) extended range by **~31-131%** in strong wind vs. a bare mic.
- **SNR profile with distance:** near-field geometric sensitivity -> stable mid-field tracking -> far-field degradation as SNR attenuates.
- Mics with a **lower low-frequency (0-300 Hz) noise floor** and **stronger mid-band tonal excess** hold SNR better at range.
- Most published systems are tested in **controlled conditions** and **may not generalize** to the field — real deployment is harder than benchmarks.

**Implication for ECHO:** our range estimates (150-300 m small, ~km large) align with the literature. A **windscreen is mandatory** for outdoor use. Mic choice should prioritize low LF noise floor.

## 7. Voice / confuser rejection (the current ECHO problem)

Research-backed discriminators between drone and speech/confusers:
- **Timbre** (MFCC/GFCC) — learned by ML, separates "buzz" from voice/birds.
- **Continuity** — drone tone is unbroken; speech has breath/syllable/stop-consonant gaps. (ECHO's continuity gate.)
- **Pitch stability** — drone holds near-constant BPF; speech glides with intonation. (ECHO's drift gate.)
- **Harmonic regularity** — propeller comb is evenly spaced; voice formants make harmonics uneven. (ECHO's contiguous-comb gate.)
- **Conclusion from the literature:** rule-based gates help, but **ML (CNN on mel-spectrogram) is the robust solution** — it learns the full timbral signature and rejects voice/fans/birds without hand-tuning.

## 8. How this maps to ECHO

**Already aligned with best practice:**
- Harmonic-stack / blade-pass detection (correct physical model).
- GCC-PHAT + SRP-PHAT DOA (matches the localization literature).
- Drift / continuity / comb gates (the right rule-based discriminators).
- Range expectations and windscreen requirement.

**Recommended next improvements (research-backed):**
1. **ML classifier (Phase B):** CNN on **mel-spectrograms**, trained on DroneAudioDataset + the 32-UAV multiclass set, optionally GAN-augmented. This is the field's answer to voice false alarms.
2. **GFCC features** for outdoor noise robustness over MFCC.
3. **Drone-type ID** (multiclass) once binary detection is solid — the 32-UAV dataset enables it.
4. **Distributed multi-node arrays** for true position (not just bearing) — Phase 3.
5. **Windscreen + low-LF-noise mic** for any real outdoor node.

---

## Sources

- Counter-UAS 101 — Acoustic Drone Detection (drone-warfare.com)
- Robust Drone Detection for Acoustic Monitoring (EUSIPCO 2020)
- Passive acoustic detection and localization of drones using MEMS microphones and ML (Acta Acustica, 2026)
- Lightweight ML models for drone detection using acoustic + optical features (Springer, 2025)
- A Multiclass Acoustic Dataset and Interactive Tool for Analyzing Drone Signatures (arXiv 2509.04715, 2025)
- AUDRON: Deep Learning Framework with Fused Acoustic Signatures for Drone Type Recognition (arXiv 2512.20407)
- HMM-based drone sound recognition using MFCC in noisy environments (ResearchGate)
- Deep Learning-Based Acoustic Recognition of UAVs in Complex Environments (MDPI Drones, 2025)
- Drones Detection Using a Fusion of RF and Acoustic Features and DNNs (Sensors/PMC, 2024)
- Audio-Based Drone Detection & Identification w/ Deep Learning + GAN augmentation (MDPI Sensors 21:4953)
- Acoustic Source Drone Detection Using Tetrahedral Microphone Array and DNNs (MDPI Sensors, 2026)
- Outdoor Microphone Range Tests and Spectral Analysis of UAV Acoustic Signatures (MDPI Sensors 25:7057)
- Drone Detection and Tracking Based on Fused Acoustical and Optical Approaches (Wiley Adv. Intelligent Systems, 2023)
- Analysis of Distance and Environmental Impact on UAV Acoustic Detection (ResearchGate)
- From classical approaches to recent advancements: A holistic review of acoustic detection for UAVs (AIP Advances 15:120701)
- Performance Enhancement of Drone Acoustic Source Localization Through Distributed Microphone Arrays (MDPI Sensors 25:1928)
- DroneDetect Dataset: RF dataset of UAS Signals (IEEE DataPort)
- DroneAudioDataset — Sara Al-Emadi (GitHub)

---

## Addendum (research pass 2) — signature detail + actionable fixes

### Refined signature facts
- **Blade-pass fundamental varies widely by drone size:** small/fast props ~400-600 Hz; larger/slower props ~100-300 Hz. (Confirms ECHO's 50-700 Hz window; your heavy-lift targets sit low.)
- **Harmonics extend 1-5 kHz, sometimes 10-15 kHz**; primary energy in the low kHz. Full useful band ~100 Hz-10 kHz.
- **Temporal modulation is itself a signature.** Rotors produce periodic amplitude/frequency modulation that is *sustained* over time — this is a distinguishing feature vs. transient sounds (dings, claps, single words). Backs a duration/persistence gate.
- **STFT params used in current papers:** 2048-sample window, Hann, ~23 Hz resolution, hop 160. (Finer than ECHO's; would sharpen wobble/beat precision.)

### State-of-the-art recognition
- **AUDRON** (2025): MFCC + STFT-CNN + recurrent (temporal) + autoencoder fusion -> 98.5%/97.1%.
- **Ensemble learning for micro-drones** (2026): integrated acoustic signatures across multiple classifiers for small/quiet UAVs.
- Common thread: **temporal modeling matters** (recurrent layers / sustained structure), not just per-frame spectra.

### Two fixes this directly supports for ECHO
1. **Sustained-duration gate** — research shows the drone signature is *sustained periodic modulation*; brief tonal sounds (text dings, beeps, claps) are not. Requiring ~2-3 s of continuous positive detection rejects those false alarms threshold-independently.
2. **Augmented retraining (fixes the speaker-playback / threshold problem WITHOUT needing field recordings):** papers synthesize/augment training audio by adding **modulation + noise + environmental factors + reverb**. Applying the same to the real DroneAudioDataset clips (add room noise, band-limiting, level variation to mimic speaker playback) would teach the model to score degraded/real-world drone audio HIGH -> lets a safe 0.5 threshold work everywhere, killing the per-machine tuning loop.

### Sources (pass 2)
- The Acoustic Signature of Drones: Detection, Identification, and Countermeasure Possibilities (2025)
- AUDRON: Deep Learning Framework with Fused Acoustic Signatures (arXiv 2512.20407)
- Ensemble learning models for micro-drone detection using integrated acoustic signatures (Springer, 2026)
- Acoustic Source Drone Detection Using Tetrahedral Mic Array + DNNs (MDPI Sensors 26:1778)
- Outdoor Microphone Range Tests and Spectral Analysis of UAV Acoustic Signatures (PMC)
