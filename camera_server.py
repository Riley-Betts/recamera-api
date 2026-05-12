#!/usr/bin/env python3
"""
reCamera API Server
Simple HTTP API for video capture and metadata storage.
Listens on port 8080 and provides endpoints for crash event video capture.
"""

import os
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Configuration
API_PORT = 8080
VIDEO_DIR = "/tmp/sd/videos"
METADATA_DIR = "/tmp/sd/metadata"
BUFFER_DURATION = 300  # Keep 5 min rolling buffer (in seconds)

# Ensure directories exist
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# Simple circular video buffer tracker
class VideoBuffer:
    def __init__(self):
        self.current_event_id = None
        self.start_time = None
        self.duration = 0
        self.filename = None

    def start_capture(self, event_id, duration):
        self.current_event_id = event_id
        self.start_time = time.time()
        self.duration = duration
        self.filename = f"event_{event_id}_{duration}s.mp4"
        return self.filename

video_buffer = VideoBuffer()

class CameraAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for camera API endpoints"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        if path == "/api/status":
            self.send_status_response()
        elif path == "/api/videos":
            self.send_video_list()
        else:
            self.send_error_response(404, "Endpoint not found")

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        if path == "/api/capture":
            self.handle_capture_request(query_params)
        elif path.startswith("/api/events/") and path.endswith("/video"):
            self.handle_video_upload(path)
        else:
            self.send_error_response(404, "Endpoint not found")

    def handle_capture_request(self, params):
        """Handle /api/capture POST request"""
        try:
            event_id = params.get("event_id", [""])[0]
            duration = int(params.get("duration", ["15"])[0])
            fmt = params.get("format", ["mp4"])[0]

            if not event_id:
                self.send_error_response(400, "Missing event_id parameter")
                return

            # Start capturing
            filename = video_buffer.start_capture(event_id, duration)
            filepath = os.path.join(VIDEO_DIR, filename)

            # Simulate video capture by creating a placeholder file
            # In production, this would trigger actual video encoding
            self.create_test_video_file(filepath)

            response = {
                "status": "capturing",
                "event_id": event_id,
                "filename": filename,
                "duration_s": duration,
                "filepath": filepath,
                "expected_size_mb": 50
            }

            self.send_json_response(200, response)

            # Log the capture
            log_msg = f"[{datetime.now().isoformat()}] Capture started: {filename}"
            print(log_msg)

        except Exception as e:
            self.send_error_response(500, f"Capture failed: {str(e)}")

    def handle_video_upload(self, path):
        """Handle video metadata upload from camera to server"""
        try:
            # Extract event_id from path: /api/events/12345/video
            parts = path.split("/")
            event_id = parts[3] if len(parts) > 3 else None

            if not event_id:
                self.send_error_response(400, "Invalid path format")
                return

            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            if not body:
                self.send_error_response(400, "Empty request body")
                return

            metadata = json.loads(body.decode("utf-8"))

            # Store metadata locally
            metadata_file = os.path.join(METADATA_DIR, f"{event_id}.json")
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            response = {
                "status": "success",
                "event_id": event_id,
                "message": "Video metadata stored"
            }

            self.send_json_response(200, response)

            log_msg = f"[{datetime.now().isoformat()}] Metadata stored: event_{event_id}.json"
            print(log_msg)

        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON in request body")
        except Exception as e:
            self.send_error_response(500, f"Upload failed: {str(e)}")

    def send_status_response(self):
        """Send camera status"""
        status = {
            "status": "ok",
            "model": "reCamera",
            "version": "1.0.0",
            "uptime_seconds": int(time.time()),
            "sd_card": {
                "status": "ok",
                "mount_point": "/tmp/sd",
                "free_mb": self.get_free_space_mb("/tmp/sd"),
                "total_mb": self.get_total_space_mb("/tmp/sd")
            },
            "recording": "enabled"
        }
        self.send_json_response(200, status)

    def send_video_list(self):
        """Send list of available videos"""
        videos = []
        if os.path.exists(VIDEO_DIR):
            for f in os.listdir(VIDEO_DIR):
                if f.endswith(".mp4"):
                    filepath = os.path.join(VIDEO_DIR, f)
                    size = os.path.getsize(filepath)
                    videos.append({
                        "filename": f,
                        "size_bytes": size,
                        "size_mb": round(size / (1024*1024), 2),
                        "path": f"/videos/{f}"
                    })

        response = {
            "status": "ok",
            "count": len(videos),
            "videos": videos
        }
        self.send_json_response(200, response)

    def send_json_response(self, status_code, data):
        """Send JSON response"""
        response_body = json.dumps(data).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response_body))
        self.end_headers()
        self.wfile.write(response_body)

    def send_error_response(self, status_code, message):
        """Send error response"""
        response = {
            "status": "error",
            "code": status_code,
            "message": message
        }
        self.send_json_response(status_code, response)

    def create_test_video_file(self, filepath):
        """Create a test MP4 file (placeholder for actual video capture)"""
        # Create a minimal MP4 file structure
        # In production, this would be actual video from the camera
        try:
            with open(filepath, "wb") as f:
                # Write minimal MP4 header
                f.write(b"\x00\x00\x00\x20ftypisom")  # ftyp atom
                f.write(b"\x00" * 8192)  # Padding (placeholder for video data)

            # Set file size to ~50MB to simulate real video
            os.truncate(filepath, 50 * 1024 * 1024)

        except Exception as e:
            print(f"Error creating test video: {e}")

    def get_free_space_mb(self, path):
        """Get free space in MB"""
        try:
            import shutil
            stat = shutil.disk_usage(path)
            return round(stat.free / (1024*1024), 2)
        except:
            return 0

    def get_total_space_mb(self, path):
        """Get total space in MB"""
        try:
            import shutil
            stat = shutil.disk_usage(path)
            return round(stat.total / (1024*1024), 2)
        except:
            return 0

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def run_server():
    """Start the HTTP server"""
    server = HTTPServer(("0.0.0.0", API_PORT), CameraAPIHandler)
    print(f"[reCamera API Server] Starting on port {API_PORT}")
    print(f"[reCamera API Server] Video directory: {VIDEO_DIR}")
    print(f"[reCamera API Server] Metadata directory: {METADATA_DIR}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[reCamera API Server] Shutting down...")
        server.shutdown()

if __name__ == "__main__":
    run_server()
