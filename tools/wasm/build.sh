#!/bin/sh
# Builds forty.wasm from forty.c (clang 18 with the wasm32 target and wasm-ld; nothing else is needed).
set -e
cd "$(dirname "$0")"
clang --target=wasm32 -O3 -nostdlib -fno-builtin -ffreestanding -Wall -Wextra -Wno-unused-function \
  -Wl,--no-entry -Wl,--export=solve -Wl,--export=deck_address -Wl,--export=path_address -Wl,--export=expansions_done \
  -Wl,--export-memory -Wl,--initial-memory=33554432 -Wl,--max-memory=33554432 -Wl,-z,stack-size=65536 \
  -o forty.wasm forty.c
ls -l forty.wasm
