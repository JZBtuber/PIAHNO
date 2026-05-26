# PIAHNO – Data Collector

## Overview

**Data Collector** is a desktop application developed for the **PIAHNO** project in the **S2M Laboratory** by **Justin Boileau** under the **Université de Montréal**.

Its purpose is to help **objectively analyze piano performances** by displaying and recording multiple observation feeds in the same workspace.

The application can combine up to **8 windows at once** in a single interface and currently supports:

* **Video feeds**
* **Audio feeds**
* **MIDI feeds**

---

## What the app does

The app lets you:

* open multiple observation windows side by side
* use either **live input** or **files** depending on the feed type
* start, pause, stop, and record active feeds
* compare video, audio, and MIDI information in the same session

This makes it useful for reviewing a performance from several angles at once.

---

## Feed types

## Video

A video window can use:

* a **live camera**
* a **video file**

Video windows display the image and show an FPS counter.

They also include an optional **MediaPipe hand-tracking mode** that can:

* detect hands in the frame
* draw landmarks on the image
* show only the detected hand information on a dark background

## Audio

An audio window can use:

* a **live microphone or audio input**
* a **WAV file**

Audio windows display a simple real-time level visualizer.

## MIDI

A MIDI window can use:

* a **live MIDI device**
* a **MIDI file**

MIDI windows show incoming or played notes in a list so the user can follow note activity while the feed is running.

---

## Main controls

Each window includes:

* **Start**
* **Pause / Resume**
* **Stop**
* **Mute** for audio-capable feeds
* **Use live input**
* **Reload Devices**
* a device selector
* a file path field
* **Browse**

The main toolbar also includes global controls for:

* adding or removing windows
* starting all windows
* pausing/resuming all windows
* stopping all windows
* starting recording for all windows
* stopping recording for all windows

---

## Recording

The app includes recording support for the current session.

Recorded files are saved in timestamped folders under a `Tests` directory.

Typical output formats are:

* **Video:** `.mp4`
* **Audio:** `.wav`
* **MIDI:** `.mid`

---

## Typical use

A typical workflow is:

1. Add the windows you need.
2. Choose either a live input or a file for each one.
3. Start the feeds.
4. Observe the performance across video, audio, and MIDI.
5. Record the session if needed.

---

## Current state of the app

The app is already usable for multi-source observation, but some parts are still in progress.

At the moment, it is best suited for:

* experimental analysis workflows
* synchronized observation of performance-related inputs
* development and testing inside the PIAHNO project

Some advanced menu entries are still incomplete, and packaged executable builds may require extra setup, especially for the MediaPipe video option.

---

## Requirements

The current application uses Python with the following main libraries:

* **PyQt6**
* **OpenCV**
* **PyAudio**
* **mido**
* **numpy**
* **MediaPipe**

The MediaPipe hand-tracking option requires the model file:

```text
src/video/hand_landmarker.task
```

---

## License

This project is distributed under the **GNU General Public License v3.0 (GPL-3.0)**.

See the `LICENSE` file included with the project for the full license text.

---

## Credits

Developed for the **PIAHNO** project in the **S2M Laboratory**.

**Author:** Justin Boileau
**Institution:** Université de Montréal
