#!/usr/bin/env python3
"""
AMI Event Listener for Trace Service
Listens to AMI events and updates call tracking
"""

import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AMIEventListener:
    """Listens to AMI events and updates trace service"""
    
    def __init__(self, trace_url: str, ami_url: str):
        self.trace_url = trace_url
        self.ami_url = ami_url
        self.active_calls: Dict[str, dict] = {}  # linkedid -> call info
        self.running = False
        
    async def start(self):
        """Start listening to AMI events"""
        self.running = True
        logger.info("Starting AMI event listener (polling mode)")
        
        # Poll AMI service for call information
        # In production, you might want to use WebSocket or direct AMI connection
        while self.running:
            try:
                await self.poll_ami_events()
                await asyncio.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error(f"Error in AMI event listener: {e}")
                await asyncio.sleep(10)
    
    async def poll_ami_events(self):
        """Poll AMI service for call information"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get all active calls from AMI service
                # Note: This assumes AMI service exposes a /calls endpoint
                # If not available, we'll rely on direct API calls from AVR Core
                try:
                    response = await client.get(f"{self.ami_url}/calls")
                    if response.status_code == 200:
                        calls = response.json()
                        await self.process_calls(calls)
                except httpx.HTTPError:
                    # Endpoint might not exist, that's okay
                    pass
        except Exception as e:
            logger.debug(f"Error polling AMI: {e}")
    
    async def process_calls(self, calls: dict):
        """Process call information from AMI"""
        for linkedid, call_info in calls.items():
            if linkedid not in self.active_calls:
                # New call detected
                await self.handle_new_call(linkedid, call_info)
            else:
                # Update existing call
                await self.handle_call_update(linkedid, call_info)
    
    async def handle_new_call(self, linkedid: str, call_info: dict):
        """Handle a new call"""
        call_uuid = call_info.get("uuid")
        if not call_uuid:
            return
        
        self.active_calls[linkedid] = call_info
        
        # Determine direction from context or channel
        channel = call_info.get("channel", "")
        context = call_info.get("context", "")
        direction = "outbound" if context == "outbound" or "outbound" in channel.lower() else "inbound"
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.trace_url}/api/calls/start",
                    json={
                        "call_uuid": call_uuid,
                        "direction": direction,
                        "channel": channel,
                        "context": context,
                        "metadata": call_info
                    }
                )
            logger.info(f"Started tracking call {call_uuid} ({direction})")
        except Exception as e:
            logger.warning(f"Failed to start tracking call {call_uuid}: {e}")
    
    async def handle_call_update(self, linkedid: str, call_info: dict):
        """Handle call update"""
        # Update call information if needed
        self.active_calls[linkedid] = call_info
    
    async def handle_call_end(self, linkedid: str):
        """Handle call end"""
        if linkedid in self.active_calls:
            call_info = self.active_calls[linkedid]
            call_uuid = call_info.get("uuid")
            
            if call_uuid:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"{self.trace_url}/api/calls/{call_uuid}/end",
                            json={
                                "end_time": datetime.utcnow().isoformat(),
                                "status": "completed"
                            }
                        )
                    logger.info(f"Ended tracking call {call_uuid}")
                except Exception as e:
                    logger.warning(f"Failed to end tracking call {call_uuid}: {e}")
            
            del self.active_calls[linkedid]
    
    def stop(self):
        """Stop the listener"""
        self.running = False

