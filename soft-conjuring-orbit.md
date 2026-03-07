# Stage 1: MVP Greedy Planning Engine

## Context

Stage 0 is complete (auth, goals, tasks, all tests passing). Stage 1 adds the core differentiator: a scheduling engine that takes a user's goals + tasks and generates a proposed, time-blocked plan. The user must approve before the plan is committed. No calendar integration yet — availability is assumed as Mon–Fri 9am–5pm.

---

## What We're Building

- `Plan` and `PlanItem` models + Alembic migration
- Pure-function greedy scheduler (`scheduler.py`)
- `plan_service.py` bridging the DB and scheduler
- 4 endpoints: generate, get, approve, reject
- 6 tests in `test_plans.py`

---

## Implementation Order

### 1. Models — `backend/app/models/plan.py`

Two classes: `Plan` and `PlanItem`.

**Plan** — uses `Base, TimestampMixin, ScopedMixin` (same triple as `Goal`)
- `id: UUID PK`
- `planning_window_start: Date`
- `planning_window_end: Date`
- `status: String(50)` — default `"draft"`
- `risk_summary: JSON | None`
- Relationships: `items = relationship("PlanItem", back_populates="plan", lazy="select")`

**PlanItem** — uses `Base` only (write-once, no `updated_at`)
- `id: UUID PK`
- `plan_id: UUID FK → plans.id`
- `task_id: UUID FK → tasks.id`
- `scheduled_date: Date`
- `start_time: Time`
- `end_time: Time`
- `risk_score: Float | None`
- `rationale: JSON | None`
- `created_at: DateTime` via `server_default=func.now()`
- Relationship: `plan = relationship("Plan", back_populates="items")`

After creating the file, add `Plan` and `PlanItem` to `backend/app/models/__init__.py` so `Base.metadata` picks them up for test `create_all`.

---

### 2. Schemas — `backend/app/schemas/plans.py`

```
PlanGenerate        planning_window_start: date, planning_window_end: date
PlanItemResponse    id, plan_id, task_id, scheduled_date, start_time, end_time, risk_score, rationale, created_at
PlanResponse        id, scope_type, scope_id, window dates, status, risk_summary, items: list[PlanItemResponse], created_at, updated_at
```
All response schemas: `model_config = ConfigDict(from_attributes=True)`

---

### 3. Scheduler — `backend/app/services/scheduler.py` ← **Learn by Doing**

Pure functions only. No `db`, no FastAPI. Input: enriched task list + date window. Output: scheduled items + risk summary dict.

**I will scaffold:** the `ScheduledTask` dataclass, the availability grid builder, and the risk metrics computation.

**User implements:** the scoring formula + greedy placement loop (the core algorithm).

---

### 4. Plan Service — `backend/app/services/plan_service.py`

```python
def generate_plan(db, scope_type, scope_id, window_start, window_end) -> Plan
def get_plan(db, plan_id) -> Plan | None
def approve_plan(db, plan) -> Plan       # sets status="approved"
def reject_plan(db, plan) -> Plan        # sets status="invalidated"
```

`generate_plan` flow:
1. Query active goals for scope
2. Query pending tasks per goal
3. Enrich tasks with `priority_weight` from parent goal
4. Call `scheduler.run(enriched_tasks, window_start, window_end)` → `(scheduled, risk_summary)`
5. Create `Plan` (status="proposed") + `PlanItem` records
6. Access `plan.items` **before closing session** to avoid `DetachedInstanceError`
7. Return plan

---

### 5. Router — `backend/app/api/routers/plans.py`

```
POST /plans/generate         → 201  PlanResponse
GET  /plans/{plan_id}        → 200  PlanResponse
POST /plans/{plan_id}/approve → 200  PlanResponse   (400 if status != "proposed")
POST /plans/{plan_id}/reject  → 200  PlanResponse   (400 if status not in proposed/approved)
```

Scope always derived from auth: `ScopeType.USER`, `current_user.id` — same pattern as `list_goals`.
Ownership check: `plan.scope_id != current_user.id → 404`.

Register in `backend/app/main.py`:
```python
from app.api.routers import auth, goals, plans, tasks
app.include_router(plans.router, prefix="/api/v1")
```

---

### 6. Migration — `backend/alembic/versions/xxxxx_add_plans.py`

- `down_revision = 'd01dd6f8e87c'`
- `scope_type` column: `postgresql.ENUM(name='scopetype', create_type=False)` — same as goals migration
- Create `plans` before `plan_items` (FK order)
- `downgrade`: drop `plan_items` then `plans`

Run after implementation:
```
docker compose exec backend alembic upgrade head
```

---

### 7. Tests — `backend/tests/test_plans.py`

Fixtures: `auth_headers`, `created_goal`, `tasks_url`, `created_task` (mirror `test_tasks.py`).
Planning window constant: `2026-03-10` to `2026-03-14` (Mon–Fri, in the future).
Task fixture must include `"due_date": "2026-03-14"` and `"estimated_minutes": 60` so the scheduler scores and places it.

6 tests:
1. `test_generate_plan` — 201, status=proposed, items non-empty
2. `test_generate_plan_unauthenticated` — 403
3. `test_get_plan` — generate then GET, correct id
4. `test_approve_plan` — generate then approve, status=approved
5. `test_reject_plan` — generate then reject, status=invalidated
6. `test_generate_empty_plan` — no tasks → 201, items=[]

---

## Key Gotchas

| Gotcha | Fix |
|---|---|
| `Base.metadata` won't include Plan/PlanItem unless model is imported | Add to `models/__init__.py` |
| `DetachedInstanceError` on `plan.items` after commit | Access `plan.items` while session is open in `generate_plan` |
| `scopetype` enum already exists in PostgreSQL | `postgresql.ENUM(name='scopetype', create_type=False)` |
| `datetime.time` has no `+` operator | Use `datetime.combine(date, time) + timedelta(minutes=n)` |
| Division by zero in score if 0 days until due | `days_until_due = max(days_until_due, 1)` |

---

## Verification

```bash
docker compose exec backend pytest tests/test_plans.py -v   # all 6 pass
docker compose exec backend alembic upgrade head             # migration applies cleanly
```
