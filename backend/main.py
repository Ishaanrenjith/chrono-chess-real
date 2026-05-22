# ==============================================================================
# LocalChess Python Backend (FastAPI + MySQL/SQLite + SQLAlchemy)
# Advanced "Command Center" Version 9.1 (Premium, Incognito & Stability Updates)
# ==============================================================================

import os
import time
import uuid
import asyncio
import secrets
import random
import urllib.parse
from typing import List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- SQLAlchemy Database Imports ---
from sqlalchemy import create_engine, Column, String, Float, Boolean, Integer, JSON, text, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.mysql import LONGTEXT

app = FastAPI(title="LocalChess Radar API", version="9.1")

# Open CORS Policy (Configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. DATABASE SETUP & AUTO-FALLBACK
# ==========================================
# Securely load credentials from environment variables, fallback to local defaults
MYSQL_USER = os.getenv("DB_USER", "root")
MYSQL_PASSWORD = os.getenv("DB_PASS", "ishaan$?$2011")
MYSQL_HOST = os.getenv("DB_HOST", "localhost")
MYSQL_DB = os.getenv("DB_NAME", "localchess_db")

# Admin configuration
ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "supersecret")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "ishaanrenjith0@gmail.com")

safe_password = urllib.parse.quote_plus(MYSQL_PASSWORD)
auth_string = f"{MYSQL_USER}:{safe_password}@"

SERVER_URL = f"mysql+pymysql://{auth_string}{MYSQL_HOST}:3306/"
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{auth_string}{MYSQL_HOST}:3306/{MYSQL_DB}"

engine = None

# TRY-EXCEPT block for seamless fallback to SQLite if MySQL fails
try:
    server_engine = create_engine(SERVER_URL, pool_pre_ping=True)
    with server_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}"))

    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        pass  # Test connection
    print("\n=== ✅ MySQL CONNECTED SUCCESSFULLY ===\n")
