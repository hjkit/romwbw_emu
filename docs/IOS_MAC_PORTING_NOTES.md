# iOS/macOS Porting Notes

Notes for the ioscpm iOS/iPad and macOS projects that use this emulator library.

## ROM Compatibility

Three ROMs are known to work:

| ROM | Works? | Notes |
|-----|--------|-------|
| `SBC_simh_std.rom` | Yes | Standard SIMH ROM - works with emulated UART |
| `emu_romwbw.rom` | Yes | SBC/SIMH platform with emu_hbios overlay |
| `emu_rcz80.rom` | Yes | RCZ80 platform with emu_hbios overlay |
| `RCZ80_std.rom` | No | Contains real HBIOS - requires hardware I/O |

### How Standard SIMH ROM Works

The `SBC_simh_std.rom` works because SIMH uses simple UART I/O (ports 0x68/0x6D) which the emulator handles directly. The emulator returns 0xFF for unknown ports, which the ROM interprets as "hardware not present" and skips initialization.

### How emu_* ROMs Work

The `emu_*` ROMs have the first 32KB replaced with `emu_hbios` code that:
1. Skips hardware initialization
2. Signals the emulator via port 0xEE to enable HBIOS interception
3. All HBIOS calls are then handled by the C++ `HBIOSDispatch` class

See `docs/ARCHITECTURE.md` for full details.

## Stop/Start Implementation

**Important:** To ensure stop/start behaves identically to a fresh app launch, you must create new instances of the emulator components on restart.

### Recommended Pattern

```cpp
// Global pointers (not static objects)
banked_mem* memory = nullptr;
qkz80* cpu = nullptr;
HBIOSDispatch* hbios = nullptr;

// Call this on start AND on restart after stop
void create_emulator() {
    // Delete old instances
    delete cpu;
    delete memory;
    delete hbios;

    // Create fresh instances
    memory = new banked_mem();
    cpu = new qkz80(memory);
    hbios = new HBIOSDispatch();

    // Initialize
    memory->enable_banking();
    hbios->setCPU(cpu);
    hbios->setMemory(memory);
}

void start_emulation() {
    create_emulator();  // Fresh state every time

    // Load ROM into memory->get_rom()
    // Load disk into hbios->loadDisk()

    cpu->set_cpu_mode(qkz80::MODE_Z80);
    hbios->reset();
    memory->select_bank(0);
    cpu->regs.PC.set_pair16(0x0000);

    running = true;
}

void stop_emulation() {
    running = false;
    // Don't delete here - wait until next start
}
```

### Why This Matters

Simply resetting registers and calling `hbios->reset()` is not sufficient because:

1. **Hidden state in qkz80**: The CPU has internal state (cycle counts, instruction state) that may not be fully exposed
2. **Memory contents**: RAM banks contain data from previous execution
3. **Static variables**: Debug counters, trace state, etc.
4. **Input queue**: Characters typed during previous session

Creating new instances guarantees the same state as a fresh app launch.

### What Persists Across Reset

Disk data loaded via `hbios->loadDisk()` is stored in the HBIOSDispatch object. When you delete and recreate `hbios`, disk data is lost. If you want disks to persist:

```cpp
// Save disk data before reset
std::vector<uint8_t> disk0_data;
if (hbios->isDiskLoaded(0)) {
    const auto& disk = hbios->getDisk(0);
    disk0_data = disk.data;  // Copy the data
}

// Create fresh emulator
create_emulator();

// Restore disk data
if (!disk0_data.empty()) {
    hbios->loadDisk(0, disk0_data.data(), disk0_data.size());
}
```

### Console Input Queue

Clear any pending input on reset:

```cpp
// In emu_io.h
void emu_console_clear_queue();

// Call before starting
emu_console_clear_queue();
```

## End-of-Line Handling

**Important:** CP/M expects CR (0x0D) for line endings, but most platforms send LF (0x0A) when Enter is pressed.

The emulator includes a `normalize_eol()` helper function that converts LF to CR:

```cpp
// Normalize line ending: LF -> CR for CP/M compatibility
static inline uint8_t normalize_eol(int ch) {
  return (ch == '\n') ? '\r' : ch;
}
```

Apply this to all console input before passing to the emulator:

```cpp
// In your keyboard input handler
int ch = get_key_from_ui();
ch = normalize_eol(ch);  // Convert LF to CR
// Pass ch to emulator via UART port or input queue
```

Without this conversion, commands will echo on screen but Enter won't submit them.

## Testing

Deploy test builds to a separate location (e.g., `romwbw1/` instead of `romwbw/`) to avoid breaking production for users during development.
