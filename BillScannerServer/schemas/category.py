"""Category schemas — no logic changes, added model_config."""

from pydantic import BaseModel
from typing import Optional


class CategoryCreate(BaseModel):
    name:               str
    description:        Optional[str] = None
    parent_category_id: Optional[int] = None


class CategoryResponse(BaseModel):
    id:                 int
    name:               str
    description:        Optional[str] = None
    parent_category_id: Optional[int] = None

    model_config = {"from_attributes": True}
