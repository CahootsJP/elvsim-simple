#!/usr/bin/env python3
"""
WebSocket Server for Elevator Visualization
Bridges between Statistics data and browser frontend
"""
import asyncio
import websockets
import json
from pathlib import Path
import queue
import threading


class VisualizerServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.message_queue = queue.Queue()  # Thread-safe queue for cross-thread communication
        self.async_queue = None  # Will be created in async context
        
    async def register(self, websocket):
        """Register a new client connection"""
        self.clients.add(websocket)
        print(f"Client connected. Total clients: {len(self.clients)}")
        
    async def unregister(self, websocket):
        """Unregister a client connection"""
        self.clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(self.clients)}")
        
    async def send_to_client(self, websocket, message):
        """Send message to a specific client"""
        try:
            await websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            await self.unregister(websocket)
            
    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        if self.clients:
            disconnected = set()
            for client in self.clients:
                try:
                    await client.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            
            # Clean up disconnected clients
            for client in disconnected:
                await self.unregister(client)
                
    async def handle_client(self, websocket):
        """Handle individual client connection"""
        await self.register(websocket)
        try:
            async for message in websocket:
                # Handle incoming messages from client (if needed)
                data = json.loads(message)
                print(f"Received from client: {data}")
                
                # Example: echo back or handle commands
                if data.get('type') == 'ping':
                    await self.send_to_client(websocket, {'type': 'pong'})
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
            
    async def message_sender(self):
        """Continuously send queued messages to all clients"""
        while True:
            # Check thread-safe queue and transfer to async queue
            try:
                # Non-blocking check of thread-safe queue
                message = self.message_queue.get_nowait()
                await self.broadcast(message)
            except queue.Empty:
                # No messages, wait a bit before checking again
                await asyncio.sleep(0.01)  # 10ms polling interval
            
    def queue_message(self, message):
        """Queue a message to be sent (thread-safe from Statistics)"""
        self.message_queue.put(message)
        
    async def start(self):
        """Start the WebSocket server"""
        print(f"Starting WebSocket server on ws://{self.host}:{self.port}")
        
        # Start message sender task
        asyncio.create_task(self.message_sender())
        
        # Start WebSocket server
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever


# Standalone server for testing
async def main():
    server = VisualizerServer(host='localhost', port=8765)
    await server.start()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")

