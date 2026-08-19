"""Custom quality rules CRUD + evaluation routes (PRO + TEAM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import CustomRule, PlanTier, RuleOperator, AlertSeverity, User
from app.profiling.loader import load_dataset
from app.schemas.schemas import CustomRuleCreate, CustomRuleOut, RuleEvaluationResult
from app.services.rules_engine import evaluate_rules

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _require_pro_or_team(user: User):
    if user.plan == PlanTier.FREE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Custom rules require Pro or Team plan.")


@router.post("", response_model=CustomRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: CustomRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    try:
        op = RuleOperator(payload.operator)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid operator: {payload.operator}")

    try:
        severity = AlertSeverity(payload.severity)
    except ValueError:
        severity = AlertSeverity.WARNING

    rule = CustomRule(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        column_name=payload.column_name,
        operator=op,
        value=payload.value,
        severity=severity,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("", response_model=list[CustomRuleOut])
def list_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_pro_or_team(user)
    return (
        db.query(CustomRule)
        .filter(CustomRule.user_id == user.id)
        .order_by(CustomRule.created_at.desc())
        .all()
    )


@router.put("/{rule_id}", response_model=CustomRuleOut)
def update_rule(
    rule_id: str,
    payload: CustomRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(CustomRule).filter(
        CustomRule.id == rule_id, CustomRule.user_id == user.id
    ).first()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found.")

    try:
        op = RuleOperator(payload.operator)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid operator: {payload.operator}")

    rule.name = payload.name
    rule.description = payload.description
    rule.column_name = payload.column_name
    rule.operator = op
    rule.value = payload.value
    try:
        rule.severity = AlertSeverity(payload.severity)
    except ValueError:
        pass
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(CustomRule).filter(
        CustomRule.id == rule_id, CustomRule.user_id == user.id
    ).first()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found.")
    db.delete(rule)
    db.commit()


@router.patch("/{rule_id}/toggle")
def toggle_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.query(CustomRule).filter(
        CustomRule.id == rule_id, CustomRule.user_id == user.id
    ).first()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found.")
    rule.is_active = not rule.is_active
    db.commit()
    return {"is_active": rule.is_active}


@router.post("/evaluate", response_model=list[RuleEvaluationResult])
async def evaluate_against_file(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a file and evaluate all active rules against it."""
    _require_pro_or_team(user)

    rules = (
        db.query(CustomRule)
        .filter(CustomRule.user_id == user.id, CustomRule.is_active == True)
        .all()
    )
    if not rules:
        return []

    raw = await file.read()
    try:
        loaded = load_dataset(raw, file.filename or "upload.csv", max_size_bytes=500 * 1024 * 1024)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to load file: {e}")

    results = evaluate_rules(rules, loaded.df)
    return [RuleEvaluationResult(**r) for r in results]
