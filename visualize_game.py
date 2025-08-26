#!/usr/bin/env python3
"""
Game visualization for CatanBench.

This script provides multiple ways to visualize Catan games:
1. Web-based interactive viewer using Catanatron's built-in UI
2. ASCII text representation
3. Game replay with step-by-step visualization
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_web_viewer(game_log_path: str):
    """Create a web-based game viewer using Catanatron's built-in UI."""
    try:
        from catanatron.game import Game
        from catanatron.models.player import RandomPlayer, Color
        import webbrowser
        import tempfile
        import os
        
        print("🌐 Starting web-based game viewer...")
        print("Note: This will open a browser window with an interactive Catan board")
        
        # Load the game log
        with open(game_log_path, 'r') as f:
            game_data = json.load(f)
        
        print(f"📊 Game: {game_data['game_id']}")
        print(f"🎮 Players: {', '.join([p['name'] for p in game_data['players']])}")
        print(f"🏆 Winner: {game_data.get('winner', 'Unknown')}")
        
        # Create a simple HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CatanBench Game Viewer - {game_data['game_id']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .game-info {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .player {{ margin: 10px 0; padding: 10px; border-left: 4px solid #007acc; }}
        .winner {{ border-left-color: #28a745; background: #f8fff8; }}
    </style>
</head>
<body>
    <h1>🏰 Catan Game Viewer</h1>
    
    <div class="game-info">
        <h2>Game: {game_data['game_id']}</h2>
        <p><strong>Winner:</strong> {game_data.get('winner', 'Unknown')}</p>
    </div>
    
    <h3>👥 Players</h3>
    {''.join([f'<div class="player {'winner' if p['color'] == game_data.get('winner') else ''}"><strong>{p['name']}</strong> ({p['color']})</div>' for p in game_data['players']])}
    
    <h3>📈 Game Actions</h3>
    <p>Total actions: {len(game_data.get('actions', []))}</p>
    
    <h3>🎯 Next Steps</h3>
    <p>For full interactive visualization:</p>
    <ol>
        <li>Install Catanatron with GUI: <code>pip install catanatron[gui]</code></li>
        <li>Run: <code>catanatron-play --gui</code></li>
        <li>Load this game file in the interface</li>
    </ol>
    
    <script>
        console.log('Game data:', {json.dumps(game_data, indent=2)});
    </script>
</body>
</html>
"""
        
        # Save to temp file and open
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = f.name
        
        webbrowser.open(f'file://{temp_path}')
        print(f"🌐 Game viewer opened in browser: {temp_path}")
        print("💡 Note: For full interactive Catan board, install: pip install catanatron[gui]")
        
    except ImportError as e:
        print(f"❌ Cannot create web viewer: {e}")
        print("💡 Try: pip install catanatron[gui]")
    except Exception as e:
        print(f"❌ Error creating web viewer: {e}")


def show_ascii_board(game_log_path: str):
    """Show ASCII representation of the final game state."""
    try:
        with open(game_log_path, 'r') as f:
            game_data = json.load(f)
        
        print("\n" + "="*60)
        print(f"🏰 CATAN GAME: {game_data['game_id']}")
        print("="*60)
        
        # Show players
        print("\n👥 PLAYERS:")
        for player in game_data['players']:
            winner_mark = " 🏆" if player['color'] == game_data.get('winner') else ""
            print(f"  • {player['name']} ({player['color']}){winner_mark}")
        
        # Show winner
        print(f"\n🏆 WINNER: {game_data.get('winner', 'Unknown')}")
        
        # Show action count
        action_count = len(game_data.get('actions', []))
        print(f"📊 TOTAL ACTIONS: {action_count}")
        
        # ASCII board representation
        print("\n🗺️  BOARD LAYOUT:")
        print("""
                    [ ]   [ ]   [ ]
                      |     |     |
              [ ]---[ ]---[ ]---[ ]---[ ]
                |     |     |     |     |
        [ ]---[ ]---[ ]---[ ]---[ ]---[ ]---[ ]
          |     |     |     |     |     |     |
        [ ]---[ ]---[ ]---[🎯]---[ ]---[ ]---[ ]
          |     |     |     |     |     |     |
        [ ]---[ ]---[ ]---[ ]---[ ]---[ ]---[ ]
                |     |     |     |     |
              [ ]---[ ]---[ ]---[ ]---[ ]
                      |     |     |
                    [ ]   [ ]   [ ]
        """)
        
        print("Legend: [ ] = Settlement spot, 🎯 = Robber")
        print("\n💡 For detailed visualization, use: python visualize_game.py --web <game_file>")
        
    except Exception as e:
        print(f"❌ Error showing ASCII board: {e}")


def replay_game(game_log_path: str, step_by_step: bool = False):
    """Replay the game actions step by step."""
    try:
        with open(game_log_path, 'r') as f:
            game_data = json.load(f)
        
        actions = game_data.get('actions', [])
        print(f"\n🎬 REPLAYING GAME: {game_data['game_id']}")
        print(f"📊 Total actions: {len(actions)}")
        
        if not actions:
            print("❌ No actions found in game log")
            return
        
        print("\n" + "-"*50)
        
        for i, action in enumerate(actions[:20]):  # Show first 20 actions
            if step_by_step:
                input(f"\nPress Enter for action {i+1}/{len(actions)}...")
            
            print(f"Action {i+1:3d}: {action}")
        
        if len(actions) > 20:
            print(f"\n... and {len(actions) - 20} more actions")
        
        print(f"\n🏆 Final result: {game_data.get('winner', 'Unknown')} won!")
        
    except Exception as e:
        print(f"❌ Error replaying game: {e}")


def list_available_games(results_dir: str = "tournament_results"):
    """List all available game logs."""
    results_path = Path(results_dir)
    
    print(f"📁 Searching for games in: {results_path.absolute()}")
    
    # Look for game logs
    game_logs = list(results_path.glob("game_logs/*.json"))
    
    if not game_logs:
        print("❌ No game logs found.")
        print("💡 Run a tournament first: python test_benchmark.py")
        return
    
    print(f"\n🎮 Found {len(game_logs)} game logs:")
    
    for i, log_path in enumerate(game_logs, 1):
        try:
            with open(log_path, 'r') as f:
                game_data = json.load(f)
            
            players = ', '.join([p['name'] for p in game_data.get('players', [])])
            winner = game_data.get('winner', 'Unknown')
            print(f"  {i:2d}. {log_path.name} - Players: {players} - Winner: {winner}")
            
        except Exception as e:
            print(f"  {i:2d}. {log_path.name} - Error reading: {e}")
    
    print(f"\n💡 To visualize a game: python visualize_game.py --web {game_logs[0]}")


def main():
    parser = argparse.ArgumentParser(description="Visualize CatanBench games")
    parser.add_argument("--web", type=str, help="Open web-based viewer for game log file")
    parser.add_argument("--ascii", type=str, help="Show ASCII representation of game")
    parser.add_argument("--replay", type=str, help="Replay game actions")
    parser.add_argument("--step", action="store_true", help="Step-by-step replay")
    parser.add_argument("--list", action="store_true", help="List available games")
    parser.add_argument("--dir", type=str, default="tournament_results", help="Results directory")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_games(args.dir)
    elif args.web:
        create_web_viewer(args.web)
    elif args.ascii:
        show_ascii_board(args.ascii)
    elif args.replay:
        replay_game(args.replay, args.step)
    else:
        print("🏰 CatanBench Game Visualizer")
        print("\nUsage options:")
        print("  --list                    List available games")
        print("  --web <game.json>         Open web viewer")
        print("  --ascii <game.json>       Show ASCII board")
        print("  --replay <game.json>      Replay actions")
        print("  --step                    Step-by-step replay")
        print("\nExamples:")
        print("  python visualize_game.py --list")
        print("  python visualize_game.py --web tournament_results/game_logs/game_M00_G00.json")
        print("  python visualize_game.py --ascii tournament_results/game_logs/game_M00_G00.json")


if __name__ == "__main__":
    main()