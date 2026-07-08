from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Entity
from ..schemas import EntityCreate, EntityCreated, EntityOut, RotateOut
from ..services import registry

router = APIRouter(prefix="/entities", tags=["entities"])


@router.post("", response_model=EntityCreated, status_code=201)
def create_entity(body: EntityCreate, db: Session = Depends(get_db)):
    if db.query(Entity).filter(Entity.name == body.name).first():
        raise HTTPException(status_code=409, detail="entity name already registered")
    try:
        entity, private_pem = registry.create_entity(
            db, body.name, body.type, body.public_key_pem
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    out = EntityCreated.model_validate(entity)
    out.private_key_pem = private_pem
    return out


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: str, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return entity


@router.post("/{entity_id}/keys/rotate", response_model=RotateOut)
def rotate_key(entity_id: str, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    new_key, private_pem = registry.rotate_key(db, entity)
    return RotateOut(
        entity_id=entity_id,
        key_id=new_key.id,
        public_key_pem=new_key.public_key_pem,
        private_key_pem=private_pem,
    )
