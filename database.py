import sqlite3
import json
import asyncio
import aiosqlite
from typing import List, Dict, Optional
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "agro_market.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()  # Bir vaqtda bitta yozish/operatsiya

    async def connect(self):
        """Birinchi marta ulanish ochish (lazily)"""
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.db_path)

            # ✅ To'g'ri row_factory (aiosqlite uchun)
            self.conn.row_factory = aiosqlite.Row

            # WAL mode yoqish — Telegram bot uchun juda tavsiya etiladi (concurrent o'qish yaxshi ishlaydi)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")

            await self._create_tables()
            await self.conn.commit()

    async def _ensure_connection(self):
        """Har bir metod boshida chaqiriladi"""
        if self.conn is None:
            await self.connect()

    async def _create_tables(self):
        """Jadvallarni yaratish"""
        async with self._lock:
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    full_name TEXT,
                    username TEXT,
                    phone_user TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount TEXT NOT NULL,
                    location TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    description TEXT,
                    photos TEXT,                    -- JSON string sifatida saqlanadi
                    status TEXT DEFAULT 'pending',
                    channel_post_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            await self.conn.commit()

    # ====================== USER METHODS ======================
    async def add_or_update_user(
            self,
            telegram_id: int,
            full_name: str = "",
            username: str = "",
            phone_user: str = ""
    ) -> Optional[int]:
        await self._ensure_connection()
        async with self._lock:
            await self.conn.execute("""
                INSERT INTO users (telegram_id, full_name, username, phone_user)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    username = excluded.username,
                    phone_user = excluded.phone_user
            """, (telegram_id, full_name, username, phone_user))
            await self.conn.commit()

            async with self.conn.execute(
                    "SELECT id FROM users WHERE telegram_id=?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row["id"] if row else None

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute(
                    "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_user_id(self, telegram_id: int) -> Optional[int]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute(
                    "SELECT id FROM users WHERE telegram_id=?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row["id"] if row else None

    # async def get_username(self, ad_id: int) -> Optional[str]:
    #     await self._ensure_connection()
    #     async with self._lock:
    #         async with self.conn.execute(
    #                 "SELECT username FROM users WHERE telegram_id=?", (ad_id,)
    #         ) as cursor:
    #             row = await cursor.fetchone()
    #             return row[0] if row else None

    # ====================== ADS METHODS ======================
    async def add_pending_ad(
            self,
            user_id: int,
            product: str,
            price: float,
            amount: str,
            location: str,
            phone: str,
            description: str = "",
            photos: Optional[List[str]] = None
    ) -> int:
        if photos is None:
            photos = []
        photos_str = json.dumps(photos)

        await self._ensure_connection()
        async with self._lock:
            cursor = await self.conn.execute("""
                INSERT INTO ads 
                (user_id, product, price, amount, location, phone, description, photos, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (user_id, product, price, amount, location, phone, description, photos_str))
            await self.conn.commit()
            return cursor.lastrowid

    async def update_ad(
            self,
            ad_id: int,
            product: str,
            price: float,
            amount: str,
            location: str,
            phone: str,
            description: str,
            photos: List[str]
    ) -> bool:
        await self._ensure_connection()
        photos_str = json.dumps(photos)
        async with self._lock:
            cursor = await self.conn.execute("""
                UPDATE ads SET
                    product = ?, price = ?, amount = ?, location = ?,
                    phone = ?, description = ?, photos = ?
                WHERE id = ?
            """, (product, price, amount, location, phone, description, photos_str, ad_id))
            await self.conn.commit()
            return cursor.rowcount > 0

    async def get_user_ads(self, user_id: int) -> List[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute("""
                SELECT * FROM ads 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return self._process_ads(rows)

    async def get_pending_ads(self) -> List[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute("""
                SELECT * FROM ads 
                WHERE status = 'pending' 
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return self._process_ads(rows)

    async def get_approved_ads(self) -> List[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute("""
                SELECT * FROM ads 
                WHERE status = 'approved' 
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return self._process_ads(rows)

    async def get_ad_by_id(self, ad_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute(
                    "SELECT * FROM ads WHERE id = ?", (ad_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._process_single_ad(row)

    async def get_ad_with_user(self, ad_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute("""
                SELECT ads.*, users.telegram_id, users.username 
                FROM ads 
                LEFT JOIN users ON ads.user_id = users.id          
                WHERE ads.id = ?
            """, (ad_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                ad = self._process_single_ad(row)
                if ad:
                    ad['telegram_id'] = row['telegram_id']  # qo'shimcha maydon
                return ad

    async def update_ad_status(
            self,
            ad_id: int,
            status: str,
            channel_post_id: Optional[int] = None
    ):
        await self._ensure_connection()
        async with self._lock:
            if channel_post_id is not None:
                await self.conn.execute("""
                    UPDATE ads 
                    SET status = ?, channel_post_id = ? 
                    WHERE id = ?
                """, (status, channel_post_id, ad_id))
            else:
                await self.conn.execute(
                    "UPDATE ads SET status = ? WHERE id = ?",
                    (status, ad_id)
                )
            await self.conn.commit()

    async def mark_as_sold(self, ad_id: int):
        await self.update_ad_status(ad_id, "SOLD")

    async def delete_ad(self, ad_id: int, user_id: Optional[int] = None):
        await self._ensure_connection()
        async with self._lock:
            if user_id:
                await self.conn.execute(
                    "UPDATE ads SET status='DELETED' WHERE id=? AND user_id=?",
                    (ad_id, user_id)
                )
            else:
                await self.conn.execute(
                    "UPDATE ads SET status='DELETED' WHERE id=?",
                    (ad_id,)
                )
            await self.conn.commit()

    async def clear_channel_post(self, ad_id: int):
        await self._ensure_connection()
        async with self._lock:
            await self.conn.execute(
                "UPDATE ads SET channel_post_id=NULL WHERE id=?",
                (ad_id,)
            )
            await self.conn.commit()

    # ====================== HELPER METHODS ======================
    def _process_single_ad(self, row) -> Optional[Dict]:
        if not row:
            return None
        ad = dict(row)
        if ad.get('photos'):
            try:
                ad['photos'] = json.loads(ad['photos'])
            except (json.JSONDecodeError, TypeError):
                ad['photos'] = []
        return ad

    def _process_ads(self, rows) -> List[Dict]:
        return [self._process_single_ad(row) for row in rows if row]

    async def get_all_ads(self) -> List[Dict]:
        """Barcha e'lonlarni olish (Cleaner uchun)"""
        await self._ensure_connection()
        async with self._lock:
            async with self.conn.execute("SELECT * FROM ads") as cursor:
                rows = await cursor.fetchall()
                return self._process_ads(rows)

    async def close(self):
        """Botni to'xtatishda chaqirish kerak"""
        if self.conn:
            await self.conn.close()
            self.conn = None