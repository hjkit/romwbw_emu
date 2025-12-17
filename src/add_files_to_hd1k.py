#!/usr/bin/env python3
"""Add R8.COM and W8.COM to an hd1k disk image without corrupting the format."""

import sys
import os
import struct

# hd1k disk parameters (matching RomWBW format)
SECTOR_SIZE = 512
SECTORS_PER_TRACK = 32
BLOCK_SIZE = 4096  # 8 sectors per block
DIR_ENTRIES = 512
BOOT_TRACKS = 1  # First track is boot area
DIR_START = BOOT_TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE  # 0x4000

def find_free_dir_entry(disk_data):
    """Find first free directory entry (starts with 0xE5)."""
    for i in range(DIR_ENTRIES):
        offset = DIR_START + (i * 32)
        if disk_data[offset] == 0xE5:
            return offset
    return None

def find_max_block(disk_data):
    """Find highest used block number in directory."""
    max_block = 0
    for i in range(DIR_ENTRIES):
        offset = DIR_START + (i * 32)
        if disk_data[offset] != 0xE5:
            # Check allocation map (bytes 16-31, 16-bit block pointers)
            for j in range(8):
                block = struct.unpack('<H', disk_data[offset+16+j*2:offset+18+j*2])[0]
                if block > max_block and block < 0xFFFF:
                    max_block = block
    return max_block

def add_file(disk_data, filename, file_data):
    """Add a file to the disk image."""
    # Find free directory entry
    dir_offset = find_free_dir_entry(disk_data)
    if dir_offset is None:
        print(f"No free directory entry for {filename}")
        return False

    # Find next free block
    next_block = find_max_block(disk_data) + 1

    # Parse filename (8.3 format)
    name, ext = filename.upper().split('.')
    name = name.ljust(8)[:8]
    ext = ext.ljust(3)[:3]

    # Calculate number of records (128 bytes each)
    num_records = (len(file_data) + 127) // 128

    # Calculate blocks needed
    records_per_block = BLOCK_SIZE // 128  # 32 records per 4KB block
    blocks_needed = (num_records + records_per_block - 1) // records_per_block

    print(f"Adding {filename}: {len(file_data)} bytes, {num_records} records, {blocks_needed} blocks starting at {next_block}")

    # Create directory entry
    entry = bytearray(32)
    entry[0] = 0  # User 0
    entry[1:9] = name.encode('ascii')
    entry[9:12] = ext.encode('ascii')
    entry[12] = 0  # Extent low
    entry[13] = 0  # S1
    entry[14] = 0  # S2
    entry[15] = min(num_records, 128)  # Record count (max 128 per extent)

    # Allocation map (16-bit block pointers)
    for i in range(min(blocks_needed, 8)):
        struct.pack_into('<H', entry, 16 + i*2, next_block + i)

    # Write directory entry
    disk_data[dir_offset:dir_offset+32] = entry

    # Write file data to blocks
    # Block 0 starts at DIR_START (after boot track), not at disk offset 0
    for i in range(blocks_needed):
        block_num = next_block + i
        block_offset = DIR_START + (block_num * BLOCK_SIZE)
        data_offset = i * BLOCK_SIZE
        chunk = file_data[data_offset:data_offset + BLOCK_SIZE]
        # Pad with 0x1A (CP/M EOF) if needed
        if len(chunk) < BLOCK_SIZE:
            chunk = chunk + bytes([0x1A] * (BLOCK_SIZE - len(chunk)))
        disk_data[block_offset:block_offset + BLOCK_SIZE] = chunk

    return True

def main():
    if len(sys.argv) < 4:
        print("Usage: add_files_to_hd1k.py <disk.img> <file1.com> [file2.com ...]")
        sys.exit(1)

    disk_path = sys.argv[1]
    files = sys.argv[2:]

    # Read disk image
    with open(disk_path, 'rb') as f:
        disk_data = bytearray(f.read())

    print(f"Disk size: {len(disk_data)} bytes")
    print(f"Directory at offset: 0x{DIR_START:X}")
    print(f"Max used block: {find_max_block(disk_data)}")

    # Add each file
    for filepath in files:
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            file_data = f.read()
        if not add_file(disk_data, filename, file_data):
            print(f"Failed to add {filename}")
            sys.exit(1)

    # Write modified disk
    with open(disk_path, 'wb') as f:
        f.write(disk_data)

    print("Done!")

if __name__ == '__main__':
    main()
