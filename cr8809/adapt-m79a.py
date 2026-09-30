#!/usr/bin/env python3
"""Adapt the pinned IPQ5018 Linux 6.12 NSS tree to CR8809 M79A."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import urllib.request

BOARD_REV = '25b90764ae9bf7cf43cb57229b98bf2211795b84'
BOARD_URL = 'https://raw.githubusercontent.com/ByteArray0/immortalwrt-device-expand/' + BOARD_REV + '/'
HERE = Path(__file__).resolve().parent
REQUIRED = ['TARGET_qualcommax_ipq50xx_DEVICE_xiaomi_cr880x-m79-v1',
            'PACKAGE_kmod-qca-nss-drv', 'PACKAGE_kmod-qca-nss-ecm',
            'PACKAGE_kmod-qca-nss-drv-pppoe', 'ATH11K_NSS_SUPPORT',
            'PACKAGE_MAC80211_NSS_SUPPORT', 'NSS_FIRMWARE_VERSION_12_5',
            'PACKAGE_openssl-util', 'OPENSSL_WITH_ASM']

def replace(path, old, new, count=1):
    text = path.read_text()
    if text.count(old) != count:
        raise RuntimeError(f'{path}: expected {count} occurrences of {old!r}')
    path.write_text(text.replace(old, new))

def fetch(path):
    with urllib.request.urlopen(BOARD_URL + path, timeout=60) as response:
        return response.read()

def check(tree):
    config = set((tree / '.config').read_text().splitlines())
    missing = [key for key in REQUIRED if f'CONFIG_{key}=y' not in config]
    if missing:
        raise RuntimeError('Required configuration lost: ' + ', '.join(missing))
    if 'KERNEL_PATCHVER:=6.12' not in (tree / 'target/linux/qualcommax/Makefile').read_text():
        raise RuntimeError('Unexpected kernel series')
    print('M79A / Linux 6.12 / NSS / AES configuration verified')

def adapt(tree):
    target = tree / 'target/linux/qualcommax'
    provenance = {}
    for name in ['ipq5018-cr880x-common.dtsi', 'ipq5018-cr880x.dtsi', 'ipq5018-cr880x-m79-v1.dts']:
        source = 'target/linux/qualcommax/files/arch/arm64/boot/dts/qcom/' + name
        data = fetch(source)
        destination = target / 'dts' / name
        destination.write_bytes(data)
        provenance[source] = hashlib.sha256(data).hexdigest()
    common = target / 'dts/ipq5018-cr880x-common.dtsi'
    replace(common, '#include "ipq5018-qcn6122.dtsi"',
            '#include "ipq5018-qcn6122.dtsi"\n#include "ipq5018-nss.dtsi"')
    # Keep the actual stock partition boundaries read from this router. The
    # donor merges both rootfs slots and overlay into one 116 MiB partition.
    replace(common, 'partition@a80000 { label = "rootfs"; reg = <0x00a80000 0x07480000>; };', '''partition@a80000 { label = "rootfs"; reg = <0x00a80000 0x02400000>; };
            partition@2e80000 { label = "rootfs_1"; reg = <0x02e80000 0x02400000>; };
            partition@5280000 { label = "overlay"; reg = <0x05280000 0x01f00000>; };
            partition@7180000 { label = "data"; reg = <0x07180000 0x00d80000>; };''')
    board = target / 'dts/ipq5018-cr880x.dtsi'
    # Both CPU links must use 802.1Q: NSS cannot parse QCA's special header.
    replace(board, 'ethernet = <&dp2>;', 'ethernet = <&dp2>;\n\t\t\t\tdsa-tag-protocol = "qca-8021q";')
    replace(board, 'ethernet = <&dp1>;', 'ethernet = <&dp1>;\n\t\t\t\tdsa-tag-protocol = "qca-8021q";')
    image = target / 'image/ipq50xx.mk'
    with image.open('a') as out:
        out.write('''
# CR8809 M79A: stock NAND slots, M79 FEM calibration, QCA8337 dual conduit.
define Device/xiaomi_cr880x-m79-v1
  $(call Device/FitImage)
  $(call Device/UbiFit)
  DEVICE_VENDOR := Xiaomi
  DEVICE_MODEL := CR880X
  DEVICE_VARIANT := M79 V1
  DEVICE_DTS_CONFIG := config@mp02.1
  SOC := ipq5018
  BLOCKSIZE := 128k
  PAGESIZE := 2048
  KERNEL_IN_UBI := 1
  IMAGE_SIZE := 36864k
  NAND_SIZE := 128m
  DEVICE_PACKAGES := kmod-ath11k-smallbuffers ath11k-firmware-ipq5018-qcn6122 ipq-wifi-xiaomi_cr880x kmod-qca-nss-drv kmod-qca-nss-ecm kmod-qca-nss-drv-pppoe nss-firmware-ipq50xx
endef
TARGET_DEVICES += xiaomi_cr880x-m79-v1
''')
    wifi = tree / 'package/firmware/ipq-wifi'
    for chip in ['ipq5018', 'qcn6122']:
        name = 'board-xiaomi_cr880x.' + chip
        source = 'package/firmware/ipq-wifi/src/' + name
        data = fetch(source)
        (wifi / 'files' / name).write_bytes(data)
        provenance[source] = hashlib.sha256(data).hexdigest()
    replace(wifi / 'Makefile', 'ALLWIFIBOARDS:=', 'ALLWIFIBOARDS:=xiaomi_cr880x ', count=1)
    anchor = '$(foreach PACKAGE,$(ALLWIFIPACKAGES),$(eval $(call BuildPackage,$(PACKAGE))))'
    replace(wifi / 'Makefile', anchor,
            '$(eval $(call generate-ipq-wifi-package,xiaomi_cr880x,Xiaomi CR880X M79A))\n\n' + anchor)
    base = target / 'ipq50xx/base-files'
    cal = base / 'etc/hotplug.d/firmware/11-ath11k-caldata'
    replace(cal, '\txiaomi,mi-router-ax3000t-v2)',
            '\txiaomi,cr880x-m79-v1|\\\n\txiaomi,mi-router-ax3000t-v2)', count=2)
    network = base / 'etc/board.d/02_network'
    replace(network, '\tcase $board in', '''\tcase $board in
    xiaomi,cr880x-m79-v1)
        ucidef_set_interfaces_lan_wan "lan1 lan2 lan3" "wan"
        ucidef_set_network_device_conduit "lan1" "eth1"
        ucidef_set_network_device_conduit "lan2" "eth1"
        ucidef_set_network_device_conduit "lan3" "eth1"
        ucidef_set_network_device_conduit "wan" "eth0"
        ;;''')
    # Do not run the RD03v2 board's recovery watchdog or boot-flag writes on M79A.
    for path in ['etc/init.d/rd03v2-watchdog', 'usr/sbin/rd03v2-watchdog']:
        (base / path).unlink(missing_ok=True)
    (base / 'etc/rc.local').write_text('''# Enable the NSS connection-manager paths after its modules have loaded.
for knob in general/redirect ipv4cfg/ipv4_accel_mode ipv6cfg/ipv6_accel_mode; do
    path=/proc/sys/dev/nss/$knob
    [ ! -e "$path" ] || echo 1 > "$path"
done
exit 0
''')
    shutil.copy2(HERE / 'patches/761-net-dsa-qca8k-8021q-linux-6.12.patch',
                 target / 'patches-6.12/999-2800-cr8809-qca8k-8021q.patch')
    with (target / 'config-6.12').open('a') as out:
        out.write('\nCONFIG_NET_DSA_TAG_QCA_8021Q=y\nCONFIG_CRYPTO_AES_ARM64_CE=y\nCONFIG_CRYPTO_AES_ARM64_CE_BLK=y\nCONFIG_CRYPTO_GHASH_ARM64_CE=y\n')
    config = tree / '.config'
    lines = [line for line in config.read_text().splitlines()
             if not re.match(r'CONFIG_TARGET_qualcommax_ipq50xx_DEVICE_.*=y$', line)]
    lines += [f'CONFIG_{key}=y' for key in REQUIRED]
    lines += ['CONFIG_PACKAGE_iperf3=y', 'CONFIG_PACKAGE_ethtool=y',
              'CONFIG_PACKAGE_kmod-crypto-user=y', 'CONFIG_TARGET_ROOTFS_INITRAMFS=y']
    config.write_text('\n'.join(lines) + '\n')
    (tree / 'cr8809-provenance.json').write_text(json.dumps({
        'board_source': BOARD_URL, 'board_files_sha256': provenance,
        'status': 'experimental-unverified-on-M79A',
        'kernel': '6.12', 'partition_layout': 'stock dual 36-MiB slots',
        'nss_source': 'ADCDS/openwrt-xiaomi-ax3000t-rd03v2@932cee77ba08d84bdb6853e5648a815c6d00ceb1',
        'qca_tag_source': 'kuncy7/openwrt-nss-edma@93f2d563e033ce2468b8b855896e79e35d5254ab',
    }, indent=2) + '\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('tree', type=Path)
    args = parser.parse_args()
    (check if args.check else adapt)(args.tree.resolve())
