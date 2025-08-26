#!/usr/bin/env python3
"""
Simple real-time tournament example using REST API polling instead of Socket.IO.

This example demonstrates the simplified approach to real-time viewing without
the complexity of WebSocket connections.
"""

import os
import sys
import time
import webbrowser
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tournament.simple_realtime_manager import SimpleRealtimeTournamentManager
from models import OpenAIClient, ClaudeClient, GeminiClient


def main():
    """Run a simple real-time tournament with polling."""
    
    print("🏰 Starting Simple CatanBench Real-time Tournament")
    print("=" * 60)
    
    # Check for API keys
    api_keys_available = {
        'OpenAI': os.getenv('OPENAI_API_KEY'),
        'Claude': os.getenv('ANTHROPIC_API_KEY'), 
        'Gemini': os.getenv('GEMINI_API_KEY')
    }
    
    print("🔑 API Key Status:")
    for service, key in api_keys_available.items():
        status = "✅ Available" if key else "❌ Missing"
        print(f"   {service}: {status}")
    
    if not any(api_keys_available.values()):
        print("\n⚠️ No API keys found. Please set at least one of:")
        print("   - OPENAI_API_KEY")
        print("   - ANTHROPIC_API_KEY")
        print("   - GEMINI_API_KEY")
        return
    
    # Initialize tournament manager
    tournament = SimpleRealtimeTournamentManager(
        name="Simple Real-time LLM Tournament",
        output_dir="tournament_results",
        log_level="INFO",
        web_port=8080
    )
    
    print(f"\n🌐 Web interface will be available at: http://localhost:8080")
    print("🎮 Visual game interface will be available at: http://localhost:3002")
    print("📄 Backend state logs will be saved to: tournament_results/backend_states.log")
    
    # Add available players
    players_added = 0
    
    if api_keys_available['OpenAI']:
        openai_client = OpenAIClient(
            model_name="gpt-4o-mini",
            api_key=api_keys_available['OpenAI']
        )
        tournament.add_player("GPT-4o-mini", openai_client)
        players_added += 1
        print(f"✅ Added player: GPT-4o-mini")
    
    if api_keys_available['Claude']:
        claude_client = ClaudeClient(
            model_name="claude-3-5-haiku-20241022",
            api_key=api_keys_available['Claude']
        )
        tournament.add_player("Claude-3.5-Haiku", claude_client)
        players_added += 1
        print(f"✅ Added player: Claude-3.5-Haiku")
    
    if api_keys_available['Gemini']:
        gemini_client = GeminiClient(
            model_name="gemini-1.5-flash",
            api_key=api_keys_available['Gemini']
        )
        tournament.add_player("Gemini-1.5-Flash", gemini_client)
        players_added += 1
        print(f"✅ Added player: Gemini-1.5-Flash")
    
    if players_added == 0:
        print("❌ No players could be added due to missing API keys")
        return
    
    print(f"\n🎮 Tournament setup complete with {players_added} LLM players")
    print("   Additional random players will be added to make 4 players per game")
    
    # Start Catanatron UI
    def start_catanatron_ui():
        try:
            import subprocess
            ui_path = project_root / "catanatron" / "ui"
            if ui_path.exists():
                print("\n🚀 Starting Catanatron visual UI...")
                subprocess.Popen(
                    ["npm", "run", "start"],
                    cwd=ui_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("✅ Catanatron UI starting on http://localhost:3002")
            else:
                print("⚠️ Catanatron UI not found - visual interface will not be available")
        except Exception as e:
            print(f"⚠️ Failed to start Catanatron UI: {e}")
            print("   You can start it manually with: cd catanatron/ui && npm run start")
    
    # Open browser after a short delay
    def open_browser_delayed():
        time.sleep(5)  # Give UI time to start
        try:
            webbrowser.open("http://localhost:8080")
            print("\n🌐 Opened tournament dashboard in your browser")
        except Exception as e:
            print(f"⚠️ Could not open browser automatically: {e}")
            print("   Please manually visit:")
            print("   - Tournament dashboard: http://localhost:8080")
            print("   - Visual games: http://localhost:3002")
    
    import threading
    
    # Start UI and open browsers
    start_catanatron_ui()
    threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    # Start tournament
    print("\n🚀 Starting tournament...")
    print("   - Web interface polling every 15 seconds")
    print("   - Backend states logged every 5 actions")
    print("   - No Socket.IO complexity!")
    print("\n" + "=" * 60)
    
    try:
        results = tournament.run_tournament(
            games_per_matchup=2,
            tournament_format="round_robin",
            save_games=True
        )
        
        print("\n🏆 Tournament completed successfully!")
        print(f"   Results saved to: {tournament.output_dir}")
        print(f"   Backend logs saved to: {tournament.output_dir}/backend_states.log")
        
        # Keep web server running for a bit to view final results
        print("\n🌐 Web server will stay running for 5 minutes to view results...")
        print("   Press Ctrl+C to stop early")
        
        try:
            time.sleep(300)  # 5 minutes
        except KeyboardInterrupt:
            print("\n👋 Stopping web server...")
        
        return results
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Tournament interrupted by user")
        return None
    except Exception as e:
        print(f"\n❌ Tournament failed: {e}")
        return None


if __name__ == "__main__":
    main()