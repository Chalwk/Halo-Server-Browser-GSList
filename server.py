#!/usr/bin/env python3
# Copyright (c) 2026 Jericho Crosby (Chalwk). Licensed under the GPL License.

import json
import subprocess
import os
import sys
import re
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Cache for server details to avoid repeated queries
server_cache = {}
cache_lock = threading.Lock()
CACHE_TTL = 60  # Cache TTL in seconds

class GSListHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/run':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                master = data.get('master', '34.197.71.170:28910')
                game = data.get('game', 'halom')
                key = data.get('key', 'halom e4Rd9J')
                qtype = data.get('qtype', '8')

                # Split key into two arguments for -Y
                key_parts = key.strip().split()
                if len(key_parts) < 2:
                    key_parts = [game, key]

                script_dir = os.path.dirname(os.path.abspath(__file__))
                gslist_exe = os.path.join(script_dir, 'gslist.exe')
                if not os.path.exists(gslist_exe):
                    gslist_exe = 'gslist.exe'

                cmd = [
                    gslist_exe,
                    '-x', master,
                    '-n', game,
                    '-Y', key_parts[0], key_parts[1],
                    '-Q', qtype,
                    '-q'
                ]

                print(f"Running: {' '.join(cmd)}", file=sys.stderr)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                stdout = result.stdout
                stderr = result.stderr

                has_server_data = stdout and ('\\' in stdout or any(':' in line and line.strip() for line in stdout.splitlines()))

                if has_server_data:
                    servers = self.parse_servers_with_players(stdout)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'output': stdout, 'servers': servers, 'error': ''}).encode())
                else:
                    error_msg = stderr if stderr else f"GSList exited with code {result.returncode}"
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'output': '', 'servers': [], 'error': error_msg}).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        elif self.path == '/api/server_details':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                ip_port = data.get('ip_port', '')

                cache_key = f"{ip_port}_old_status"
                with cache_lock:
                    if cache_key in server_cache:
                        cached_data, timestamp = server_cache[cache_key]
                        if time.time() - timestamp < CACHE_TTL:
                            print(f"Returning cached data for {ip_port}", file=sys.stderr)
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'details': cached_data}).encode())
                            return

                if ':' in ip_port:
                    host, port = ip_port.split(':', 1)
                else:
                    host, port = ip_port, '2302'

                script_dir = os.path.dirname(os.path.abspath(__file__))
                gslist_exe = os.path.join(script_dir, 'gslist.exe')
                if not os.path.exists(gslist_exe):
                    gslist_exe = 'gslist.exe'

                cmd = [gslist_exe, '-i', host, port, '-q']
                print(f"Running server details: {' '.join(cmd)}", file=sys.stderr)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                raw_output = result.stdout.strip()
                print(f"Raw output for {ip_port}:\n{raw_output}", file=sys.stderr)

                details = self.parse_server_details(raw_output)

                with cache_lock:
                    server_cache[cache_key] = (details, time.time())

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'details': details}).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def parse_servers_with_players(self, stdout):
        """Parse server list from master query (includes basic info, not full player list)"""
        servers = []
        for line in stdout.split('\n'):
            line = line.strip()
            if not line or ' ' not in line or '\\' not in line:
                continue
            first_space = line.find(' ')
            if first_space == -1:
                continue
            ip_port = line[:first_space].strip()
            rest = line[first_space+1:].strip()
            if not rest.startswith('\\'):
                continue
            rest = rest[1:]
            parts = rest.split('\\')
            data = {}
            for i in range(0, len(parts)-1, 2):
                data[parts[i].lower()] = parts[i+1]

            server = {
                'ipPort': ip_port,
                'ip': ip_port.split(':')[0],
                'port': ip_port.split(':')[1] if ':' in ip_port else '2302',
                'hostname': data.get('hostname', 'Unknown'),
                'mapname': data.get('mapname', 'unknown'),
                'gametype': data.get('gametype', '?'),
                'gamevariant': data.get('gamevariant', ''),
                'numplayers': int(data.get('numplayers', 0)),
                'maxplayers': int(data.get('maxplayers', 0)),
                'password': data.get('password') == '1',
                'ping': int(data.get('ping', 999)),
                'has_players': False,
                'player_count': 0
            }
            servers.append(server)
        return servers

    def parse_server_details(self, output):
        r"""Parse detailed server info including player names.
        Handles both backslash-delimited (\status\) and plain text key-value formats.
        """
        details = {'players': [], 'rules': {}, 'raw_output': output}
        if not output:
            return details

        # Format 1: backslash-delimited (e.g. \hostname\Server\player0\Alice\...)
        if output.startswith('\\'):
            parts = output.split('\\')
            data = {}
            for i in range(1, len(parts)-1, 2):
                key = parts[i].strip().lower()
                value = parts[i+1].strip()
                data[key] = value

            # Extract players (keys like player0, player_1, player)
            player_keys = []
            for k in data.keys():
                if k.startswith('player'):
                    match = re.search(r'player[_-]?(\d+)', k)
                    if match:
                        player_keys.append((int(match.group(1)), k))
                    elif k == 'player':
                        player_keys.append((0, k))
            player_keys.sort(key=lambda x: x[0])
            for _, key in player_keys:
                if data[key]:
                    details['players'].append(data[key])

            # Everything else -> rules??
            for key, value in data.items():
                if not key.startswith('player'):
                    details['rules'][key] = value
            return details

        # Format 2: plain text key-value (space-separated, like "hostname   MY COOL SERVER")
        lines = output.strip().split('\n')
        data = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Split on first whitespace only
            parts = line.split(None, 1)
            if len(parts) == 2:
                key, value = parts[0].lower(), parts[1].strip()
                data[key] = value

        if data:
            # Find player keys (player_0, player_1, etc.) – ignore player_flags, player_team etc.
            player_keys = []
            for k in data.keys():
                if re.match(r'^player_\d+$', k):
                    # extract number
                    num = int(k.split('_')[1])
                    player_keys.append((num, k))
                elif k == 'player':
                    player_keys.append((0, k))
            player_keys.sort(key=lambda x: x[0])
            for _, key in player_keys:
                if data[key]:
                    details['players'].append(data[key])

            # All other keys become rules
            for key, value in data.items():
                if not re.match(r'^player_\d+$', key) and key != 'player':
                    details['rules'][key] = value
            return details

        # Fallback to legacy parser (for very old or unusual formats)
        return self._parse_legacy_details(output)

    def _parse_legacy_details(self, output):
        """Fallback parser for non-backslash, non-space-separated formats."""
        details = {'players': [], 'rules': {}, 'raw_output': output}
        lines = output.split('\n')
        in_players = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'Players:' in line:
                in_players = True
                continue
            if 'Rules:' in line or 'Raw Response:' in line:
                in_players = False
                continue
            if in_players:
                if '\\' in line:
                    for p in line.split('\\'):
                        p = p.strip()
                        if p and not p.startswith('Players:'):
                            details['players'].append(p)
                elif line and not line.startswith('  '):
                    details['players'].append(line)
            else:
                if '=' in line:
                    k, v = line.split('=', 1)
                    details['rules'][k.strip()] = v.strip()
                elif ':' in line:
                    k, v = line.split(':', 1)
                    details['rules'][k.strip()] = v.strip()
        return details

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)

if __name__ == '__main__':
    port = 8000
    print(f"Halo CE Server Browser at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server = HTTPServer(('localhost', port), GSListHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")