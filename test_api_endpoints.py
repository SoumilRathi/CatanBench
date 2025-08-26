#!/usr/bin/env python3
"""
Test script to verify API endpoints work correctly.
"""

import requests
import json
import time

def test_endpoints():
    """Test the tournament API endpoints."""
    
    base_url = "http://localhost:8080"
    
    print("🧪 Testing CatanBench API endpoints...")
    print("=" * 50)
    
    # Test 1: Tournament status
    try:
        response = requests.get(f"{base_url}/api/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status endpoint: {data['status']}")
            print(f"   Games: {data['current_games']}")
        else:
            print(f"❌ Status endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
    
    # Test 2: Games list
    try:
        response = requests.get(f"{base_url}/api/games")
        if response.status_code == 200:
            data = response.json()
            games = data.get('games', {})
            print(f"✅ Games endpoint: {len(games)} games")
            for game_id, game_data in games.items():
                print(f"   - {game_id}: {game_data['status']}")
                
                # Test 3: Individual game state
                try:
                    state_response = requests.get(f"{base_url}/api/games/{game_id}/states/latest")
                    if state_response.status_code == 200:
                        state_data = state_response.json()
                        print(f"   ✅ Game {game_id} state available")
                        
                        # Check for required fields
                        required_fields = ['game_id', 'players', 'tiles', 'nodes', 'edges']
                        missing_fields = [field for field in required_fields if field not in state_data]
                        if missing_fields:
                            print(f"   ⚠️  Missing fields: {missing_fields}")
                        else:
                            print(f"   ✅ All required fields present")
                            print(f"   - Players: {len(state_data.get('players', []))}")
                            print(f"   - Tiles: {len(state_data.get('tiles', []))}")
                            print(f"   - Nodes: {len(state_data.get('nodes', {}))}")
                            print(f"   - Edges: {len(state_data.get('edges', {}))}")
                    else:
                        error_data = state_response.json() if state_response.headers.get('content-type', '').startswith('application/json') else state_response.text
                        print(f"   ❌ Game {game_id} state failed: {state_response.status_code}")
                        print(f"      Error: {error_data}")
                except Exception as e:
                    print(f"   ❌ Game {game_id} state error: {e}")
        else:
            print(f"❌ Games endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Games endpoint error: {e}")
    
    # Test 4: Catanatron UI compatibility
    print("\n🎮 Testing Catanatron UI compatibility...")
    try:
        # Test game creation endpoint
        response = requests.post(f"{base_url}/api/games")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Game creation endpoint: {data.get('game_id', 'Unknown')}")
        else:
            print(f"❌ Game creation endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Game creation endpoint error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 API test complete!")


if __name__ == "__main__":
    test_endpoints()