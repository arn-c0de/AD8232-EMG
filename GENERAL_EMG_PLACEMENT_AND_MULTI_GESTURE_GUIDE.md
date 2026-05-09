# General EMG Placement and Multi-Gesture Guide

## Purpose

This document is a general practical guide for hobby and prototype EMG projects with `AD8232`-style modules.

It covers:

1. general electrode-placement rules,
2. useful body locations for different EMG goals,
3. forearm placement as a dedicated section,
4. how to move from simple `on/off` detection to multiple gestures or finger-related control,
5. when several low-cost modules are enough and when more advanced sensing is needed.

## Important Limitation

Surface EMG is useful for detecting muscle activation, but it does not give perfect access to deep anatomy. Nearby muscles can contaminate each other through crosstalk, especially when electrodes are close together or placed over crowded anatomical regions.

For finger-related control, this matters a lot: the forearm contains several extrinsic finger muscles packed close together, so one channel rarely isolates a single finger cleanly.

Source:
- Mogk and Keir, proximal forearm crosstalk study: https://pubmed.ncbi.nlm.nih.gov/12488088/

## General Electrode Placement Rules

For conventional bipolar surface EMG, the most reliable baseline rules are:

- place the bipolar pair on the **muscle belly**,
- avoid tendons and bony landmarks for the active pair,
- align the two active electrodes **parallel to the muscle fibers**,
- keep a typical **inter-electrode distance around 20 mm**,
- place the reference electrode on relatively **inactive or bony tissue**,
- clean the skin and reduce cable motion.

Sources:
- SENIAM sensor-location overview: https://seniam.org/sensorlocation.htm
- SENIAM fixation recommendations: https://seniam.org/fixation.htm
- CEDE project overview: https://cede.isek.org/

## What Makes a Good EMG Location

A good EMG site usually has:

- a superficial muscle belly,
- a clear contraction during the movement of interest,
- low motion artifact,
- enough distance from neighboring muscles to reduce crosstalk,
- repeatable placement from session to session.

In practice, the best location is not "where the sticker fits", but where the signal changes strongly and repeatably during one specific movement.

## General Body Locations by Use Case

## Forearm

Use the forearm when the goal is:

- hand open/close detection,
- grip effort detection,
- pinch or point gesture classification,
- finger-related gesture research.

Best general regions:

- **volar/anterior forearm** for flexor activity,
- **dorsal/posterior forearm** for extensor activity,
- **proximal to mid forearm** rather than directly at the wrist.

Good superficial targets:

- `Flexor carpi radialis (FCR)`
- `Flexor carpi ulnaris (FCU)`
- `Flexor digitorum superficialis (FDS)` region
- `Extensor digitorum (ED)`
- radial extensor region
- `Brachioradialis (BRD)` as an additional channel in some gesture setups

Avoid:

- very distal wrist tendon zones,
- arbitrary central spots without palpation,
- trying to isolate deep finger muscles with one surface channel.

## Biceps

Use the biceps when the goal is:

- elbow flexion detection,
- simple strong `on/off` control,
- robust beginner EMG testing.

Why it is good:

- large superficial muscle,
- easy to palpate,
- strong signal during elbow flexion.

Placement idea:

- bipolar pair on the mid-belly of the biceps brachii,
- reference on a nearby bony area such as elbow region or clavicle-area inactive site depending on wiring setup.

## Triceps

Use the triceps when the goal is:

- elbow extension detection,
- antagonist pairing with biceps,
- two-state arm control.

Why it is good:

- large superficial muscle,
- easy to separate functionally from biceps.

Good pair:

- `biceps` for flexion,
- `triceps` for extension.

This is one of the easiest two-channel control setups outside the forearm.

## Shoulder

Use shoulder muscles when the goal is:

- gross arm posture or shoulder movement detection,
- wearable control where forearm access is inconvenient.

Common superficial targets:

- `anterior deltoid`
- `middle deltoid`
- `posterior deltoid`

Good for:

- lifting arm forward,
- abducting arm sideways,
- coarse multi-state control.

Less ideal for:

- fine finger or hand gesture decoding.

## Chest

Use pectoral EMG when the goal is:

