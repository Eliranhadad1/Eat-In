import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Table, Boolean, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Support both local and Home Assistant environments
DB_PATH = "/data/eatin.db" if os.path.exists("/data") else "eatin.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Many-to-many: recipes <-> tags
recipe_tags = Table(
    'recipe_tags',
    Base.metadata,
    Column('recipe_id', Integer, ForeignKey('recipes.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    source_url = Column(String, nullable=True)
    prep_time = Column(String, nullable=True)
    cook_time = Column(String, nullable=True)       # NEW
    servings = Column(String, nullable=True)
    rating = Column(Integer, default=0)             # NEW: 0–5 stars
    is_favorite = Column(Boolean, default=False)    # NEW: heart toggle
    last_made = Column(DateTime, nullable=True)     # NEW: last cooked date
    created_at = Column(DateTime, default=datetime.utcnow)

    ingredients = relationship("Ingredient", back_populates="recipe", cascade="all, delete-orphan")
    instructions = relationship("Instruction", back_populates="recipe", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=recipe_tags, backref="recipes")
    images = relationship("RecipeImage", back_populates="recipe", cascade="all, delete-orphan")

class RecipeImage(Base):
    __tablename__ = "recipe_images"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    image_path = Column(String)
    recipe = relationship("Recipe", back_populates="images")

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    amount = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    name = Column(String)
    note = Column(String, nullable=True)
    recipe = relationship("Recipe", back_populates="ingredients")

class Instruction(Base):
    __tablename__ = "instructions"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    section = Column(String, default="כללי")
    step_order = Column(Integer)
    text = Column(Text)
    recipe = relationship("Recipe", back_populates="instructions")


def _migrate(conn, table, col, col_type, default=None):
    """Add a column to an existing table if it doesn't already exist."""
    inspector = inspect(engine)
    existing = [c['name'] for c in inspector.get_columns(table)]
    if col not in existing:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}{default_clause}"))


def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe migrations for existing databases that predate new columns
    with engine.connect() as conn:
        _migrate(conn, 'recipes', 'rating',      'INTEGER',  0)
        _migrate(conn, 'recipes', 'is_favorite', 'BOOLEAN',  0)
        _migrate(conn, 'recipes', 'last_made',   'DATETIME')
        _migrate(conn, 'recipes', 'cook_time',   'VARCHAR')
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")