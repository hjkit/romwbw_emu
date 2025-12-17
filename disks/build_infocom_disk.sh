#!/bin/bash
# Build Infocom disk for RomWBW emulator
# This script creates a properly formatted hd1k disk image with Infocom games
#
# Usage: ./build_infocom_disk.sh [source_disk] [output_disk]
#
# source_disk: Path to source disk with Infocom files (default: ioscpm release)
# output_disk: Output disk image name (default: hd1k_infocom.img)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_SOURCE="/Users/wohl/src/ioscpm/release_assets/hd1k_infocom.img"
DEFAULT_OUTPUT="${SCRIPT_DIR}/hd1k_infocom.img"
DISKDEFS="${DISKDEFS:-/Users/wohl/esrc/RomWBW-v3.5.1/Tools/cpmtools/diskdefs}"
# Template disk for boot sector - use combo disk (boot sector at 1MB offset)
TEMPLATE_DISK="${SCRIPT_DIR}/hd1k_combo.img"
TEMPLATE_OFFSET=1048576  # 1MB prefix in combo disk

# Parse arguments
SOURCE_DISK="${1:-$DEFAULT_SOURCE}"
OUTPUT_DISK="${2:-$DEFAULT_OUTPUT}"

echo "=== Building Infocom Disk ==="
echo "Source: ${SOURCE_DISK}"
echo "Output: ${OUTPUT_DISK}"
echo "Diskdefs: ${DISKDEFS}"

# Check prerequisites
if [ ! -f "$DISKDEFS" ]; then
    echo "ERROR: diskdefs file not found at $DISKDEFS"
    echo "Set DISKDEFS environment variable to point to RomWBW diskdefs"
    exit 1
fi

if [ ! -f "$SOURCE_DISK" ]; then
    echo "ERROR: Source disk not found: $SOURCE_DISK"
    exit 1
fi

if [ ! -f "$TEMPLATE_DISK" ]; then
    echo "ERROR: Template disk not found: $TEMPLATE_DISK"
    echo "Need a working hd1k disk to copy boot sector from"
    exit 1
fi

# Check for required tools
for tool in cpmls cpmcp mkfs.cpm dd; do
    if ! command -v $tool &> /dev/null; then
        echo "ERROR: Required tool not found: $tool"
        exit 1
    fi
done

# Create temp directory for extraction
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo ""
echo "=== Extracting files from source disk ==="
cd "$TEMP_DIR"
export DISKDEFS

# Extract all valid files from user 0
cpmcp -f wbw_hd1k "$SOURCE_DISK" '0:*.*' . 2>/dev/null || true

# Count extracted files
FILE_COUNT=$(ls -1 *.com *.z[3-6] *.txt 2>/dev/null | wc -l)
echo "Extracted ${FILE_COUNT} files"

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "ERROR: No files extracted from source disk"
    exit 1
fi

# List of adult-rated games to exclude (for Apple App Store compliance)
# Currently only Leather Goddesses of Phobos (lgop)
EXCLUDED_GAMES="lgop leather"

echo ""
echo "=== Creating new disk image ==="

# Create blank 8MB disk (16384 sectors * 512 bytes)
dd if=/dev/zero of="$OUTPUT_DISK" bs=512 count=16384 2>/dev/null

# Format the disk with CP/M filesystem
mkfs.cpm -f wbw_hd1k "$OUTPUT_DISK" 2>/dev/null

# Copy boot sector from template disk (first 32 sectors = 16KB)
# This must be done AFTER mkfs.cpm because mkfs.cpm fills with 0xE5
# For combo disk, skip the 1MB MBR prefix to get slice 0's boot sector
dd if="$TEMPLATE_DISK" of="$OUTPUT_DISK" bs=512 skip=$((TEMPLATE_OFFSET / 512)) count=32 conv=notrunc 2>/dev/null

# Clear the MBR partition table and signature (we only need the boot code)
# Partition table is at 0x1BE-0x1FD (64 bytes), signature at 0x1FE-0x1FF
# This prevents warnings about stale FAT16 partition entries
printf '\x00%.0s' {1..66} | dd of="$OUTPUT_DISK" bs=1 seek=446 count=66 conv=notrunc 2>/dev/null

echo ""
echo "=== Copying files to new disk ==="

# Copy all .com files
for f in *.com; do
    [ -f "$f" ] || continue
    name=$(basename "$f" | tr '[:upper:]' '[:lower:]')

    # Check if this is an excluded game
    excluded=false
    for excl in $EXCLUDED_GAMES; do
        if echo "$name" | grep -qi "^${excl}"; then
            echo "SKIPPED (adult content): $name"
            excluded=true
            break
        fi
    done

    if [ "$excluded" = false ]; then
        cpmcp -f wbw_hd1k "$OUTPUT_DISK" "$f" "0:$name" 2>/dev/null && echo "Copied: $name"
    fi
done

# Copy all z-machine story files
for f in *.z[3-6]; do
    [ -f "$f" ] || continue
    name=$(basename "$f" | tr '[:upper:]' '[:lower:]')

    # Check if this is an excluded game
    excluded=false
    for excl in $EXCLUDED_GAMES; do
        if echo "$name" | grep -qi "^${excl}"; then
            echo "SKIPPED (adult content): $name"
            excluded=true
            break
        fi
    done

    if [ "$excluded" = false ]; then
        cpmcp -f wbw_hd1k "$OUTPUT_DISK" "$f" "0:$name" 2>/dev/null && echo "Copied: $name"
    fi
done

# Copy text files
for f in *.txt; do
    [ -f "$f" ] || continue
    name=$(basename "$f" | tr '[:upper:]' '[:lower:]')
    cpmcp -f wbw_hd1k "$OUTPUT_DISK" "$f" "0:$name" 2>/dev/null && echo "Copied: $name"
done

echo ""
echo "=== Disk creation complete ==="
ls -la "$OUTPUT_DISK"

echo ""
echo "=== Disk contents ==="
cpmls -f wbw_hd1k "$OUTPUT_DISK" | grep -v '^[0-9]*:$' | grep -v '^$' | head -40
echo "..."

echo ""
echo "Done! Disk image created at: $OUTPUT_DISK"
