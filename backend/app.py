import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

DATABASE_URL = "database.db"

def create_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            column_name TEXT NOT NULL
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

class Card(BaseModel):
    id: Optional[int] = None
    title: str
    column: str

def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

@app.get('/')
async def read_root():
    return {"message": "Bem-vindo à API do Kanban!"}

@app.get('/cards', response_model=List[Card])
async def get_cards(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, column FROM cards")
    cards = cursor.fetchall()
    return [Card(**dict(card)) for card in cards]

@app.get('/cards/{card_id}', response_model=Card)
async def get_card(card_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, column FROM cards WHERE id = ?", (card_id,))
    card = cursor.fetchone()
    if card:
        return Card
    raise HTTPException(status_code=404, detail="Card não encontrado")

@app.post('/cards', response_model=Card, status_code=201)
async def create_card(card: Card, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO cards (title, column)",
        (card.title, card.column)
    )
    db.commit()
    card.id = cursor.lastrowid
    return card

@app.put("/cards/{card_id}", response_model=Card)
async def update_card(card_id: int, updated_card: Card, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
    existing_card = cursor.fetchone()
    if not existing_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    
    cursor.execute(
        "UPDATE cards SET title = ?, column = ?",
        (updated_card.title, updated_card.column)
    )
    db.commit()
    updated_card.id = card_id
    return updated_card

@app.delete("/cards/{card_id}", status_code=204)
async def delete_card(card_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    return {"message": "Card deletado com sucesso"}