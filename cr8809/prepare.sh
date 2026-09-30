#!/usr/bin/env bash
set -euo pipefail
PORT_DIR=$(cd "$(dirname "$0")" && pwd)
WORK_DIR=${CR8809_WORK_DIR:?set CR8809_WORK_DIR outside the checkout}
mkdir -p "$WORK_DIR"
checkout() {
  local url=$1 revision=$2 directory=$3
  git init "$directory"
  git -C "$directory" remote add origin "$url"
  git -C "$directory" fetch --depth 1 origin "$revision"
  git -C "$directory" checkout --detach FETCH_HEAD
}
checkout https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2.git 932cee77ba08d84bdb6853e5648a815c6d00ceb1 "$WORK_DIR/nss-port"
checkout https://github.com/qosmio/openwrt-ipq.git 92a2d104145c8d265851c4b388a41bd8e9c21cd9 "$WORK_DIR/wifi-nss-donor"
# Insert the feed lock before the donor resolves its package graph.
python3 - "$WORK_DIR/nss-port/build.sh" "$PORT_DIR" <<'PYLOCK'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
anchor = './scripts/feeds update -a'
assert text.count(anchor) == 1
text = text.replace(anchor, 'python3 "' + sys.argv[2] + '/lock-feeds.py" "$PWD"\n' + anchor)
path.write_text(text)
PYLOCK
# This prepares the pinned 6.12 source and the upstream-tested IPQ5018 NSS
# interfaces. Board-specific RD03v2 state is replaced below, before compiling.
NSS=1 PREPARE_ONLY=1 WIFI_NSS_DONOR="$WORK_DIR/wifi-nss-donor" \
  bash "$WORK_DIR/nss-port/build.sh"
python3 "$PORT_DIR/adapt-m79a.py" "$WORK_DIR/nss-port/openwrt"
cd "$WORK_DIR/nss-port/openwrt"
make defconfig
python3 "$PORT_DIR/adapt-m79a.py" --check "$PWD"
./scripts/diffconfig.sh > cr8809.config.buildinfo
