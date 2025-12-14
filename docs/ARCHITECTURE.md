# RomWBW Emulator Architecture

This document describes the architecture of the RomWBW emulator, focusing on the shared HBIOS implementation that enables cross-platform support.

## Design Goals

1. **Single HBIOS Implementation** - One codebase for all platforms
2. **Platform Abstraction** - Clean separation between emulation and I/O
3. **Easy Porting** - Minimal code needed for new platforms
4. **Feature Parity** - Same capabilities across CLI, Web, iOS, macOS

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Application Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │   CLI    │  │   Web    │  │   iOS    │  │  macOS   │            │
│  │  main()  │  │  main()  │  │ ViewController │ AppDelegate │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │             │             │             │                   │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐            │
│  │emu_io   │  │emu_io   │  │emu_io   │  │emu_io   │            │
│  │_cli.cc  │  │_wasm.cc │  │_ios.mm  │  │_macos.mm│            │
│  └────┬─────┘  └────┴─────┘  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                    Shared Emulation Layer                            │
│                            │                                         │
│  ┌─────────────────────────┴─────────────────────────┐              │
│  │              emu_io.h (Interface)                  │              │
│  │  • emu_console_write_char()  • emu_get_time()     │              │
│  │  • emu_console_read_char()   • emu_log()          │              │
│  │  • emu_console_has_input()   • emu_error()        │              │
│  └─────────────────────────┬─────────────────────────┘              │
│                            │                                         │
│  ┌─────────────────────────┴─────────────────────────┐              │
│  │           hbios_dispatch.cc (Shared HBIOS)         │              │
│  │                                                    │              │
│  │  Character I/O (CIO)    │  Disk I/O (DIO)         │              │
│  │  • Console input/output │  • Read/write sectors   │              │
│  │  • Status checking      │  • Seek, capacity       │              │
│  │                         │  • Up to 16 units       │              │
│  │  ─────────────────────────────────────────────    │              │
│  │  RTC/NVRAM              │  Video (VDA)            │              │
│  │  • Get/set time         │  • Cursor positioning   │              │
│  │  • 64-byte NVRAM        │  • Clear, scroll        │              │
│  │  • Persistence callback │  • Character attributes │              │
│  │  ─────────────────────────────────────────────    │              │
│  │  System (SYS)           │  Sound (SND)            │              │
│  │  • Reset (warm/cold)    │  • Beep, notes          │              │
│  │  • Bank switching       │  • Volume control       │              │
│  │  • Memory peek/poke     │                         │              │
│  └─────────────────────────┬─────────────────────────┘              │
│                            │                                         │
│  ┌─────────────────────────┴─────────────────────────┐              │
│  │              romwbw_mem.h (Memory)                 │              │
│  │  • 512KB ROM (16 x 32KB banks)                    │              │
│  │  • 512KB RAM (16 x 32KB banks)                    │              │
│  │  • Bank switching via I/O ports                   │              │
│  └─────────────────────────┬─────────────────────────┘              │
│                            │                                         │
│  ┌─────────────────────────┴─────────────────────────┐              │
│  │                qkz80 (CPU Core)                    │              │
│  │  • Full Z80 instruction set                       │              │
│  │  • Undocumented opcodes                           │              │
│  │  • 8080 compatibility mode                        │              │
│  └───────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### qkz80 (CPU Core)

The Z80 CPU emulator from the cpmemu project. Provides:

- All documented Z80 instructions
- Undocumented instructions (IX/IY bit operations, etc.)
- DD/FD prefix chaining (last prefix wins)
- 8080 compatibility mode
- Register access via `cpu.regs.*`

```cpp
#include "qkz80.h"

qkz80 cpu(&memory);
cpu.set_cpu_mode(qkz80::MODE_Z80);
cpu.regs.PC.set_pair16(0x0000);
cpu.execute();  // Execute one instruction
```

### romwbw_mem.h (Memory System)

Bank-switched memory emulating RomWBW hardware:

- **ROM:** 512KB (banks 0x00-0x0F), read-only
- **RAM:** 512KB (banks 0x80-0x8F), read-write
- **Bank Selection:** Port 0x78 (RAM) / 0x7C (ROM)
- **Shadow:** RAM 0x8000-0xFFFF shadows ROM when RAM bank selected

```cpp
#include "romwbw_mem.h"

banked_mem memory;
memory.enable_banking();
memory.select_bank(0x80);  // Select RAM bank 0
uint8_t byte = memory.fetch_mem(0x1234);
memory.store_mem(0x1234, 0xFF);
```

