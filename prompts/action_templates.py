"""
Action decision templates for LLM players.

This module provides structured templates that help LLMs make
strategic decisions in different game situations.
"""

def get_decision_template() -> str:
    """
    Get the main decision-making template.
    
    Returns:
        Template string for action decisions
    """
    return """
# DECISION ANALYSIS

Based on the current game state, analyze your situation:

## Current Position Assessment
- Your victory points: [analyze your VP from game state]
- Your resource situation: [assess your resources]
- Your building capabilities: [what can you build now?]
- Your strategic position: [are you leading, catching up, or behind?]

## Opponent Threat Analysis
- Who is closest to winning? [identify the leader]
- What are their likely next moves? [predict opponent actions]
- How can you disrupt their plans? [consider blocking moves]

## Action Evaluation
For each available action, consider:
1. **Immediate benefit**: What does this action accomplish right now?
2. **Long-term value**: How does this improve your position over time?
3. **Opportunity cost**: What other actions are you giving up?
4. **Risk/reward**: What are the potential downsides?

## Strategic Priorities
Based on the game phase and your position, determine:
- Primary objective: [what's your main goal this turn?]
- Secondary objectives: [what else would be valuable?]
- Risk mitigation: [what threats do you need to address?]

## Decision Reasoning
Explain your thought process:
- Why is this action optimal given the current state?
- How does this align with your overall strategy?
- What do you expect to happen as a result?

Choose the action that maximizes your winning probability while considering all factors above.
"""


def get_building_decision_template() -> str:
    """Template specifically for building decisions."""
    return """
# BUILDING DECISION ANALYSIS

## Settlement Placement Strategy
- Resource diversity: Will this provide new resource types?
- Production value: How often will this location produce resources?
- Expansion potential: Does this enable future city upgrades or road building?
- Blocking value: Does this prevent opponents from taking a good spot?

## City Upgrade Strategy  
- Resource amplification: Will this double production from a valuable tile?
- Investment return: Do you have enough turns left to benefit from doubled production?
- Resource cost: Can you afford the 3 Ore + 2 Wheat without hindering other plans?

## Road Building Strategy
- Longest Road potential: Does this contribute to achieving Longest Road?
- Settlement enabling: Does this road open up new settlement possibilities?
- Blocking purpose: Does this road prevent opponents from expanding?
- Connection value: Does this improve your network connectivity?
"""


def get_trading_decision_template() -> str:
    """Template for trading decisions.""" 
    return """
# TRADING DECISION ANALYSIS

## Resource Needs Assessment
- What resources do you need for your next key building?
- What resources do you have in excess?
- How many turns until you can use traded resources effectively?

## Trade Evaluation Framework
- Exchange ratio: Are you getting fair value? (consider scarcity)
- Opponent benefit: How much does this help your trading partner?
- Alternative options: Could you get these resources elsewhere?
- Timing: Is now the optimal time for this trade?

## Maritime vs. Player Trading
- Port availability: Do you have access to favorable port ratios?
- Player willingness: Are opponents open to beneficial trades?
- Competitive impact: Which option helps opponents less?

## Risk Considerations
- Card limit: Will trading prevent you from exceeding 7 cards?
- Future availability: Will these resources be available later?
- Opponent strategy: Does this trade enable opponent victories?
"""


def get_robber_decision_template() -> str:
    """Template for robber placement decisions."""
    return """
# ROBBER PLACEMENT ANALYSIS

## Target Tile Selection
- Production value: Which tiles produce resources most frequently?
- Player impact: Which placement affects the most opponents or the leader?
- Your benefit: Will this placement help your resource acquisition?
- Strategic timing: Is this the right moment to block this tile?

## Victim Selection (for stealing)
- Card count: Who has the most cards to steal from?
- Resource likelihood: Who probably has resources you need?
- Diplomatic cost: What are the relationship consequences?
- Retaliation risk: How likely is this player to target you back?

## Defensive Considerations
- Protect your tiles: Should you place the robber on your own tile?
- Opponent disruption: Which placement hurts opponents most?
- Future planning: How will this affect upcoming turns?
"""


