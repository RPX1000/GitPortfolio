// Native synthesis for Shlok Fighter 1's procedural audio.
//
// This is a line-for-line port of the hot loops in audio.py's _sweep, _noise and
// _render_track: plain per-sample sine/noise math that a Python for-loop does slowly
// and a compiled loop does fast. Nothing here talks to pygame or SDL - every function
// just fills a caller-supplied buffer of doubles, exactly like the Python functions
// return a list of floats. audio.py falls back to the pure-Python versions whenever
// this library can't be loaded, so nothing here is required to run the game.
//
// Build: see build.sh in this folder. Produces libsynth.dylib (macOS), libsynth.so
// (Linux) or synth.dll (Windows, built elsewhere - see build.sh's comment).

#include <cmath>
#include <random>
#include <algorithm>

namespace {
constexpr double PI = 3.14159265358979323846;

double midi_freq(double m) {
    return 440.0 * std::pow(2.0, (m - 69.0) / 12.0);
}
}  // namespace

extern "C" {

// Mirrors _sweep(f0, f1, dur, wave, amp, decay): a frequency glide with an
// exponential decay envelope. wave: 0 = sine, 1 = square, 2 = triangle.
// The caller has already worked out n = max(1, int(dur * rate)).
void sweep(double f0, double f1, int wave, double amp, double decay, int rate,
           double* out, int n) {
    double phase = 0.0;
    for (int i = 0; i < n; ++i) {
        double t = static_cast<double>(i) / n;
        phase += 2.0 * PI * (f0 + (f1 - f0) * t) / rate;
        double s;
        if (wave == 1) {
            s = std::sin(phase) >= 0.0 ? 1.0 : -1.0;
        } else if (wave == 2) {
            s = 2.0 / PI * std::asin(std::sin(phase));
        } else {
            s = std::sin(phase);
        }
        out[i] = amp * s * std::exp(-decay * t);
    }
}

// Mirrors _noise(dur, amp, decay, brightness): a one-pole filtered noise burst.
// seed comes from the Python side (random.getrandbits(32)) so every call still
// sounds fresh from run to run, the way the unseeded Python version did.
void noise(double amp, double decay, double brightness, unsigned int seed,
           double* out, int n) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> uni(-1.0, 1.0);
    double y = 0.0;
    for (int i = 0; i < n; ++i) {
        y += (uni(rng) - y) * brightness;
        out[i] = amp * y * std::exp(-decay * static_cast<double>(i) / n);
    }
}

// Mirrors _render_track(spec): builds one looping bar-by-bar music track - a warm
// pad, a plucked bass, and optional kick, hats and arpeggio layers - into `out`.
//
// beat, bar and n_bar are precomputed by the Python caller from spec["bpm"] and the
// mixer's sample rate, so the two sides can never disagree about buffer sizes.
// chord_offsets[i] / chord_major[i] (1 = major, 0 = minor) describe chord i of
// n_chords; out must hold n_bar * n_chords samples and is zeroed here.
void render_track(double root_base, double beat, double bar, int n_bar,
                   const double* chord_offsets, const int* chord_major, int n_chords,
                   int kick, int hats, int arp, unsigned int seed, int rate,
                   double* out) {
    std::fill(out, out + static_cast<long>(n_bar) * n_chords, 0.0);
    std::mt19937 rng(seed);  // only advanced inside the hats layer, like Python's rnd
    std::uniform_real_distribution<double> uni(-1.0, 1.0);
    static const int MINOR[3] = {0, 3, 7};
    static const int MAJOR[3] = {0, 4, 7};

    for (int bi = 0; bi < n_chords; ++bi) {
        long base = static_cast<long>(bi) * n_bar;
        const int* intervals = chord_major[bi] ? MAJOR : MINOR;
        double root = root_base + chord_offsets[bi];

        // warm pad, faded in and out so the loop join is silent
        for (int k = 0; k < 3; ++k) {
            double step = 2.0 * PI * midi_freq(root + intervals[k] + 12) / rate;
            double phase = 0.0;
            for (int i = 0; i < n_bar; ++i) {
                double t = static_cast<double>(i) / n_bar;
                double env = std::min(1.0, t / 0.18) * std::min(1.0, (1.0 - t) / 0.22);
                out[base + i] += 0.05 * env * std::sin(phase);
                phase += step;
            }
        }

        // plucked bass on every beat
        {
            double bass_step = 2.0 * PI * midi_freq(root - 12) / rate;
            int ln = static_cast<int>(0.5 * beat * rate);
            for (int b = 0; b < 4; ++b) {
                long start = base + static_cast<long>(b * beat * rate);
                double phase = 0.0;
                for (int j = 0; j < ln; ++j) {
                    long idx = start + j;
                    if (idx >= base + n_bar) break;
                    out[idx] += 0.18 * std::exp(-5.5 * j / static_cast<double>(ln)) * std::sin(phase);
                    phase += bass_step;
                }
            }
        }

        if (kick) {
            int ln = static_cast<int>(0.22 * rate);
            int beats[2] = {0, 2};
            for (int b : beats) {
                long start = base + static_cast<long>(b * beat * rate);
                double phase = 0.0;
                for (int j = 0; j < ln; ++j) {
                    long idx = start + j;
                    if (idx >= base + n_bar) break;
                    double freq = 42.0 + 90.0 * std::exp(-4.0 * j / static_cast<double>(ln));
                    phase += 2.0 * PI * freq / rate;
                    out[idx] += 0.3 * std::exp(-7.0 * j / static_cast<double>(ln)) * std::sin(phase);
                }
            }
        }

        if (hats) {
            int ln = static_cast<int>(0.04 * rate);
            for (int k = 0; k < 8; ++k) {
                long start = base + static_cast<long>(k * bar / 8.0 * rate);
                for (int j = 0; j < ln; ++j) {
                    long idx = start + j;
                    if (idx >= base + n_bar) break;
                    out[idx] += 0.05 * std::exp(-60.0 * j / static_cast<double>(ln)) * uni(rng);
                }
            }
        }

        if (arp) {
            int ln = static_cast<int>(0.5 * beat * rate);
            double notes[3] = {root + 24 + intervals[0], root + 24 + intervals[1], root + 24 + intervals[2]};
            for (int k = 0; k < 8; ++k) {
                double step = 2.0 * PI * midi_freq(notes[k % 3]) / rate;
                long start = base + static_cast<long>(k * bar / 8.0 * rate);
                double phase = 0.0;
                for (int j = 0; j < ln; ++j) {
                    long idx = start + j;
                    if (idx >= base + n_bar) break;
                    out[idx] += 0.045 * std::exp(-7.0 * j / static_cast<double>(ln)) * std::sin(phase);
                    phase += step;
                }
            }
        }
    }
}

}  // extern "C"
