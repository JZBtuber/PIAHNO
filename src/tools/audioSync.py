import wave
import mido
import numpy as np


@staticmethod
def getAudioPeaks(filePath: str, threshold: int = 6000):
    """
    Get audio peaks from a wave file.\n
    :param `str` filePath: Path to the wave file.
    :param `int` threshold: Minimum amplitude needed to detect a peak, defaults to `6000`.
    :returns: Returns a list of detected peaks with their time and value.
    """
    # Open the wave file
    wf = wave.open(filePath)

    # Get wave file information
    sampleRate = wf.getframerate()
    channels = wf.getnchannels()
    sampleWidth = wf.getsampwidth()

    # Only accept 16-bit wave files
    if sampleWidth == 2:
        dtype = np.int16
    else:
        wf.close()
        raise ValueError("Can only read 16-bit wave files")

    # Read the audio data
    data = wf.readframes(wf.getnframes())
    wf.close()

    # Convert raw audio data to numpy samples
    samples = np.frombuffer(data, dtype=dtype)

    # Get amplitudes from mono or stereo audio
    if channels > 1:
        samples = samples.reshape(-1, channels)
        amplitudes = np.max(np.abs(samples), axis=1)
    else:
        amplitudes = np.abs(samples)

    # Set default peak variables
    peaks = []
    minGapSamples = int(sampleRate * 100 / 1000)

    insidePeak = False
    bestValue = 0
    bestIndex = 0
    lastPeakIndex = -minGapSamples

    # Find peak groups above the threshold
    for i, amplitude in enumerate(amplitudes):
        if amplitude >= threshold:
            insidePeak = True

            # Keep the highest sample inside the current peak
            if amplitude > bestValue:
                bestValue = amplitude
                bestIndex = i

        elif insidePeak:
            # Save the peak if it is far enough from the last one
            if bestIndex - lastPeakIndex >= minGapSamples:
                peaks.append({
                    "timeMs": bestIndex * 1000 / sampleRate,
                    "value": int(bestValue)
                })
                lastPeakIndex = bestIndex

            # Reset peak detection variables
            insidePeak = False
            bestValue = 0
            bestIndex = 0

    return peaks


@staticmethod
def getMidiNotes(filePath: str):
    """
    Get MIDI note-on events from a MIDI file.\n
    :param `str` filePath: Path to the MIDI file.
    :returns: Returns a list of MIDI notes with time, note number, and velocity.
    """
    # Open the MIDI file
    midi = mido.MidiFile(filePath, clip=True)

    # Set default variables
    currentTime = 0
    notes = []

    # Read every MIDI event
    for event in midi:
        currentTime += event.time

        # Save note-on events
        if event.type == "note_on" and event.velocity > 0:
            notes.append({
                "timeMs": currentTime * 1000,
                "note": event.note,
                "velocity": event.velocity
            })

    return notes
