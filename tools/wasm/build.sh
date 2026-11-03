#!/bin/sh
# Builds solver.wasm from solver.c (clang 18 with the wasm32 target and wasm-ld; nothing else is needed).
# MAX_NODES and TABLE_BITS (see core.h) can be given in the environment, for experiments.
set -e
cd "$(dirname "$0")"
EXPORTS="solve solve_tuned nodes_made image_address path_address expansions_done gaps_address tuning_address load_position position_moves position_step position_score position_key_high position_key_low"
FLAGS=""
for name in $EXPORTS; do FLAGS="$FLAGS -Wl,--export=$name"; done
MEMORY=$(( ${MEMORY_MB:-32} * 1048576 ))
clang --target=wasm32 -O3 -nostdlib -fno-builtin -ffreestanding -Wall -Wextra -Wno-unused-function \
  ${MAX_NODES:+-DMAX_NODES=$MAX_NODES} ${TABLE_BITS:+-DTABLE_BITS=$TABLE_BITS} \
  -Wl,--no-entry $FLAGS -Wl,--export-memory -Wl,--initial-memory=$MEMORY -Wl,--max-memory=$MEMORY -Wl,-z,stack-size=65536 \
  -o "${OUT:-solver.wasm}" solver.c
ls -l "${OUT:-solver.wasm}"
