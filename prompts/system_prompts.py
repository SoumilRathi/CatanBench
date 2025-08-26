"""
System prompts containing Catan rules and strategic knowledge.

This module provides comprehensive Catan knowledge that LLMs can use
to make informed strategic decisions.
"""


def get_system_prompt() -> str:
    """
    Get the main system prompt with Catan rules and strategy knowledge.
    
    Returns:
        Comprehensive system prompt string
    """
    return """You are an expert Settlers of Catan player participating in a competitive game. You have deep knowledge of Catan strategy and must make optimal decisions to win the game.

# CATAN RULES SUMMARY

## OBJECTIVE
- Be the first player to reach 10 victory points
- Victory points come from settlements (1 VP), cities (2 VP), development cards (some worth 1 VP), longest road (2 VP), and largest army (2 VP)

## BASIC GAMEPLAY
- Each turn: Roll dice → Collect resources → Take actions → End turn
- Resources: Wood, Brick, Sheep, Wheat, Ore (produced by tiles when dice match their numbers)
- Build settlements on intersections, roads on edges, upgrade settlements to cities
- Trade resources with other players or maritime ports
- Buy development cards for special abilities and victory points

## BUILDING COSTS
- Road: 1 Wood + 1 Brick
- Settlement: 1 Wood + 1 Brick + 1 Sheep + 1 Wheat
- City: 3 Ore + 2 Wheat (upgrades existing settlement)
- Development Card: 1 Ore + 1 Sheep + 1 Wheat

## STRATEGIC PRINCIPLES

- Secure good resource production 
- Focus on numbers that roll frequently (6, 8, 5, 9, 4, 10)
- Upgrade settlements to cities for double resource production
- Start buying development cards for VP and special abilities
- Consider blocking opponents from valuable spots
- Develop longest road and/or largest army if achievable

## TRADING STRATEGY
- Trade away excess resources to prevent loss on 7s
- Maritime trading (4:1 or port advantages) when player trading unavailable

## ROBBER TACTICS
- Place robber on high-production tiles of leading players
- Target players with many cards when robber moves
- Consider diplomatic implications of robber placement
- Use robber to protect your own high-production tiles

## DEVELOPMENT CARDS
- Knights: Move robber and count toward largest army (3+ knights needed)
- Progress cards: Year of Plenty (2 resources), Road Building (2 roads), Monopoly (all of one resource)
- Victory Point cards: Keep hidden until you can win

## RISK MANAGEMENT
- Avoid holding 8+ cards to prevent discarding on 7s
- Diversify resource production across different numbers
- Don't overcommit to one strategy - stay flexible
- Watch opponent victory point progress carefully

# DECISION-MAKING FRAMEWORK

When choosing an action, consider:
1. **Immediate VP gain**: Does this action directly provide victory points?
2. **Resource efficiency**: What's the long-term resource production benefit?
3. **Opponent disruption**: Does this prevent opponents from winning?
4. **Future opportunities**: Does this enable better moves later?
5. **Risk mitigation**: Does this protect against opponent advantages?

Always choose the action that maximizes your winning probability while considering opponent responses."""


def get_trading_strategy_prompt() -> str:
    """Get specific prompts for trading decisions."""
    return """
# TRADING DECISION FRAMEWORK

## When to Trade
- You have excess resources that aren't immediately needed
- You need specific resources for high-value builds (city, settlement)
- Risk of losing cards to robber (holding 8+ cards)
- Opponent offers beneficial exchange ratio

## Trading Evaluation
- Calculate value: What do you gain vs. what you give up?
- Consider opponent benefit: Are you helping them more than yourself?
- Timing: Is this the right moment or should you wait?
- Alternative options: Maritime trade vs. player trade vs. waiting

## Maritime Trading
- 4:1 general ports: Trade 4 of same resource for 1 of any other
- 3:1 specific ports: Trade 3 of specific resource for 1 of any other  
- 2:1 resource ports: Trade 2 of specific resource for 1 of any other
- Use when player trading is unavailable or unfavorable
"""


def get_robber_strategy_prompt() -> str:
    """Get specific prompts for robber placement decisions."""
    return """
# ROBBER PLACEMENT STRATEGY

## Target Selection Priority
1. **Leading players**: Focus on whoever is closest to 10 VP
2. **High production tiles**: Target 6s and 8s, then 5s and 9s
3. **Multiple settlements**: Tiles that affect multiple opponent buildings
4. **Resource bottlenecks**: Block resources opponents need most

## Victim Selection
- Players with most cards in hand
- Players who just gained resources from the tile
- Avoid players who might retaliate against you
- Consider diplomatic consequences

## Defensive Robber Use
- Use to protect key resources during crucial building phases
- Block tiles that would help opponents complete high-VP builds
"""

