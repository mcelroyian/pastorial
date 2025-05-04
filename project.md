 # Pastorial
A simple resource chain simulator with autonomous agents that gather and process food resources. Agents move between berry bushes, wheat fields, and processing stations to create a production chain from raw materials to finished goods. Players can influence agent behavior by setting priorities.

 ### Core Features
 - Simulation environment with resource nodes
 - Autonomous agents with basic AI
 - Linear resource processing chain
 - Simple UI for resource tracking
 - Basic player controls for agent priorities

 ### Implementation Plan

 - Follow the vertical slices outlined previously
 - Start with minimal viable implementations
 - Focus on core game loop and agent behavior first

 ### Success Criteria

 - Agents autonomously gather and process resources
 - Complete production chain functions
 - Simulation runs without crashing for at least 5 minutes
 - Player can influence agent behavior

 ## Project Implementation Plan
  - Detailed plan found a ./breakdown.md

Setup PyGame with fixed timestep loop 
Create resource nodes and visualization

Berry bushes, wheat fields, water sources
Simple colored circles with resource counts

Implement basic agent behavior system 

Movement and state machine
Basic decision making for resource gathering

Create processing stations 

Mill (wheat → flour)
Bakery (flour + water → bread)

Implement player controls 

Priority settings
Direct commands


Add UI for resources and status
Testing and balancing