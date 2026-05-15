/**
 * Minimal Web Audio synth for viz components.
 * Triangle-wave oscillator with a quick ADSR envelope — gives a clean
 * electric-piano quality without needing sample files.
 */

let ctx: AudioContext | null = null;

function getCtx(): AudioContext {
	if (!ctx) ctx = new AudioContext();
	return ctx;
}

/** Resume audio context after user gesture (browsers require this). */
export function resumeAudio(): void {
	const c = getCtx();
	if (c.state === 'suspended') c.resume();
}

/** MIDI note number → frequency in Hz. */
export function midiToFreq(note: number): number {
	return 440 * Math.pow(2, (note - 69) / 12);
}

/** Note name (e.g. "C4") → MIDI note number. */
const NOTE_OFFSETS: Record<string, number> = {
	C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3,
	E: 4, F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8,
	Ab: 8, A: 9, 'A#': 10, Bb: 10, B: 11
};

export function noteToMidi(name: string): number {
	const match = name.match(/^([A-Ga-g][#b]?)(\d)$/);
	if (!match) return 60;
	const offset = NOTE_OFFSETS[match[1]] ?? 0;
	const octave = parseInt(match[2]);
	return 12 * (octave + 1) + offset;
}

export interface PlayOptions {
	/** MIDI note number (default 60 = C4). */
	midi?: number;
	/** Frequency in Hz (overrides midi). */
	freq?: number;
	/** Duration in seconds (default 0.25). */
	duration?: number;
	/** Gain 0–1 (default 0.15). */
	gain?: number;
	/** Oscillator type (default 'triangle'). */
	type?: OscillatorType;
	/** Delay before note starts, in seconds. */
	delay?: number;
}

/**
 * Play a single note with ADSR envelope.
 * Returns immediately — sound is scheduled via Web Audio.
 */
export function playNote(opts: PlayOptions = {}): void {
	const c = getCtx();
	if (c.state === 'suspended') return; // not yet resumed

	const freq = opts.freq ?? midiToFreq(opts.midi ?? 60);
	const dur = opts.duration ?? 0.25;
	const vol = opts.gain ?? 0.15;
	const type = opts.type ?? 'triangle';
	const startOffset = opts.delay ?? 0;

	const now = c.currentTime + startOffset;

	const osc = c.createOscillator();
	osc.type = type;
	osc.frequency.value = freq;

	const env = c.createGain();
	env.gain.setValueAtTime(0, now);
	// Attack: 8ms
	env.gain.linearRampToValueAtTime(vol, now + 0.008);
	// Decay to sustain: 60ms → 60% of peak
	env.gain.linearRampToValueAtTime(vol * 0.6, now + 0.068);
	// Release: ramp to 0 before note end
	env.gain.setValueAtTime(vol * 0.6, now + dur * 0.7);
	env.gain.linearRampToValueAtTime(0, now + dur);

	osc.connect(env);
	env.connect(c.destination);
	osc.start(now);
	osc.stop(now + dur + 0.05);
}

/**
 * Play a chord (multiple notes simultaneously).
 */
export function playChord(midis: number[], opts: Omit<PlayOptions, 'midi' | 'freq'> = {}): void {
	const perNoteGain = (opts.gain ?? 0.12) / Math.max(midis.length, 1);
	for (const midi of midis) {
		playNote({ ...opts, midi, gain: perNoteGain });
	}
}

/** Common chord shapes as semitone offsets from root. */
export const CHORD_SHAPES: Record<string, number[]> = {
	major: [0, 4, 7],
	minor: [0, 3, 7],
	dim: [0, 3, 6],
	'7': [0, 4, 7, 10],
	m7: [0, 3, 7, 10],
	maj7: [0, 4, 7, 11]
};

/**
 * Parse a chord symbol ("Am", "F", "G7", "Em7") and return MIDI notes
 * rooted at the given octave.
 */
export function chordToMidis(symbol: string, octave = 3): number[] {
	const match = symbol.match(/^([A-G][#b]?)(m7|maj7|m|7|dim)?$/);
	if (!match) return [60, 64, 67]; // fallback C major

	const root = NOTE_OFFSETS[match[1]] ?? 0;
	const quality = match[2] ?? '';

	let shape: number[];
	if (quality === 'm7') shape = CHORD_SHAPES.m7;
	else if (quality === 'maj7') shape = CHORD_SHAPES.maj7;
	else if (quality === '7') shape = CHORD_SHAPES['7'];
	else if (quality === 'm') shape = CHORD_SHAPES.minor;
	else if (quality === 'dim') shape = CHORD_SHAPES.dim;
	else shape = CHORD_SHAPES.major;

	const rootMidi = 12 * (octave + 1) + root;
	return shape.map((s) => rootMidi + s);
}
