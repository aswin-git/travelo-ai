from sqlalchemy.orm import Session
from ..models.place_model import Place

def get_place_by_name(db: Session, name: str) -> Place:
    """Case-insensitive search for a place by name in DB."""
    return db.query(Place).filter(Place.name.ilike(f"%{name}%")).first()

def create_place(db: Session, place_data: dict) -> Place:
    """Creates a new place record in the database."""
    db_place = Place(**place_data)
    db.add(db_place)
    db.commit()
    db.refresh(db_place)
    return db_place
