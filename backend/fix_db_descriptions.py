from app.database import SessionLocal
from app.models.place_model import Attraction

db = SessionLocal()
empty_attrs = db.query(Attraction).filter(Attraction.description == '').all()
count = len(empty_attrs)
for a in empty_attrs:
    db.delete(a)
db.commit()
print(f"Deleted {count} attractions with empty descriptions from DB.")