def game_state_to_prompt(game_state):
    """Convert game state dictionary to readable prompt format."""
    
    # Extract key information
    turn_num = game_state.get("turn_number", 0)
    board = game_state.get("board_state", {})
    current_player = game_state.get("current_player", {})
    opponents = game_state.get("opponents", [])
    
    # Build the readable game state
    prompt_parts = []
    
    # Turn information
    prompt_parts.append(f"Turn: {turn_num}")
    
    # Current player info
    prompt_parts.append(f"\n=== YOUR STATUS ({current_player.get('color', 'UNKNOWN')}) ===")
    prompt_parts.append(f"Victory Points: {current_player.get('victory_points', 0)}")
    prompt_parts.append(f"Resource Cards: {current_player.get('resource_cards_count', 0)}")
    prompt_parts.append(f"Development Cards: {current_player.get('development_cards_count', 0)}")
    
    # Resources (if available)
    if 'resources' in current_player:
        resources = current_player['resources']
        resource_str = ", ".join([f"{res}: {count}" for res, count in resources.items() if count > 0])
        if resource_str:
            prompt_parts.append(f"Resources: {resource_str}")
    
    # Development cards in hand (if available)  
    if 'development_cards_in_hand' in current_player:
        dev_cards = current_player['development_cards_in_hand']
        dev_card_str = ", ".join([f"{card}: {count}" for card, count in dev_cards.items() if count > 0])
        if dev_card_str:
            prompt_parts.append(f"Development Cards: {dev_card_str}")
    
    # Buildings
    buildings = current_player.get('buildings', {})
    prompt_parts.append(f"Buildings: {len(buildings.get('settlements', []))} settlements, {len(buildings.get('cities', []))} cities, {len(buildings.get('roads', []))} roads")
    
    # Opponents
    prompt_parts.append(f"\n=== OPPONENTS ===")
    for opp in opponents:
        opp_color = opp.get('color', 'UNKNOWN')
        opp_vp = opp.get('public_victory_points', 0)
        opp_resources = opp.get('resource_cards_count', 0)
        opp_dev_cards = opp.get('development_cards_count', 0)
        opp_buildings = opp.get('buildings', {})
        opp_settlements = len(opp_buildings.get('settlements', []))
        opp_cities = len(opp_buildings.get('cities', []))
        opp_roads = len(opp_buildings.get('roads', []))
        
        prompt_parts.append(f"{opp_color}: {opp_vp} VP, {opp_resources} resources, {opp_dev_cards} dev cards, {opp_settlements}S/{opp_cities}C/{opp_roads}R")
    
    # Board state - Tiles with axial coordinates
    tiles = board.get('tiles', [])
    if tiles:
        prompt_parts.append(f"\n=== BOARD TILES (AXIAL COORDINATES) ===")
        for tile in tiles:
            tile_name = tile.get('name', 'Unknown')
            axial_coord = tile.get('axial_coord', '')
            resource = tile.get('resource', 'Desert')
            number = tile.get('number', '')
            robber = ' (ROBBER)' if tile.get('has_robber') else ''
            neighbors = tile.get('neighbors', [])
            
            # Main tile info
            if resource and number:
                line = f"{tile_name} {axial_coord}: {resource} {number}{robber}"
            else:
                line = f"{tile_name} {axial_coord}: {resource}{robber}"
            
            # Add neighbor info (first 3 neighbors to keep it readable)
            if neighbors:
                neighbor_str = ", ".join(neighbors[:3])
                if len(neighbors) > 3:
                    neighbor_str += f"... (+{len(neighbors)-3} more)"
                line += f" [Adjacent: {neighbor_str}]"
            
            prompt_parts.append(line)
    
    # Intersections (settlement/city spots)
    intersections = board.get('intersections', [])
    if intersections:
        prompt_parts.append(f"\n=== INTERSECTIONS (Settlement/City Spots) ===")
        for intersection in intersections[:10]:  # Limit to first 10 for readability
            description = intersection.get('description', intersection.get('id', 'Unknown'))
            prompt_parts.append(description)
        if len(intersections) > 10:
            prompt_parts.append(f"... and {len(intersections)-10} more intersections")
    
    # Edges (road spots) 
    edges = board.get('edges', [])
    if edges:
        prompt_parts.append(f"\n=== EDGES (Road Spots) ===")
        for edge in edges[:10]:  # Limit to first 10 for readability
            description = edge.get('description', edge.get('id', 'Unknown'))
            prompt_parts.append(description)
        if len(edges) > 10:
            prompt_parts.append(f"... and {len(edges)-10} more edges")
    
    # Ports
    ports = board.get('ports', [])
    if ports:
        prompt_parts.append(f"\n=== PORTS ===")
        for i, port in enumerate(ports):
            description = port.get('description', 'Unknown Port')
            node_ids = port.get('node_ids', [])
            
            port_line = f"Port {i+1}: {description}"
            if node_ids:
                # Show node IDs so LLMs can correlate with action indices
                node_str = ", ".join([f"node {nid}" for nid in node_ids[:2]])
                port_line += f" (build at actions {', '.join([str(nid) for nid in node_ids[:2]])})"
            
            prompt_parts.append(port_line)
    
    # Special achievements
    longest_road = board.get('longest_road_owner')
    largest_army = board.get('largest_army_owner')
    if longest_road or largest_army:
        prompt_parts.append(f"\n=== ACHIEVEMENTS ===")
        if longest_road:
            prompt_parts.append(f"Longest Road: {longest_road}")
        if largest_army:
            prompt_parts.append(f"Largest Army: {largest_army}")
    
    return "\n".join(prompt_parts)

def get_development_card_strategy_prompt() -> str:
    """Get specific prompts for development card decisions.""" 
    return """
# DEVELOPMENT CARD STRATEGY

## When to Buy Development Cards
- Late game when VP cards provide direct path to victory
- When you have excess Ore/Sheep/Wheat production
- Building toward Largest Army (need 3+ Knight cards)
- When building spots are limited or blocked

## Playing Development Cards

### Knight Cards
- Move robber to disrupt leading opponent
- Build toward Largest Army (worth 2 VP)
- Timing: Play when robber placement is most valuable

### Year of Plenty
- Gain exactly the resources needed for key builds
- Use when specific resources are hard to obtain through trading
- Emergency resource acquisition before opponents' turns

### Road Building
- Complete Longest Road for 2 VP
- Secure crucial settlement locations
- Block opponent expansion routes

### Monopoly
- Target resources that opponents have accumulated
- Use when you know opponents have many of a specific resource
- Combine with other actions for powerful turns

## Victory Point Cards
- Keep hidden until you can reach 10 VP
- Count carefully - don't reveal early
- Consider as insurance against being blocked from building VP
"""