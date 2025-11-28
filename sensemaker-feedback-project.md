# SenseMaker-Inspired Feedback Application

## Project Overview

### What We're Building

A feedback collection and analysis system inspired by Dave Snowden's SenseMaker methodology from Cognitive Edge. The application allows users to share narrative stories about their experiences with systems, products, or processes, and place those stories on triangular signifiers (triads) with positive descriptors. The system then uses LLM-powered analysis and graph database technology to discover emergent patterns and insights that weren't predetermined by the designers.

Unlike traditional feedback mechanisms (surveys, ticket systems, Likert scales), this approach:
- Avoids framing bias by letting users tell stories in their own words
- Uses signification rather than categorization (users place stories on continuums, not in boxes)
- Discovers patterns through analysis rather than imposing predetermined categories
- Reveals weak signals and hidden connections across narratives

### Why We're Building This

**Primary Use Case**: Product development and internal tooling feedback, where understanding nuanced user experience is critical but traditional surveys fail to capture the full picture.

**Key Benefits**:
- Captures complexity and nuance that structured surveys miss
- Reveals patterns and correlations humans might not notice
- Scales organizational sensemaking
- Provides actionable insights from narrative data
- Enables continuous feedback without survey fatigue

**Strategic Value**: Demonstrates senior-level technical capability through novel application of LLM technology, graph databases, and organizational intelligence systems.

## Architecture

### High-Level Architecture

```
                    CAPTURE LAYER
┌─────────────────────────────────────────┐
│           Web Frontend                  │
│  (Story capture + triad placement)      │
└────────────────┬────────────────────────┘
                 │ HTTP/REST
┌────────────────▼────────────────────────┐
│           API Layer (FastAPI)           │
│     (Capture, Query, Analysis)          │
└────┬─────────────────────────────┬──────┘
     │                             │
     │                             │
                 STORAGE LAYER
     │                             │
┌────▼─────────────────┐   ┌───────▼──────────────┐
│      MongoDB         │   │   Insight Cache      │
│ (Raw stories)        │   │ (Redis/Postgres)     │
└────┬─────────────────┘   │ (Precomputed         │
     │                     │  patterns)           │
     │                     └──────────────────────┘
     │ Event trigger
     │
                PROCESSING LAYER
     │
┌────▼──────────────────────────────────────┐
│        Processing Pipeline                │
│         (Async workers)                   │
└────┬──────────────────────────────────────┘
     │
┌────▼──────────────────────────────────────┐
│        LLM Provider Interface             │
├───────────────────────────────────────────┤
│  • Claude API                             │
│  • Local Model (ollama/vLLM)              │
│  • OpenAI API                             │
└────┬──────────────────────────────────────┘
     │ Extracted entities,
     │ themes, relationships
     │
┌────▼──────────────────────────────────────┐
│     Neo4j Knowledge Graph                 │
│  (Stories, entities, themes,              │
│   relationships, clusters)                │
└────┬──────────────────────────────────────┘
     │
                ANALYSIS LAYER
     │
┌────▼──────────────────────────────────────┐
│        Analysis Engine                    │
├───────────────────────────────────────────┤
│  • Cypher query execution                 │
│  • Graph algorithms (centrality,          │
│    community detection, pathfinding)      │
│  • Clustering (DBSCAN, k-means)           │
│  • Semantic embeddings & similarity       │
│  • Temporal analysis                      │
└────┬──────────────────────────────────────┘
     │
┌────▼──────────────────────────────────────┐
│     Pattern Discovery Service             │
├───────────────────────────────────────────┤
│  • Batch analytics (scheduled jobs)       │
│  • Anomaly detection                      │
│  • Trend identification                   │
│  • LLM-powered insight synthesis          │
│  • Correlation discovery                  │
│  • Weak signal detection                  │
└────┬──────────────────────────────────────┘
     │
                PRESENTATION LAYER
     │
┌────▼──────────────────────────────────────┐
│        Query API (FastAPI)                │
├───────────────────────────────────────────┤
│  GET  /api/patterns/themes                │
│  GET  /api/patterns/entities              │
│  GET  /api/patterns/clusters              │
│  GET  /api/patterns/correlations          │
│  GET  /api/patterns/temporal              │
│  POST /api/insights/synthesize            │
│  POST /api/graph/query                    │
│  GET  /api/insights/cached                │
└────┬──────────────────────────────────────┘
     │
┌────▼──────────────────────────────────────┐
│        Visualization Layer                │
├───────────────────────────────────────────┤
│  • D3.js / vis.js (graph viz)             │
│  • Chart.js (trends, distributions)       │
│  • Custom canvas (triad heatmaps)         │
│  • Interactive dashboards                 │
│  • Natural language query interface       │
└───────────────────────────────────────────┘
```

