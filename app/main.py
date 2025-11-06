from contextlib import asynccontextmanager 
from fastapi.middleware.cors import CORSMiddleware 
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import engine, SessionLocal
from app.models import Base, UserDB, CourseDB, ProjectDB
from app.schemas import (
    UserCreate,
    UserRead,
    UserUpdate,
    CourseCreate,
    CourseRead,
    ProjectCreate,
    ProjectRead,
    ProjectReadWithOwner,
    ProjectCreateForUser,
    ProjectUpdate
)

#Replacing @app.on_event("startup") 
@asynccontextmanager 
async def lifespan(app: FastAPI): 
    Base.metadata.create_all(bind=engine)    
    yield 
 
app = FastAPI(lifespan=lifespan) 
 
# CORS (add this block) 
#Used to decide what can connect to it, for now anythign can connect
app.add_middleware( 
    CORSMiddleware, 
    allow_origins=["*"],   # dev-friendly; tighten in prod 
    allow_methods=["*"], 
    allow_headers=["*"], 
) 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
  

def commit_or_rollback(db: Session, error_msg: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=error_msg)


@app.get("/health")
def health():
    return {"status": "ok"}


# Courses
@app.post(
    "/api/courses",
    response_model=CourseRead,
    status_code=201,
    summary="You could add details",
)
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    db_course = CourseDB(**course.model_dump())
    db.add(db_course)
    commit_or_rollback(db, "Course already exists")
    db.refresh(db_course)
    return db_course


@app.get("/api/courses", response_model=list[CourseRead])
def list_courses(limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(CourseDB).order_by(CourseDB.id).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


# Projects
@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    user = db.get(UserDB, project.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    proj = ProjectDB(
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
    )
    db.add(proj)
    commit_or_rollback(db, "Project creation failed")
    db.refresh(proj)
    return proj


@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    stmt = select(ProjectDB).order_by(ProjectDB.id)
    return db.execute(stmt).scalars().all()


@app.get("/api/projects/{project_id}", response_model=ProjectReadWithOwner)
def get_project_with_owner(project_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(ProjectDB)
        .where(ProjectDB.id == project_id)
        .options(selectinload(ProjectDB.owner))
    )
    proj = db.execute(stmt).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@app.patch("/api/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(ProjectDB, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True) #exclude unset only changes the fields that have been updated 
    for field, value in updates.items():
        setattr(project, field, value)

    try:
        db.commit()
        db.refresh(project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project update failed (unique constraint)")
    return project
    

@app.put("/api/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectCreate, db: Session = Depends(get_db)):
    project = db.get(ProjectDB, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field_name, field_value in payload.model_dump().items():
        setattr(project, field_name, field_value)
    try:
        db.commit()
        db.refresh(project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Project already exists")
    return project


# Nested Routes
@app.get("/api/users/{user_id}/projects", response_model=list[ProjectRead])
def get_user_projects(user_id: int, db: Session = Depends(get_db)):
    stmt = select(ProjectDB).where(ProjectDB.owner_id == user_id)
    # space it out for debugging
    result = db.execute(stmt)
    rows = result.scalars().all()
    return rows
    # return db.execute(stmt).scalars().all()


@app.post("/api/users/{user_id}/projects", response_model=ProjectRead, status_code=201)
def create_user_project(
    user_id: int, project: ProjectCreateForUser, db: Session = Depends(get_db)
):
    user = db.get(UserDB, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    proj = ProjectDB(
        name=project.name,
        description=project.description,  # <-- set it
        owner_id=user_id,
    )
    db.add(proj)
    commit_or_rollback(db, "Project creation failed")
    db.refresh(proj)
    return proj


@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    stmt = select(UserDB).order_by(UserDB.id)
    # Useful for debugging
    result = db.execute(stmt)
    users = result.scalars().all()
    return users
    # return list(db.execute(stmt).scalars())


@app.get("/api/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(UserDB, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = UserDB(**payload.model_dump())
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")
    return user


# DELETE a user (triggers ORM cascade -> deletes their projects too)
@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Response:
    user = db.get(UserDB, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)  # <-- triggers cascade="all, delete-orphan" on projects
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.patch("/api/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(UserDB, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True) #exclude unset only changes the fields that have been updated 
    for field, value in updates.items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User update failed (unique constraint)")
    return user
    

@app.put("/api/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserCreate, db: Session = Depends(get_db)):
    user = db.get(UserDB, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field_name, field_value in payload.model_dump().items():
        setattr(user, field_name, field_value)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        # email/user_name unique conflict, etc.
        raise HTTPException(status_code=409, detail="User already exists")
    return user