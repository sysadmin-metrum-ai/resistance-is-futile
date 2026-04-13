# Firmware Manifest

All known-working firmware binaries for the drone fleet and LPS infrastructure.

## Crazyflie (firmware/crazyflie/)

| File | Platform | Version | Status |
|------|----------|---------|--------|
| cf21bl-2025.12.1.bin | Crazyflie 2.1+ Brushless | 2025.12.1 | Active on BL21+_0 |
| cf2-2025.12.1.bin | Crazyflie 2.1 (brushed) | 2025.12.1 | Stock Bitcraze release |

### Active drone firmware details (BL21+_0)

- firmware.revision0: 2570053570
- firmware.revision1: 59824
- firmware.modified: 0
- cpu.id0: 4456535

## LPS Nodes (firmware/lps-nodes/)

| File | Platform | Notes |
|------|----------|-------|
| lps-node-firmware.dfu | Loco Positioning Node (DWM1000) | Flash via DFU: `dfu-util -a 0 -s 0x08000000 -D lps-node-firmware.dfu` |

## Crazyradio (firmware/radio/)

| File | Platform | Version |
|------|----------|---------|
| crazyradio2-CRPA-emulation-1.1.uf2 | Crazyradio 2.0 PA | CRPA emulation 1.1 |

## AI Deck (firmware/aideck/)

| File | Platform | Version |
|------|----------|---------|
| aideck_esp-2025.02.bin | AI Deck ESP32 | 2025.02 |
| aideck_gap8_wifi_img_streamer_with_ap-2025.02.bin | AI Deck GAP8 | 2025.02 |

## Color LED Deck (firmware/color-led/)

| File | Platform | Notes |
|------|----------|-------|
| color-led.bin | Color LED deck (STM32) | Custom build |

## Flashing

- Crazyflie: `cfloader flash firmware/crazyflie/cf21bl-2025.12.1.bin stm32-fw`
- LPS Node: `dfu-util -a 0 -s 0x08000000 -D firmware/lps-nodes/lps-node-firmware.dfu`
- Crazyradio 2: copy `.uf2` to radio's USB mass storage
- AI Deck: via cfclient AI deck flasher