- large intentional contractions,
- switch-like control,
- accessibility setups where arm muscles are not preferred.

Common target:

- `pectoralis major`

Advantages:

- large superficial muscle,
- strong intentional activation.

Limitations:

- not suitable for fine hand/finger decoding,
- can pick up motion artifact from upper body movement.

## Calf

Use calf muscles when the goal is:

- foot press / plantarflexion detection,
- ankle movement monitoring,
- leg-triggered switch control.

Common superficial target:

- `gastrocnemius`

Good for:

- strong, easily detectable contractions,
- simple lower-limb control experiments.

## Jaw / Face

Use face or jaw muscles only when the goal is clearly facial control.

Typical use cases:

- jaw clench detection,
- blink or facial-trigger interfaces.

Practical note:

- these placements are very application-specific and not a good default if your main goal is hand gesture work.

## Best Places for a Single AD8232 Channel

If you only want `active vs inactive`, choose one large superficial muscle that strongly matches the action you care about.

Good beginner single-channel choices:

- `biceps` for simple arm flex control,
- `triceps` for arm extension,
- `forearm flexor side` for grip/fist detection,
- `forearm extensor side` for hand-open detection,
- `gastrocnemius` for leg-triggered control.

For a single `AD8232`, the most useful rule is:

- choose one target muscle on purpose,
- place the bipolar pair along its fibers,
- keep the reference on a bony or relatively inactive site,
- test only one movement at a time during setup.

## Forearm Section: Best Placements for Hand and Finger Tasks

If the goal is hand or finger control, forearm placement matters more than most other body regions because fine control depends on separating similar muscles.

### Best starting targets

#### Flexion-heavy gestures

Use the **anterior / volar forearm** over:

- `FCR`
- `FCU`
- `FDS` region

Good for:

- grip,
- fist,
- squeeze,
- pinch-like flexion patterns.

#### Extension-heavy gestures

Use the **posterior / dorsal forearm** over:

- `ED`
- radial extensor region

Good for:

- hand opening,
- release,
- finger extension gestures.

### Better than the current generic forearm rule

Instead of putting one channel somewhere on the inner forearm, choose:

- one defined flexor target for `grip/fist`,
- or one defined extensor target for `open/release`.

That gives a more interpretable signal than a generic inner-forearm placement.

## Can Surface EMG Distinguish Different Fingers?

### Short answer

Yes, to a degree, but **not reliably with one threshold on one forearm muscle**.

Research with multi-channel forearm EMG shows that different finger and wrist tasks can produce distinct spatial patterns. At the same time, wrist position and neighboring-muscle activity can change those patterns significantly.

Sources:
- Gazzoni et al., multi-channel forearm EMG mapping: https://pmc.ncbi.nlm.nih.gov/articles/PMC4188712/
- Pelaez Murciego et al., online gesture classification with changing wrist positions: https://link.springer.com/article/10.1186/s12984-022-01056-w

### Practical interpretation

You should not expect:

- one channel to tell `index`, `middle`, `ring`, `little` reliably,
- one threshold to separate many gestures.

You can reasonably expect:

- one channel: `rest vs contract`,
- two channels: `grip vs open`,
- three to four channels: several trained hand gestures,
- many channels or HD-EMG: better chance of separating individual finger patterns.

## Two-Channel Forearm Layout

The best low-cost step up from one channel is usually:

- `Channel 1`: flexor side
- `Channel 2`: extensor side

### Suggested layout

```
Right forearm

Palm-up view
Elbow ---------------------------------------------- Wrist

CH1 flexor pair:
  YELLOW (LA+)   over FCR/FDS region
  RED (RA-)      2-3 cm distal on same fiber line
  GREEN (RL)     bony wrist area

Back-of-forearm view
Elbow ---------------------------------------------- Wrist

CH2 extensor pair:
  YELLOW (LA+)   over ED region
  RED (RA-)      2-3 cm distal on same fiber line
  GREEN (RL)     bony wrist or elbow reference area
```

Why it works:

- flexor-heavy gestures and extensor-heavy gestures create clearly different activity patterns,
- flexor and extensor compartments are easier to separate than neighboring muscles on the same side.

## Three- to Four-Channel Forearm Layout

