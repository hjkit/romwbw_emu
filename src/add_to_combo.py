#!/usr/bin/env python3
"""Add files to slice 0 of an hd1k combo disk image."""

import sys
import os
import struct

# hd1k combo disk parameters
SECTOR_SIZE = 512
SECTORS_PER_TRACK = 16
TRACK_SIZE = SECTOR_SIZE * SECTORS_PER_TRACK  # 8KB
BLOCK_SIZE = 4096  # 8 sectors per block
DIR_ENTRIES = 1024
BOOT_TRACKS = 2

# Combo disk: 1MB prefix, then slices
PREFIX_SIZE = 1048576  # 1MB
SLICE_SIZE = 8388608   # 8MB

# Directory starts after prefix + boot tracks
DIR_OFFSET = PREFIX_SIZE + (BOOT_TRACKS * TRACK_SIZE)  # 1MB + 16KB = 0x104000
DIR_SIZE = DIR_ENTRIES * 32  # Each entry is 32 bytes

# Data area starts after directory
# Directory uses blocks 0-7 (8 blocks × 4KB = 32KB for 1024 entries)
DATA_OFFSET = PREFIX_SIZE + (BOOT_TRACKS * TRACK_SIZE) + (8 * BLOCK_SIZE)

def find_free_dir_entry(disk_data):
    """Find first free directory entry (starts with 0xE5)."""
    for i in range(DIR_ENTRIES):
        entry_offset = DIR_OFFSET + (i * 32)
        if disk_data[entry_offset] == 0xE5:
            return i
    return -1

def find_free_block(disk_data, used_blocks):
    """Find first free block (skip blocks 0-7 used by directory)."""
    # Blocks 0-7 are for directory, data starts at block 8
    # Total blocks per slice: 8MB / 4KB = 2048 blocks
    for block in range(8, 2048):
        if block not in used_blocks:
            return block
    return -1

def get_used_blocks(disk_data):
    """Scan directory to find all used blocks."""
    used = set(range(8))  # Directory blocks are always used
    for i in range(DIR_ENTRIES):
        entry_offset = DIR_OFFSET + (i * 32)
        user = disk_data[entry_offset]
        if user != 0xE5 and user < 32:  # Valid user number
            # Block pointers are at offset 16-31 (16 bytes, 8 16-bit pointers)
            for j in range(8):
                ptr_offset = entry_offset + 16 + (j * 2)
                block = struct.unpack('<H', disk_data[ptr_offset:ptr_offset+2])[0]
                if block != 0:
                    used.add(block)
    return used

def add_file(disk_data, filename, file_data, user=0):
    """Add a file to the disk image."""
    # CP/M filename: 8 chars name + 3 chars extension, uppercase, space-padded
    name, ext = os.path.splitext(filename.upper())
    name = name[:8].ljust(8)
    ext = ext[1:4].ljust(3) if ext else '   '

    # Calculate number of records (128 bytes each) and extents
    num_records = (len(file_data) + 127) // 128
    num_blocks = (len(file_data) + BLOCK_SIZE - 1) // BLOCK_SIZE

    # Get currently used blocks
    used_blocks = get_used_blocks(disk_data)

    # Allocate blocks for file
    allocated_blocks = []
    for _ in range(num_blocks):
        block = find_free_block(disk_data, used_blocks)
        if block < 0:
            print(f"Error: No free blocks for {filename}")
            return False
        allocated_blocks.append(block)
        used_blocks.add(block)

    # Write file data to blocks
    for i, block in enumerate(allocated_blocks):
        block_offset = PREFIX_SIZE + (block * BLOCK_SIZE)
        start = i * BLOCK_SIZE
        end = min(start + BLOCK_SIZE, len(file_data))
        chunk = file_data[start:end]
        # Pad with 0x1A (CP/M EOF) if needed
        if len(chunk) < BLOCK_SIZE:
            chunk = chunk + bytes([0x1A] * (BLOCK_SIZE - len(chunk)))
        disk_data[block_offset:block_offset+BLOCK_SIZE] = chunk

    # Create directory entries (one extent can hold up to 8 block pointers = 32KB)
    # For files up to 32KB, we need one extent
    # For larger files, we need multiple extents
    blocks_per_extent = 8
    extent_num = 0
    block_idx = 0

    while block_idx < len(allocated_blocks):
        dir_idx = find_free_dir_entry(disk_data)
        if dir_idx < 0:
            print(f"Error: No free directory entry for {filename}")
            return False

        entry_offset = DIR_OFFSET + (dir_idx * 32)

        # Build directory entry
        entry = bytearray(32)
        entry[0] = user  # User number
        entry[1:9] = name.encode('ascii')  # Filename
        entry[9:12] = ext.encode('ascii')  # Extension
        entry[12] = extent_num & 0x1F  # Extent low (EX)
        entry[13] = 0  # S1 (reserved)
        entry[14] = (extent_num >> 5) & 0x3F  # Extent high (S2)

        # Calculate records in this extent
        extent_blocks = allocated_blocks[block_idx:block_idx+blocks_per_extent]
        extent_bytes = len(extent_blocks) * BLOCK_SIZE
        if block_idx + blocks_per_extent >= len(allocated_blocks):
            # Last extent - actual record count
            remaining = len(file_data) - (block_idx * BLOCK_SIZE)
            extent_records = (remaining + 127) // 128
        else:
            extent_records = 128  # Full extent
        entry[15] = min(extent_records, 128)  # RC (record count, max 128)

        # Block pointers (16-bit, little-endian)
        for i, block in enumerate(extent_blocks):
            struct.pack_into('<H', entry, 16 + i*2, block)

        # Write entry to disk
        disk_data[entry_offset:entry_offset+32] = entry

        block_idx += blocks_per_extent
        extent_num += 1

    print(f"Added {filename}: {len(file_data)} bytes, {num_blocks} blocks")
    return True

def main():
    if len(sys.argv) < 3:
        print("Usage: add_to_combo.py <combo.img> <file1.com> [file2.com ...]")
        sys.exit(1)

    disk_path = sys.argv[1]
    files = sys.argv[2:]

    # Read disk image
    with open(disk_path, 'rb') as f:
        disk_data = bytearray(f.read())

    # Check it's a combo disk (has 1MB prefix)
    if len(disk_data) < PREFIX_SIZE + SLICE_SIZE:
        print(f"Error: {disk_path} is too small to be a combo disk")
        sys.exit(1)

    # Add each file
    for filepath in files:
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            file_data = f.read()
        if not add_file(disk_data, filename, file_data):
            sys.exit(1)

    # Write modified disk
    with open(disk_path, 'wb') as f:
        f.write(disk_data)

    print(f"Successfully updated {disk_path}")

if __name__ == '__main__':
    main()
