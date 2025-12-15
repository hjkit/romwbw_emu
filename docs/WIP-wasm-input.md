# WIP: WASM Input Not Working

## Status
Boot loader displays correctly but keyboard input has no effect.

## What Works
- ROM loads successfully
- Memory disks initialized (MD0 RAM, MD1 ROM)
- HD0 disk loaded
- Boot loader starts and displays prompt
- Z flag fix applied (disk I/O failure resolved)
- Keys are received by JavaScript (console shows `[KEY] char=104 waiting=0`)

## What Doesn't Work
- Typed characters don't appear / aren't processed
- Boot loader stays at "Boot [H=Help]:" prompt

## Current Theory
The boot loader polls CIOIST (input status) in a loop rather than blocking on CIOIN.
When key is pressed:
1. JS receives key, logs `[KEY] char=104 waiting=0`
2. `waiting=0` means emulator is NOT in blocking CIOIN wait
3. Key is queued via `emu_console_queue_char()`
4. Next CIOIST poll should see it and return E=0xFF
5. Boot loader should then call CIOIN to read character

Somewhere in steps 4-5, something isn't working.

## Debug Logging Added
- `[KEY]` logging in HTML onKey handler
- `[CIOIST]` logging when has_input=true
- `[CIOIN]` logging when character is read

## Files Changed (uncommitted)
- `src/hbios_dispatch.cc` - Z flag fix via setResult(), debug logging
- `src/hbios_dispatch.h` - setResult() declaration
- `web/romwbw_web.cc` - Use hbios.isWaitingForInput() instead of local flag
- `web/romwbw.html` - Key debug logging
- `web/Makefile` - Timestamp in dev deploy
- `cpmemu/src/qkz80_reg_set.cc` - set_flag_bits/clear_flag_bits helpers
- `cpmemu/src/qkz80_reg_set.h` - set_flag_bits/clear_flag_bits declarations

## Next Steps
1. Rebuild and test with debug logging
2. Check if CIOIST ever sees input ready
3. Check if CIOIN ever gets called after key press
4. May need to examine boot loader code to understand its input loop

## Version
1.17 (with HHMMSS timestamp in dev builds)
