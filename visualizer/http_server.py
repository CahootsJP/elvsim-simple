#!/usr/bin/env python3
"""
HTTP Server for JSONL Log Streaming
Serves static files and provides API endpoints for log file access
"""
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import json
import os
from pathlib import Path

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Base directory for the project
BASE_DIR = Path(__file__).parent.parent


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_file(BASE_DIR / 'visualizer' / 'static' / 'index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory(BASE_DIR / 'visualizer' / 'static', path)


@app.route('/api/logs/list')
def list_logs():
    """List all available JSONL log files"""
    log_files = []
    for file in BASE_DIR.glob('*.jsonl'):
        stat = file.stat()
        log_files.append({
            'name': file.name,
            'size': stat.st_size,
            'modified': stat.st_mtime
        })
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify(log_files)


@app.route('/api/logs/<filename>')
def get_log_file(filename):
    """Get complete log file (for replay mode)"""
    file_path = BASE_DIR / filename
    
    if not file_path.exists() or not file_path.name.endswith('.jsonl'):
        return jsonify({'error': 'File not found'}), 404
    
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    return jsonify(events)


@app.route('/api/logs/stream')
def stream_log():
    """
    Stream log file from a specific line (for live mode)
    Query params:
        - file: filename (default: simulation_log.jsonl)
        - from: starting line number (default: 0)
    """
    filename = request.args.get('file', 'simulation_log.jsonl')
    from_line = int(request.args.get('from', 0))
    
    file_path = BASE_DIR / filename
    
    if not file_path.exists():
        return jsonify({'error': 'File not found', 'events': []}), 404
    
    events = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        # Get lines from 'from_line' onwards
        for i, line in enumerate(lines[from_line:], start=from_line):
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    # Add line number for client to track
                    event['_line_number'] = i
                    events.append(event)
                except json.JSONDecodeError:
                    continue
    
    return jsonify({
        'events': events,
        'total_lines': len(lines),
        'from_line': from_line,
        'returned_count': len(events)
    })


@app.route('/api/status')
def status():
    """Server status endpoint"""
    return jsonify({
        'status': 'ok',
        'server': 'Elevator Visualization HTTP Server',
        'version': '1.0'
    })


def run_server(host='localhost', port=5000, debug=False):
    """Run the Flask server"""
    print(f"Starting HTTP server on http://{host}:{port}")
    print(f"API endpoints:")
    print(f"  - GET  /api/logs/list")
    print(f"  - GET  /api/logs/<filename>")
    print(f"  - GET  /api/logs/stream?file=<filename>&from=<line>")
    print(f"  - GET  /api/status")
    
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    run_server(debug=True)

