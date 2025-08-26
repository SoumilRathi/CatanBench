# LLM Catan Competition

This repository contains a competition system to evaluate different LLMs at playing Settlers of Catan and determine which model excels at grand strategy.

## Competition Setup

The competition features **4 premier LLM models**:
- **GPT-5** (OpenAI)
- **Claude Sonnet 4** (Anthropic)  
- **Gemini 2.5 Pro** (Google)
- **Kimi K2** (via OpenRouter)

## Game Rules & Configuration

- **Standard Catan Rules**: Full implementation via Catanatron library
- **Victory Condition**: First to 10 victory points OR 30 rounds (120 turns), whichever comes first
- **Tournament Structure**: 3 games per competition
- **Scoring System**: Multi-factor competence scoring based on:
  - Win rate (40%)
  - Average final position (30%)
  - Average victory points (30%)

## Quick Start

### 1. Setup Environment
```bash
# Create and activate virtual environment
python3 -m venv catanbench_env
source catanbench_env/bin/activate  # On Windows: catanbench_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
# Copy and edit environment file
cp .env.example .env
# Add your API keys for all 4 providers
```

Required API keys:
- `OPENAI_API_KEY` - For GPT-5
- `ANTHROPIC_API_KEY` - For Claude Sonnet 4  
- `GOOGLE_API_KEY` - For Gemini 2.5 Pro
- `OPENROUTER_API_KEY` - For Kimi K2 (via OpenRouter)

### 3. Run Competition Tournament
```bash
python competition_tournament.py
```

## Output & Results

The competition generates comprehensive results:

### 📊 Rankings
Models are ranked by **Competence Score** (0-1 scale):
```
1. Kimi K2
   Win Rate: 66.7% (2/3 wins)  
   ELO Rating: 1547
   Competence Score: 0.847

2. GPT-5
   Win Rate: 33.3% (1/3 wins)
   ELO Rating: 1502
   Competence Score: 0.623
   
[etc...]
```

### 📁 Files Generated
- `tournament_results/competition_summary_*.csv` - Detailed metrics
- `tournament_results/tournament.log` - Execution logs
- `tournament_results/tournament_results_*.json` - Complete game data

## Key Features

✅ **Standard Catan Mechanics**
- Settlement/city building, road construction
- Resource trading (maritime & player-to-player)  
- Development cards (Knights, Victory Points, etc.)
- Robber movement and resource theft
- Longest Road & Largest Army bonuses

✅ **Robust Tournament System** 
- Comprehensive error handling & retry logic
- Performance tracking & cost estimation
- ELO rating calculations
- Multi-factor competence scoring

✅ **Strategic AI Integration**
- Structured JSON game state for LLMs
- Expert-level Catan strategy prompts
- Detailed action descriptions & reasoning
- Fallback systems for API failures

## Understanding the Metrics

### Win Rate
Percentage of games won out of total games played

### ELO Rating  
Chess-style rating system updated based on head-to-head results

### Competence Score
Composite metric combining:
- **Win Rate** (40%): Direct success measure
- **Average Position** (30%): Consistency measure (1st=1.0, 4th=0.0)
- **Average Victory Points** (30%): Strategic effectiveness

## Architecture

```
Core Components:
├── models.py              # LLM client implementations
├── competition_tournament.py   # Main competition script  
├── core/
│   ├── llm_player.py     # LLM-Catan integration
│   ├── game_state.py     # State extraction for LLMs
│   └── action_parser.py  # Action descriptions
├── tournament/
│   └── manager.py        # Tournament orchestration
├── prompts/
│   ├── system_prompts.py # Catan strategy knowledge
│   └── action_templates.py # Decision-making templates
└── catanatron/           # Core Catan game engine
```

## Troubleshooting

### API Issues
- Ensure all API keys are valid and have sufficient credits
- Check API quotas and rate limits
- Verify network connectivity

### Game Issues  
- Turn limit prevents infinite games (30 rounds max)
- Fallback actions prevent crashes from LLM failures
- Comprehensive logging in `tournament.log`

### Performance
- Each game typically takes 20-50 minutes
- Full competition: 1-3hours depending on API speeds
- Results saved incrementally to prevent data loss

---

🎯 **Ready to discover which LLM reigns supreme at Catan?**

Run `python competition_tournament.py` and let the strategic battle begin!