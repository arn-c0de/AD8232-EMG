# Multi-Channel EMG Gesture Guide

## Purpose

This document explains how to move from a single `AD8232` channel to a multi-channel EMG setup for:

- multiple hand gestures,
- better forearm muscle separation,
- limited finger-related gesture recognition.

## Important Limitation

Surface EMG can separate several gesture patterns, but **individual finger control is not cleanly isolated** with one simple channel. The forearm has strong anatomical coupling and crosstalk between nearby muscles.

Source:
- Mogk and Keir, proximal forearm crosstalk study: https://pubmed.ncbi.nlm.nih.gov/12488088/

Practical meaning:

- one channel is usually good for `rest vs contract`,
- two channels can often separate `grip vs open`,
- three to four channels can classify several trained gestures,
- true per-finger decoding usually needs more channels and better algorithms.

## General Multi-Channel Placement Rules

For multi-channel surface EMG:

- treat each `AD8232` as one bipolar channel,
- place each pair on a **different target muscle region**,
- keep each active pair aligned with local muscle fibers,
- avoid stacking channels too close together,
- keep cable motion low,
- expect placement repeatability to matter a lot.

Sources:
- SENIAM sensor location: https://seniam.org/sensorlocation.htm
- SENIAM fixation guidance: https://seniam.org/fixation.htm
- CEDE overview: https://cede.isek.org/

## Best First Upgrade: Two Channels

The best low-cost improvement over one channel is usually:

1. one channel on the **forearm flexor side**
2. one channel on the **forearm extensor side**

Why this works:

- flexion-heavy gestures and extension-heavy gestures produce clearly different activation patterns,
- flexor and extensor compartments are easier to separate than neighboring muscles on the same side.

### Suggested two-channel layout

#### Channel 1

- target: `FCR` or `FDS` region
- purpose: fist, grip, pinch-like flexion effort

#### Channel 2

- target: `ED` region
- purpose: hand opening, release, extension

### AD8232 lead mapping per channel

- `YELLOW` = `LA+`
- `RED` = `RA-`
- `GREEN` = `RL` reference

Per channel:

- `YELLOW`: proximal electrode on the target muscle belly,
- `RED`: distal electrode on the same fiber line,
- `GREEN`: reference on a bony or relatively inactive site.

## Three- to Four-Channel Forearm Layout

If the goal is more than `open/close`, a practical 3-4 channel forearm layout is:

1. `FCR` region
2. `FCU` or `FDS` region
3. `ED` region
4. `BRD` or radial extensor region

Why these channels are useful:

- they sample both forearm compartments,
- they capture different hand/wrist synergies,
- they are more practical than trying to isolate deep finger muscles directly.

### Example 4-channel arrangement

```
Volar side:
  CH1 -> FCR/FDS region
  CH2 -> FCU region

Dorsal/radial side:
  CH3 -> ED region
  CH4 -> BRD or radial extensor region
```

## Can Multi-Channel Forearm EMG Distinguish Finger Movements?

### Short answer

Yes, to a degree, but not perfectly.

Research with multi-channel forearm EMG shows that different finger and wrist tasks can create distinct spatial activity patterns, but those patterns are influenced by wrist posture and neighboring-muscle activity.

Sources:
- Gazzoni et al., multi-channel forearm EMG mapping: https://pmc.ncbi.nlm.nih.gov/articles/PMC4188712/
- Pelaez Murciego et al., online gesture classification with wrist-position changes: https://link.springer.com/article/10.1186/s12984-022-01056-w

### Practical expectations

Reasonable expectations:

- `2 channels`: `grip vs open`
- `3-4 channels`: several trained hand gestures
- `many channels`: better finger-pattern separation

Unrealistic expectation:

- one simple forearm channel reliably telling `index`, `middle`, `ring`, `little`.

## Using Several AD8232 Modules

### Is it possible?

Yes. One `AD8232` can be used per bipolar EMG channel.

### Good architecture

- `1 module` = simple trigger
- `2 modules` = basic flexor/extensor gesture sensing
- `3-4 modules` = practical small gesture-classification prototype

### Wiring notes

- keep analog leads short,
- secure cables to reduce motion artifact,
- use battery power during measurement,
- sample channels at stable timing,
- expect more noise as cable count grows.

## Best Strategy for Multiple Gestures

The best hobby-scale path is:

1. record raw EMG from each channel,
2. compute features such as `RMS`, `MAV`, `waveform length`, `zero crossings`,
3. train a classifier such as `LDA`, `SVM`, or a small `ANN`.

Good first gesture set:

- rest
- fist
- open hand
- pinch
- point

A 2022 study reported strong subject-specific hand/finger gesture classification using only three forearm channels on `FCR`, `FCU`, and `BRD`.

Source:
- Lee et al., *Sensors* 2022: https://www.mdpi.com/1424-8220/22/1/225

## When You Need More Than Simple Multi-Channel Forearm EMG

If your real goal is reliable individual-finger decoding, the better direction is often:

- more channels around the forearm,
- high-density EMG,
- intrinsic hand-muscle EMG,
- or a hybrid system with IMU, glove, or bend sensors.

Finger-movement datasets show that combining extrinsic forearm muscles with intrinsic hand muscles improves dexterous finger recognition.

Source:
- Hu et al., *Scientific Data* 2022: https://pmc.ncbi.nlm.nih.gov/articles/PMC9243097/

## Practical Recommendation for This Repository

The most sensible upgrade path here is:

1. keep the current project for single-channel threshold control,
2. add a second forearm channel on the opposite compartment,
3. move to `3-4` channels for a small trained gesture set,
4. avoid expecting true per-finger control from simple threshold logic.

## References

- SENIAM, sensor location: https://seniam.org/sensorlocation.htm
- SENIAM, placement and fixation: https://seniam.org/fixation.htm
- CEDE project overview: https://cede.isek.org/
- Mogk JPM, Keir PJ. Crosstalk in surface electromyography of the proximal forearm during gripping tasks. PubMed entry: https://pubmed.ncbi.nlm.nih.gov/12488088/
- Gazzoni M et al. Quantifying Forearm Muscle Activity during Wrist and Finger Movements by Means of Multi-Channel Electromyography. https://pmc.ncbi.nlm.nih.gov/articles/PMC4188712/
- Pelaez Murciego L et al. Reducing the number of EMG electrodes during online hand gesture classification with changing wrist positions. https://link.springer.com/article/10.1186/s12984-022-01056-w
- Lee KH et al. Electromyogram-Based Classification of Hand and Finger Gestures Using Artificial Neural Networks. https://www.mdpi.com/1424-8220/22/1/225
- Hu X et al. Finger Movement Recognition via High-Density Electromyography of Intrinsic and Extrinsic Hand Muscles. https://pmc.ncbi.nlm.nih.gov/articles/PMC9243097/
