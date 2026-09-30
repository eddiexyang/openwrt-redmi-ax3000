#!/usr/bin/env python3
"""Pin feeds to the July 2026 base instead of mixing current package metadata."""
from pathlib import Path
import json
import sys

pins = {
    'packages': ('https://github.com/openwrt/packages.git', '1302d3e88aacb698fdec91b5fb2de3bcbbe56509'),
    'luci': ('https://github.com/openwrt/luci.git', 'f7e59912304972e500fa6caf63d925c671b26cb6'),
    'routing': ('https://github.com/openwrt/routing.git', '8c2385009d29a6d4e3ecc8cc38e8c5c0d71c691f'),
    'telephony': ('https://github.com/openwrt/telephony.git', '4d8d33a023b24c52cd9443b9dc201fbdfe9c6aef'),
    'nss_packages': ('https://github.com/qosmio/nss-packages.git', '0d970dbf0185e3f53709bd803e8a466598023c57'),
}
tree = Path(sys.argv[1])
path = tree / 'feeds.conf.default'
lines = []
seen = set()
for line in path.read_text().splitlines():
    words = line.split()
    if len(words) >= 3 and words[0] == 'src-git':
        name = words[1]
        if name in ('video', 'sqm_scripts_nss'):
            lines.append('# Not part of the M79A image: ' + line)
            continue
        if name not in pins:
            raise SystemExit('Unpinned active feed: ' + name)
        url, sha = pins[name]
        lines.append(f'src-git {name} {url}^{sha}')
        seen.add(name)
    else:
        lines.append(line)
if seen != set(pins):
    raise SystemExit('Missing feed definitions: ' + str(set(pins) - seen))
path.write_text('\n'.join(lines) + '\n')
(tree / 'cr8809-feeds-lock.json').write_text(json.dumps(pins, indent=2) + '\n')
print('Pinned every active feed; excluded unused video/SQM feeds')
