# Halo-Server-Browser (using GSList)

A lightweight, server browser for **Halo: Custom Edition** (and other Halo titles) that uses Luigi Auriemma's `gslist` tool to query the master server.

## Features

- Fetch live server list from Halo: Beta, Halo: Trial, Halo: Trial (Mac), Halo: Mac, Halo: Combat Evolved (PC) Halo: Custom Edition
- Filter by server name, map, game type, password protection
- Sort by ping, player count, name, or map
- View current players on a server (detailed query)
- Display server rules / settings

## Installation

**Requirements:** Windows, Python 3.6+, and `gslist.exe`.

1. **Clone or download** this repository.
2. **Download `gslist.exe`** from Luigi Auriemma's website:  
   [https://aluigi.altervista.org/papers.htm#gslist](https://aluigi.altervista.org/papers.htm#gslist)  
   (look for `Gslist 0.8.11a` - clicking this will download `gslist.zip` - extract it.
3. **Place `gslist.exe`** in the same folder as `server.py` (or somewhere in your `PATH`).
4. **Run the Python server**:

```bash
python server.py
```

5. **Open your browser** and go to [http://localhost:8000](http://localhost:8000).

That's it! The server will show the Halo server browser interface.

## Usage

### Main view

- Click **Refresh Servers** to fetch the latest server list from the master server (takes a few seconds).
- Use the **filters** (name, map, game type, password) to narrow down the list.
- **Sort** by clicking the table headers or using the sort dropdown.

### Player & rule details

- Click **Players** on any server row to see the current player names.
- Click **Rules** to see the server's custom settings (gametype, version, etc.).

### Changing the game / master server

The tool is pre-configured for **Halo Custom Edition** (`halom`). You can modify:

- **Master server** (`-x`): e.g., `34.197.71.170:28910` (default Gamespy replacement)
- **Game preset** - choose Halo PC, Halo Demo, Halo CE, etc.
- **Game name** (`-n`) and **Game key** (`-Y`) - the values are automatically updated when you select a preset.

> **Note**: The default settings work out of the box for Halo Custom Edition. Only change them if you know what you are doing.

## How it works (for developers).

1. The Python HTTP server (`server.py`) receives requests from the web page.
2. On a **refresh**, it runs `gslist.exe -x <master> -n <game> -Y <key> -Q 8 -q` to fetch the server list from the master server.
3. The list is parsed and displayed in the browser.
4. When you click **Players** or **Rules**, the server runs `gslist.exe -i <ip> <port> -q` to retrieve detailed information from that specific server.
5. Details are cached for 60 seconds to avoid excessive queries.

## Troubleshooting

### `gslist.exe not found`

- Make sure `gslist.exe` is in the same folder as `server.py`, or add its directory to your system `PATH`.
- Verify the filename - it must be exactly `gslist.exe`.

### No servers appear / "No output from GSList"

- Check that the master server address is correct and reachable.
- Try a different game preset (e.g., "Halo Custom Edition").
- Run `gslist.exe` manually from a command prompt to see if it works:  
  `gslist.exe -x 34.197.71.170:28910 -n halom -Y "halom e4Rd9J" -Q 8 -q`

### Timeouts or slow refresh

- The default timeout is 30 seconds for the master query and 15 seconds for server details.
- If you have many servers, the first refresh may take a few seconds - subsequent refreshes are faster due to caching.

### Firewall / antivirus

- Some security software may flag `gslist.exe` because it sends UDP packets. It is safe - it's a well-known open-source tool used for game server queries. You may need to allow it.

## Credits

- **Luigi Auriemma** - author of [gslist](https://aluigi.altervista.org/papers.htm#gslist)
- **Jericho Crosby (Chalwk)** - Python HTTP wrapper and web front-end

## [License](LICENSE)

This project is released under the same license as `gslist` (GPL).

---
