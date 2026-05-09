# Single-Channel EMG Placement Guide

## Purpose

This document is a practical guide for using a single `AD8232` channel for simple EMG detection.

It focuses on:

1. where to place one EMG channel,
2. which body locations are easiest and most useful,
3. how to choose a muscle for `on/off` or simple trigger control.

## General Placement Rules

For a single bipolar surface EMG channel:

- place the two active electrodes on the **muscle belly**,
- align them **parallel to the muscle fibers**,
- avoid tendons and bony landmarks for the active pair,
- keep about **20 mm** electrode spacing as a good baseline,
- place the reference electrode on a **bony or relatively inactive site**,
- clean the skin and reduce cable movement.

Sources:
- SENIAM sensor location: https://seniam.org/sensorlocation.htm
- SENIAM fixation guidance: https://seniam.org/fixation.htm
- CEDE overview: https://cede.isek.org/

## How to Choose the Best Single-Channel Location

For one channel, the best location is usually:

- a **large superficial muscle**,
- with a **clear contraction** during the movement you want,
- with **low crosstalk** from nearby muscles,
- and with **repeatable placement**.

Good single-channel EMG is usually about choosing **one clear muscle for one clear action**.

## Best Body Locations for One EMG Channel

## Biceps

Use the biceps when the goal is:

- elbow flexion detection,
- strong `on/off` control,
- simple beginner experiments.

Why it is good:

- large superficial muscle,
- easy to palpate,
- strong signal during elbow flexion.

Placement:

- active pair on the mid-belly of the biceps,
- reference on a nearby bony or relatively inactive site.

## Triceps

Use the triceps when the goal is:

- elbow extension detection,
- simple extension-trigger control.

Why it is good:

- large superficial muscle,
- easy functional separation from biceps.

Placement:

- active pair on the triceps belly,
- reference on a stable bony or inactive area.

## Forearm Flexor Side

Use the forearm flexor side when the goal is:

- grip detection,
- fist detection,
- general hand-closing effort.

Best general region:

- **volar/anterior forearm**,
- **proximal to mid forearm**,
- over a clear superficial flexor area.

Good targets:

- `Flexor carpi radialis (FCR)`
- `Flexor carpi ulnaris (FCU)`
- `Flexor digitorum superficialis (FDS)` region

Practical note:

- this is usually better than placing a channel at a random inner-forearm point.

## Forearm Extensor Side

Use the forearm extensor side when the goal is:

- hand-open detection,
- release detection,
- finger-extension-heavy gestures.

Best general region:

- **dorsal/posterior forearm**,
- **proximal to mid forearm**.

Good targets:

- `Extensor digitorum (ED)`
- radial extensor region

## Shoulder

Use the shoulder when the goal is:

- gross arm movement detection,
- simple wearable triggers,
- posture-related control.

Common targets:

- `anterior deltoid`
- `middle deltoid`
- `posterior deltoid`

Good for:

- large arm movements,
- coarse control states.

## Chest

Use the chest when the goal is:

- large intentional contractions,
- switch-like control,
- accessibility-oriented interfaces.

Common target:

- `pectoralis major`

## Calf

Use the calf when the goal is:

- foot press or plantarflexion detection,
- lower-limb trigger control.

Common target:

- `gastrocnemius`

## Jaw / Face

Use face or jaw muscles only for specific facial-control applications such as:

- jaw clench detection,
- blink or facial-trigger interfaces.

## Best Forearm Placement for This Repository

For the current single-channel `AD8232` project, the best practical options are:

### Option 1: Grip / Fist Detector

- place the active pair on the **forearm flexor side**,
- target `FCR`, `FCU`, or `FDS` region,
- place the reference on a bony wrist area.

### Option 2: Hand-Open Detector

- place the active pair on the **forearm extensor side**,
- target `ED` or radial extensor region,
- place the reference on a bony wrist or elbow area.

### AD8232 lead mapping

- `YELLOW` = `LA+`
- `RED` = `RA-`
- `GREEN` = `RL` reference

Practical rule:

- `YELLOW`: first electrode on the target muscle belly, slightly more proximal,
- `RED`: second electrode on the same fiber line, about `2-3 cm` more distal,
- `GREEN`: reference on a bony or relatively inactive location.

## Locations to Avoid

Avoid these as primary active-electrode sites:

- directly over tendons,
- directly over bone,
- very distal wrist tendon zones,
- crowded areas where several muscles overlap strongly,
- arbitrary spots chosen without palpating the muscle during contraction.

## Practical Recommendation

If you only want one simple EMG trigger, the easiest and most reliable options are usually:

1. `biceps` for arm-flex control,
2. `forearm flexor side` for grip/fist,
3. `forearm extensor side` for hand-open detection.

For this repository specifically, the best single-channel improvement is to switch from a generic inner-forearm placement to a **deliberate flexor or extensor target**.

## References

- SENIAM, sensor location: https://seniam.org/sensorlocation.htm
- SENIAM, placement and fixation: https://seniam.org/fixation.htm
- CEDE project overview: https://cede.isek.org/
