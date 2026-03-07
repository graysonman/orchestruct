import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task

def create_task(db: Session, goal_id: uuid.UUID, **fields) -> Task:
    task = Task(id=uuid.uuid4(), goal_id=goal_id, **fields)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def get_task(db: Session, task_id: uuid.UUID) -> Task | None:
    return db.get(Task, task_id)

def list_tasks(db: Session, goal_id: uuid.UUID) -> list[Task]:
    return list(
        db.scalars(
            select(Task).where(Task.goal_id == goal_id)
        )
    )
def update_task(db: Session, task: Task, **fields) -> Task:
    for key, value in fields.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task

def delete_task(db:Session, task: Task):
    db.delete(task)
    db.commit()