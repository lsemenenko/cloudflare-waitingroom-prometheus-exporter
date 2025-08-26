#!/usr/bin/env python3
"""
Cloudflare Waiting Room Metrics Exporter

A Prometheus exporter for Cloudflare Waiting Room analytics.
Exposes metrics via HTTP endpoint for scraping by Prometheus.
"""

import os
import time
import logging
import threading
from typing import List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from cloudflare_client import CloudflareClient
from metrics_collector import MetricsCollector


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving Prometheus metrics."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        elif parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(format % args)


class WaitingRoomExporter:
    """Main exporter class that orchestrates metrics collection and serving."""
    
    def __init__(self):
        self.api_token = self._get_env_var('CF_API_TOKEN')
        self.zone_id = self._get_env_var('CF_ZONE_ID')
        self.waiting_room_ids = self._parse_waiting_room_ids(
            self._get_env_var('CF_WAITING_ROOM_IDS')
        )
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '60'))
        self.http_port = int(os.getenv('HTTP_PORT', '8000'))
        
        # Initialize clients
        self.cf_client = CloudflareClient(self.api_token, self.zone_id)
        self.metrics_collector = MetricsCollector(self.cf_client)
        
        # Control flags
        self._stop_event = threading.Event()
        self._metrics_thread = None
        
        logger.info(f"Initialized exporter for {len(self.waiting_room_ids)} waiting rooms")
        logger.info(f"Poll interval: {self.poll_interval}s, HTTP port: {self.http_port}")
    
    def _get_env_var(self, name: str) -> str:
        """Get required environment variable."""
        value = os.getenv(name)
        if not value:
            raise ValueError(f"Required environment variable {name} is not set")
        return value
    
    def _parse_waiting_room_ids(self, ids_string: str) -> List[str]:
        """Parse comma-separated waiting room IDs."""
        ids = [id.strip() for id in ids_string.split(',') if id.strip()]
        if not ids:
            raise ValueError("At least one waiting room ID must be specified")
        return ids
    
    def _metrics_loop(self):
        """Background loop to continuously update metrics."""
        logger.info("Starting metrics collection loop")
        
        while not self._stop_event.is_set():
            try:
                success_count = self.metrics_collector.update_metrics_for_rooms(
                    self.waiting_room_ids
                )
                
                if success_count < len(self.waiting_room_ids):
                    logger.warning(f"Only {success_count}/{len(self.waiting_room_ids)} "
                                 "waiting rooms updated successfully")
                
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
            
            # Wait for next interval or stop signal
            self._stop_event.wait(self.poll_interval)
        
        logger.info("Metrics collection loop stopped")
    
    def start_metrics_collection(self):
        """Start the background metrics collection thread."""
        if self._metrics_thread and self._metrics_thread.is_alive():
            logger.warning("Metrics collection already running")
            return
        
        self._stop_event.clear()
        self._metrics_thread = threading.Thread(target=self._metrics_loop, daemon=True)
        self._metrics_thread.start()
    
    def stop_metrics_collection(self):
        """Stop the background metrics collection thread."""
        self._stop_event.set()
        if self._metrics_thread:
            self._metrics_thread.join(timeout=5)
    
    def start_http_server(self):
        """Start the HTTP server for metrics endpoint."""
        server = HTTPServer(('', self.http_port), MetricsHandler)
        logger.info(f"Starting HTTP server on port {self.http_port}")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        finally:
            server.server_close()
            self.stop_metrics_collection()
    
    def run(self):
        """Run the exporter."""
        # Start metrics collection in background
        self.start_metrics_collection()
        
        # Run initial collection to populate metrics immediately
        #logger.info("Performing initial metrics collection...")
        #self.metrics_collector.update_metrics_for_rooms(self.waiting_room_ids)
        
        # Start HTTP server (blocks until interrupted)
        self.start_http_server()


def main():
    """Entry point."""
    try:
        exporter = WaitingRoomExporter()
        exporter.run()
    except Exception as e:
        logger.error(f"Failed to start exporter: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())