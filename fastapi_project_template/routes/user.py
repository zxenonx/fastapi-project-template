from typing import List, Union

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from sqlmodel import Session, or_, select

from ..db import ActiveSession
from ..security import (
    AdminUser,
    AuthenticatedUser,
    HashedPassword,
    User,
    UserCreate,
    UserPasswordPatch,
    UserResponse,
    get_current_user,
)

router = APIRouter()


@router.get("/", response_model=List[UserResponse], dependencies=[AdminUser])
async def list_users(*, session: Session = ActiveSession):
    return session.exec(select(User)).all()


@router.post("/", response_model=UserResponse, dependencies=[AdminUser])
async def create_user(*, session: Session = ActiveSession, user: UserCreate):
    db_user = User.from_orm(user)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.patch(
    "/{user_id}/password/",
    response_model=UserResponse,
    dependencies=[AuthenticatedUser],
)
async def update_user_password(
    *,
    user_id: int,
    session: Session = ActiveSession,
    request: Request,
    patch: UserPasswordPatch,
):
    # Query the content
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check the user can update the password
    current_user: User = get_current_user(request=request)
    if user.id != current_user.id and not current_user.superuser:
        raise HTTPException(
            status_code=403, detail="You can't update this user password"
        )

    if patch.password != patch.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords don't match")

    # Update the password
    user.password = HashedPassword(patch.password)

    # Commit the session
    session.commit()
    session.refresh(user)
    return user


@router.get(
    "/{user_id_or_username}/",
    response_model=UserResponse,
    dependencies=[AuthenticatedUser],
)
async def query_user(
    *, session: Session = ActiveSession, user_id_or_username: Union[str, int]
):
    if user := session.query(User).where(
        or_(
            User.id == user_id_or_username,
            User.username == user_id_or_username,
        )
    ):
        return user.first()
    else:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/me/", response_model=UserResponse)
async def my_profile(current_user: User = AuthenticatedUser):
    return current_user


@router.delete("/{user_id}/", dependencies=[AdminUser])
def delete_user(
    *, session: Session = ActiveSession, request: Request, user_id: int
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Content not found")
    # Check the user is not deleting himself
    current_user = get_current_user(request=request)
    if user.id == current_user.id:
        raise HTTPException(
            status_code=403, detail="You can't delete yourself"
        )
    session.delete(user)
    session.commit()
    return {"ok": True}