If the goal is several gestures rather than just `open/close`, a practical 3-4 channel layout is:

1. `FCR` region
2. `FCU` or `FDS` region
3. `ED` region
4. `BRD` or radial extensor region

### Example 4-channel map

```
Right forearm, proximal-to-mid region

Volar side:
  CH1 -> FCR/FDS region
  CH2 -> FCU region

Dorsal/radial side:
  CH3 -> ED region
  CH4 -> BRD or radial extensor region

Each channel:
  YELLOW (LA+)   proximal electrode on muscle belly
  RED (RA-)      distal electrode on same muscle line
  GREEN (RL)     reference on bony/inactive site
```

A 2022 study reported strong subject-specific classification performance with three forearm channels on `FCR`, `FCU`, and `BRD`.

Source:
- Lee et al., *Sensors* 2022: https://www.mdpi.com/1424-8220/22/1/225

## Using Several AD8232 Modules

### Is it possible?

Yes. You can build a multi-channel prototype by using one `AD8232` per bipolar EMG channel.

### Practical architecture

- `1 AD8232 = 1 bipolar channel`
- `2 modules = basic flexor/extensor gesture sensing`
- `3 to 4 modules = practical small gesture-classification setup`

### AD8232 lead mapping

For each module:

- `YELLOW` = `LA+`
- `RED` = `RA-`
- `GREEN` = `RL` reference

Practical placement rule per module:

- `YELLOW`: place first on the target muscle belly, slightly more proximal,
- `RED`: place on the same fiber direction, usually `2-3 cm` more distal,
- `GREEN`: place on a bony or relatively inactive site, not on the active muscle belly.

### Wiring notes

- keep analog leads short,
- tape or fix cables to the skin to reduce cable-pull artifact,
- prefer battery power during measurement,
- sample channels simultaneously if possible,
- expect more noise and placement sensitivity as the cable count grows.

## Best Strategy for Multiple Finger Movements

The correct strategy depends on the ambition level.

### Option A: Low complexity hobby build

Use `2 to 4` forearm channels and classify a small gesture set such as:

- rest
- fist
- open hand
- pinch
- point

Recommended method:

- record raw EMG from each channel,
- compute short-window features such as `RMS`, `MAV`, `waveform length`, `zero crossings`,
- train `LDA`, `SVM`, or a small `ANN`.

### Option B: More finger detail without hand electrodes

Use more channels distributed around the proximal forearm and select the most informative channels.

Important findings from recent work:

- high gesture accuracy is possible with only a few channels,
- changing wrist posture usually increases the number of useful channels,
- optimized channel selection can outperform a naive uniform layout.

Source:
- Pelaez Murciego et al., *JNER* 2022: https://link.springer.com/article/10.1186/s12984-022-01056-w

### Option C: Highest finger resolution

If the real goal is many different finger movements, the better direction is:

- high-density EMG around the forearm,
- or forearm EMG plus intrinsic hand-muscle EMG,
- or a hybrid system with EMG plus IMU, glove, or bend sensors.

Finger-movement datasets and studies show that combining extrinsic forearm muscles with intrinsic hand muscles improves dexterous finger recognition.

Source:
- Hu et al., *Scientific Data* 2022: https://pmc.ncbi.nlm.nih.gov/articles/PMC9243097/

## Recommended Upgrade Path for This Repository

### Stage 1

Keep the current single-channel build for simple threshold control, but choose a more deliberate target muscle.

### Stage 2

Add a second channel on the opposite compartment:

- flexor side,
- extensor side.

Then classify:

- rest,
- grip,
- open.

### Stage 3

Move to `3 or 4` channels and train a simple classifier for:

- rest,
- fist,
- open,
- pinch,
- point.

### Stage 4

If true per-finger decoding matters, move beyond simple threshold logic and consider:

- more channels,
- intrinsic hand-muscle EMG,
- or hybrid sensing.

## Practical Recommendation

For this repository, the best cost/performance path is:

1. keep single-channel mode for basic `on/off`,
2. use a deliberate target muscle instead of a generic placement,
3. add a second forearm channel for flexor/extensor separation,
4. use `3-4` channels plus classification for multiple gestures,
5. do not expect reliable individual-finger decoding from one simple forearm channel.
