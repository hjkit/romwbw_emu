# iOS/macOS Porting Guide

This document describes how to port the RomWBW emulator to iOS or macOS using the shared HBIOS implementation.

## Architecture Overview

The emulator is designed for easy cross-platform porting:

```
┌─────────────────────────────────────────────┐
│           Your iOS/macOS App                │
│  (ViewController, SwiftUI View, etc.)       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────┴───────────────────────────┐
│        emu_io_ios.mm / emu_io_macos.mm      │
│  (Platform-specific I/O implementation)     │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────┴───────────────────────────┐
│            Shared Emulation Core            │
│  • hbios_dispatch.cc - HBIOS services       │
│  • romwbw_mem.h - Bank-switched memory      │
│  • qkz80 - Z80 CPU (from cpmemu)            │
└─────────────────────────────────────────────┘
```

## Step 1: Add Source Files to Project

Add these files from `src/`:

**Required (Shared Core):**
- `hbios_dispatch.h` / `hbios_dispatch.cc` - HBIOS implementation
- `romwbw_mem.h` - Banked memory (header-only)
- `emu_io.h` - I/O interface definition

**Required (CPU - from cpmemu project):**
- `qkz80.h` / `qkz80.cc` - Z80 CPU core
- `qkz80_mem.h` / `qkz80_mem.cc` - Memory interface
- `qkz80_reg_set.h` / `qkz80_reg_set.cc` - Register set
- `qkz80_errors.h` / `qkz80_errors.cc` - Error handling

## Step 2: Implement Platform I/O

Create `emu_io_ios.mm` (or `emu_io_macos.mm`) implementing `emu_io.h`:

```objc
// emu_io_ios.mm
#import <Foundation/Foundation.h>
#include "emu_io.h"
#include <queue>
#include <mutex>

// Thread-safe input queue
static std::queue<int> input_queue;
static std::mutex input_mutex;

// Callbacks to UI (set these from your ViewController)
static void (*console_output_callback)(int ch) = nullptr;
static void (*status_callback)(const char* msg) = nullptr;
static void (*nvram_save_callback)(const uint8_t* data, int size) = nullptr;

extern "C" {

void emu_io_init() {
    // Initialize any platform-specific state
}

void emu_console_write_char(int ch) {
    if (console_output_callback) {
        // Dispatch to main thread for UI update
        dispatch_async(dispatch_get_main_queue(), ^{
            console_output_callback(ch);
        });
    }
}

int emu_console_read_char() {
    std::lock_guard<std::mutex> lock(input_mutex);
    if (input_queue.empty()) return -1;
    int ch = input_queue.front();
    input_queue.pop();
    return ch;
}

bool emu_console_has_input() {
    std::lock_guard<std::mutex> lock(input_mutex);
    return !input_queue.empty();
}

void emu_console_queue_char(int ch) {
    std::lock_guard<std::mutex> lock(input_mutex);
    input_queue.push(ch);
}

void emu_get_time(emu_time* t) {
    NSDate *now = [NSDate date];
    NSCalendar *calendar = [NSCalendar currentCalendar];
    NSDateComponents *components = [calendar components:
        NSCalendarUnitYear | NSCalendarUnitMonth | NSCalendarUnitDay |
        NSCalendarUnitHour | NSCalendarUnitMinute | NSCalendarUnitSecond
        fromDate:now];

    t->year = (int)[components year];
    t->month = (int)[components month];
    t->day = (int)[components day];
    t->hour = (int)[components hour];
    t->minute = (int)[components minute];
    t->second = (int)[components second];
}

void emu_log(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    NSString *format = [NSString stringWithUTF8String:fmt];
    NSString *message = [[NSString alloc] initWithFormat:format arguments:args];
    va_end(args);
    NSLog(@"[EMU] %@", message);
}

void emu_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    NSString *format = [NSString stringWithUTF8String:fmt];
    NSString *message = [[NSString alloc] initWithFormat:format arguments:args];
    va_end(args);
    NSLog(@"[EMU ERROR] %@", message);
}

void emu_status(const char* msg) {
    if (status_callback) {
        dispatch_async(dispatch_get_main_queue(), ^{
            status_callback(msg);
        });
    }
}

// Call these from your ViewController to set up callbacks
void emu_set_console_output_callback(void (*callback)(int ch)) {
    console_output_callback = callback;
}

void emu_set_status_callback(void (*callback)(const char* msg)) {
    status_callback = callback;
}

} // extern "C"
```

