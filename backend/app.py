import json
import sqlite3
from contextlib import asynccontextmanager

from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = "database.db"

def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def create_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            column TEXT NOT NULL,
            fields_data TEXT DEFAULT '{}'
        )
    """)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando a aplicação e configurando o banco de dados")
    conn = sqlite3.connect(DATABASE_URL)
    create_table(conn)
    conn.close()

    yield

    print("Encerrando a aplicação...")

app = FastAPI(
    title="Simple Kanban API",
    description="Backend de Kanban com FastAPI e SQLite para demonstração",
    version="1.0.0",
    lifespan=lifespan
)

origins = [
    'http://localhost',
    'http://localhost:8000',
    'http://localhost:8080',
    'http://127.0.0.1:5500',
    'file://',
    'null'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class CardBase(BaseModel):
    title: str
    column: str
    fields_data: Optional[Dict[str, Any]] = None

class CardCreate(CardBase):
    pass

class CardUpdate(CardBase):
    title: Optional[str] = None
    column: Optional[str] = None
    fields_data: Optional[Dict[str, Any]] = None

class CardInDB(CardBase):
    id: Optional[int] = None


@app.get('/')
async def read_root():
    return {"message": "Bem-vindo à API do Kanban!"}


@app.get('/cards', response_model=List[CardInDB])
async def get_cards(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, column FROM cards")
    cards = cursor.fetchall()

    parsed_cards = []
    for card in cards:
        card_dict = dict(card)
        if card_dict['fields_data']:
            card_dict['fields_data'] = json.loads(card_dict['fields_data'])
        else:
            card_dict['fields_data'] = {}
        parsed_cards.append(CardInDB(**card_dict))
    return parsed_cards


@app.get('/cards/{card_id}', response_model=CardInDB)
async def get_card(card_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, column FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()
    if card:
        card_dict = dict(card)
        if card_dict['fields_data']:
            card_dict['fields_data'] = json.loads(card_dict['fields_data'])
        else:
            card_dict['fields_data'] = {}
        return CardInDB(**card_dict)
    raise HTTPException(status_code=404, detail="Card não encontrado")


@app.post('/cards', response_model=CardInDB, status_code=201)
async def create_card(card: CardCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()

    fields_data_json = json.dumps(card.fields_data)

    cursor.execute(
        "INSERT INTO cards (title, column, fields_data) VALUES (?, ?, ?)",
        (card.title, card.column, fields_data_json)
    )
    db.commit()
    card_id = cursor.lastrowid
    return CardInDB(id=card_id, **card.model_dump())


@app.put("/cards/{card_id}", response_model=CardInDB)
async def update_card(card_id: int, updated_card: CardUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT fields_data FROM cards WHERE id = ?", (card_id,))
    existing_fields_data_raw = cursor.fetchone()
    if not existing_fields_data_raw:
        raise HTTPException(status_code=404, detail="Card não encontrado")

    existing_fields_data = json.loads(existing_fields_data_raw['fields_data']) if existing_fields_data_raw['fields_data'] else {}

    if updated_card.fields_data is not None:
        merged_fields_data = {**existing_fields_data, **updated_card.fields_data}
    else:
        merged_fields_data = existing_fields_data
    
    fields_data_json = json.dumps(merged_fields_data)
    
    update_fields = []
    update_values = []
    if updated_card.title is not None:
        update_fields.append("title = ?")
        update_values.append(updated_card.title)
    if updated_card.column is not None:
        update_fields.append("column_name = ?")
        update_values.append(updated_card.column)
    
    update_fields.append("fields_data = ?")
    update_values.append(fields_data_json)

    if not update_fields:
        return await get_card(card_id, db)
    
    query = f"UPDATE cards SET {', '.join(update_fields)} WHERE id = ?"
    update_values.append(card_id)
    
    cursor.execute(query, tuple(update_values))
    db.commit()

    return await get_card(card_id, db)


@app.delete("/cards/{card_id}", status_code=204)
async def delete_card(card_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    return {"message": "Card deletado com sucesso"}