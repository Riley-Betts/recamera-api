#!/usr/bin/env python3
"""
reCamera API Server
Simple HTTP server for video capture and metadata storage.
Listens on port 8080 and provides endpoints for crash event video capture.
Automatically uploads video metadata to the forklift crash detector server.
"""

import os
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Configuration
API_PORT = 8080
VIDEO_DIR = "/tmp/sd/videos"
METADATA_DIR = "/tmp/sd/metadata"
SERVER_URL = "http://10.35.2.216:8000"  # Forklift crash detector server

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

def upload_video_metadata(event_id, filename, filepath):
    """Upload video metadata to crash detector server"""
    try:
        # Get file size
        file_size = os.path.getsize(filepath)

        # Build video URL
        video_url = f"http://172.24.30.125:8080/videos/{filename}"

        # Prepare metadata
        metadata = {
            "video_url": video_url,
            "video_filename": filename,
            "video_size": file_size
        }

        # Send to server
        url = f"{SERVER_URL}/api/events/{event_id}/video"
        data = json.dumps(metadata).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            log_msg = f"[{datetime.now().isoformat()}] ✓ Video uploaded to server: {filename} ({file_size / (1024*1024):.1f} MB)"
            print(log_msg)
            return True

    except urllib.error.HTTPError as e:
        log_msg = f"[{datetime.now().isoformat()}] ✗ Server error uploading video: HTTP {e.code} - {e.reason}"
        print(log_msg)
        return False
    except Exception as e:
        log_msg = f"[{datetime.now().isoformat()}] ✗ Failed to upload video: {str(e)}"
        print(log_msg)
        return False

def capture_video_async(event_id, duration, filename, filepath):
    """Async function to handle capture and upload"""
    try:
        # Create test video file
        create_test_video_file(filepath)
        log_msg = f"[{datetime.now().isoformat()}] ✓ Video captured: {filename}"
        print(log_msg)

        # Wait a moment for file to be written
        time.sleep(0.5)

        # Upload metadata to server
        upload_video_metadata(event_id, filename, filepath)

    except Exception as e:
        log_msg = f"[{datetime.now().isoformat()}] ✗ Capture failed: {str(e)}"
        print(log_msg)

def create_test_video_file(filepath):
    """Create a test MP4 file (placeholder for actual video capture)"""
    try:
        with open(filepath, "wb") as f:
            # Write minimal MP4 header
            f.write(b"\x00\x00\x00\x20ftypisom")
            f.write(b"\x00" * 8192)

        # Set file size to ~50MB to simulate real video
        os.truncate(filepath, 50 * 1024 * 1024)

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error creating test video: {e}")

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
        elif path.startswith("/videos/"):
            # Serve video files
            self.serve_video_file(path)
        else:
            self.send_error_response(404, "Endpoint not found")

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        if path == "/api/capture":
            self.handle_capture_request(query_params)
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

            # Get filename
            filename = f"event_{event_id}_{duration}s.mp4"
            filepath = os.path.join(VIDEO_DIR, filename)

            # Start async capture and upload
            thread = threading.Thread(
                target=capture_video_async,
                args=(event_id, duration, filename, filepath),
                daemon=True
            )
            thread.start()

            response = {
                "status": "capturing",
                "event_id": event_id,
                "filename": filename,
                "duration_s": duration,
                "filepath": filepath,
                "expected_size_mb": 50
            }

            self.send_json_response(200, response)
            log_msg = f"[{datetime.now().isoformat()}] Capture started: {filename}"
            print(log_msg)

        except Exception as e:
            self.send_error_response(500, f"Capture failed: {str(e)}")

    def serve_video_file(self, path):
        """Serve video files from /videos/ endpoint"""
        try:
            filename = path.split("/")[-1]
            filepath = os.path.join(VIDEO_DIR, filename)

            # Security check - prevent directory traversal
            if not os.path.abspath(filepath).startswith(os.path.abspath(VIDEO_DIR)):
                self.send_error_response(403, "Access denied")
                return

            if not os.path.exists(filepath):
                self.send_error_response(404, "Video not found")
                return

            # Serve the file
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", os.path.getsize(filepath))
            self.end_headers()

            with open(filepath, "rb") as f:
                self.wfile.write(f.read())

        except Exception as e:
            self.send_error_response(500, f"Error serving file: {str(e)}")

    def send_status_response(self):
        """Send camera status"""
        status = {
            "status": "ok",
            "model": "reCamera",
            "version": "1.0.0",
            "uptime_seconds": int(time.time()),
            "server_url": SERVER_URL,
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
    print(f"[reCamera API Server] Server URL: {SERVER_URL}")
    print(f"[reCamera API Server] Ready to receive capture signals from ESP32\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[reCamera API Server] Shutting down...")
        server.shutdown()

if __name__ == "__main__":
    run_server()
