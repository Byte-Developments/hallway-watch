# Hallway Watch

Lightweight head detection for Raspberry Pi. Watches a hallway via USB webcam, plays a sound on the 3.5mm jack, and sends browser notifications to your Mac.

## How it works

1. **Black & white preprocessing** — every frame is converted to grayscale with CLAHE contrast boost so motion and AI work in dark hallways.
2. **Motion gate** — background subtraction runs on the enhanced frame; AI only runs when something moves (saves CPU).
3. **YOLOv8n + head regions** — detects people, then checks the **head** (top of the box) so partial hallway appearances still trigger.
4. **ROI mask** (optional) — strict black-and-white PNG; white = watch, black = ignore.
5. **Cooldown** — won't spam alerts for the same visit.
6. **Browser notifications** — a local HTTPS page registers a service worker and Web Push subscription so alerts arrive even when the page is closed.

## Quick start (on the Pi)

**Interactive installer** (prompts for settings and writes `config.yaml`):

```bash
# Copy project to Pi, then:
scp -r hallway-watch pi@raspberrypi.local:~/
ssh pi@raspberrypi.local
cd ~/hallway-watch
chmod +x install.sh
./install.sh
```

**Non-interactive** (accept all defaults):

```bash
./install.sh -y
```

**Curl one-liner** (clone + install):

```bash
curl -fsSL https://raw.githubusercontent.com/Byte-Developments/hallway-watch/main/install.sh | bash
```

Installer flags: `-y` defaults only, `--config-only` rewrite config, `--no-service` skip systemd, `-h` help.

## Updates

After install, update the Pi anytime with:

```bash
hwatch update
```

This pulls the latest code from GitHub, refreshes pip libraries and model weights, and restarts the service.

## Configuration

The installer writes `config.yaml`, downloads **YOLOv8n weights** to `models/yolov8n.pt`, installs pip libraries, and sets up the service — all in the background with a log at `install.log`.

```bash
./install.sh --config-only   # re-run prompts, rewrite config
# or edit by hand:
nano config.yaml
sudo systemctl restart hallway-watch
```

Key settings:

| Setting | Description |
|---------|-------------|
| `camera.device` | Usually `0` for `/dev/video0` |
| `detection.confidence` | Lower = more sensitive (try 0.45–0.65) |
| `detection.low_light_enhance` | Grayscale + CLAHE for dark hallways (default: on) |
| `detection.head_height_fraction` | How much of a person box counts as head (default: 0.35) |
| `detection.motion_threshold` | Lower = triggers AI more often |
| `detection.roi_mask` | B&W PNG — white = watch area, black = ignore |
| `notifications.port` | HTTPS web page port (default: 8765) |
| `audio.sound_file` | Path to a `.wav` alert sound |

## Browser notifications

Background notifications use a **service worker** and **Web Push**. You only need to set this up once.

1. Make sure hallway-watch is running on the Pi (`install.sh` creates a self-signed HTTPS cert).
2. On your Mac, open `https://raspberrypi.local:8765` (or the Pi's IP address).
3. Accept the browser's certificate warning (self-signed cert for your home network).
4. Click **Enable notifications** and allow them when prompted.
5. Close the page — alerts will still show up as native macOS notifications.

Safari, Chrome, and Firefox all support this. Subscriptions are saved on the Pi in `data/push_subscriptions.json`.

## Test with preview

```bash
source .venv/bin/activate
python -m hallway_watch.main --preview
```

Press `q` to quit. Draw an ROI mask (optional) by taking a snapshot and painting **pure white** where you want to watch and **pure black** everywhere else.

## Run as a service

```bash
sudo systemctl start hallway-watch
sudo systemctl status hallway-watch
journalctl -u hallway-watch -f
```

## Hardware

- Raspberry Pi 4 or 5 (Pi 3 works but is slower)
- USB webcam taped to wall facing the hallway
- Speaker plugged into 3.5mm jack
- Stable Wi-Fi so your Mac can reach the Pi's notification page