### Technology Stack

**Frontend**:
- Simple HTML/JavaScript for MVP
- Canvas API for triad visualization
- Minimal framework overhead

**Backend API**:
- FastAPI (Python) - async support, automatic OpenAPI docs, easy auth later
- Pydantic for data validation

**Data Storage**:
- MongoDB - raw story storage (schemaless, handles evolving structure)
- Neo4j Community Edition - processed knowledge graph
- Redis or PostgreSQL - insight cache for precomputed patterns
- Reasoning: Separate concerns - preserve everything raw, analyze in graph, cache expensive queries

**LLM Integration**:
- Abstraction layer for model flexibility
- Support for: Claude API, local models (Llama, Mistral via ollama/vLLM), OpenAI
- Configuration-driven provider selection
- Used both for extraction AND synthesis

**Processing Pipeline**:
- Python asyncio or Celery for async job processing
- Event-driven: story arrival triggers analysis pipeline

**Analysis Engine**:
- Neo4j graph algorithms (GDS library) - community detection, centrality, pathfinding
- scikit-learn or custom clustering for signifier space analysis
- Sentence transformers for semantic similarity embeddings
- Python analytics layer wrapping Cypher queries

**Pattern Discovery Service**:
- Scheduled jobs (cron or Celery beat) for batch analytics
- On-demand synthesis via LLM for specific queries
- Anomaly detection algorithms (isolation forest, DBSCAN outliers)
- Temporal windowing for trend analysis

**Query & API Layer**:
- FastAPI for all endpoints (capture + analysis)
- Pydantic models for request/response validation
- Background task support for expensive syntheses
- WebSocket support for streaming insights (future)

**Development Environment**:
- Docker Compose for local development
- All services containerized for portability

### Key Architectural Decisions

**1. Separate Raw and Processed Storage**
- **Decision**: MongoDB for raw data, Neo4j for analyzed data
- **Rationale**: Allows pipeline reprocessing if we improve analysis; maintains data lineage; buffers processing delays

**2. LLM Provider Abstraction**
- **Decision**: Interface-based abstraction with multiple implementations
- **Rationale**: Flexibility between local dev (small models) and production (Claude/GPT); ability to A/B test extraction strategies; cost management

**3. Event-Driven Processing**
- **Decision**: Async pipeline triggered by story submission
- **Rationale**: Decouples capture from analysis; handles processing latency; enables retry logic; natural buffering under load

**4. Graph Database for Analysis**
- **Decision**: Neo4j for storing relationships between stories, entities, themes
- **Rationale**: First-class relationship support; pattern matching via Cypher; multi-hop reasoning; emergent pattern discovery

**5. Pseudonymization from Day One**
- **Decision**: Strip PII, assign pseudonymous identifiers
- **Rationale**: Privacy by design; enables org-wide deployment; builds trust with users

**6. Dual-Purpose LLM Usage**
- **Decision**: LLMs used for both extraction (entities/themes) AND synthesis (insight generation)
- **Rationale**: Graph queries return data structures; humans need narrative explanations; LLM synthesizes "what this pattern means" from raw results

**7. Insight Caching Layer**
- **Decision**: Cache precomputed patterns and common queries
- **Rationale**: Dashboard responsiveness; reduce Neo4j load; expensive syntheses computed once

**8. Natural Language Query Interface**
- **Decision**: LLM translates questions to Cypher queries
- **Rationale**: Non-technical users can ask questions without learning Cypher; makes insights accessible to broader audience

**9. Configurable Triad Definitions**
- **Decision**: Triad descriptors loaded from configuration file
- **Rationale**: Allows iteration on triad design without code changes; different contexts need different signifiers; maintains positive-only descriptor constraint

## Core Concepts

### Signifiers (Triads)

Triangular signifiers where users place their story based on three positive descriptors at each vertex. Position on the triangle encodes their experience as coordinates.

