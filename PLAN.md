# orchestruct

**Autonomous Goal-Driven Planning System: be the conductor of your life**

---

## Executive Summary

Orchestruct is a backend-first, machine learning assisted, constraint-based planning engine that converts structured goals into executable schedules, learns from user behavior, optimizes under real-world constraints, and integrates with external systems.

This document is the complete technical and architectural source of truth for building Orchestruct from scratch. It defines: vision, product scope, architecture, data modeling, planning algorithms, ML strategy, multi-tenant design, APIs, deployment, security, and roadmap.

It is intended to be readable by engineers, AI agents, and system architects.

---

## 1. Vision & Purpose

### 1.1 Problem Statement

Modern individuals and teams struggle with:

- Overcommitment
- Poor prioritization
- Unrealistic time estimation
- Reactive scheduling
- Goal drift
- Burnout cycles
- Fragmented tools (calendar, notes, tasks, goals, meetings)

Existing tools:

- Store information
- Do not optimize
- Do not learn behavior
- Do not adapt

There is no system that:

- Converts structured goals into executable schedules
- Learns behavioral patterns
- Optimizes under real-world constraints
- Proactively adjusts plans
- Requires approval before acting
- Integrates into existing ecosystems

### 1.2 Project Goal

Build a backend-first, ML-assisted, constraint-based planning engine that:

- Accepts structured goals
- Decomposes into tasks
- Predicts effort and risk
- Generates optimized schedules
- Learns from real behavior
- Adapts future plans
- Requires human approval before committing
- Integrates with external calendar systems
- Scales from individual to team to organization

### 1.3 Core Philosophy

- Autonomy with guardrails
- Learning from behavior, not assumptions
- Optimization under constraints
- Explainable decisions
- Multi-tenant extensibility
- Backend-driven intelligence
- UI as presentation layer only

---

## 2. High-Level Architecture

### 2.1 System Components

**Core Backend (FastAPI)**
- API Layer
- Planning Engine
- ML Service Layer
- Behavior Modeling Service
- Risk Engine
- State Machine
- Notification Engine
- Sync Engine

**Background Worker System**
- Plan recalculation
- Feature updates
- Model training
- Notification scheduling
- External sync retries

**Database**
- PostgreSQL
- Optional pgvector extension (later)

**Queue**
- Redis

**Frontend**
- React or Next.js
- Calendar UI
- Dashboard
- Goal management
- Approval interface

**Mobile (Future)**
- React Native
- API-driven

---

## 3. Technology Stack

**Backend**
- Python 3.11+
- FastAPI
- SQLAlchemy or SQLModel
- Pydantic
- Celery or RQ for workers
- Redis
- PostgreSQL

**ML**
- scikit-learn
- pandas
- numpy
- optional: lightgbm
- later: PyTorch if needed

**Frontend**
- Next.js
- React
- Tailwind CSS
- FullCalendar for calendar UI

**Auth**
- JWT
- OAuth2
- Later: Google OAuth integration

**Deployment**
- Docker
- Docker Compose (dev)
- AWS ECS or EC2 (prod)
- GitHub Actions CI/CD
- Terraform optional (infra as code)

---

## 4. Multi-Tenant Scope Model

All records belong to a scope.

**scope_type:**
- `user`
- `team`
- `organization`

**scope_id:** Foreign key to the relevant entity.

**Hierarchy:** User → Team → Organization

The planning engine receives scope context and applies relevant constraints at each level.

---

## 5. Core Data Modeling

### 5.1 Identity

- User
- Team
- Organization
- TeamMembership
- Role

Every record includes:
- `scope_type` (user, team, org)
- `scope_id`

### 5.2 Goals

| Field | Description |
|---|---|
| `id` | Primary key |
| `scope_type` | user / team / org |
| `scope_id` | Owner identifier |
| `title` | Goal name |
| `description` | Details |
| `success_metric_type` | How success is measured |
| `target_value` | Target metric value |
| `target_date` | Deadline |
| `priority_weight` | Relative importance |
| `min_weekly_time` | Floor time commitment |
| `max_weekly_time` | Cap time commitment |
| `constraints` | JSON — additional scheduling constraints |
| `created_at` | Timestamp |

### 5.3 Tasks

| Field | Description |
|---|---|
| `id` | Primary key |
| `goal_id` | Parent goal |
| `title` | Task name |
| `description` | Details |
| `estimated_minutes` | Expected duration |
| `difficulty` | Complexity rating |
| `due_date` | Deadline |
| `disliked_score` | User aversion signal |
| `owner_user_id` | Assignee |
| `prerequisites` | Dependency list |

### 5.4 Plans

| Field | Description |
|---|---|
| `id` | Primary key |
| `scope_type` | user / team / org |
| `scope_id` | Owner identifier |
| `planning_window_start` | Start of window |
| `planning_window_end` | End of window |
| `status` | draft / proposed / approved / committed / invalidated |
| `created_at` | Timestamp |

### 5.5 Plan Items

| Field | Description |
|---|---|
| `id` | Primary key |
| `plan_id` | Parent plan |
| `task_id` | Scheduled task |
| `start_time` | Block start |
| `end_time` | Block end |
| `owner_user_id` | Assignee |
| `risk_score` | Computed risk |
| `rationale` | JSON — explanation of placement decision |

### 5.6 Learning & Telemetry

**WorkLog**
- `task_id`
- `user_id`
- `started_at`
- `ended_at`
- `completed`
- `notes`

**UserFeatures**
- `completion_rate`
- `estimation_bias_multiplier`
- `focus_probability_by_hour`
- `reschedule_rate`
- `burnout_score`
- `dislike_clusters`

**TeamFeatures**
- `throughput_trend`
- `coordination_overhead`
- `delay_multiplier`