except Exception as e:
    print(f"\n=== ❌ MySQL CONNECTION FAILED: {e} ===")
    print("=== ⚠️ FALLING BACK TO LOCAL SQLITE DATABASE (localchess.db) ===\n")
    engine = create_engine("sqlite:///./localchess.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Database Models ---
class DBPlayer(Base):
    __tablename__ = "players"
    id = Column(String(255), primary_key=True, index=True)
    name = Column(String(255))
    avatar = Column(String(500))
    status = Column(String(500))
    about = Column(String(1000))
    baseLocation = Column(String(255))
    isOnline = Column(Boolean, default=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    wins = Column(Integer, default=0)
    elo = Column(Integer)
    platform = Column(String(50))
    linkedUsername = Column(String(255))
    hasRanked = Column(Boolean, default=False)
    isPremium = Column(Boolean, default=False)
    isIncognito = Column(Boolean, default=False)
    updatedAt = Column(Float)


class DBMessage(Base):
    __tablename__ = "messages"
    id = Column(String(255), primary_key=True, index=True)
    senderId = Column(String(255), index=True)
    recipientId = Column(String(255), index=True)
    senderName = Column(String(255))
    recipientName = Column(String(255))
    senderAvatar = Column(String(500))
    recipientAvatar = Column(String(500))
    text = Column(String(1000))
    location = Column(String(500))
    time = Column(String(255))
    format = Column(String(255))
    status = Column(String(50), default="pending")
    read = Column(Boolean, default=False)
    chatLogs = Column(JSON, default=list)
    timestamp = Column(Float)
    salt = Column(String(255), default=lambda: secrets.token_hex(16))


class DBMarketItem(Base):
    __tablename__ = "market_items"
    id = Column(String(255), primary_key=True, index=True)
    sellerId = Column(String(255), index=True)
    sellerName = Column(String(255))
    sellerAvatar = Column(String(500))
    title = Column(String(255))
    price = Column(Float)
    description = Column(String(1000))
    imageUrl = Column(String(1000000), nullable=True)  # Text length safe for SQLite & MySQL
    lat = Column(Float)
    lng = Column(Float)
    views = Column(Integer, default=0)
    interactions = Column(Integer, default=0)
    timestamp = Column(Float)


class DBReport(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reporterId = Column(String(255))
    reportedUserId = Column(String(255))
    reason = Column(String(255))
    details = Column(String(2000))
    timestamp = Column(Float, default=time.time)


# Initialize DB
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"\n[CRITICAL ERROR] Failed to create tables. Error: {e}\n")

# Auto-Migrations
try:
    with engine.begin() as conn:
        migrations = [
            "ALTER TABLE players ADD COLUMN lat FLOAT;",
            "ALTER TABLE players ADD COLUMN lng FLOAT;",
            "ALTER TABLE players ADD COLUMN wins INTEGER DEFAULT 0;",
            "ALTER TABLE players ADD COLUMN elo INTEGER;",
            "ALTER TABLE players ADD COLUMN platform VARCHAR(50);",
            "ALTER TABLE players ADD COLUMN linkedUsername VARCHAR(255);",
            "ALTER TABLE players ADD COLUMN updatedAt FLOAT;",
            "ALTER TABLE players ADD COLUMN hasRanked BOOLEAN DEFAULT 0;",
            "ALTER TABLE players ADD COLUMN isPremium BOOLEAN DEFAULT 0;",
            "ALTER TABLE players ADD COLUMN isIncognito BOOLEAN DEFAULT 0;",
            "ALTER TABLE market_items ADD COLUMN imageUrl LONGTEXT;",
            "ALTER TABLE market_items ADD COLUMN views INTEGER DEFAULT 0;",
            "ALTER TABLE market_items ADD COLUMN interactions INTEGER DEFAULT 0;",
            "ALTER TABLE messages ADD COLUMN timestamp FLOAT;",
            "ALTER TABLE messages ADD COLUMN chatLogs JSON;",
            "ALTER TABLE messages ADD COLUMN `read` BOOLEAN DEFAULT 0;",
            "ALTER TABLE messages ADD COLUMN format VARCHAR(255);",
            "ALTER TABLE messages ADD COLUMN salt VARCHAR(255);"
        ]
        for query in migrations:
            try:
                conn.execute(text(query))
            except Exception:
                pass  # Ignore if column exists
except Exception as e:
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# 2. ADVANCED ERROR LOGGING
# ==========================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    print("\n--- 422 VALIDATION ERROR ---")
    print(f"Errors: {exc.errors()}")
    print(f"Body Received: {body.decode()}")
    print("----------------------------\n")
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": body.decode()})


# ==========================================
# 3. PYDANTIC MODELS (API Validation)
# ==========================================
class Coordinates(BaseModel):
    lat: float
    lng: float


class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    status: Optional[str] = None
    about: Optional[str] = None
    baseLocation: Optional[str] = None
    isOnline: Optional[bool] = None
    hasRanked: Optional[bool] = None
    isPremium: Optional[bool] = None
    isIncognito: Optional[bool] = None
    coords: Optional[Coordinates] = None


class AdminPlayerUpdate(BaseModel):
    name: Optional[str] = None
    elo: Optional[int] = None
    wins: Optional[int] = None
    status: Optional[str] = None


class Player(BaseModel):
    id: str
    name: Optional[str] = "Anonymous"
    avatar: Optional[str] = ""
    status: Optional[str] = "Hey!"
    about: Optional[str] = ""
    baseLocation: Optional[str] = ""
    coords: Optional[Coordinates] = None
    isOnline: Optional[bool] = False
    hasRanked: Optional[bool] = False
    isPremium: Optional[bool] = False
    isIncognito: Optional[bool] = False


class MarketItemCreate(BaseModel):
    sellerId: str
    sellerName: str
    sellerAvatar: str
    title: str
    price: float
    description: str
    imageUrl: str
    coords: Coordinates


class ChatLog(BaseModel):
    senderId: str
    text: str
    audioBase64: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class MatchMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    senderId: str
    recipientId: str
    senderName: str
    recipientName: str
    senderAvatar: str
    recipientAvatar: str
    text: str
    location: str
    time: str
    format: str
    status: str = "pending"
    read: bool = False
    chatLogs: List[ChatLog] = []
    timestamp: float = Field(default_factory=time.time)
    salt: str = Field(default_factory=lambda: secrets.token_hex(16))


class MessageUpdate(BaseModel):
    read: Optional[bool] = None
    status: Optional[str] = None
    winnerId: Optional[str] = None


class ReportModel(BaseModel):
    reporterId: str
    reportedUserId: str
    reason: str
    details: str


class BroadcastModel(BaseModel):
    message: str


class AdminCheckRequest(BaseModel):
    email: str
    uid: str


# ==========================================
# 4. WEBSOCKET MANAGER
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception:
                pass

    async def broadcast_radar_update(self, player_data: dict):
        for uid, connection in list(self.active_connections.items()):
            if uid != player_data.get("id"):
                try:
                    await connection.send_json({"type": "RADAR_UPDATE", "data": player_data})
                except Exception:
                    pass

    async def broadcast_announcement(self, text_msg: str):
        for uid, connection in list(self.active_connections.items()):
            try:
                await connection.send_json({"type": "SERVER_ANNOUNCEMENT", "data": text_msg})
            except Exception:
                pass


manager = ConnectionManager()


def format_player(p: DBPlayer):
    return {
        "id": p.id, "name": p.name, "avatar": p.avatar, "status": p.status,
        "about": p.about, "baseLocation": p.baseLocation, "isOnline": p.isOnline,
        "coords": {"lat": p.lat, "lng": p.lng} if p.lat is not None else None,
        "wins": p.wins, "elo": p.elo, "platform": p.platform,
        "linkedUsername": p.linkedUsername, "updatedAt": p.updatedAt,
        "hasRanked": getattr(p, "hasRanked", False),
        "isPremium": getattr(p, "isPremium", False),
        "isIncognito": getattr(p, "isIncognito", False)
    }


def format_message(m: DBMessage):
    return {
        "id": m.id, "senderId": m.senderId, "recipientId": m.recipientId,
        "senderName": m.senderName, "recipientName": m.recipientName,
        "senderAvatar": m.senderAvatar, "recipientAvatar": m.recipientAvatar,
        "text": m.text, "location": m.location, "time": m.time, "format": m.format,
        "status": m.status, "read": m.read, "chatLogs": m.chatLogs, "timestamp": m.timestamp,
        "salt": m.salt
    }


def format_market_item(i: DBMarketItem):
    return {
        "id": i.id, "sellerId": i.sellerId, "sellerName": i.sellerName,
        "sellerAvatar": i.sellerAvatar, "title": i.title, "price": i.price,
        "description": i.description, "imageUrl": getattr(i, "imageUrl", None),
        "views": getattr(i, "views", 0), "interactions": getattr(i, "interactions", 0),
        "coords": {"lat": i.lat, "lng": i.lng} if i.lat is not None else None,
        "timestamp": i.timestamp
    }


# ==========================================
# ADMIN PANEL SECURITY
# ==========================================
security_basic = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security_basic)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ==========================================
# 5. PUBLIC REST API ENDPOINTS
# ==========================================
@app.get("/")
def health_check():
    return {"status": "LocalChess Command Center Backend is Active", "version": "9.1"}


@app.post("/api/admin/check")
async def check_admin_status(req: AdminCheckRequest):
    if req.email and req.email.lower() == ADMIN_EMAIL.lower():
        return {"isAdmin": True}
    return {"isAdmin": False}


@app.get("/api/players/{user_id}")
async def get_player(user_id: str, db: Session = Depends(get_db)):
    db_player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="Player not found")
    return format_player(db_player)


