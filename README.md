# RomWBW Emulator

A cross-platform Z80 emulator for running RomWBW and CP/M systems. Features full Z80 CPU emulation with 512KB ROM + 512KB RAM bank switching, HBIOS hardware abstraction, and NVRAM persistence.

**Platforms:** Linux CLI, WebAssembly (browser), iOS/macOS (in development)

## Live Demo

Try RomWBW in your browser: [https://your-domain.com/romwbw/](https://your-domain.com/romwbw/)

No installation required - runs entirely in your browser with localStorage persistence.

## Quick Start

### Web Version (Easiest)
1. Open the web emulator in your browser
2. Click **Start** - auto-loads default ROM and disk
3. At boot menu: press `C` for CP/M, `Z` for ZSDOS, or `0` to boot from hard disk

### CLI Version
```bash
# Build the emulator
cd src && make

# Run with default ROM
./romwbw_emu --romwbw ../roms/emu_romwbw.rom

# Run with disk image
./romwbw_emu --romwbw ../roms/SBC_simh_std.rom --hbdisk0=path/to/hd512.img
```

## Features

### Core Emulation
- **Z80 CPU:** Full Z80 instruction set including undocumented opcodes
- **Memory:** 512KB ROM + 512KB RAM with 32KB bank switching (16 banks each)
- **HBIOS:** Complete hardware abstraction layer implemented in C++
- **Interrupts:** Maskable (INT) and non-maskable (NMI) support

### Storage
- **ROM Disk:** Built-in ROM disk with CP/M and utilities
- **RAM Disk:** Fast volatile storage
- **Hard Disks:** Up to 16 virtual hard disk images (8MB each)
- **Formats:** Standard RomWBW hd1k (1024-byte sectors) disk images

### Persistence (Web Version)
- **Disk Downloads:** Modified disk images can be downloaded
- **NVRAM:** Ready for ROMs with DS1302/DS1307 RTC (localStorage persistence)

### Supported ROMs
| ROM | Description |
|-----|-------------|
| `SBC_simh_std.rom` | Standard SimH build - **recommended** for emulation |
| `SBC_std.rom` | Standard SBC build with DS1302 RTC (NVRAM support) |
| `RCZ80_std.rom` | RC2014/Z80 compatible ROM |

Download from [RomWBW releases](https://github.com/wwarthen/RomWBW/releases).

### Supported Disk Images
| Image | Description |
|-------|-------------|
| `hd1k_cpm22.img` | CP/M 2.2 with utilities (8MB) |
| `hd1k_zsdos.img` | ZSDOS with extended utilities (8MB) |
| `hd512_combo.img` | Combined CP/M + ZSDOS + extras |

## Building

### Requirements
- C++11 compiler (gcc/clang)
- POSIX system (Linux, macOS)
- For WebAssembly: [Emscripten](https://emscripten.org/)

### CLI Build
```bash
cd src/
make
```

### WebAssembly Build
```bash
cd web/
make romwbw.js
make deploy-romwbw  # Deploy to ~/www/romwbw/
```

### Dependencies
The emulator uses qkz80 from the [cpmemu](https://github.com/avwohl/cpmemu) project:
```bash
# Install qkz80 library (required)
cd ../cpmemu
sudo make install  # Installs to /usr/local/lib and /usr/local/include
```

## Architecture

The emulator uses a **shared HBIOS implementation** that works across all platforms:

```
┌─────────────────────────────────────────────────────────────┐
│                    Platform Layer                           │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   CLI        │  WebAssembly │    iOS       │    macOS      │
│ (romwbw_emu) │ (romwbw_web) │  (planned)   │   (planned)   │
├──────────────┴──────────────┴──────────────┴───────────────┤
│                  emu_io.h (I/O Abstraction)                 │
├─────────────────────────────────────────────────────────────┤
│               hbios_dispatch.cc (Shared HBIOS)              │
│  • Character I/O    • Disk I/O      • RTC/NVRAM            │
│  • Video Display    • Sound         • System Functions     │
├─────────────────────────────────────────────────────────────┤
│                 romwbw_mem.h (Bank Switching)               │
├─────────────────────────────────────────────────────────────┤
│                    qkz80 (Z80 CPU Core)                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Description |
|-----------|------|-------------|
| CPU Core | `qkz80.*` | Z80/8080 CPU emulation (from cpmemu) |
| Memory | `romwbw_mem.h` | 512KB+512KB banked memory |
| HBIOS | `hbios_dispatch.*` | **Shared** HBIOS implementation |
| I/O Layer | `emu_io.h` | Platform-independent I/O interface |
| CLI I/O | `emu_io_cli.cc` | Terminal I/O for CLI |
| WASM I/O | `emu_io_wasm.cc` | Browser I/O for WebAssembly |

### Porting to New Platforms

To port to iOS, macOS, or other platforms:

1. **Implement `emu_io.h` interface** for your platform:
   - `emu_console_write_char()` - Output character
   - `emu_console_has_input()` - Check for input
   - `emu_console_read_char()` - Read character
   - `emu_get_time()` - Get current time
   - `emu_log()` / `emu_error()` - Logging

2. **Link with shared components:**
   - `hbios_dispatch.cc` - HBIOS services
   - `qkz80` library - CPU emulation

3. **Set up callbacks:**
   - NVRAM save callback for persistence
   - Reset callback for warm/cold boot
   - VDA callbacks for video display (optional)

See `docs/IOS_PORTING.md` for detailed porting guide.

## Command Line Options

```bash
./romwbw_emu --romwbw <rom.rom> [options]

Required:
  --romwbw=FILE       RomWBW ROM image (512KB)

Storage:
  --hbdiskN=FILE      Attach disk image to unit N (0-15)
  --romldr=FILE       Custom boot loader

Debug:
  --debug             Enable debug output
  --trace=FILE        Write execution trace
  --strict-io         Halt on unexpected I/O ports
```

## NVRAM Configuration

The emulator implements 64-byte NVRAM (matching DS1302/DS1307 RTC chips):

- **Web:** Persisted to browser localStorage
- **CLI:** Stored in `~/.romwbw_nvram` (planned)
- **Requires:** ROM built with DS1302/DS1307 RTC driver (not SIMRTC)

To use NVRAM configuration:
1. Load a ROM with DS1302/DS1307 support (e.g., `SBC_std.rom`)
2. Press `W` at boot menu for configuration utility

Note: `SBC_simh_std.rom` uses SIMRTC which doesn't support NVRAM.

## Project Structure

```
romwbw_emu/
├── src/                    # Core emulator source
│   ├── hbios_dispatch.*    # Shared HBIOS (use this!)
│   ├── romwbw_mem.h        # Bank-switched memory
│   ├── emu_io.h            # I/O abstraction interface
│   ├── emu_io_cli.cc       # CLI I/O implementation
│   ├── romwbw_emu.cc       # CLI main program
│   └── emu_hbios.asm       # HBIOS entry point stubs
├── web/                    # WebAssembly version
│   ├── romwbw_web.cc       # WASM main program
│   ├── emu_io_wasm.cc      # WASM I/O implementation
│   ├── romwbw.html         # Web interface
│   └── Makefile            # WASM build
├── roms/                   # ROM images
├── docs/                   # Technical documentation
│   ├── ARCHITECTURE.md     # Detailed architecture guide
│   ├── IOS_PORTING.md      # iOS/macOS porting guide
│   └── HBIOS_*.md          # HBIOS documentation
└── archive/                # Legacy code (reference only)
```

## Documentation

- `docs/ARCHITECTURE.md` - Detailed architecture and design decisions
- `docs/IOS_PORTING.md` - Guide for iOS/macOS porters
- `docs/HBIOS_Implementation_Guide.md` - HBIOS function reference
- `docs/ROMWBW_INTEGRATION.md` - RomWBW system details

## Getting RomWBW Images

Download from [RomWBW releases](https://github.com/wwarthen/RomWBW/releases):

```bash
# Or clone for all images
git clone https://github.com/wwarthen/RomWBW.git
ls RomWBW/Binary/*.rom  # ROM images
ls RomWBW/Binary/*.img  # Disk images
```

Recommended: `SBC_simh_std.rom` with `hd1k_cpm22.img` or `hd1k_zsdos.img`

## Related Projects

- [cpmemu](https://github.com/avwohl/cpmemu) - Z80 CPU core and CP/M utilities
- [RomWBW](https://github.com/wwarthen/RomWBW) - Z80/Z180 ROM-based system software

## Version History

- **2.0** - Shared HBIOS architecture, NVRAM persistence, web auto-load
- **1.2** - NVRAM support, localStorage persistence
- **1.1** - Web version improvements, disk image support
- **1.0** - Initial release with CLI and WebAssembly support

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE).
