from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BinCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{2,32}$")
    name: str = Field(min_length=1, max_length=100)
    zone_id: int
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    capacity_liters: float = Field(default=120, gt=0)


class ReadingIn(BaseModel):
    fill_level: float = Field(ge=0, le=100)


class CollectionIn(BaseModel):
    bin_id: int
    weight_kg: float | None = Field(default=None, ge=0)