---

## 6. Planning Engine Design

### 6.1 Inputs

- Goals
- Tasks
- Calendar events
- Work hours
- Learned user features
- Soft constraint weights

### 6.2 Objective

**Maximize:**
- Weighted goal progress

**Minimize:**
- Stress score
- Deadline risk
- Overcommitment risk
- Context switching

**Final objective:** Composite weighted score.

### 6.3 MVP Scheduling Algorithm

1. Build availability grid
2. Convert tasks into work units
3. Score candidate placements:
   - Deadline proximity
   - Focus window probability
   - Disliked clustering penalty
   - Goal priority weight
4. Greedy placement
5. Compute risk metrics
6. Output proposed plan
7. Require user approval before commit

### 6.4 Risk Metrics

- Deadline slack ratio
- Overload ratio
- Context switching count
- Burnout likelihood
- Estimation uncertainty

---

## 7. Machine Learning Plan

### Phase 1 Models

**Duration Prediction**
- Regression
- Features: category, difficulty, time of day, historical bias, recent velocity

**Focus Window Modeling**
- Hourly productivity clustering
- Exponential moving averages

**Overcommitment Detection**
- Weighted heuristic scoring

### Phase 2 Models

- Burnout classification
- Task abandonment predictor
- Team throughput forecasting

### Model Evaluation Metrics

- Mean Absolute Error
- Calibration score
- Schedule adherence rate
- Plan success rate
- Nudge effectiveness rate

---

## 8. Lifecycle & Stages

### Stage 0: Foundation
- Repo setup
- Docker infrastructure
- Auth system
- User model
- Basic UI shell

**MVP Output:** User login and dashboard.

### Stage 1: Goals & Tasks
- Structured goal creation
- Manual task creation
- Optional LLM decomposition
- Task UI

**MVP Output:** Goals produce task backlog.

### Stage 2: Internal Calendar
- Internal calendar model
- Work hours config
- Availability computation
- Calendar UI

**MVP Output:** User sees free/busy grid.

### Stage 3: Planning Engine v1
- Generate weekly plan
- Risk scoring
- Rationale output
- Approval step

**MVP Output:** User can generate and approve plan.

### Stage 4: Learning Loop
- Work logs
- Feature updates
- Estimation bias correction
- Display personal stats

**MVP Output:** System adapts predictions.

### Stage 5: Nudges & Accountability
- Notification engine
- Context-aware reminders
- Weekly alignment score
- Nudge effectiveness tracking

**MVP Output:** Behavior-aware nudging.

### Stage 6: Team Mode
- Team creation
- Shared goals
- Assignment suggestions
- Capacity conflict detection

**MVP Output:** Team planning suggestions.

### Stage 7: External Calendar Integration
- Google OAuth
- Pull events
- Push approved plan blocks
- Conflict detection
- Idempotent updates

**MVP Output:** Two-way sync.

### Stage 8: Meeting & Notes Ingestion
- Upload transcripts
- Extract action items
- Convert to tasks
- Trigger plan recalculation
- Present approval diff

**MVP Output:** Meeting → plan update.

### Stage 9: Advanced Optimization
- Local search improvements
- Swap and merge heuristics
- Team global optimization
- Stress-aware scheduling

### Stage 10: Production Hardening
- Logging
- Metrics
- Observability
- Rate limiting
- Error handling
- Privacy compliance
- Data encryption

---

## 9. API Design Principles

- RESTful endpoints
- Versioned API (`/v1/...`)
- Idempotent plan commits
- Explicit state transitions
- Clear separation between draft and committed plans

**Example endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/goals` | Create a goal |
| `POST` | `/tasks` | Create a task |
| `POST` | `/plans/generate` | Trigger plan generation |
| `POST` | `/plans/{id}/approve` | Approve a proposed plan |
| `GET` | `/calendar` | Fetch calendar availability |
| `POST` | `/worklogs` | Log completed work |
| `GET` | `/metrics` | Fetch user/team metrics |

---

## 10. Deployment Strategy

| Environment | Stack |
|---|---|
| Dev | Docker Compose |
| Staging | AWS EC2, RDS PostgreSQL, Redis |
| Production | ECS or Kubernetes, auto-scaling workers, CloudWatch |

CI/CD via GitHub Actions.

---

## 11. Admin & Management Dashboard

- User analytics
- Plan generation frequency
- Prediction error trends
- Risk calibration metrics
- Active users
- System health

---

## 12. Security & Privacy

- Encrypted tokens
- Scoped OAuth access
- Minimal data retention
- Secure secret storage
- Role-based permissions
- Audit logs
- Encryption at rest and in transit

---

## 13. Future Extensions

- Reinforcement learning scheduling
- Team global solver
- Slack integration
- Email parsing
- Obsidian sync
- Burnout early detection system
- Habit tracking layer
- AI coach mode
- Public API

---

## 14. Documentation Requirements

Project must include:

- Architecture diagram
- Database schema diagram
- Planning engine explanation
- ML modeling explanation
- Tradeoff discussion
- Evaluation metrics report
- Deployment guide
- API documentation
- Roadmap updates

---

## 15. Success Criteria

The project is considered complete when:

- Personal mode reliably generates realistic plans
- Duration prediction improves over time
- Risk warnings are calibrated
- Approval flow works cleanly
- Integration is stable
- Documentation explains all architectural decisions

---

## 16. Final Vision Statement

This project demonstrates:

- Backend architecture design
- Multi-tenant modeling
- Constraint optimization
- ML integration
- Behavioral learning
- Event-driven systems
- Real-world automation guardrails
- Production-ready thinking

> It is not a calendar app. It is an adaptive execution engine.
