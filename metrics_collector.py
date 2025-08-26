import logging
from typing import Dict, List
from prometheus_client import Gauge, Counter
from cloudflare_client import CloudflareClient

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and manages Prometheus metrics for Cloudflare Waiting Rooms."""
    
    def __init__(self, cf_client: CloudflareClient):
        self.cf_client = cf_client
        
        # Initialize Prometheus metrics
        self.queued_users = Gauge(
            'cf_waitingroom_queued_users',
            'Estimated number of users currently waiting in the queue',
            ['waitingroom']
        )
        
        self.total_active_users = Gauge(
            'cf_waitingroom_total_active_users',
            'Estimated number of users currently active on the origin',
            ['waitingroom']
        )
        
        self.max_estimated_time_minutes = Gauge(
            'cf_waitingroom_max_estimated_time_minutes',
            'Maximum estimated time currently presented to users in minutes',
            ['waitingroom']
        )
        
        self.room_status = Gauge(
            'cf_waitingroom_status',
            'Status of the waiting room (0=not_queueing, 1=queueing, 2=event_prequeueing, 3=suspended)',
            ['waitingroom', 'status']
        )
    
    def update_metrics_for_room(self, waiting_room_id: str) -> bool:
        """Update metrics for a single waiting room."""
        try:
            # Get status data
            status = self.cf_client.get_waiting_room_status(waiting_room_id)
            if not status:
                logger.warning(f"No status data for waiting room {waiting_room_id}")
                return False
            
            # Update queued users
            queued_users = status.get('estimated_queued_users', 0)
            self.queued_users.labels(waitingroom=waiting_room_id).set(queued_users)
            
            # Update total active users
            total_active_users = status.get('estimated_total_active_users', 0)
            self.total_active_users.labels(waitingroom=waiting_room_id).set(total_active_users)
            
            # Update max estimated time (convert to seconds for consistency)
            max_time_minutes = status.get('max_estimated_time_minutes', 0)
            self.max_estimated_time_minutes.labels(waitingroom=waiting_room_id).set(max_time_minutes)
            
            # Update room status as numeric gauge with labels
            room_status = status.get('status', 'unknown')
            status_map = {
                'not_queueing': 0,
                'queueing': 1, 
                'event_prequeueing': 2,
                'suspended': 3
            }
            
            # Reset all status gauges for this room first
            for status_name in status_map.keys():
                self.room_status.labels(waitingroom=waiting_room_id, status=status_name).set(0)
            
            # Set the current status to 1
            if room_status in status_map:
                self.room_status.labels(waitingroom=waiting_room_id, status=room_status).set(1)
            
            logger.debug(f"Updated metrics for waiting room {waiting_room_id}: "
                        f"queued={queued_users}, active={total_active_users}, "
                        f"max_time={max_time_minutes}min, status={room_status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update metrics for waiting room {waiting_room_id}: {e}")
            return False
    
    def update_metrics_for_rooms(self, waiting_room_ids: List[str]) -> int:
        """Update metrics for multiple waiting rooms. Returns count of successful updates."""
        success_count = 0
        
        for room_id in waiting_room_ids:
            if self.update_metrics_for_room(room_id):
                success_count += 1
        
        logger.info(f"Updated metrics for {success_count}/{len(waiting_room_ids)} waiting rooms")
        return success_count