**Example Triads for Internal Tooling** (Note: All descriptors must be positive - users shouldn't know the "right" answer):

**Triad 1: Work Flow Nature**
- Vertex A: Streamlined (efficient, smooth, direct)
- Vertex B: Creative (requires ingenuity, flexible approach)
- Vertex C: Collaborative (involves coordination, teamwork)

**Triad 2: Understanding Quality**
- Vertex A: Intuitive (immediately clear, natural)
- Vertex B: Systematic (understandable through structured approach)
- Vertex C: Exploratory (discovered through experimentation)

**Triad 3: Value Character**
- Vertex A: Foundational (enables other work, essential infrastructure)
- Vertex B: Amplifying (multiplies effectiveness, force multiplier)
- Vertex C: Enabling (opens new possibilities, creates opportunities)

**Note**: Actual triad definitions will be loaded from a configuration file (YAML/JSON) to allow iteration and context-specific customization without code changes.

### Story Entity Model

```javascript
// Raw story (MongoDB)
{
  "id": "uuid",
  "timestamp": "ISO8601",
  "story_text": "User's narrative...",
  "triads": [
    {
      "triad_id": "workflow_character",
      "coordinates": {"x": 0.3, "y": 0.6}  // Barycentric coordinates
    },
    // ... other triads
  ],
  "metadata": {
    "user_pseudonym": "user_abc123",
    "department": "engineering",
    "role": "developer",
    "tool_context": "CI/CD pipeline"
  },
  "processing_status": "pending"
}

// Processed entities (Neo4j nodes/relationships)
(:Story {id, coordinates_json, timestamp})
(:Entity {name, type})  // e.g., tools, processes, features
(:Theme {name, description})
(:UserSegment {department, role})

(:Story)-[:MENTIONS]->(:Entity)
(:Story)-[:EXPRESSES]->(:Theme)
(:Story)-[:AUTHORED_BY]->(:UserSegment)
(:Story)-[:SIMILAR_TO {weight}]->(:Story)
(:Entity)-[:RELATES_TO]->(:Entity)
```

## User Stories - MVP Implementation

### Phase 0: Project Bootstrap

#### Story 0.1: Initialize Project Structure
**As a** developer  
**I want to** have a working project skeleton with all infrastructure configured  
**So that** I can start implementing features immediately

**Acceptance Criteria**:
- [ ] Git repository initialized with .gitignore
- [ ] GitHub repository created and linked
- [ ] All user stories created as GitHub Issues with appropriate labels and milestones
- [ ] Python project structure created (src/, tests/, temp/)
- [ ] pyproject.toml or requirements.txt with initial dependencies
- [ ] Docker Compose file with MongoDB, Neo4j, Redis services
- [ ] Environment configuration template (.env.example)
- [ ] README.md with setup and run instructions
- [ ] Directory structure documented
- [ ] All services start successfully with docker-compose up
- [ ] Basic health check endpoint returns 200

**Technical Tasks**:
- [ ] Initialize git repository
- [ ] Create .gitignore (include temp/, .env, __pycache__, etc.)
- [ ] Create GitHub repository
- [ ] Create GitHub Issues from all user stories in project.md
  - Use labels: phase-0, phase-1, etc.
  - Use milestones for each phase
  - Reference issue numbers in commit messages
- [ ] Create directory structure:
  ```
  sensemaker-feedback/
    src/
      domain/        # Domain models, value objects
      ports/         # Interface definitions (StoragePort, LLMPort, etc)
      adapters/      # Infrastructure implementations
      services/      # Application services
      api/          # FastAPI routes and schemas
    tests/
      unit/
      integration/
      fakes/        # Test implementations of ports
    temp/           # Working notes (git-ignored)
    docs/           # Project documentation
    scripts/        # Utility scripts
  ```
- [ ] Create pyproject.toml with dependencies:
  - FastAPI, uvicorn
  - pymongo, neo4j, redis
  - pytest, pytest-asyncio
  - pydantic
  - anthropic (for Claude API)
- [ ] Create Docker Compose with:
  - MongoDB (with test database)
  - Neo4j Community Edition
  - Redis
  - FastAPI service (development mode)
- [ ] Create .env.example with configuration variables
- [ ] Write README.md with quickstart
- [ ] Create basic FastAPI app with health check endpoint
- [ ] Verify all services connect

**Definition of Done**:
- New developer can run `docker-compose up` and see services running
- Health check endpoint accessible at http://localhost:8000/health
- Tests can be run with `pytest`
- Documentation is clear and complete

---

#### Story 0.2: Configure Triad Definitions
**As a** developer  
**I want to** have a configuration file for triad definitions  
**So that** we can iterate on signifier design without code changes

**Acceptance Criteria**:
- [ ] YAML config file at `config/triads.yaml`
- [ ] Contains 3 example triads with positive descriptors
- [ ] Each triad has id, name, and three vertex descriptors
- [ ] Config loaded and validated at application startup
- [ ] Invalid config causes clear error message
- [ ] Config structure documented

**Technical Tasks**:
- [ ] Create config/triads.yaml:
  ```yaml
  triads:
    - id: workflow_nature
      name: Work Flow Nature
      vertices:
        - id: streamlined
          label: Streamlined
          description: Efficient, smooth, direct
        - id: creative
          label: Creative
          description: Requires ingenuity, flexible approach
        - id: collaborative
          label: Collaborative
          description: Involves coordination, teamwork
    # ... two more triads
  ```
- [ ] Create Pydantic models for config validation
- [ ] Create config loader module
- [ ] Add config validation to startup
- [ ] Write tests for config loading
- [ ] Document config format in docs/

**Definition of Done**:
- Config loads successfully on startup
- Invalid config prevents application start with clear error
- Tests verify config structure validation

---

#### Story 0.3: Define Core Port Interfaces
**As a** developer  
**I want to** have the core port interfaces defined  
**So that** we can implement features against stable contracts

**Acceptance Criteria**:
- [ ] StoragePort interface defined
- [ ] LLMPort interface defined  
- [ ] GraphPort interface defined
- [ ] Each port has clear docstring with CRC card
- [ ] Ports are in src/ports/ directory
- [ ] Ports use domain models, not infrastructure types
- [ ] All ports are abstract base classes

**Technical Tasks**:
- [ ] Create src/ports/storage.py with StoragePort ABC
- [ ] Create src/ports/llm.py with LLMPort ABC
- [ ] Create src/ports/graph.py with GraphPort ABC
- [ ] Define methods based on user stories (start minimal)
- [ ] Add CRC cards to docstrings
- [ ] Create basic domain models they depend on
- [ ] Document port contracts in docs/architecture.md

**Example Port**:
```python
# src/ports/storage.py
from abc import ABC, abstractmethod
from domain.models import Story

class StoragePort(ABC):
    """
    Responsibilities:
    - Persist story data
    - Retrieve story data by ID
    
    Collaborators:
    - Story (domain model)
    
    Notes:
    - No knowledge of storage implementation
    - Operations are atomic
    - May raise StorageError for infrastructure issues
    """
    
    @abstractmethod
    def save_story(self, story: Story) -> str:
        """Save story and return assigned ID"""
        pass
    
    @abstractmethod
    def get_story(self, story_id: str) -> Story:
        """Retrieve story by ID, raise NotFoundError if missing"""
        pass
```

**Definition of Done**:
- All three ports defined with clear interfaces
- Each has CRC card in docstring
- Imports don't reference any infrastructure (no pymongo, neo4j, etc)
- Ready to implement adapters and fakes against these ports

---

### Phase 1: Core Data Capture

#### Story 1.1: Submit a Story with Triad Placement
**As a** user providing feedback  
**I want to** write a narrative story and place it on triangular signifiers  
**So that** I can express my experience without being forced into predefined categories

**Acceptance Criteria**:
- [ ] Web form with text area for story (minimum 50 characters, maximum 2000 characters)
- [ ] Visual representation of 3 triads with labeled vertices
- [ ] Click/drag interaction to place marker on each triad
- [ ] Coordinates calculated and stored as barycentric coordinates (0-1 range)
- [ ] Form validation ensures story text and all triad placements are complete
- [ ] Successful submission shows confirmation message
- [ ] Story stored in MongoDB with timestamp and generated UUID

**Technical Tasks**:
- [ ] Create MongoDB connection and story collection schema
- [ ] Build FastAPI endpoint `POST /api/stories`
- [ ] Implement HTML canvas-based triad visualization
- [ ] Calculate barycentric coordinates from click position
- [ ] Add client-side form validation
- [ ] Return story ID on successful submission

---

#### Story 1.2: Include Optional Metadata
**As a** user providing feedback  
**I want to** optionally include context about my role and department  
**So that** patterns can be found across different user segments

**Acceptance Criteria**:
- [ ] Optional dropdown fields for department and role
- [ ] Metadata saved with story if provided
- [ ] System assigns pseudonymous identifier to user session
- [ ] No PII (names, emails) collected or stored
- [ ] Form submits successfully with or without metadata

**Technical Tasks**:
- [ ] Add metadata fields to MongoDB schema
- [ ] Generate pseudonymous user identifier (hash-based or UUID)
- [ ] Store user pseudonym in session cookie
- [ ] Update API endpoint to accept optional metadata
- [ ] Add metadata dropdowns to frontend

---

#### Story 1.3: View Raw Story Data
**As a** system administrator  
**I want to** retrieve and view raw story data  
**So that** I can verify data is being captured correctly

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/stories` returns list of all stories
- [ ] API endpoint `GET /api/stories/{id}` returns specific story
- [ ] Response includes story text, triad coordinates, metadata, timestamp
- [ ] Basic pagination support (limit/offset)
- [ ] Simple admin UI to browse submitted stories

**Technical Tasks**:
- [ ] Implement `GET /api/stories` with pagination
- [ ] Implement `GET /api/stories/{id}` endpoint
- [ ] Create basic HTML admin page listing stories
- [ ] Add JSON response formatting

---

### Phase 2: LLM Processing Pipeline

#### Story 2.1: Abstract LLM Provider Interface
**As a** developer  
**I want to** switch between different LLM providers without changing pipeline code  
**So that** I can use local models for dev and API models for production

**Acceptance Criteria**:
- [ ] Python abstract base class defining LLM operations
- [ ] At least two implementations: Claude API and local model (ollama)
- [ ] Configuration file specifies which provider to use
- [ ] Provider implementations handle their own auth/connection
- [ ] Consistent input/output format across providers

**Technical Tasks**:
- [ ] Create `LLMProvider` abstract base class with methods:
  - `extract_entities(story: str) -> dict`
  - `extract_themes(story: str) -> list[str]`
  - `extract_relationships(story: str) -> list[dict]`
- [ ] Implement `ClaudeProvider` using Anthropic API
- [ ] Implement `LocalProvider` using ollama
- [ ] Create config.yaml for provider selection
- [ ] Add provider factory pattern for instantiation

---

#### Story 2.2: Extract Entities from Stories
**As a** system  
**I want to** automatically extract mentioned entities (tools, processes, features) from stories  
**So that** I can build a knowledge graph of what users are discussing

**Acceptance Criteria**:
- [ ] LLM identifies entities mentioned in story text
- [ ] Entities categorized by type (tool, process, feature, person_role, concept)
- [ ] Entity extraction results stored in MongoDB with story
- [ ] Extraction handles stories in multiple languages (if needed)
- [ ] Failed extractions logged but don't block pipeline

**Technical Tasks**:
- [ ] Design entity extraction prompt template
- [ ] Implement entity extraction in LLM provider interface
- [ ] Create entity schema in MongoDB (nested in story document)
- [ ] Add async processing job triggered on story submission
- [ ] Handle LLM errors gracefully with retry logic
- [ ] Update story processing_status field

---

#### Story 2.3: Extract Themes and Topics
**As a** system  
**I want to** identify themes and topics present in each story  
**So that** I can cluster similar stories together

**Acceptance Criteria**:
- [ ] LLM identifies 1-5 themes per story
- [ ] Themes are descriptive phrases (not single words)
- [ ] Theme extraction considers story context and triad placement
- [ ] Themes stored with story in MongoDB
- [ ] Common themes normalized (e.g., "login problems" = "authentication issues")

**Technical Tasks**:
- [ ] Design theme extraction prompt template
- [ ] Implement theme extraction in LLM provider
- [ ] Add theme normalization/fuzzy matching logic
- [ ] Store themes array in MongoDB story document
- [ ] Test theme extraction across various story types

---

#### Story 2.4: Analyze Sentiment and Emotional Tone
**As a** system  
**I want to** understand the emotional tone of each story  
**So that** I can correlate sentiment with triad placement patterns

**Acceptance Criteria**:
- [ ] LLM extracts emotional markers (frustration, satisfaction, confusion, etc.)
- [ ] Sentiment stored as structured data (not just positive/negative)
- [ ] Analysis distinguishes between emotion about process vs outcome
- [ ] Sentiment data stored in MongoDB

**Technical Tasks**:
- [ ] Design sentiment analysis prompt
- [ ] Implement sentiment extraction returning structured JSON
- [ ] Store sentiment analysis in MongoDB
- [ ] Test sentiment extraction accuracy

---

### Phase 3: Knowledge Graph Construction

#### Story 3.1: Connect to Neo4j and Create Story Nodes
**As a** system  
**I want to** store processed stories as nodes in Neo4j  
**So that** I can query relationships between stories

**Acceptance Criteria**:
- [ ] Neo4j Community Edition running in Docker
- [ ] Story nodes created with properties: id, timestamp, triad_coordinates
- [ ] Full story text NOT duplicated in Neo4j (MongoDB remains source of truth)
- [ ] Story node links back to MongoDB via ID

**Technical Tasks**:
- [ ] Add Neo4j Docker container to docker-compose.yml
- [ ] Install neo4j Python driver
- [ ] Create story node creation function
- [ ] Add Neo4j connection to processing pipeline
- [ ] Create Cypher constraints for story.id uniqueness

---

#### Story 3.2: Create Entity Nodes and Relationships
**As a** system  
**I want to** create entity nodes and link them to stories  
**So that** I can find all stories mentioning a specific tool or concept

**Acceptance Criteria**:
- [ ] Entity nodes created with properties: name, type
- [ ] `(:Story)-[:MENTIONS]->(:Entity)` relationships created
- [ ] Duplicate entities merged (same name/type = same node)
- [ ] Entity nodes include count of stories mentioning them

**Technical Tasks**:
- [ ] Create entity node creation function with MERGE logic
- [ ] Create MENTIONS relationship function
- [ ] Update processing pipeline to create entities after story node
- [ ] Add entity node count aggregation query
- [ ] Test entity deduplication

---

#### Story 3.3: Create Theme Nodes and Clustering
**As a** system  
**I want to** create theme nodes and cluster similar stories  
**So that** I can discover pattern across narratives

**Acceptance Criteria**:
- [ ] Theme nodes created with properties: name, description
- [ ] `(:Story)-[:EXPRESSES]->(:Theme)` relationships created
- [ ] Stories sharing themes linked via similarity relationships
- [ ] Themes with high story counts surfaced as "major patterns"

**Technical Tasks**:
- [ ] Create theme node creation function
- [ ] Create EXPRESSES relationship function
- [ ] Calculate story-to-story similarity based on shared themes
- [ ] Create `(:Story)-[:SIMILAR_TO {weight}]->(:Story)` relationships
- [ ] Test theme clustering

---

#### Story 3.4: Link Stories by Triad Proximity
**As a** system  
**I want to** find stories with similar triad placements  
**So that** I can identify clusters in signifier space

**Acceptance Criteria**:
- [ ] Calculate Euclidean distance between story coordinates
- [ ] Stories within distance threshold linked by NEAR_IN_SIGNIFIER_SPACE relationship
- [ ] Distance threshold configurable
- [ ] Relationship weight proportional to proximity

**Technical Tasks**:
- [ ] Implement coordinate distance calculation function
- [ ] Create batch job to calculate all pairwise distances
- [ ] Create proximity relationships in Neo4j
- [ ] Make distance threshold configurable
- [ ] Optimize for performance with spatial indexing if needed

---

### Phase 4: Pattern Discovery and Query

#### Story 4.1: Query Stories by Entity
**As a** user analyzing feedback  
**I want to** find all stories mentioning a specific entity  
**So that** I can understand experiences with a particular tool or process

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/by-entity/{entity_name}`
- [ ] Returns all stories mentioning the entity
- [ ] Results include story text, coordinates, metadata
- [ ] Results paginated

**Technical Tasks**:
- [ ] Write Cypher query for entity-based story retrieval
- [ ] Create FastAPI endpoint
- [ ] Link back to MongoDB to fetch full story text
- [ ] Add pagination support
- [ ] Create simple UI for entity search

---

#### Story 4.2: Discover Emergent Themes
**As a** user analyzing feedback  
**I want to** see the most common themes across all stories  
**So that** I can identify what matters most to users

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/themes`
- [ ] Returns themes ranked by story count
- [ ] Shows example stories for each theme
- [ ] Filterable by date range, metadata

**Technical Tasks**:
- [ ] Write Cypher query aggregating theme frequencies
- [ ] Create FastAPI endpoint
- [ ] Add date range filtering
- [ ] Include sample stories in response
- [ ] Create visualization showing theme distribution

---

#### Story 4.3: Find Correlated Patterns
**As a** user analyzing feedback  
**I want to** discover which entities frequently appear together  
**So that** I can understand systemic issues or opportunities

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/correlations`
- [ ] Returns pairs of entities that co-occur above threshold
- [ ] Includes correlation strength and example stories
- [ ] Supports filtering by entity type

**Technical Tasks**:
- [ ] Write Cypher query finding co-occurring entities
- [ ] Calculate correlation strength (stories with both / stories with either)
- [ ] Create FastAPI endpoint
- [ ] Add threshold parameter
- [ ] Visualize correlations as network graph

---

#### Story 4.4: Identify Signifier Space Clusters
**As a** user analyzing feedback  
**I want to** see clusters of stories in signifier space  
**So that** I can identify distinct experience patterns

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/clusters`
- [ ] Returns identified clusters with center coordinates
- [ ] Lists stories in each cluster
- [ ] Shows common themes/entities per cluster

**Technical Tasks**:
- [ ] Implement clustering algorithm (DBSCAN or k-means on coordinates)
- [ ] Create Cypher query or Python analysis for clustering
- [ ] Create FastAPI endpoint
- [ ] Visualize clusters on triad space
- [ ] Summarize cluster characteristics (themes, entities, metadata patterns)

---

#### Story 4.5: Temporal Pattern Analysis
**As a** user analyzing feedback  
**I want to** see how patterns change over time  
**So that** I can track improvement or degradation

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/temporal`
- [ ] Shows theme/entity frequency over time windows
- [ ] Shows triad coordinate drift over time
- [ ] Filterable by theme, entity, metadata

**Technical Tasks**:
- [ ] Create time-windowed Cypher queries
- [ ] Calculate coordinate centroid movement over time
- [ ] Create FastAPI endpoint
- [ ] Visualize temporal trends (line charts)
- [ ] Identify significant shifts

---

#### Story 4.5: Temporal Pattern Analysis
**As a** user analyzing feedback  
**I want to** see how patterns change over time  
**So that** I can track improvement or degradation

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/temporal`
- [ ] Shows theme/entity frequency over time windows
- [ ] Shows triad coordinate drift over time
- [ ] Filterable by theme, entity, metadata

**Technical Tasks**:
- [ ] Create time-windowed Cypher queries
- [ ] Calculate coordinate centroid movement over time
- [ ] Create FastAPI endpoint
- [ ] Visualize temporal trends (line charts)
- [ ] Identify significant shifts

---

#### Story 4.6: LLM-Powered Insight Synthesis
**As a** user analyzing feedback  
**I want to** get natural language explanations of discovered patterns  
**So that** I understand what the data means without interpreting raw graph results

**Acceptance Criteria**:
- [ ] API endpoint `POST /api/insights/synthesize` accepts pattern query
- [ ] System retrieves relevant graph data based on query
- [ ] LLM generates narrative explanation of patterns
- [ ] Response includes supporting evidence (story excerpts, statistics)
- [ ] Synthesis considers context (triad positions, metadata, temporal trends)

**Technical Tasks**:
- [ ] Create synthesis prompt templates
- [ ] Implement graph data retrieval for synthesis context
- [ ] Add LLM synthesis method to provider interface
- [ ] Create synthesis endpoint
- [ ] Test synthesis quality across various pattern types
- [ ] Add caching for expensive syntheses

**Example Queries**:
- "Why do stories mentioning the CI/CD pipeline cluster in the 'Creative + Exploratory' region?"
- "What changed between Q1 and Q2 for authentication-related stories?"
- "What are the common themes in stories from the engineering department?"

---

#### Story 4.7: Natural Language Query Interface
**As a** non-technical user  
**I want to** ask questions in plain English  
**So that** I can discover insights without learning Cypher

**Acceptance Criteria**:
- [ ] API endpoint `POST /api/insights/query` accepts natural language question
- [ ] LLM translates question to appropriate Cypher query or analysis operation
- [ ] System executes query against Neo4j
- [ ] Results synthesized into natural language answer
- [ ] Failed translations provide helpful error messages

**Technical Tasks**:
- [ ] Create query translation prompt with Cypher examples
- [ ] Implement safety constraints (read-only queries, query timeout)
- [ ] Add query validation before execution
- [ ] Create endpoint for natural language queries
- [ ] Test translation accuracy on diverse question types
- [ ] Add query history/examples for users

**Example Questions**:
- "Which tools do mobile developers find most frustrating?"
- "What are the biggest pain points mentioned in the last month?"
- "Show me stories similar to this one" (with story ID)

---

#### Story 4.8: Anomaly Detection and Outliers
**As a** user analyzing feedback  
**I want to** identify unusual or outlier stories  
**So that** I can catch emerging issues or unique perspectives

**Acceptance Criteria**:
- [ ] API endpoint `GET /api/patterns/anomalies`
- [ ] Identifies stories that don't fit established patterns
- [ ] Multiple anomaly detection methods (isolation, statistical, graph-based)
- [ ] Ranked by "unusualness" score
- [ ] Explanation of why story is anomalous

**Technical Tasks**:
- [ ] Implement isolation forest on story embeddings
- [ ] Identify graph structure anomalies (disconnected stories, unusual centrality)
- [ ] Detect statistical outliers in triad coordinate space
- [ ] Create combined anomaly scoring
- [ ] Create FastAPI endpoint
- [ ] Add LLM explanation of anomaly characteristics

---

### Phase 5: Caching and Performance

#### Story 5.1: Insight Cache Implementation
**As a** system  
**I want to** cache expensive pattern computations  
**So that** dashboards load quickly without recomputing

**Acceptance Criteria**:
- [ ] Redis or PostgreSQL cache configured
- [ ] Common patterns cached (top themes, entity frequencies, clusters)
- [ ] Cache invalidation on new story processing
- [ ] TTL-based expiration for temporal queries
- [ ] Cache hit/miss metrics

**Technical Tasks**:
- [ ] Set up Redis in Docker Compose
- [ ] Implement cache layer in Python
- [ ] Add cache decorators to expensive endpoints
- [ ] Implement cache invalidation strategy
- [ ] Add cache warming for common queries
- [ ] Monitor cache performance

---

#### Story 5.2: Scheduled Pattern Discovery Jobs
**As a** system  
**I want to** run pattern discovery in background batches  
**So that** insights are pre-computed and always current

**Acceptance Criteria**:
- [ ] Scheduled jobs run nightly or on configurable schedule
- [ ] Jobs compute: cluster analysis, correlations, trending themes
- [ ] Results stored in cache for fast retrieval
- [ ] Job failures logged and alerted
- [ ] Manual job triggering available

**Technical Tasks**:
- [ ] Set up Celery beat for job scheduling
- [ ] Create pattern discovery job tasks
- [ ] Implement result caching
- [ ] Add job monitoring and logging
- [ ] Create admin interface for job management

---

### Phase 6: Visualization and User Interface

#### Story 6.1: Story Submission Interface
**As a** user  
**I want** an intuitive interface for submitting stories  
**So that** I can easily provide feedback

**Acceptance Criteria**:
- [ ] Clean, accessible web form
- [ ] Clear instructions for triad placement
- [ ] Visual feedback on marker placement
- [ ] Mobile-responsive design
- [ ] Submission confirmation

**Technical Tasks**:
- [ ] Design HTML/CSS for story form
- [ ] Improve triad canvas UX (draggable markers, labels)
- [ ] Add helpful hints/tooltips
- [ ] Implement responsive CSS
- [ ] Add loading states and error messages

---

#### Story 6.2: Pattern Exploration Dashboard
**As a** user analyzing feedback  
**I want** a dashboard showing discovered patterns  
**So that** I can quickly understand key insights

**Acceptance Criteria**:
- [ ] Dashboard showing top themes, entities, clusters
- [ ] Interactive visualizations (clickable to drill down)
- [ ] Date range filtering
- [ ] Export capabilities (JSON, CSV)

**Technical Tasks**:
- [ ] Create dashboard HTML page
- [ ] Integrate Chart.js or D3.js for visualizations
- [ ] Connect to pattern API endpoints
- [ ] Add interactive filtering
- [ ] Implement data export

---

#### Story 6.3: Graph Exploration Interface
**As a** power user  
**I want to** explore the knowledge graph directly  
**So that** I can run custom queries and discover unexpected patterns

**Acceptance Criteria**:
- [ ] Embedded Neo4j Browser or custom graph viz
- [ ] Predefined query templates
- [ ] Ability to run custom Cypher queries
- [ ] Visual graph exploration of story relationships

**Technical Tasks**:
- [ ] Embed Neo4j Browser or integrate vis.js
- [ ] Create query template library
- [ ] Add Cypher query executor (with safety limits)
- [ ] Style graph visualization
- [ ] Add export graph data option

---

#### Story 6.4: Natural Language Query UI
**As a** user  
**I want to** ask questions about patterns in plain English via the UI  
**So that** I can explore insights conversationally

**Acceptance Criteria**:
- [ ] Chat-like interface for asking questions
- [ ] Query history preserved in session
- [ ] Responses include visualizations where appropriate
- [ ] Option to export query results
- [ ] Suggested follow-up questions

**Technical Tasks**:
- [ ] Create chat UI component
- [ ] Connect to natural language query API
- [ ] Add response rendering (text + charts)
- [ ] Implement query history
- [ ] Add follow-up question generation
- [ ] Mobile-responsive design

---

## Development Phases Summary

**Phase 0**: Project bootstrap and infrastructure (1 week)
- Git init, project structure, Docker Compose
- Core port interfaces defined
- Triad configuration

**Phase 1**: Basic story capture and storage (1-2 weeks)
- Web form, MongoDB storage, FastAPI foundation

**Phase 2**: LLM processing pipeline (2-3 weeks)
- Provider abstraction, entity/theme/sentiment extraction

**Phase 3**: Knowledge graph construction (2 weeks)
- Neo4j integration, node/relationship creation

**Phase 4**: Pattern discovery and insight synthesis (3-4 weeks)
- Query endpoints, clustering, correlation analysis
- LLM-powered synthesis and natural language querying
- Anomaly detection

**Phase 5**: Caching and performance (1-2 weeks)
- Insight cache implementation
- Scheduled pattern discovery jobs

**Phase 6**: Visualization and polish (2-3 weeks)
- UI improvements, dashboards, graph exploration
- Natural language query interface

**Total MVP Timeline**: 12-17 weeks part-time

## Next Steps

1. Complete Story 0.1 (Issue #1) - Initialize project structure and create GitHub Issues
2. Complete Story 0.2 (Issue #2) - Configure triad definitions
3. Complete Story 0.3 (Issue #3) - Define core port interfaces
4. Begin Phase 1 Story 1.1 - Basic story submission

## User Stories Location

All user stories will be tracked as GitHub Issues with:
- **Labels**: `phase-0`, `phase-1`, etc. for organization
- **Milestones**: One per phase for progress tracking
- **Projects**: Optional Kanban board for workflow visualization

When implementing:
- Reference issue numbers in commits: "Implements #5" or "Fixes #12"
- GitHub will automatically link commits to issues
- Use `temp/issue-N/` directories for working notes (e.g., `temp/issue-5/`)
- Update issue status and check acceptance criteria as you progress

## References

- Cognitive Edge SenseMaker: https://thecynefin.co/
- Neo4j Documentation: https://neo4j.com/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- MongoDB Python Driver: https://pymongo.readthedocs.io/