@app.post("/api/players")
async def create_or_update_player(player: Player, db: Session = Depends(get_db)):
    try:
        db_player = db.query(DBPlayer).filter(DBPlayer.id == player.id).first()

        if not db_player:
            db_player = DBPlayer(
                id=player.id,
                elo=1200,
                wins=0,
                platform="local",
                linkedUsername="none",
                hasRanked=False,
                isPremium=False,
                isIncognito=False
            )
            db.add(db_player)

        db_player.name = player.name
        db_player.avatar = player.avatar
        db_player.status = player.status
        db_player.about = player.about
        db_player.baseLocation = player.baseLocation
        db_player.isOnline = player.isOnline
        db_player.hasRanked = player.hasRanked
        db_player.isPremium = player.isPremium
        db_player.isIncognito = player.isIncognito
        db_player.updatedAt = time.time()

        if player.coords:
            db_player.lat = player.coords.lat
            db_player.lng = player.coords.lng

        db.commit()
        db.refresh(db_player)
        return {"status": "success", "player": format_player(db_player)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database save error: {str(e)}")


@app.patch("/api/players/{user_id}")
async def patch_player(user_id: str, updates: PlayerUpdate, db: Session = Depends(get_db)):
    db_player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="Player not found")

    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "coords" and value:
            db_player.lat = value["lat"]
            db_player.lng = value["lng"]
        elif hasattr(db_player, key):
            setattr(db_player, key, value)

    db_player.updatedAt = time.time()
    try:
        db.commit()
        db.refresh(db_player)
        formatted = format_player(db_player)

        # Broadcast critical state changes
        if any(k in update_data for k in ("coords", "isOnline", "isIncognito", "isPremium", "hasRanked")):
            await manager.broadcast_radar_update(formatted)

        return {"status": "success", "player": formatted}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database save error: {str(e)}")


@app.get("/api/players")
async def get_active_players(db: Session = Depends(get_db)):
    players = db.query(DBPlayer).order_by(DBPlayer.updatedAt.desc()).limit(500).all()
    return [format_player(p) for p in players]


