from typing import Annotated, Optional, List
from annotated_types import Ge, Le
from pydantic import BaseModel, EmailStr, ConfigDict, StringConstraints
 
NameStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]
StudentIdStr = Annotated[str, StringConstraints(pattern=r"^S\d{7}$")]
CodeStr = Annotated[str, StringConstraints(min_length=1, max_length=32)]
CourseNameStr = Annotated[str, StringConstraints(min_length=1, max_length=255)]
ProjectNameStr = Annotated[str, StringConstraints(min_length=1, max_length=255)]
DescStr = Annotated[str, StringConstraints(min_length=0, max_length=2000)]
AgeInt = Annotated[int, Ge(0), Le(150)]
CreditsInt = Annotated[int, Ge(1), Le(120)]

#different schemas used for reading models becaise we don't always want all the information returned
#The course does not contain a foreign key becaus eits not related to the other two

# ---------- Users ----------
class UserCreate(BaseModel):
    name: NameStr
    email: EmailStr
    age: AgeInt
    student_id: StudentIdStr

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int #inlcude the ID so we can look them up later on 
    name: NameStr
    email: EmailStr
    age: AgeInt
    student_id: StudentIdStr

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    student_id: Optional[str] = None

# Optionally return users with their projects
class ProjectRead(BaseModel): #when we're creating a project, we put in the following parameters
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: ProjectNameStr
    description: Optional[DescStr] = None
    owner_id: int

class UserReadWithProjects(UserRead):
    projects: List[ProjectRead] = []



# ---------- Projects ----------
# Flat route: POST /api/projects (owner_id in body)
class ProjectCreate(BaseModel):
    name: ProjectNameStr
    description: Optional[DescStr] = None
    owner_id: int

# Nested route: POST /api/users/{user_id}/projects (owner implied by path)
class ProjectCreateForUser(BaseModel):
    name: ProjectNameStr
    description: Optional[DescStr] = None

class ProjectReadWithOwner(ProjectRead):
    owner: Optional["UserRead"] = None # use selectinload(ProjectDB.owner) when querying

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[DescStr] = None
    owner_id: Optional[int] = None

# ---------- Courses ----------
class CourseCreate(BaseModel):
    code: CodeStr
    name: CourseNameStr
    credits: CreditsInt

class CourseRead(CourseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int