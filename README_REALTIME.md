doc# CatanBench Real-time Tournament System

A real-time web interface for viewing Catan tournaments with live game streaming and integration with Catanatron's web GUI.

## Features

🎮 **Real-time Tournament Viewing**: Watch tournaments as they happen with live updates  
🌐 **Web Dashboard**: Beautiful web interface showing game progress and leaderboards  
🔄 **WebSocket Updates**: Real-time game state broadcasting to connected viewers  
🏆 **Live Leaderboard**: See player standings update in real-time  
🎯 **Catanatron Integration**: Direct integration with Catanatron's web GUI for detailed game visualization  
📊 **Tournament Analytics**: Live statistics and performance metrics  

## Quick Start

### Option 1: Python (Local Development)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Environment** (optional for LLM players):
   ```bash
   cp .env.example .env
   # Add your API keys to .env
   ```

3. **Run Real-time Tournament**:
   ```bash
   python examples/realtime_tournament.py
   ```

4. **Open Web Interface**:
   - Tournament Dashboard: http://localhost:8080
   - Catanatron Game GUI: http://localhost:3000 (if running separately)

### Option 2: Docker (Complete Setup)

1. **Start All Services**:
   ```bash
   docker compose up
   ```

2. **Access Interfaces**:
   - Tournament Dashboard: http://localhost:8080
   - Catanatron Game GUI: http://localhost:3000
   - Traefik Dashboard: http://localhost:8081

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Browser                              │
│  ┌─────────────────────┐  ┌─────────────────────────────────┤
│  │ Tournament Dashboard│  │ Catanatron Game Visualization  │
│  │ (localhost:8080)    │  │ (localhost:3000)                │
│  └─────────────────────┘  └─────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket Connection
                              │
┌─────────────────────────────────────────────────────────────┐
│              RealTimeTournamentManager                      │
│  ┌─────────────────────────────────────────────────────────┤
│  │ • Tournament Orchestration                              │
│  │ • Game State Broadcasting                               │
│  │ • WebSocket Server                                      │
│  │ • REST API Endpoints                                    │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Game Execution
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Catanatron Engine                          │
│  ┌─────────────────────────────────────────────────────────┤
│  │ • Game Logic                                            │
│  │ • LLM Players                                           │
│  │ • Game State Management                                 │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
```

## Web Interface Features

### Tournament Dashboard (localhost:8080)

- **Real-time Status**: See tournament progress (not started, running, completed, failed)
- **Live Game Cards**: View all currently running games with player information
- **Dynamic Leaderboard**: Rankings update automatically as games complete
- **Connection Status**: See how many viewers are connected
- **Catanatron Integration**: Direct link to open detailed game visualization

### Catanatron Game GUI (localhost:3000)

- **Interactive Board**: Visual representation of the Catan board
- **Game State Details**: Resources, buildings, development cards
- **Action History**: Complete log of all game actions
- **Player Information**: Detailed stats for each player

## API Endpoints

The real-time tournament system provides several REST API endpoints:

- `GET /` - Main tournament dashboard
- `GET /api/tournament/status` - Tournament status and info
- `GET /api/tournament/games` - Current games data
- `GET /api/tournament/leaderboard` - Live leaderboard

## WebSocket Events

### Client Events (sent to server)
- `join_game(data)` - Join specific game view
- `leave_game(data)` - Leave game view

### Server Events (sent to clients)
- `tournament_status(data)` - Tournament status updates
- `game_update(data)` - Game state changes
- `game_state(data)` - Complete game state

## Configuration

### Environment Variables

```bash
# LLM API Keys (optional)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Web Server Configuration
TOURNAMENT_WEB_PORT=8080
CATANATRON_GUI_URL=http://localhost:3000
```

### Tournament Settings

```python
tournament = RealTimeTournamentManager(
    name="My Tournament",
    output_dir="tournament_results",
    web_port=8080,
    enable_websockets=True
)
```

## Usage Examples

### Basic Real-time Tournament

```python
from tournament.realtime_manager import RealTimeTournamentManager

# Create tournament manager
tournament = RealTimeTournamentManager()

# Add players (supports any LLM client)
tournament.add_player("GPT-4", openai_client)
tournament.add_player("Claude", claude_client)

# Run tournament with web interface
results = tournament.run_tournament(
    games_per_matchup=3,
    start_web_server=True
)
```

### Custom Web Configuration

```python
tournament = RealTimeTournamentManager(
    name="Custom Tournament",
    web_port=9000,
    enable_websockets=True
)

# Start web server manually
tournament.start_web_server()

# Run tournament
tournament.run_tournament(save_games=True)
```

### Mock Players for Testing

```python
class MockLLMClient:
    def __init__(self, name):
        self.model_name = name
    
    def query(self, prompt, **kwargs):
        import random, json
        return json.dumps({
            "action_index": random.randint(0, 3),
            "reasoning": f"Decision by {self.model_name}"
        })

tournament.add_player("TestBot", MockLLMClient("TestBot"))
```

## File Structure

```
tournament/
├── realtime_manager.py     # Real-time tournament manager
└── manager.py             # Base tournament manager

examples/
├── realtime_tournament.py  # Real-time tournament example
└── simple_tournament.py   # Basic tournament example

docker-compose.yml          # Docker services configuration
Dockerfile.dev             # Development container
requirements.txt           # Python dependencies (updated)
README_REALTIME.md         # This file
```

## Docker Services

The `docker-compose.yml` defines three services:

1. **catanatron-web**: Official Catanatron web GUI
2. **catanbench-dev**: CatanBench tournament system
3. **traefik**: Reverse proxy (optional)

## Troubleshooting

### Common Issues

**Port already in use**: Change the port in the configuration
```python
tournament = RealTimeTournamentManager(web_port=9000)
```

**WebSocket connection failed**: Ensure the server is running and ports are accessible

**Catanatron GUI not loading**: Make sure Docker is running and the catanatron-web service is healthy

**No LLM players**: Add API keys to `.env` file or use mock players for testing

### Debugging

Enable debug logging:
```python
tournament = RealTimeTournamentManager(log_level="DEBUG")
```

Check server logs:
```bash
docker compose logs catanbench-dev
```

### Performance Tips

- **Reduce games per matchup** for faster tournaments
- **Disable WebSockets** if not using real-time viewing: `enable_websockets=False`
- **Use mock players** for testing without API costs

## Advanced Usage

### Custom Game State Broadcasting

```python
class CustomTournament(RealTimeTournamentManager):
    async def _broadcast_custom_event(self, data):
        await self.sio.emit('custom_event', data)
```

### Multiple Tournament Instances

Run multiple tournaments on different ports:
```python
tournament1 = RealTimeTournamentManager(web_port=8080)
tournament2 = RealTimeTournamentManager(web_port=8081)
```

### Integration with Other Systems

The REST API allows integration with external monitoring systems:
```bash
curl http://localhost:8080/api/tournament/status
curl http://localhost:8080/api/tournament/leaderboard
```

## Contributing

To add features to the real-time system:

1. Extend `RealTimeTournamentManager`
2. Add new WebSocket events in `_setup_socket_events()`
3. Update the HTML template in `_generate_tournament_html()`
4. Add corresponding JavaScript handlers

## License

Same license as the main CatanBench project. 