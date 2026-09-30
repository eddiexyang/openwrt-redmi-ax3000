"""Keep M79A stock NAND slots usable by envtools and sysupgrade."""
from pathlib import Path


def replace_once(path, old, new):
    data = path.read_text()
    if data.count(old) != 1:
        raise RuntimeError(f'{path}: expected one stock-layout anchor')
    path.write_text(data.replace(old, new))


def adapt_stock_layout(tree):
    base = tree / 'target/linux/qualcommax/ipq50xx/base-files'
    upgrade = base / 'lib/upgrade/platform.sh'
    anchor = 'platform_do_upgrade() {\n\tcase "$(board_name)" in\n'
    replace_once(upgrade, anchor, anchor + '''\txiaomi,cr880x-m79-v1)
        # Preserve the other stock slot. The root filesystem uses ubi0.
        local active_mtd active_part
        active_mtd="$(cat /sys/class/ubi/ubi0/mtd_num 2>/dev/null)"
        case "$active_mtd" in
            ''|*[!0-9]*) echo "M79A: cannot identify active NAND slot" >&2; return 1 ;;
        esac
        active_part="$(cat /sys/class/mtd/mtd${active_mtd}/name 2>/dev/null)"
        case "$active_part" in
            rootfs|rootfs_1) CI_UBIPART="$active_part" ;;
            *) echo "M79A: unexpected active NAND partition" >&2; return 1 ;;
        esac
        nand_do_upgrade "$1"
        ;;
''')
    env = tree / 'package/boot/uboot-tools/uboot-envtools/files/qualcommax_ipq50xx'
    # Verified against this router's APPSBLENV dump: 64 KiB CRC region,
    # stored in 128 KiB erase blocks.
    replace_once(env, 'xiaomi,mi-router-ax3000t-v2)',
                 'xiaomi,cr880x-m79-v1|\\\nxiaomi,mi-router-ax3000t-v2)')
    boot = base / 'etc/init.d/bootcount'
    anchor = '\tcase $(board_name) in\n'
    replace_once(boot, anchor, anchor + '''\txiaomi,cr880x-m79-v1)
        # Mark a NAND boot successful without disabling stock-slot recovery.
        [ -r /sys/class/ubi/ubi0/mtd_num ] || return 0
        [ "$(fw_printenv -n flag_boot_success 2>/dev/null)" = 1 ] ||
            fw_setenv flag_boot_success 1
        ;;
''')


if __name__ == '__main__':
    import sys
    adapt_stock_layout(Path(sys.argv[1]))