# --- MARKETPLACE ENDPOINTS ---
@app.post("/api/market")
async def create_market_item(item: MarketItemCreate, db: Session = Depends(get_db)):
    try:
        db_item = DBMarketItem(
            id=str(uuid.uuid4()),
            sellerId=item.sellerId,
            sellerName=item.sellerName,
            sellerAvatar=item.sellerAvatar,
            title=item.title,
            price=item.price,
            description=item.description,
            imageUrl=item.imageUrl,
            lat=item.coords.lat,
            lng=item.coords.lng,
            timestamp=time.time()
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return {"status": "success", "item": format_market_item(db_item)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database save error: {str(e)}")


@app.get("/api/market")
async def get_market_items(db: Session = Depends(get_db)):
    items = db.query(DBMarketItem).order_by(DBMarketItem.timestamp.desc()).limit(100).all()
    return [format_market_item(i) for i in items]


@app.get("/api/market/seller/{seller_id}")
async def get_seller_items(seller_id: str, db: Session = Depends(get_db)):
    items = db.query(DBMarketItem).filter(DBMarketItem.sellerId == seller_id).order_by(
        DBMarketItem.timestamp.desc()).all()
    return [format_market_item(i) for i in items]


@app.post("/api/market/{item_id}/view")
async def increment_market_view(item_id: str, db: Session = Depends(get_db)):
    item = db.query(DBMarketItem).filter(DBMarketItem.id == item_id).first()
    if item:
        item.views = (getattr(item, 'views', 0) or 0) + 1
        db.commit()
    return {"status": "success"}


@app.delete("/api/market/{item_id}")
async def delete_market_item(item_id: str, user_id: str, db: Session = Depends(get_db)):
    item = db.query(DBMarketItem).filter(DBMarketItem.id == item_id).first()
    if item:
        if item.sellerId == user_id:
            db.delete(item)
            db.commit()
            return {"status": "success"}
        else:
            raise HTTPException(status_code=403, detail="Unauthorized")
    raise HTTPException(status_code=404, detail="Item not found.")


# --- CHAT / MESSAGE ENDPOINTS ---
@app.post("/api/messages")
async def create_match_request(msg: MatchMessage, db: Session = Depends(get_db)):
    db_msg = DBMessage(**msg.dict())
    db.add(db_msg)
    db.commit()
    await manager.send_personal_message({"type": "NEW_MATCH_REQUEST", "data": format_message(db_msg)}, msg.recipientId)
    return {"status": "success", "messageId": msg.id}


@app.get("/api/messages/{user_id}")
async def get_user_messages(user_id: str, db: Session = Depends(get_db)):
    msgs = db.query(DBMessage).filter(or_(DBMessage.recipientId == user_id, DBMessage.senderId == user_id)).order_by(
        DBMessage.timestamp.desc()).all()
    return [format_message(m) for m in msgs]


@app.post("/api/messages/{msg_id}/chat")
async def send_chat_log(msg_id: str, chat: ChatLog, db: Session = Depends(get_db)):
    db_msg = db.query(DBMessage).filter(DBMessage.id == msg_id).first()
    if not db_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    current_logs = list(db_msg.chatLogs)
    current_logs.append(chat.dict())
    db_msg.chatLogs = current_logs

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_msg, "chatLogs")
    db.commit()

    target_id = db_msg.recipientId if chat.senderId == db_msg.senderId else db_msg.senderId
    await manager.send_personal_message({"type": "CHAT_UPDATE", "messageId": msg_id, "chat": chat.dict()}, target_id)
    return {"status": "success"}


@app.patch("/api/messages/{msg_id}")
async def update_message(msg_id: str, updates: MessageUpdate, db: Session = Depends(get_db)):
    db_msg = db.query(DBMessage).filter(DBMessage.id == msg_id).first()
    if not db_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if updates.read is not None:
        db_msg.read = updates.read
    if updates.status is not None:
        db_msg.status = updates.status

    if updates.winnerId is not None:
        current_logs = list(db_msg.chatLogs)
        current_logs.append(
            {"senderId": "system", "text": "🏆 Match concluded! Winner confirmed.", "timestamp": time.time()})

        winner = db.query(DBPlayer).filter(DBPlayer.id == updates.winnerId).first()
        loser_id = db_msg.senderId if db_msg.recipientId == updates.winnerId else db_msg.recipientId
        loser = db.query(DBPlayer).filter(DBPlayer.id == loser_id).first()

        if winner and loser:
            winner.wins = (winner.wins or 0) + 1

            # ADVANCED ZERO-SUM ELO CALCULATION
            if winner.hasRanked and loser.hasRanked:
                K = 32
                expected_winner = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
                win_gain = int(round(K * (1 - expected_winner)))

                winner.elo += win_gain
                loser.elo -= win_gain  # Strictly zero-sum preventing inflation

                current_logs.append({
                    "senderId": "system",
                    "text": f"📈 Ranked Update: {winner.name} (+{win_gain} Trophies) | {loser.name} (-{win_gain} Trophies)",
                    "timestamp": time.time()
                })

        db_msg.chatLogs = current_logs
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(db_msg, "chatLogs")

    db.commit()
    db.refresh(db_msg)
    await manager.send_personal_message({"type": "MESSAGE_UPDATED"}, db_msg.senderId)
    await manager.send_personal_message({"type": "MESSAGE_UPDATED"}, db_msg.recipientId)
    return {"status": "success"}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: str, db: Session = Depends(get_db)):
    db_msg = db.query(DBMessage).filter(DBMessage.id == msg_id).first()
    if db_msg:
        db.delete(db_msg)
        db.commit()
    return {"status": "success"}


