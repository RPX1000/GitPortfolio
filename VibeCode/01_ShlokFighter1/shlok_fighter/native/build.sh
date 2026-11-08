#!/bin/sh
# Builds the native audio synth for the current platform. Safe to re-run any time
# synth.cpp changes; audio.py falls back to pure Python if this hasn't been run
# or fails, so the game works fine without it.
#
# macOS / Linux: run this script.
# Windows: not buildable from here. Either run it under WSL/MSYS2 to produce
#   libsynth.so and ship that to WSL users, or build synth.dll with MSVC/MinGW, e.g.
#   cl /O2 /LD synth.cpp /Fe:synth.dll
#   (or, with MinGW-w64)  g++ -O3 -shared -static -o synth.dll synth.cpp
set -e
cd "$(dirname "$0")"

case "$(uname -s)" in
    Darwin) out=libsynth.dylib ;;
    Linux)  out=libsynth.so ;;
    *) echo "Unrecognised platform $(uname -s); build synth.cpp with your own compiler." >&2; exit 1 ;;
esac

clang++ -O3 -std=c++17 -shared -fPIC -o "$out" synth.cpp \
    || g++ -O3 -std=c++17 -shared -fPIC -o "$out" synth.cpp
echo "built $(pwd)/$out"
