import wave
import mido
import numpy as np

@staticmethod
def getAudioPeaks(filePath: str, threshold: int = 6000):
    wf = wave.open(filePath)

    sampleRate = wf.getframerate()
    channels = wf.getnchannels()
    sampleWidth = wf.getsampwidth()

    if sampleWidth == 2:
        dtype = np.int16
    else:
        wf.close()
        raise ValueError("Can only read 16-bit wave files")
    
    data = wf.readframes(wf.getnframes())
    wf.close()

    samples = np.frombuffer(data, dtype=np.int16)

    if channels > 1:
        samples = samples.reshape(-1, channels)
        amplitudes = np.max(np.abs(samples), axis=1)
    else:
        amplitudes = np.abs(samples)

    peaks = []
    minGapSamples = int(sampleRate * 100 / 1000)

    insidePeak = False
    bestValue = 0
    bestIndex = 0
    lastPeakIndex = -minGapSamples

    for i, amplitude in enumerate(amplitudes):
        if amplitude >= threshold:
            insidePeak = True

            if amplitude > bestValue:
                bestValue = amplitude
                bestIndex = i

        elif insidePeak:
            if bestIndex - lastPeakIndex >= minGapSamples:
                peaks.append({
                    "timeMs": bestIndex * 1000 / sampleRate,
                    "value": int(bestValue)
                })
                lastPeakIndex = bestIndex

            insidePeak = False
            bestValue = 0
            bestIndex = 0

    return peaks



@staticmethod
def getMidiNotes(filePath: str):
    midi = mido.MidiFile(filePath, clip=True)

    currentTime = 0
    notes = []

    for event in midi:
        currentTime += event.time

        if event.type == "note_on" and event.velocity > 0:
            notes.append({
                "timeMs" : currentTime * 1000,
                "note" : event.note,
                "velocity" : event.velocity
            })
        
    return notes