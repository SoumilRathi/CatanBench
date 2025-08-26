#!/usr/bin/env python3
"""
Real-time tournament example with web GUI integration.

This example demonstrates how to run tournaments with real-time web viewing
capabilities, including integration with catanatron's web GUI for detailed
game visualization.
"""

import os
import sys
import time
import webbrowser
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tournament.realtime_manager import RealTimeTournamentManager
from models import OpenAIClient, ClaudeClient, GeminiClient


def main():
    """Run a real-time tournament with web GUI integration."""
    print("=== CatanBench Real-time Tournament with Web GUI ===\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check available API keys
    print("Checking API availability...")
    apis = {
        "OpenAI": os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"), 
        "Google": os.getenv("GOOGLE_API_KEY")
    }
    
    available_apis = []
    for name, key in apis.items():
        if key:
            available_apis.append(name)
            print(f"✓ {name} API key found")
        else:
            print(f"✗ {name} API key missing")
    
    if not available_apis:
        print("\nNo API keys found! Using mock players for demonstration.")
        print("For real LLM players, set up your .env file with API keys.")
    
    print(f"\nFound {len(available_apis)} API provider(s): {', '.join(available_apis)}")
    
    # Create real-time tournament manager
    tournament = RealTimeTournamentManager(
        name="Real-time LLM Catan Tournament",
        output_dir="tournament_results",
        web_port=8080,
        enable_websockets=True
    )
    
    print(f"\n🌐 Web interface will be available at: http://localhost:8080")
    print(f"🎮 Catanatron GUI will be available at: http://localhost:3000")
    
    # Add players based on available APIs
    players_added = 0
    
    if "OpenAI" in available_apis:
        try:
            gpt4_client = OpenAIClient("gpt-4o-mini")
            tournament.add_player("GPT-4o-mini", gpt4_client)
            players_added += 1
            print("✓ Added GPT-4o-mini player")
        except Exception as e:
            print(f"✗ Failed to add OpenAI player: {e}")
    
    if "Anthropic" in available_apis:
        try:
            claude_client = ClaudeClient("claude-3-5-haiku-20241022")
            tournament.add_player("Claude-3.5-Haiku", claude_client)
            players_added += 1
            print("✓ Added Claude-3.5-Haiku player")
        except Exception as e:
            print(f"✗ Failed to add Claude player: {e}")
    
    if "Google" in available_apis:
        try:
            gemini_client = GeminiClient("gemini-1.5-flash")
            tournament.add_player("Gemini-1.5-Flash", gemini_client)
            players_added += 1
            print("✓ Added Gemini-1.5-Flash player")
        except Exception as e:
            print(f"✗ Failed to add Gemini player: {e}")
    
    # Add mock players if no real APIs are available
    if players_added == 0:
        print("\n🤖 Adding mock players for demonstration...")
        
        class MockLLMClient:
            def __init__(self, name):
                self.model_name = name
                self.stats = {
                    "total_requests": 0, "successful_requests": 0, "failed_requests": 0,
                    "total_response_time": 0.0, "avg_response_time": 0.0,
                    "total_tokens_used": 0, "total_cost": 0.0
                }
            
            def query(self, prompt, **kwargs):
                import random
                import json
                import time
                time.sleep(0.2)  # Simulate thinking time
                return json.dumps({
                    "action_index": random.randint(0, 3),
                    "reasoning": f"Strategic decision by {self.model_name}"
                })
            
            def get_model_info(self):
                return {"provider": "Mock", "model": self.model_name}
        
        tournament.add_player("Strategic-AI", MockLLMClient("Strategic-AI"))
        tournament.add_player("Aggressive-Bot", MockLLMClient("Aggressive-Bot"))
        players_added = 2
        print("✓ Added 2 mock AI players")
    
    if players_added < 4:
        remaining = 4 - players_added
        print(f"\nNote: {remaining} random player(s) will be added to fill the game")
    
    print(f"\n🏗️  Starting tournament with {players_added} AI player(s)...")
    
    # Configure tournament settings
    games_per_matchup = 2  # Keep it small for demonstration
    print(f"⚙️  Configuration: {games_per_matchup} games per matchup")
    
    # Start the web interface automatically
    print("\n🚀 Starting web server...")
    
    # Confirm before running (auto-proceed in non-interactive environments)
    try:
        response = input(f"\nProceed with real-time tournament? (y/N): ")
        if response.lower() != 'y':
            print("Tournament cancelled.")
            return
    except EOFError:
        # Auto-proceed in non-interactive environments (like Docker)
        print("Running in non-interactive mode, proceeding automatically...")
    except KeyboardInterrupt:
        print("\nTournament cancelled by user.")
        return
    
    # Start the tournament with web interface
    try:
        print("\n🎮 Starting real-time tournament...")
        print("📱 Opening web interface in browser...")
        
        # Open the web interface in browser (only when running locally)
        import threading
        import sys
        
        def open_browser():
            time.sleep(3)  # Give server time to start
            # Only try to open browser if not running in Docker
            if not os.path.exists('/.dockerenv'):
                try:
                    webbrowser.open('http://localhost:8080')
                    print("🌐 Web interface opened in browser")
                    return
                except Exception as e:
                    print(f"Could not open browser automatically: {e}")
            
            print("Please open http://localhost:8080 in your browser")
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # Run the tournament
        results = tournament.run_tournament(
            games_per_matchup=games_per_matchup,
            tournament_format="round_robin",
            save_games=True,
            start_web_server=True
        )
        
        print("\n🎉 Tournament completed successfully!")
        
        # Display results
        print("\n=== TOURNAMENT RESULTS ===")
        info = results["tournament_info"]
        analysis = results["analysis"]
        
        print(f"Tournament: {info['name']}")
        print(f"Duration: {info['duration_seconds']:.1f} seconds")
        print(f"Total Games: {info['total_games']}")
        print(f"Success Rate: {analysis['success_rate']:.1%}")
        
        print("\n=== LEADERBOARD ===")
        leaderboard = tournament.get_leaderboard()
        for i, player in enumerate(leaderboard, 1):
            print(f"{i}. {player['player']} ({player.get('model', 'Unknown')})")
            print(f"   Wins: {player['wins']}/{player['games']} ({player['win_rate']:.1%})")
            if 'avg_decision_time' in player and player['avg_decision_time'] > 0:
                print(f"   Avg Decision Time: {player['avg_decision_time']:.2f}s")
        
        # Show cost information if available
        print("\n=== COST ANALYSIS ===")
        total_cost = 0.0
        for game in results["games"]:
            for player_name, perf in game.get("player_performance", {}).items():
                if perf and "total_cost" in perf and perf["total_cost"] > 0:
                    cost = perf["total_cost"]
                    total_cost += cost
                    print(f"{player_name}: ${cost:.4f}")
        
        if total_cost > 0:
            print(f"Total Estimated Cost: ${total_cost:.4f}")
        else:
            print("Cost information not available")
        
        # Show where results are saved and web interfaces
        print(f"\n📁 Detailed results saved in: tournament_results/")
        print("   - tournament_results_*.json (complete data)")
        print("   - tournament_summary_*.csv (game summary)")
        print("   - tournament.log (execution log)")
        print("   - game_logs/ (individual game data)")
        
        print(f"\n🌐 Web interfaces:")
        print(f"   - Tournament Dashboard: http://localhost:8080")
        print(f"   - Catanatron Game GUI: http://localhost:3000")
        print("\n💡 Keep the terminal open to continue viewing the web interface")
        print("   Press Ctrl+C to stop the server")
        
        # Keep the server running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏸️  Shutting down web server...")
        
    except KeyboardInterrupt:
        print("\n⏸️  Tournament interrupted by user")
    except Exception as e:
        print(f"\n❌ Tournament failed: {e}")
        import traceback
        traceback.print_exc()


def run_with_docker():
    """Instructions for running with Docker."""
    print("=== Docker Setup Instructions ===\n")
    
    print("To run the complete setup with Docker:")
    print("1. Make sure Docker is installed and running")
    print("2. Run: docker compose up")
    print("3. Wait for all services to start")
    print("4. Open http://localhost:8080 for tournament dashboard")
    print("5. Open http://localhost:3000 for catanatron game GUI")
    print("\nThis will start:")
    print("- Tournament web interface on port 8080")
    print("- Catanatron game visualization on port 3000") 
    print("- Traefik reverse proxy on port 80 (optional)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run real-time Catan tournament with web GUI")
    parser.add_argument("--docker-info", action="store_true", 
                       help="Show Docker setup instructions")
    
    args = parser.parse_args()
    
    if args.docker_info:
        run_with_docker()
    else:
        main() 