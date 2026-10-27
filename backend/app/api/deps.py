from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Listing, Profile, Vehicle

DB = Depends(get_db)


def get_listing(session: Session, listing_id: int) -> Listing:
    listing = session.scalar(select(Listing).options(selectinload(Listing.prices)).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(404, "Advertentie niet gevonden")
    return listing


def get_vehicle(session: Session, listing: Listing) -> Vehicle | None:
    return session.get(Vehicle, listing.kenteken) if listing.kenteken else None


def get_profile(session: Session, profile_id: int | None) -> Profile | None:
    if profile_id is None:
        return session.scalar(select(Profile).order_by(Profile.id).limit(1))
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(404, "Profiel niet gevonden")
    return profile
