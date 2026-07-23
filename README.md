# Hallway Watch

Lightweight head detection for Raspberry Pi. Watches a hallway via USB webcam, plays a sound on the 3.5mm jack, and sends browser notifications to your Mac.

## How it works

1. **Black & white preprocessing** — every frame is converted to grayscale with CLAHE contrast boost so motion and AI work in dark hallways.
2. **Motion gate** — background subtraction runs on the enhanced frame; AI only runs when something moves (saves CPU).
3. **YOLOv8n + head regions** — detects people, then checks the **head** (top of the box) so partial hallway appearances still trigger.
4. **ROI mask** (optional) — strict black-and-white PNG; white = watch, black = ignore.
5. **One alert per visit** — alerts once when someone enters, not continuously while they're in frame.
6. **Alert snapshots** — saves a JPEG with head boxes to `snapshots/` on each alert.
7. **Browser notifications** — a local HTTPS page at **https://hallway.local:8765** with service worker + Web Push.

## Install (one command)

SSH into your Raspberry Pi and paste:

```bash
git clone --depth 1 https://github.com/Byte-Developments/hallway-watch.git ~/hallway-watch
~/hallway-watch/install.sh
```

That's it. The script walks you through setup prompts, installs everything, sets hostname to **hallway.local**, and starts the service.

**Already cloned / re-run install:**

```bash
cd ~/hallway-watch && git pull && ./install.sh
```

**Skip prompts** (use all defaults):

```bash
~/hallway-watch/install.sh -y
```

Installer flags: `-y` defaults only · `--config-only` rewrite config · `--no-service` skip systemd · `-h` help

> Prefer `git pull && ./install.sh` over `curl … | bash` — GitHub’s raw CDN can serve a stale `install.sh` for a while after pushes.

## Updates

```bash
hwatch update
```

Pulls the latest code, refreshes pip libraries and model weights, and restarts the service.

## Configuration

The installer writes `config.yaml`. To change settings later:

```bash
~/hallway-watch/install.sh --config-only
# or: nano ~/hallway-watch/config.yaml && hwatch stop && hwatch start
```

Key settings:

| Setting | Description |
|---------|-------------|
| `camera.device` | Usually `0` for `/dev/video0` |
| `detection.confidence` | Lower = more sensitive (try 0.38–0.50) |
| `detection.low_light_enhance` | Grayscale + CLAHE for dark hallways (default: on) |
| `detection.motion_threshold` | Lower = triggers AI more often |
| `detection.roi_mask` | B&W PNG — white = watch area, black = ignore |
| `snapshots.dir` | Where alert JPEGs are saved (default: `snapshots/`) |
| `snapshots.retention_days` | Delete alert JPEGs older than this (default: `7`) |
| `camera.recovery_enabled` | Reopen USB camera after sustained read failures (default: on) |
| `notifications.port` | HTTPS web page port (default: 8765) |
| `audio.sound_file` | Path to a `.wav` alert sound |

## Browser notifications

1. Make sure hallway-watch is running (`install.sh` sets up **hallway.local** via mDNS).
2. On your Mac, open **`https://hallway.local:8765`**.
3. Accept the certificate warning (self-signed cert).
4. Click **Enable notifications** and allow them when prompted.
5. Close the page — alerts still arrive via the service worker.

## Commands

```bash
hwatch start    # start the service
hwatch stop     # stop the service
hwatch update   # pull latest code + restart
hwatch logs     # detection log viewer (scroll, search, live tail)
hwatch debug    # developer log viewer
hwatch status   # install info + service state
```

**Log viewer keys:** `j`/`k` scroll · `/` search · `n`/`N` next match · `f` follow · `g`/`G` top/bottom · `o` older file · `q` quit

## Test with preview

```bash
cd ~/hallway-watch && source .venv/bin/activate
python -m hallway_watch.main --preview
```

Press `q` to quit.

## Hardware

- Raspberry Pi 4 or 5 (Pi 3 works but is slower)
- USB webcam taped to wall facing the hallway
- Speaker plugged into 3.5mm jack
- Stable Wi-Fi so your Mac can reach **hallway.local**
