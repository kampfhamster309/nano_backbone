import storage

# Remount the filesystem as writable from code. This is required for:
#   - The captive portal to write settings.toml on first boot
#   - OTA updates to overwrite firmware files
#
# Trade-off: while remounted this way, the CIRCUITPY USB drive is read-only
# from the host. To copy files via USB (e.g. during development), hold the
# BOOTSEL button on reset to enter the UF2 bootloader, or use the REPL.
storage.remount("/", readonly=False)

# OTA rollback logic is implemented in Ticket 5.