### emu_io.h (I/O Abstraction)

Platform-independent interface for console, time, and logging:

```cpp
// Console I/O
void emu_console_write_char(int ch);
int emu_console_read_char();
bool emu_console_has_input();
void emu_console_queue_char(int ch);

// Time
void emu_get_time(emu_time* t);

// Logging
void emu_log(const char* fmt, ...);
void emu_error(const char* fmt, ...);
void emu_status(const char* msg);

// Initialization
void emu_io_init();
```

Each platform implements these in `emu_io_*.cc`:
- `emu_io_cli.cc` - Terminal I/O with termios
- `emu_io_wasm.cc` - JavaScript callbacks via Emscripten

### hbios_dispatch.cc (Shared HBIOS)

The core HBIOS implementation. Handles all RomWBW system calls:

```cpp
#include "hbios_dispatch.h"

HBIOSDispatch hbios;
hbios.setCPU(&cpu);
hbios.setMemory(&memory);

// Check for HBIOS trap at current PC
if (hbios.checkTrap(cpu.regs.PC.get_pair16())) {
    int trap_type = hbios.getTrapType(pc);
    hbios.handleCall(trap_type);
}

// Callbacks for platform-specific behavior
hbios.setResetCallback([](uint8_t type) {
    // Handle warm/cold boot
});
hbios.setNvramSaveCallback([](const uint8_t* data, int size) {
    // Persist NVRAM to storage
});
```

#### HBIOS Function Groups

| Group | Functions | Description |
|-------|-----------|-------------|
| CIO (0x00-0x06) | CIOIN, CIOOUT, CIOIST, CIOOST | Character I/O |
| DIO (0x10-0x1B) | DIOREAD, DIOWRITE, DIOSEEK, etc. | Disk I/O |
| RTC (0x20-0x28) | RTCGETTIM, RTCGETBYT, RTCSETBLK | Time and NVRAM |
| VDA (0x40-0x4F) | VDAINI, VDACLS, VDASCP, etc. | Video display |
| SND (0x50-0x56) | SNDRESET, SNDBEEP, SNDNOTE | Sound |
| SYS (0xF0-0xFF) | SYSRESET, SYSGET, SYSSET, etc. | System control |

## NVRAM Implementation

NVRAM provides 64 bytes of persistent storage for system configuration:

```cpp
// In HBIOSDispatch class
uint8_t nvram[64];
NvramCallback nvram_save_callback;

// RTC functions access NVRAM
case HBF_RTCGETBYT:  // Get byte by index
case HBF_RTCSETBYT:  // Set byte by index
case HBF_RTCGETBLK:  // Get entire block
case HBF_RTCSETBLK:  // Set entire block
```

Platform persistence:
- **Web:** localStorage as base64
- **CLI:** File `~/.romwbw_nvram`
- **iOS:** UserDefaults or Keychain

## Disk I/O Architecture

The emulator supports multiple disk formats:

```cpp
struct HBDisk {
    bool is_open;
    std::vector<uint8_t> data;  // In-memory data
    void* handle;               // File handle (for large disks)
    bool file_backed;
    size_t size;
    uint32_t current_lba;
};

// Up to 16 disk units
HBDisk disks[16];
```

Disk operations:
1. **DIOSEEK** - Set LBA position
2. **DIOREAD** - Read sectors to memory
3. **DIOWRITE** - Write sectors from memory
4. **DIOCAP** - Report capacity

## Adding a New Platform

### Step 1: Implement emu_io.h

Create `emu_io_yourplatform.cc`:

```cpp
#include "emu_io.h"

void emu_io_init() {
    // Initialize your I/O system
}

void emu_console_write_char(int ch) {
    // Output character to display
}

int emu_console_read_char() {
    // Read character from input
}

bool emu_console_has_input() {
    // Check if input available
}

void emu_console_queue_char(int ch) {
    // Queue character for later reading
}

void emu_get_time(emu_time* t) {
    // Fill in current time
}

void emu_log(const char* fmt, ...) {
    // Debug logging
}

void emu_error(const char* fmt, ...) {
    // Error logging
}

void emu_status(const char* msg) {
    // Status display update
}
```

### Step 2: Create Main Program