## Step 3: Create Emulator Wrapper

Create a Swift or Objective-C++ wrapper class:

```objc
// RomWBWEmulator.h
#import <Foundation/Foundation.h>

@protocol RomWBWEmulatorDelegate <NSObject>
- (void)emulatorDidOutputCharacter:(int)ch;
- (void)emulatorDidUpdateStatus:(NSString *)status;
- (void)emulatorDidSaveNVRAM:(NSData *)data;
@end

@interface RomWBWEmulator : NSObject

@property (weak, nonatomic) id<RomWBWEmulatorDelegate> delegate;
@property (readonly, nonatomic) BOOL isRunning;

- (BOOL)loadROMFromData:(NSData *)romData;
- (BOOL)loadDiskUnit:(int)unit fromData:(NSData *)diskData;
- (void)start;
- (void)stop;
- (void)sendKey:(int)ch;
- (void)loadNVRAMFromData:(NSData *)data;

@end
```

```objc
// RomWBWEmulator.mm
#import "RomWBWEmulator.h"
#include "qkz80.h"
#include "romwbw_mem.h"
#include "hbios_dispatch.h"
#include "emu_io.h"

@implementation RomWBWEmulator {
    banked_mem _memory;
    qkz80 *_cpu;
    HBIOSDispatch _hbios;
    BOOL _running;
    dispatch_queue_t _emulatorQueue;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _cpu = new qkz80(&_memory);
        _emulatorQueue = dispatch_queue_create("com.yourapp.emulator", DISPATCH_QUEUE_SERIAL);

        // Initialize I/O
        emu_io_init();

        // Set up callbacks (bridge to delegate)
        __weak typeof(self) weakSelf = self;
        emu_set_console_output_callback([](int ch) {
            [weakSelf.delegate emulatorDidOutputCharacter:ch];
        });
    }
    return self;
}

- (BOOL)loadROMFromData:(NSData *)romData {
    _memory.enable_banking();

    uint8_t *rom = _memory.get_rom();
    memcpy(rom, romData.bytes, MIN(romData.length, 512 * 1024));

    // Patch APITYPE for HBIOS
    rom[0x0112] = 0x00;

    // Copy HCB to RAM
    uint8_t *ram = _memory.get_ram();
    memcpy(ram, rom, 512);

    // Set up HBIOS ident signatures
    [self setupHBIOSIdent];

    return YES;
}

- (void)setupHBIOSIdent {
    uint8_t *ram = _memory.get_ram();
    const uint32_t COMMON_BASE = 0x0F * 32768;

    // Ident at 0xFF00
    uint32_t ident = COMMON_BASE + (0xFF00 - 0x8000);
    ram[ident + 0] = 'W';
    ram[ident + 1] = ~'W';
    ram[ident + 2] = 0x35;  // v3.5

    // Pointer at 0xFFFC
    uint32_t ptr = COMMON_BASE + (0xFFFC - 0x8000);
    ram[ptr + 0] = 0x00;
    ram[ptr + 1] = 0xFF;
}

- (BOOL)loadDiskUnit:(int)unit fromData:(NSData *)diskData {
    return _hbios.loadDisk(unit, (const uint8_t *)diskData.bytes, diskData.length);
}

- (void)start {
    _cpu->set_cpu_mode(qkz80::MODE_Z80);
    _memory.enable_banking();

    _hbios.setCPU(_cpu);
    _hbios.setMemory(&_memory);

    // Set up reset callback
    _hbios.setResetCallback([self](uint8_t type) {
        _memory.select_bank(0x00);
        _cpu->regs.PC.set_pair16(0x0000);
    });

    // Set up NVRAM save callback
    __weak typeof(self) weakSelf = self;
    _hbios.setNvramSaveCallback([weakSelf](const uint8_t *data, int size) {
        NSData *nvramData = [NSData dataWithBytes:data length:size];
        dispatch_async(dispatch_get_main_queue(), ^{
            [weakSelf.delegate emulatorDidSaveNVRAM:nvramData];
        });
    });

    _cpu->regs.PC.set_pair16(0x0000);
    _memory.select_bank(0x00);

    _running = YES;

    // Run emulator on background queue
    dispatch_async(_emulatorQueue, ^{
        [self runLoop];
    });
}

- (void)runLoop {
    while (_running) {
        // Execute batch of instructions
        for (int i = 0; i < 50000 && _running; i++) {
            uint16_t pc = _cpu->regs.PC.get_pair16();

            // Check for HBIOS trap
            if (_hbios.checkTrap(pc)) {
                int trap_type = _hbios.getTrapType(pc);
                _hbios.handleCall(trap_type);
                continue;
            }

            uint8_t opcode = _memory.fetch_mem(pc);

            // Handle HLT
            if (opcode == 0x76) {
                _running = NO;
                break;
            }

            _cpu->execute();
        }

        // Yield to other threads
        usleep(1000);  // 1ms
    }
}

- (void)stop {
    _running = NO;
}

- (void)sendKey:(int)ch {
    if (ch == '\n') ch = '\r';  // LF -> CR
    emu_console_queue_char(ch);
}

- (void)loadNVRAMFromData:(NSData *)data {
    _hbios.loadNvram((const uint8_t *)data.bytes, (int)data.length);
}

- (void)dealloc {
    delete _cpu;
}

@end
```

