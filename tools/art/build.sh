#!/bin/sh
# Rebuilds the embedded card faces from the CC0 npm package and writes them into baize.html.
set -eu
cd "$(dirname "$0")"
npm install --silent
tmp=$(mktemp -d)
(cd "$tmp" && npm pack @letele/playing-cards@0.1.0 --silent >/dev/null && tar xzf ./*.tgz)
cp "$tmp/package/dist/index.esm.js" cards.mjs
rm -rf "$tmp"
node all.mjs
node embed.mjs