@app.post("/api/report")
async def submit_report(report: ReportModel, db: Session = Depends(get_db)):
    db_report = DBReport(**report.dict())
    db.add(db_report)
    db.commit()
    return {"status": "Report received."}


# ==========================================
# 6. COMMAND CENTER HTML UI
# ==========================================
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(db: Session = Depends(get_db), admin_username: str = Depends(verify_admin)):
    total_users = db.query(DBPlayer).count()
    online_users = db.query(DBPlayer).filter(DBPlayer.isOnline == True).count()
    total_matches = db.query(DBMessage).count()

    reports = db.query(DBReport).order_by(DBReport.timestamp.desc()).all()
    players = db.query(DBPlayer).order_by(DBPlayer.updatedAt.desc()).all()
    matches = db.query(DBMessage).order_by(DBMessage.timestamp.desc()).limit(20).all()

    matches_html = "".join([
        f"""
        <tr class="border-b border-neutral-800 hover:bg-neutral-800 transition">
            <td class="py-2 px-3 text-xs">{m.senderName} ⚔ {m.recipientName}</td>
            <td class="py-2 px-3 text-xs truncate max-w-[150px]">{m.location}</td>
            <td class="py-2 px-3 text-xs"><span class="px-2 py-1 rounded {'bg-yellow-500/20 text-yellow-500' if m.status == 'pending' else 'bg-green-500/20 text-green-500'} font-bold uppercase">{m.status}</span></td>
        </tr>
        """ for m in matches
    ])

    reports_html = "".join([
        f"""
        <div class="bg-neutral-800 p-4 rounded-xl border-l-4 border-red-500 mb-3 shadow-lg">
            <div class="flex justify-between items-start">
                <div>
                    <h3 class="font-bold text-red-400 text-sm">Target ID: {r.reportedUserId}</h3>
                    <p class="text-xs text-neutral-400 mt-1"><strong>Reason:</strong> {r.reason}</p>
                    <p class="text-neutral-300 mt-2 text-sm">"{r.details}"</p>
                </div>
                <button onclick="dismissReport({r.id})" class="bg-neutral-700 hover:bg-neutral-600 text-white px-3 py-1.5 rounded text-xs font-bold transition">Dismiss</button>
            </div>
        </div>
        """ for r in reports
    ]) or "<p class='text-neutral-500 italic text-sm'>No active reports.</p>"

    players_html = ""
    for p in players:
        status_color = "text-green-500" if p.isOnline else "text-neutral-600"
        safe_name = p.name.replace("'", "\\'") if p.name else ""
        safe_status = p.status.replace("'", "\\'") if p.status else ""

        badges = ""
        if getattr(p, 'isPremium',
                   False): badges += "<span class='text-[10px] bg-yellow-500/20 text-yellow-500 px-1 rounded ml-1 font-bold'>PRO</span>"
        if getattr(p, 'hasRanked',
                   False): badges += "<span class='text-[10px] bg-blue-500/20 text-blue-400 px-1 rounded ml-1'>Ranked</span>"

        players_html += f"""
        <tr class="border-b border-neutral-800 hover:bg-neutral-800 transition">
            <td class="py-3 px-4 flex items-center gap-3">
                <div class="w-2 h-2 rounded-full bg-current {status_color}"></div>
                <img src="{p.avatar}" class="w-8 h-8 rounded-full border border-neutral-700 bg-neutral-900"> 
                <strong class="text-sm">{p.name} {badges}</strong>
            </td>
            <td class="py-3 px-4 text-xs font-mono text-neutral-500">{p.id[:8]}...</td>
            <td class="py-3 px-4 text-sm font-bold text-yellow-500">ELO {p.elo}</td>
            <td class="py-3 px-4 text-right flex justify-end gap-2">
                <button onclick="openEditModal('{p.id}', '{safe_name}', {p.elo}, {p.wins}, '{safe_status}')" class="bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-600/50 px-3 py-1.5 rounded-lg text-xs font-bold transition">Edit</button>
                <button onclick="kickUser('{p.id}')" class="bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 border border-yellow-600/50 px-3 py-1.5 rounded-lg text-xs font-bold transition" title="Force Offline">Kick</button>
                <button onclick="banUser('{p.id}')" class="bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-600/50 px-3 py-1.5 rounded-lg text-xs font-bold transition">Ban</button>
            </td>
        </tr>
        """

    page = f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>God's Eye Command Center</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>tailwind.config = {{ darkMode: 'class' }}</script>
        <style>
            .leaflet-layer, .leaflet-control-zoom-in, .leaflet-control-zoom-out, .leaflet-control-attribution {{
                filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%);
            }}
        </style>
    </head>
    <body class="bg-neutral-950 text-neutral-200 font-sans min-h-screen selection:bg-yellow-500/30">

        <nav class="bg-neutral-900 border-b border-neutral-800 p-4 shadow-2xl sticky top-0 z-40">
            <div class="max-w-7xl mx-auto flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <span class="text-2xl">🌍</span>
                    <h1 class="text-xl font-black uppercase tracking-wider text-white">Command <span class="text-yellow-500">Center</span></h1>
                </div>
                <div class="flex gap-4">
                    <div class="bg-neutral-950 border border-neutral-800 px-4 py-1.5 rounded-lg text-sm font-bold text-neutral-400">Total: <span class="text-white">{total_users}</span></div>
                    <div class="bg-green-500/10 border border-green-500/30 px-4 py-1.5 rounded-lg text-sm font-bold text-green-500">Online: <span>{online_users}</span></div>
                    <div class="bg-blue-500/10 border border-blue-500/30 px-4 py-1.5 rounded-lg text-sm font-bold text-blue-500">Matches: <span>{total_matches}</span></div>
                </div>
            </div>
        </nav>

        <div class="max-w-7xl mx-auto p-6 pt-12 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-1 flex flex-col gap-6">
                <div class="bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl overflow-hidden flex flex-col h-[350px]">
                    <div class="p-3 bg-neutral-950 border-b border-neutral-800 font-bold text-sm uppercase tracking-wider flex justify-between items-center text-neutral-400">
                        <span>God's Eye Radar</span>
                        <div class="w-2 h-2 bg-green-500 rounded-full animate-ping"></div>
                    </div>
                    <div id="adminMap" class="flex-1 w-full bg-neutral-800"></div>
                </div>

                <div class="bg-neutral-900 rounded-2xl border border-neutral-800 p-5 shadow-xl">
                    <h3 class="font-bold text-sm uppercase tracking-wider mb-4 text-neutral-400">Server Controls</h3>
                    <div class="mb-5">
                        <label class="block text-xs font-bold text-neutral-500 mb-2">Global Broadcast Announcement</label>
                        <div class="flex gap-2">
                            <input type="text" id="broadcastText" placeholder="Message to all screens..." class="flex-1 bg-neutral-950 border border-neutral-700 rounded-lg p-2 text-sm text-white focus:ring-1 focus:ring-yellow-500 outline-none">
                            <button onclick="sendBroadcast()" class="bg-yellow-500 hover:bg-yellow-400 text-neutral-950 px-4 py-2 rounded-lg text-sm font-black uppercase transition">Send</button>
                        </div>
                    </div>

                    <div class="border-t border-neutral-800 pt-4">
                        <label class="block text-xs font-bold text-neutral-500 mb-2">Simulation Tools</label>
                        <button onclick="spawnBots()" class="w-full bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 border border-purple-600/50 py-2.5 rounded-lg text-sm font-bold transition flex justify-center items-center gap-2">
                            <span>🤖</span> Spawn 5 Test Bots
                        </button>
                        <button onclick="clearBots()" class="w-full bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-600/50 py-2.5 rounded-lg text-sm font-bold transition flex justify-center items-center gap-2 mt-2">
                            <span>🗑️</span> Clear All Bots
                        </button>
                        <p class="text-[10px] text-neutral-500 mt-2 text-center">Spawns/Clears fake players in Guelph area for UI testing.</p>
                    </div>
                </div>

                <div class="bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl overflow-hidden">
                    <div class="p-3 bg-neutral-950 border-b border-neutral-800 font-bold text-sm uppercase tracking-wider text-neutral-400">Live Match Surveillance</div>
                    <div class="max-h-[250px] overflow-y-auto">
                        <table class="w-full text-left">
                            <tbody class="divide-y divide-neutral-800">{matches_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-2 flex flex-col gap-6">
                <div class="bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl p-5">
                    <h2 class="text-lg font-black mb-4 flex items-center gap-2 text-white"><span class="text-red-500">⚠</span> Moderation Queue</h2>
                    <div class="max-h-[200px] overflow-y-auto pr-2">{reports_html}</div>
                </div>

                <div class="bg-neutral-900 rounded-2xl border border-neutral-800 shadow-xl overflow-hidden flex-1">
                    <div class="p-4 bg-neutral-950 border-b border-neutral-800 font-bold text-sm uppercase tracking-wider flex justify-between text-neutral-400">
                        <span>👥 Player Database</span>
                        <span class="text-xs font-normal">Auto-updates off</span>
                    </div>
                    <div class="overflow-x-auto max-h-[500px] overflow-y-auto">
                        <table class="w-full text-left border-collapse whitespace-nowrap">
                            <thead class="bg-neutral-900 text-neutral-500 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="py-3 px-4 font-bold text-xs uppercase tracking-wider">Player</th>
                                    <th class="py-3 px-4 font-bold text-xs uppercase tracking-wider">UID</th>
                                    <th class="py-3 px-4 font-bold text-xs uppercase tracking-wider">Stats</th>
                                    <th class="py-3 px-4 font-bold text-xs uppercase tracking-wider text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>{players_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div id="editModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div class="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl w-full max-w-md shadow-2xl relative">
                <h3 class="font-black text-xl mb-6 text-white uppercase tracking-wide">Edit Player</h3>
                <input type="hidden" id="edit-id">
                <div class="mb-4">
                    <label class="block text-xs font-bold text-neutral-500 mb-1 uppercase">Display Name</label>
                    <input type="text" id="edit-name" class="w-full bg-neutral-950 border border-neutral-700 p-3 rounded-xl text-white outline-none">
                </div>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-xs font-bold text-neutral-500 mb-1 uppercase">ELO Rating</label>
                        <input type="number" id="edit-elo" class="w-full bg-neutral-950 border border-neutral-700 p-3 rounded-xl text-white outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-neutral-500 mb-1 uppercase">Total Wins</label>
                        <input type="number" id="edit-wins" class="w-full bg-neutral-950 border border-neutral-700 p-3 rounded-xl text-white outline-none">
                    </div>
                </div>
                <div class="mb-6">
                    <label class="block text-xs font-bold text-neutral-500 mb-1 uppercase">Status Statement</label>
                    <input type="text" id="edit-status" class="w-full bg-neutral-950 border border-neutral-700 p-3 rounded-xl text-white outline-none">
                </div>
                <div class="flex justify-end gap-3 pt-2">
                    <button onclick="closeEditModal()" class="px-5 py-3 bg-neutral-800 hover:bg-neutral-700 text-white font-bold rounded-xl transition">Cancel</button>
                    <button onclick="submitEdit()" id="btn-save-edit" class="px-5 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition">Save</button>
                </div>
            </div>
        </div>

        <script>
            const map = L.map('adminMap').setView([43.5460, -80.2436], 12);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);

            async function loadMapMarkers() {{
                const res = await fetch('/api/players');
                const players = await res.json();
                players.forEach(p => {{
                    if(p.lat && p.lng && p.isOnline && !p.isIncognito) {{
                        const icon = L.divIcon({{
                            className: 'bg-transparent',
                            html: `<div class="w-4 h-4 bg-green-500 border-2 border-white rounded-full shadow-[0_0_10px_rgba(34,197,94,0.8)]"></div>`
                        }});
                        L.marker([p.lat, p.lng], {{icon}}).addTo(map).bindPopup(`<b class="text-neutral-900">${{p.name}}</b><br><span class="text-neutral-600">ELO: ${{p.elo}}</span>`);
                    }}
                }});
            }}
            loadMapMarkers();

            async function sendBroadcast() {{
                const msg = document.getElementById('broadcastText').value;
                if(!msg) return;
                await fetch('/api/admin/broadcast', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{message: msg}})
                }});
                document.getElementById('broadcastText').value = '';
                alert("Broadcast Sent!");
            }}

            async function spawnBots() {{
                const res = await fetch('/api/admin/spawn_bots', {{method: 'POST'}});
                if(res.ok) window.location.reload();
            }}

            async function clearBots() {{
                if(!confirm("Clear all bots?")) return;
                const res = await fetch('/api/admin/clear_bots', {{method: 'POST'}});
                if(res.ok) window.location.reload();
            }}

            async function dismissReport(id) {{
                if(!confirm("Dismiss report?")) return;
                const res = await fetch('/api/admin/reports/' + id, {{ method: 'DELETE' }});
                if(res.ok) window.location.reload();
            }}

            async function kickUser(id) {{
                if(!confirm("Force disconnect user?")) return;
                const res = await fetch('/api/admin/players/' + id + '/kick', {{ method: 'POST' }});
                if(res.ok) window.location.reload();
            }}

            async function banUser(id) {{
                if(!confirm("Permanently BAN user?")) return;
                const res = await fetch('/api/admin/players/' + id, {{ method: 'DELETE' }});
                if(res.ok) window.location.reload();
            }}

            function openEditModal(id, name, elo, wins, status) {{
                document.getElementById('edit-id').value = id;
                document.getElementById('edit-name').value = name;
                document.getElementById('edit-elo').value = elo;
                document.getElementById('edit-wins').value = wins;
                document.getElementById('edit-status').value = status;
                document.getElementById('editModal').classList.remove('hidden');
            }}

            function closeEditModal() {{ document.getElementById('editModal').classList.add('hidden'); }}

            async function submitEdit() {{
                const btn = document.getElementById('btn-save-edit');
                btn.innerText = "Saving..."; btn.disabled = true;
                const id = document.getElementById('edit-id').value;
                const payload = {{
                    name: document.getElementById('edit-name').value,
                    elo: parseInt(document.getElementById('edit-elo').value),
                    wins: parseInt(document.getElementById('edit-wins').value),
                    status: document.getElementById('edit-status').value
                }};
                const res = await fetch('/api/admin/players/' + id, {{
                    method: 'PATCH',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                if(res.ok) window.location.reload();
                else {{ alert("Error"); btn.innerText = "Save"; btn.disabled = false; }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=page)


# ==========================================
# 7. ADMIN TOOL API ENDPOINTS
# ==========================================
@app.delete("/api/admin/reports/{report_id}")
async def dismiss_report(report_id: int, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    report = db.query(DBReport).filter(DBReport.id == report_id).first()
    if report:
        db.delete(report)
        db.commit()
    return {"status": "success"}


@app.delete("/api/admin/players/{user_id}")
async def ban_player(user_id: str, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
    if player:
        db.delete(player)
        db.commit()
        if user_id in manager.active_connections:
            await manager.active_connections[user_id].close(code=1008, reason="Account banned")
            manager.disconnect(user_id)
    return {"status": "success"}


@app.post("/api/admin/players/{user_id}/kick")
async def kick_player(user_id: str, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
    if player:
        player.isOnline = False
        db.commit()
        if user_id in manager.active_connections:
            await manager.active_connections[user_id].close(code=1008, reason="Kicked by Admin")
            manager.disconnect(user_id)
        await manager.broadcast_radar_update(format_player(player))
    return {"status": "success"}


@app.patch("/api/admin/players/{user_id}")
async def admin_update_player(user_id: str, updates: AdminPlayerUpdate, db: Session = Depends(get_db),
                              admin: str = Depends(verify_admin)):
    player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
    if not player:
        raise HTTPException(status_code=404)
    if updates.name is not None: player.name = updates.name
    if updates.elo is not None: player.elo = updates.elo
    if updates.wins is not None: player.wins = updates.wins
    if updates.status is not None: player.status = updates.status
    db.commit()
    db.refresh(player)
    await manager.broadcast_radar_update(format_player(player))
    return {"status": "success"}


@app.post("/api/admin/broadcast")
async def broadcast_msg(msg: BroadcastModel, admin: str = Depends(verify_admin)):
    await manager.broadcast_announcement(msg.message)
    return {"status": "sent"}


@app.post("/api/admin/spawn_bots")
async def spawn_bots(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    base_lat, base_lng = 43.5460, -80.2436
    for i in range(5):
        bot_id = f"bot_{uuid.uuid4().hex[:8]}"
        bot = DBPlayer(
            id=bot_id,
            name=f"ChessBot Alpha {i + 1}",
            avatar=f"https://api.dicebear.com/9.x/bottts-neutral/svg?seed={bot_id}&backgroundColor=eab308",
            status="Scanning area for challengers. Beep.",
            about="I am an automated test bot.",
            baseLocation="Admin Spawned",
            isOnline=True,
            lat=base_lat + random.uniform(-0.02, 0.02),
            lng=base_lng + random.uniform(-0.02, 0.02),
            wins=random.randint(0, 20),
            elo=random.randint(800, 2200),
            platform="chesscom",
            linkedUsername="chessbot",
            hasRanked=random.choice([True, False]),
            isPremium=random.choice([True, False]),
            isIncognito=False,
            updatedAt=time.time()
        )
        db.add(bot)
    db.commit()

    bots = db.query(DBPlayer).filter(DBPlayer.id.like("bot_%")).all()
    for b in bots:
        await manager.broadcast_radar_update(format_player(b))
    return {"status": "spawned"}


@app.post("/api/admin/clear_bots")
async def clear_bots(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    bots = db.query(DBPlayer).filter(DBPlayer.id.like("bot_%")).all()
    for b in bots:
        b.isOnline = False
        await manager.broadcast_radar_update(format_player(b))
        db.delete(b)
    db.commit()
    return {"status": "cleared"}


# ==========================================
# 8. WEBSOCKET ENDPOINT (RACE CONDITION FIXED)
# ==========================================
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = None):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "GPS_PING":
                db = SessionLocal()
                formatted_player = None
                try:
                    db_player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
                    if db_player:
                        coords = data.get("coords", {})
                        db_player.lat = coords.get("lat")
                        db_player.lng = coords.get("lng")
                        db_player.updatedAt = time.time()
                        db.commit()
                        formatted_player = format_player(db_player)
                finally:
                    db.close()

                # Broadcast safely OUTSIDE of the DB lock/session
                if formatted_player:
                    await manager.broadcast_radar_update(formatted_player)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
        db = SessionLocal()
        formatted_player = None
        try:
            db_player = db.query(DBPlayer).filter(DBPlayer.id == user_id).first()
            if db_player:
                db_player.isOnline = False
                db.commit()
                formatted_player = format_player(db_player)
        finally:
            db.close()

        # Broadcast safely OUTSIDE of the DB lock/session to prevent crashes
        if formatted_player:
            asyncio.create_task(manager.broadcast_radar_update(formatted_player))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