## Step 4: NVRAM Persistence

Store NVRAM in UserDefaults or Keychain:

```objc
// In your ViewController or AppDelegate
- (void)emulatorDidSaveNVRAM:(NSData *)data {
    [[NSUserDefaults standardUserDefaults] setObject:data forKey:@"RomWBW_NVRAM"];
}

- (void)loadSavedNVRAM {
    NSData *nvram = [[NSUserDefaults standardUserDefaults] objectForKey:@"RomWBW_NVRAM"];
    if (nvram) {
        [self.emulator loadNVRAMFromData:nvram];
    }
}
```

## Step 5: ROM Loading

Load ROM from bundle or download:

```objc
// Load from app bundle
NSString *romPath = [[NSBundle mainBundle] pathForResource:@"SBC_simh_std" ofType:@"rom"];
NSData *romData = [NSData dataWithContentsOfFile:romPath];
[emulator loadROMFromData:romData];

// Or download from server
NSURL *url = [NSURL URLWithString:@"https://your-server.com/roms/SBC_simh_std.rom"];
NSData *romData = [NSData dataWithContentsOfURL:url];
[emulator loadROMFromData:romData];
```

## Critical Implementation Notes

### 1. APITYPE Patching
The ROM at offset 0x0112 MUST be patched to 0x00 (HBIOS). Without this, REBOOT and other utilities will fail with "UNA not supported".

### 2. HBIOS Ident Signatures
Must set up 'W' + ~'W' + version at 0xFF00 and 0xFE00 in common RAM area. This is required for REBOOT to detect HBIOS.

### 3. Thread Safety
Run the emulator loop on a background thread. Use dispatch_async to update UI from callbacks.

### 4. Input Handling
Queue keyboard input thread-safely. Convert LF (0x0A) to CR (0x0D) for CP/M.

## NVRAM Compatibility

NVRAM (64 bytes) requires a ROM with DS1302/DS1307 RTC support:
- `SBC_std.rom` - Has NVRAM support
- `SBC_simh_std.rom` - No NVRAM (uses SIMRTC)

## Testing

1. Boot to CP/M prompt - should show boot menu
2. `REBOOT /W` - warm boot should work
3. `REBOOT /C` - cold boot should work
4. If using DS1302 ROM, press `W` at boot for NVRAM config

## Files Reference

| File | Description |
|------|-------------|
| `web/romwbw_web.cc` | WebAssembly reference implementation |
| `src/romwbw_emu.cc` | CLI reference implementation |
| `src/emu_io_wasm.cc` | WASM I/O implementation |
| `src/emu_io_cli.cc` | CLI I/O implementation |

## Questions?

See `docs/ARCHITECTURE.md` for detailed component documentation.
