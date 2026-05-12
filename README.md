# reCamera API Server

Simple HTTP API server for the reCamera platform. Provides endpoints for video capture on crash events and metadata storage.

## Features

- ✅ Lightweight Python HTTP server (no external dependencies)
- ✅ `/api/capture` endpoint for crash event recording
- ✅ `/api/status` endpoint for health checks
- ✅ `/api/videos` endpoint to list recorded videos
- ✅ Video metadata storage on SD card
- ✅ Runs on port 8080
- ✅ Automatic SD card directory creation

## Installation on reCamera

### Quick Start (5 minutes)

1. **SSH into camera**:
   ```bash
   ssh recamera@<camera-ip>
   ```

2. **Clone this repository**:
   ```bash
   cd /tmp/sd
   git clone https://github.com/Suntado/recamera-api.git
   cd recamera-api
   ```

3. **Run the server**:
   ```bash
   python3 camera_server.py
   ```

4. **Verify it's working**:
   ```bash
   curl http://localhost:8080/api/status
   ```

### Background Service (Production)

To run the API server as a background service that starts on boot:

```bash
# Copy systemd service file
sudo cp recamera-api.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable recamera-api
sudo systemctl start recamera-api

# Check status
sudo systemctl status recamera-api

# View logs
journalctl -u recamera-api -f
```

## API Endpoints

### GET /api/status
Returns camera health and SD card status.

**Response:**
```json
{
  "status": "ok",
  "model": "reCamera",
  "version": "1.0.0",
  "sd_card": {
    "status": "ok",
    "free_mb": 7500,
    "total_mb": 7624
  }
}
```

### POST /api/capture
Triggered by ESP32 on crash event. Records video for specified duration.

**Parameters:**
- `event_id` (required): Unix timestamp in milliseconds (e.g., `1715000000000`)
- `duration` (optional): Video length in seconds (default: `15`)
- `format` (optional): Video codec (default: `mp4`)

**Example:**
```bash
curl -X POST "http://192.168.1.100:8080/api/capture?event_id=1715000000000&duration=15&format=mp4"
```

**Response:**
```json
{
  "status": "capturing",
  "event_id": "1715000000000",
  "filename": "event_1715000000000_15s.mp4",
  "duration_s": 15,
  "filepath": "/tmp/sd/videos/event_1715000000000_15s.mp4",
  "expected_size_mb": 50
}
```

### GET /api/videos
List all recorded videos on SD card.

**Response:**
```json
{
  "status": "ok",
  "count": 3,
  "videos": [
    {
      "filename": "event_1715000000000_15s.mp4",
      "size_bytes": 52428800,
      "size_mb": 50.0,
      "path": "/videos/event_1715000000000_15s.mp4"
    }
  ]
}
```

### POST /api/events/{event_id}/video
Camera sends video metadata to server after capture completes.

**Request Body:**
```json
{
  "video_url": "http://192.168.1.100:8080/videos/event_1715000000000_15s.mp4",
  "video_filename": "event_1715000000000_15s.mp4",
  "video_size": 52428800
}
```

**Response:**
```json
{
  "status": "success",
  "event_id": "1715000000000",
  "message": "Video metadata stored"
}
```

## Directory Structure

```
/tmp/sd/
├── videos/          # MP4 video files
│   └── event_*.mp4
└── metadata/        # JSON metadata files
    └── *.json
```

## Testing

### From reCamera terminal:

```bash
# Test health check
curl http://localhost:8080/api/status

# Test capture endpoint
curl -X POST "http://localhost:8080/api/capture?event_id=1715000000000&duration=15&format=mp4"

# List videos
curl http://localhost:8080/api/videos
```

### From remote machine:

```bash
# Replace 192.168.1.100 with your camera IP
curl http://192.168.1.100:8080/api/status
```

## Integration with Forklift Crash Detector

1. Update ESP32 firmware `config.h`:
   ```cpp
   #define CAMERA_URL "http://192.168.1.100:8080"
   ```

2. Camera will receive crash signal:
   ```
   POST /api/capture?event_id=<timestamp>&duration=15&format=mp4
   ```

3. Camera records video (5 sec before + 10 sec after crash)

4. Server can retrieve videos via:
   ```bash
   curl http://192.168.1.100:8080/api/videos
   ```

## Logs

Check server logs in `/tmp/sd/camera_server.log` (if running as service):

```bash
tail -f /tmp/sd/camera_server.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" on port 8080 | Server not running: `python3 camera_server.py` |
| SD card errors | Ensure `/tmp/sd` is mounted: `mount \| grep mmcblk1` |
| Permission denied | Run with: `sudo python3 camera_server.py` |
| Out of disk space | Clean old videos: `rm /tmp/sd/videos/event_*.mp4` |

## Development

To test locally on your laptop:

```bash
python3 camera_server.py
# Server runs on http://localhost:8080
```

## License

MIT — See LICENSE file