```cpp
#include "qkz80.h"
#include "romwbw_mem.h"
#include "hbios_dispatch.h"
#include "emu_io.h"

banked_mem memory;
qkz80 cpu(&memory);
HBIOSDispatch hbios;

int main() {
    emu_io_init();

    // Load ROM
    memory.enable_banking();
    // ... load ROM data into memory.get_rom() ...

    // Set up HBIOS
    hbios.setCPU(&cpu);
    hbios.setMemory(&memory);
    hbios.setResetCallback(handle_reset);
    hbios.setNvramSaveCallback(handle_nvram_save);

    // Load persisted NVRAM
    // ... load from storage and call hbios.loadNvram() ...

    // Main loop
    cpu.set_cpu_mode(qkz80::MODE_Z80);
    cpu.regs.PC.set_pair16(0x0000);

    while (running) {
        uint16_t pc = cpu.regs.PC.get_pair16();

        if (hbios.checkTrap(pc)) {
            hbios.handleCall(hbios.getTrapType(pc));
            continue;
        }

        cpu.execute();
    }
}
```

### Step 3: Build

Link with:
- `hbios_dispatch.cc`
- `qkz80` library
- Your `emu_io_yourplatform.cc`

## Memory Map

```
Address Range    Bank Type    Description
─────────────────────────────────────────
0x0000-0x7FFF    ROM/RAM      Lower 32KB (bank-switched)
0x8000-0xFFFF    RAM          Upper 32KB (common area, always RAM)

Bank Register (Port 0x78/0x7C):
  Bit 7: 0=ROM, 1=RAM
  Bits 3-0: Bank number (0-15)

Examples:
  0x00 = ROM bank 0 (boot ROM)
  0x80 = RAM bank 0
  0x8F = RAM bank 15 (common area)
```

## HBIOS Entry Point

HBIOS calls are made via RST 08 which jumps to 0xFFF0:

```
Address  Function
0xFFF0   Main HBIOS entry
0xFFF3   Interrupt vector
0xFFF6   NMI vector
```

The emulator traps execution at 0xFFF0 and dispatches to the appropriate handler based on the B register (function code).

## Thread Safety

The current implementation is **not thread-safe**. For platforms requiring threading:

1. Wrap CPU execution in a mutex
2. Queue input characters from I/O thread
3. Use atomic flags for running state

## Performance Considerations

- **Instruction batching:** Execute multiple instructions per UI update
- **I/O polling:** Only check console status periodically
- **Memory access:** Direct array access, no virtual methods
- **Disk caching:** Keep small disks in memory, large ones file-backed

## ROM Compatibility

### Why Standard ROMs Don't Work

Standard RomWBW ROMs (`*_std.rom`) contain real HBIOS code that attempts to access hardware I/O ports. This emulator does not emulate hardware - instead, it intercepts HBIOS calls and handles them in C++.

When a standard ROM runs:
1. It immediately tries to access hardware ports (e.g., port 0xC0 for RTC latch)
2. The emulator returns 0x00 for unknown port reads
3. HBIOS trapping is never enabled (no signal to port 0xEE)
4. The Z80 HBIOS code runs and hangs waiting for hardware responses

### EMU ROMs

The `emu_*` ROMs have the first 32KB replaced with `emu_hbios` code that:
1. Skips all hardware initialization
2. Signals the emulator via port 0xEE to enable HBIOS interception
3. Routes all HBIOS calls through dispatch addresses the emulator traps

The rest of the ROM (banks 1-15) is preserved from the original, keeping OS images and ROM disk intact.

### Building EMU ROMs

Use `roms/build_emu_rom.sh` to create an EMU ROM from any standard RomWBW ROM:

```bash
cd roms
./build_emu_rom.sh SBC_simh_std.rom emu_romwbw.rom
./build_emu_rom.sh RCZ80_std.rom emu_rcz80.rom
```

### ROM Types

| ROM | Description | Works? |
|-----|-------------|--------|
| `emu_romwbw.rom` | SBC/SIMH with emu_hbios overlay | Yes |
| `emu_rcz80.rom` | RCZ80 with emu_hbios overlay | Yes |
| `SBC_simh_std.rom` | Standard SBC/SIMH ROM | No - requires hardware |
| `RCZ80_std.rom` | Standard RCZ80 ROM | No - requires hardware |

## Version Compatibility

The shared HBIOS is designed to work with RomWBW 3.x ROMs. Key compatibility points:

- HBIOS function codes match RomWBW hbios.inc
- Bank switching matches SBC hardware
- NVRAM size matches DS1302/DS1307 chips
- Disk geometry matches hd1k format (1024-byte sectors)
