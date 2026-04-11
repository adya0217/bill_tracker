"""Category model for bill items."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Category(Base):
    """Product categories for bill item organisation."""
    __tablename__ = "categories"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)


    parent_category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    icon_code = Column(String(50), nullable=True)   # for frontend icons

    # ── Relationships
    bill_items = relationship("BillItem", back_populates="category")

    # Self-referential: children categories
    children = relationship(
        "Category",
        backref   = __import__("sqlalchemy.orm", fromlist=["backref"])
                    .backref("parent", remote_side="Category.id"),
        lazy      = "select",
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name='{self.name}'>"
