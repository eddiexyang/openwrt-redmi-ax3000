# CR8809 M79A: Linux 6.12 NSS port

Experimental source integration. No M79A boot or throughput validation yet.
GitHub Actions prepares and builds the entire image; local work is source editing only.

## Adaptation

- Linux 6.12.94 / IPQ5018 NSS baseline from ADCDS, pinned in `prepare.sh`.
- M79 V1 device tree and FEM-specific BDF from ByteArray0, pinned in `adapt-m79a.py`.
- QCA8337 uses the backported QCA 802.1Q tagger on both CPU ports. LAN uses
  eth1 and WAN eth0. ECM's DSA-conduit and tag_8021q VID rules are retained.
- The QCA tagger is rebased onto Linux 6.12.94 with OpenWrt's 751/711/712
  QCA8K changes. Its source patch retains Stanislaw Pal's attribution.
- NSS core reset/cache fixes, matching 12.5 firmware/driver interfaces,
  ath11k smallbuffers, and IPQ5018/QCN6122 NSS radio priorities are retained
  from the pinned and hardware-tested RD03v2 integration. Its measurements
  do not establish M79A performance.
- Enable ARM64 AES Crypto Extensions and OpenSSL assembly support; include
  openssl-util and iperf3 for hardware validation.
- Preserve the actual router's 36 MiB rootfs / 36 MiB rootfs_1 boundaries.
  Remove RD03v2-specific watchdog and boot-flag writes from its rootfs overlay.

## Validation required before installing

The CI must compile kernel, DSA tagger, NSS, ath11k and the M79A image. Boot
compatibility with the stock bootloader still needs verification. Build success
alone does not authorize or validate a NAND flash. First use an appropriate RAM
boot/recovery procedure, then verify LAN/WAN separation, NSS counters under NAT
and Wi-Fi traffic, HE160 operation and AES accelerated versus software benchmarks.

DFS/CAC behavior has not been modified. `forward_delay` is a Linux bridge/STP
parameter; it does not control wireless CAC. The prior 5.4 source trace found
hostapd -> nl80211 radar detection -> driver/firmware -> nl80211 DFS events ->
hostapd channel switching. The corresponding 6.12 path remains to be audited.

## Sources

- https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2/tree/932cee77ba08d84bdb6853e5648a815c6d00ceb1
- https://github.com/ByteArray0/immortalwrt-device-expand/tree/25b90764ae9bf7cf43cb57229b98bf2211795b84
- https://github.com/kuncy7/openwrt-nss-edma/tree/93f2d563e033ce2468b8b855896e79e35d5254ab
- https://github.com/qosmio/openwrt-ipq/tree/92a2d104145c8d265851c4b388a41bd8e9c21cd9