def get_development_card_template() -> str:
    """Template for development card decisions."""
    return """
# DEVELOPMENT CARD ANALYSIS

## Purchase Decision
- Resource availability: Can you afford the Ore + Sheep + Wheat?
- Expected value: What's the likely benefit from a random development card?
- Alternative uses: What else could you do with these resources?
- Timing: Is this the right phase of the game for development cards?

## Playing Decision
- Card type benefits: What does each available card accomplish?
- Optimal timing: When should each card be played for maximum impact?
- Combination potential: Can you combine cards for powerful turns?
- Hidden information: Should you keep victory point cards secret?

## Largest Army Strategy
- Current knight count: How many knights do you and opponents have?
- Competition assessment: Is Largest Army achievable for you?
- Resource investment: Is pursuing Largest Army worth the resource cost?
"""


def get_endgame_template() -> str:
    """Template for endgame decisions (8+ VP)."""
    return """
# ENDGAME DECISION ANALYSIS

## Victory Path Assessment
- Current VP count: How many victory points do you have?
- Hidden VP: Do you have undisclosed victory point cards?
- Turns to victory: What's the fastest path to 10 VP?
- Opponent threats: Who else is close to winning?

## Critical Decision Points
- Immediate win: Can any action give you victory this turn?
- Victory prevention: Must you stop an opponent from winning?
- Resource efficiency: What's the most VP per resource spent?
- Risk tolerance: Should you play it safe or take calculated risks?

## Tactical Considerations
- Information warfare: What do opponents know about your VP count?
- Blocking priorities: Which opponent poses the greatest threat?
- Resource management: Can you afford to make suboptimal moves to block?
- Timing sensitivity: Do you have enough turns left to execute your plan?
"""


def get_few_shot_examples() -> str:
    """Get few-shot examples for different decision scenarios."""
    return """
# DECISION EXAMPLES

## Example 1: Early Game Building Decision
Game State: Turn 3, you have 3 VP, resources: 2 Wood, 1 Brick, 1 Sheep, 1 Wheat
Available Actions: [0] Build settlement at (1,0,-1), [1] Build road at edge 15, [2] End turn

Analysis: 
- Settlement gives immediate VP and new resource production
- Road enables future expansion but no immediate benefit  
- Ending turn wastes resources and tempo

Decision: {"action_index": 0, "reasoning": "Settlement provides immediate VP gain and establishes resource production on a good tile. Early game priority is expanding territory for resource diversity."}

## Example 2: Trading Decision
Game State: Turn 8, you have 6 VP, resources: 4 Ore, 1 Wood, 1 Brick
Available Actions: [0] Trade 4 Ore for 1 Wood (maritime), [1] Build city, [2] End turn

Analysis:
- Have excess ore but city costs 3 Ore + 2 Wheat (missing wheat)
- Maritime trade is inefficient (4:1) but gets needed resource
- City provides VP but can't build yet due to missing wheat

Decision: {"action_index": 2, "reasoning": "Without enough wheat for city, trading ore is premature. Better to end turn and seek wheat through dice rolls or better trades next turn."}

## Example 3: Endgame Blocking Decision  
Game State: Turn 15, you have 8 VP, opponent has 9 VP with resources for settlement
Available Actions: [0] Build road blocking opponent, [1] Buy development card, [2] Build city

Analysis:
- Opponent can win with settlement (10 VP total)
- Road blocks their winning move for 1 turn
- Development card might give hidden VP for immediate win
- City gives guaranteed 2 VP but opponent wins first

Decision: {"action_index": 0, "reasoning": "Must prevent opponent victory immediately. Blocking road buys time to find winning move next turn. Development card is too risky when opponent has guaranteed win."}
"""