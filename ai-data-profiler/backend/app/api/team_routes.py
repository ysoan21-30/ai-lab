"""Team workspace CRUD + member management routes (TEAM plan)."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import PlanTier, Team, TeamMember, TeamRole, User
from app.schemas.schemas import TeamCreate, TeamInvite, TeamMemberOut, TeamOut
from app.services.audit_service import log_action
from app.services.notification_service import send_email

router = APIRouter(prefix="/api/teams", tags=["teams"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "team"


def _require_team_plan(user: User):
    if user.plan != PlanTier.TEAM:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Team features require the Team plan.")


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_team_plan(user)

    slug = _slugify(payload.name)
    # Ensure unique slug
    existing = db.query(Team).filter(Team.slug == slug).first()
    if existing:
        slug = f"{slug}-{str(user.id)[:8]}"

    team = Team(name=payload.name, slug=slug, owner_id=user.id)
    db.add(team)
    db.flush()

    # Add owner as first member
    membership = TeamMember(team_id=team.id, user_id=user.id, role=TeamRole.OWNER)
    db.add(membership)
    db.commit()
    db.refresh(team)

    log_action(db, user_id=user.id, team_id=team.id, action="create",
               resource_type="team", resource_id=team.id)

    result = TeamOut.model_validate(team)
    result.member_count = 1
    return result


@router.get("", response_model=list[TeamOut])
def list_teams(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    team_ids = [m.team_id for m in memberships]
    teams = db.query(Team).filter(Team.id.in_(team_ids)).all() if team_ids else []
    results = []
    for t in teams:
        out = TeamOut.model_validate(t)
        out.member_count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        results.append(out)
    return results


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def list_members(
    team_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify user is a member
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this team.")

    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    results = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        out = TeamMemberOut(
            id=m.id,
            user_id=m.user_id,
            email=u.email if u else None,
            full_name=u.full_name if u else None,
            role=m.role.value,
            joined_at=m.joined_at,
        )
        results.append(out)
    return results


@router.post("/{team_id}/invite", status_code=status.HTTP_201_CREATED)
def invite_member(
    team_id: str,
    payload: TeamInvite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify inviter is owner or admin
    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == user.id
    ).first()
    if not membership or membership.role not in (TeamRole.OWNER, TeamRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins can invite members.")

    # Find or note the invitee
    invitee = db.query(User).filter(User.email == payload.email.lower()).first()
    if not invitee:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "User not found. They need to register first.")

    # Check not already a member
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == invitee.id
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a team member.")

    try:
        role = TeamRole(payload.role)
    except ValueError:
        role = TeamRole.MEMBER

    new_member = TeamMember(
        team_id=team_id, user_id=invitee.id, role=role, invited_by=user.id
    )
    db.add(new_member)
    db.commit()

    log_action(db, user_id=user.id, team_id=team_id, action="invite",
               resource_type="team_member", resource_id=invitee.id,
               details={"invited_email": payload.email, "role": role.value})

    # Send invitation email
    team = db.query(Team).filter(Team.id == team_id).first()
    send_email(
        to=payload.email,
        subject=f"You've been invited to {team.name if team else 'a team'} on AI Data Profiler",
        html_body=f"<p>{user.full_name or user.email} invited you to join their team. "
                  f"Log in to start collaborating.</p>",
    )

    return {"message": f"Invited {payload.email} as {role.value}"}


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    team_id: str,
    member_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify requester is owner/admin or removing themselves
    requester = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == user.id
    ).first()
    target = db.query(TeamMember).filter(
        TeamMember.id == member_id, TeamMember.team_id == team_id
    ).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found.")

    is_self = target.user_id == user.id
    is_privileged = requester and requester.role in (TeamRole.OWNER, TeamRole.ADMIN)

    if not is_self and not is_privileged:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to remove this member.")

    if target.role == TeamRole.OWNER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove team owner.")

    db.delete(target)
    db.commit()
