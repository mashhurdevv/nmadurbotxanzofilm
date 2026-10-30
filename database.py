# database.py
# Botning barcha SQLite bilan ishlash funksiyalari shu yerda joylashgan

import aiosqlite
import datetime
from config import DB_NAME, PREMIUM_DURATION_HOURS, PREMIUM_PRICE, STATS_RESET_DAYS


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_name)
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.create_tables()

    async def close(self):
        await self.conn.close()

    # ------------------------------------------------------------------ #
    #                         JADVALLARNI YARATISH                       #
    # ------------------------------------------------------------------ #
    async def create_tables(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT,
                joined_at TEXT,
                left_at TEXT,
                is_active INTEGER DEFAULT 1,
                expiry_notified INTEGER DEFAULT 1,
                pending_code TEXT
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                username TEXT,
                channel_id TEXT,
                invite_link TEXT,
                is_zayavka INTEGER DEFAULT 0
            )
        """)

        # Eski bazalarda ustunlar mavjud bo'lmasa, qo'shib qo'yamiz (xavfsiz migratsiya)
        cur = await self.conn.execute("PRAGMA table_info(channels)")
        existing_cols = [row[1] for row in await cur.fetchall()]
        if "invite_link" not in existing_cols:
            await self.conn.execute("ALTER TABLE channels ADD COLUMN invite_link TEXT")
        if "is_zayavka" not in existing_cols:
            await self.conn.execute("ALTER TABLE channels ADD COLUMN is_zayavka INTEGER DEFAULT 0")

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                description TEXT,
                file_id TEXT,
                content_type TEXT DEFAULT 'video',
                added_at TEXT,
                category TEXT DEFAULT 'film'
            )
        """)

        # Serial / anime qismlari
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS movie_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id INTEGER NOT NULL,
                part_no INTEGER NOT NULL,
                file_id TEXT,
                content_type TEXT DEFAULT 'video',
                UNIQUE (movie_id, part_no)
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                photo_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                resolved_at TEXT
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS premium_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source TEXT,
                amount INTEGER DEFAULT 0,
                granted_at TEXT
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS join_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                requested_at TEXT,
                UNIQUE(user_id, channel_id)
            )
        """)

        # Eski (serverdagi) bazalarda yetishmayotgan ustunlarni qo'shamiz — ma'lumotlar o'zgarmaydi
        expected_columns = {
            "users": {
                "username": "TEXT", "full_name": "TEXT", "is_premium": "INTEGER DEFAULT 0",
                "premium_until": "TEXT", "joined_at": "TEXT", "left_at": "TEXT",
                "is_active": "INTEGER DEFAULT 1", "expiry_notified": "INTEGER DEFAULT 1",
                "pending_code": "TEXT",
            },
            "channels": {
                "name": "TEXT", "username": "TEXT", "channel_id": "TEXT",
                "invite_link": "TEXT", "is_zayavka": "INTEGER DEFAULT 0",
            },
            "movies": {
                "description": "TEXT", "file_id": "TEXT",
                "content_type": "TEXT DEFAULT 'video'", "added_at": "TEXT",
                "category": "TEXT DEFAULT 'film'",
            },
            "payments": {
                "user_id": "INTEGER", "photo_file_id": "TEXT",
                "status": "TEXT DEFAULT 'pending'", "created_at": "TEXT", "resolved_at": "TEXT",
            },
            "premium_history": {
                "user_id": "INTEGER", "source": "TEXT",
                "amount": "INTEGER DEFAULT 0", "granted_at": "TEXT",
            },
        }
        for table, cols in expected_columns.items():
            cur = await self.conn.execute(f"PRAGMA table_info({table})")
            have = {row[1] for row in await cur.fetchall()}
            for col, decl in cols.items():
                if col not in have:
                    await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

        await self.conn.commit()

        # statistika davri boshlanish sanasini sozlash (birinchi ishga tushganda)
        if await self.get_setting("stats_period_start") is None:
            await self.set_setting("stats_period_start", now_str())
        if await self.get_setting("stats_cache") is None:
            await self.set_setting("stats_cache", "")
        if await self.get_setting("stats_cache_time") is None:
            await self.set_setting("stats_cache_time", "")

    # ------------------------------------------------------------------ #
    #                              SETTINGS                              #
    # ------------------------------------------------------------------ #
    async def get_setting(self, key: str):
        cur = await self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def set_setting(self, key: str, value: str):
        await self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await self.conn.commit()

    async def get_premium_enabled(self) -> bool:
        """Premium tizimi umuman yoqilganmi (True) yoki o'chirilib, hammaga tekin qilinganmi (False)."""
        value = await self.get_setting("premium_enabled")
        if value is None:
            await self.set_setting("premium_enabled", "1")
            return True
        return value == "1"

    async def set_premium_enabled(self, enabled: bool):
        await self.set_setting("premium_enabled", "1" if enabled else "0")

    # ------------------------------------------------------------------ #
    #                              USERS                                  #
    # ------------------------------------------------------------------ #
    async def add_user(self, user_id: int, username: str, full_name: str):
        cur = await self.conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            await self.conn.execute(
                "INSERT INTO users (user_id, username, full_name, joined_at, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (user_id, username, full_name, now_str())
            )
            await self.conn.commit()
            return True  # yangi foydalanuvchi
        else:
            # foydalanuvchi qayta kirgan bo'lsa - активность qayta tiklaymiz
            await self.conn.execute(
                "UPDATE users SET is_active = 1, username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id)
            )
            await self.conn.commit()
            return False

    async def mark_user_left(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET is_active = 0, left_at = ? WHERE user_id = ?",
            (now_str(), user_id)
        )
        await self.conn.commit()

    async def get_user(self, user_id: int):
        cur = await self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()

    async def get_all_user_ids(self):
        cur = await self.conn.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def is_premium(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if not user:
            return False
        premium_until = user[4]  # premium_until column
        if user[3] == 1 and premium_until:
            until_dt = datetime.datetime.strptime(premium_until, "%Y-%m-%d %H:%M:%S")
            if until_dt > datetime.datetime.now():
                return True
            else:
                # muddati tugagan, holatni yangilaymiz
                await self.conn.execute(
                    "UPDATE users SET is_premium = 0 WHERE user_id = ?", (user_id,)
                )
                await self.conn.commit()
                return False
        return False

    async def get_premium_until(self, user_id: int):
        user = await self.get_user(user_id)
        if user and user[4]:
            return datetime.datetime.strptime(user[4], "%Y-%m-%d %H:%M:%S")
        return None

    async def grant_premium(self, user_id: int, source: str = "check", amount: int = PREMIUM_PRICE):
        until = datetime.datetime.now() + datetime.timedelta(hours=PREMIUM_DURATION_HOURS)
        until_str = until.strftime("%Y-%m-%d %H:%M:%S")
        await self.conn.execute(
            "UPDATE users SET is_premium = 1, premium_until = ?, expiry_notified = 0 WHERE user_id = ?",
            (until_str, user_id)
        )
        await self.conn.execute(
            "INSERT INTO premium_history (user_id, source, amount, granted_at) VALUES (?, ?, ?, ?)",
            (user_id, source, amount, now_str())
        )
        await self.conn.commit()
        return until_str

    async def get_expired_unnotified_users(self):
        """Muddati tugagan, lekin hali xabar berilmagan premium foydalanuvchilarni qaytaradi."""
        now = now_str()
        cur = await self.conn.execute(
            "SELECT user_id FROM users WHERE is_premium = 1 AND premium_until < ? AND expiry_notified = 0",
            (now,)
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def mark_expired_and_notified(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET is_premium = 0, expiry_notified = 1 WHERE user_id = ?",
            (user_id,)
        )
        await self.conn.commit()

    async def revoke_premium(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?",
            (user_id,)
        )
        await self.conn.commit()

    async def set_pending_code(self, user_id: int, code: str):
        await self.conn.execute(
            "UPDATE users SET pending_code = ? WHERE user_id = ?", (code, user_id)
        )
        await self.conn.commit()

    async def get_pending_code(self, user_id: int):
        user = await self.get_user(user_id)
        if user:
            return user[9]  # pending_code column
        return None

    async def clear_pending_code(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET pending_code = NULL WHERE user_id = ?", (user_id,)
        )
        await self.conn.commit()

    # ------------------------------------------------------------------ #
    #                              CHANNELS                              #
    # ------------------------------------------------------------------ #
    async def add_channel(self, name: str, username: str, channel_id: str,
                           invite_link: str = None, is_zayavka: int = 0):
        await self.conn.execute(
            "INSERT INTO channels (name, username, channel_id, invite_link, is_zayavka) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, username, channel_id, invite_link, is_zayavka)
        )
        await self.conn.commit()

    async def remove_channel(self, channel_db_id: int):
        await self.conn.execute("DELETE FROM channels WHERE id = ?", (channel_db_id,))
        await self.conn.commit()

    async def get_channels(self):
        cur = await self.conn.execute("SELECT * FROM channels")
        return await cur.fetchall()

    async def get_channel(self, channel_db_id: int):
        cur = await self.conn.execute("SELECT * FROM channels WHERE id = ?", (channel_db_id,))
        return await cur.fetchone()

    async def get_zayavka_channels(self):
        """Zayavka (to'lov cheklari yuboriladigan) kanallarning channel_id larini qaytaradi."""
        cur = await self.conn.execute("SELECT channel_id FROM channels WHERE is_zayavka = 1")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ #
    #                           JOIN REQUESTS                             #
    # ------------------------------------------------------------------ #
    async def save_join_request(self, user_id: int, channel_id: str):
        """
        Foydalanuvchidan kanalga kelgan Join Request'ni bazaga yozib qo'yadi.
        Bot bu so'rovni hech qachon avtomatik qabul qilmaydi (approve qilmaydi) —
        faqat "obuna tekshiruvi" uchun dalil sifatida saqlanadi.
        """
        await self.conn.execute(
            "INSERT INTO join_requests (user_id, channel_id, requested_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, channel_id) DO UPDATE SET requested_at = excluded.requested_at",
            (user_id, str(channel_id), now_str())
        )
        await self.conn.commit()

    async def has_join_request(self, user_id: int, channel_id: str) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM join_requests WHERE user_id = ? AND channel_id = ? LIMIT 1",
            (user_id, str(channel_id))
        )
        return (await cur.fetchone()) is not None

    # ------------------------------------------------------------------ #
    #                               MOVIES                                #
    # ------------------------------------------------------------------ #
    # Ustunlar tartibi serverdagi eski bazada ham bir xil bo'lishi uchun aniq yoziladi
    MOVIE_COLS = (
        "id, code, description, file_id, COALESCE(content_type, 'video'), "
        "added_at, COALESCE(category, 'film')"
    )

    async def movie_exists(self, code: str) -> bool:
        cur = await self.conn.execute("SELECT id FROM movies WHERE code = ?", (code,))
        return (await cur.fetchone()) is not None

    async def add_movie(self, code: str, description: str, file_id: str,
                        content_type: str = "video", category: str = "film"):
        await self.conn.execute(
            "INSERT INTO movies (code, description, file_id, content_type, added_at, category) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code, description, file_id, content_type, now_str(), category)
        )
        await self.conn.commit()

    async def add_series(self, code: str, description: str, parts: list):
        """parts: [(file_id, content_type), ...] — 1-qismdan boshlab tartib bilan."""
        first_file, first_type = parts[0]
        cur = await self.conn.execute(
            "INSERT INTO movies (code, description, file_id, content_type, added_at, category) "
            "VALUES (?, ?, ?, ?, ?, 'serial')",
            (code, description, first_file, first_type, now_str())
        )
        movie_id = cur.lastrowid
        for n, (file_id, ctype) in enumerate(parts, start=1):
            await self.conn.execute(
                "INSERT INTO movie_parts (movie_id, part_no, file_id, content_type) VALUES (?, ?, ?, ?)",
                (movie_id, n, file_id, ctype)
            )
        await self.conn.commit()
        return movie_id

    async def get_movie_by_code(self, code: str):
        cur = await self.conn.execute(
            f"SELECT {self.MOVIE_COLS} FROM movies WHERE code = ?", (code,)
        )
        return await cur.fetchone()

    async def get_movie_by_id(self, movie_id: int):
        cur = await self.conn.execute(
            f"SELECT {self.MOVIE_COLS} FROM movies WHERE id = ?", (movie_id,)
        )
        return await cur.fetchone()

    async def get_random_movie(self):
        cur = await self.conn.execute(
            f"SELECT {self.MOVIE_COLS} FROM movies ORDER BY RANDOM() LIMIT 1"
        )
        return await cur.fetchone()

    async def get_today_movies(self):
        today = datetime.date.today().strftime("%Y-%m-%d")
        cur = await self.conn.execute(
            f"SELECT {self.MOVIE_COLS} FROM movies WHERE substr(added_at, 1, 10) = ?", (today,)
        )
        return await cur.fetchall()

    async def get_top_movies(self, category: str, limit: int = 10):
        """Berilgan turdagi tasodifiy (har safar boshqacha) 10 tagacha kino. Kam bo'lsa — borichasi."""
        cur = await self.conn.execute(
            "SELECT id, code, description FROM movies "
            "WHERE COALESCE(category, 'film') = ? ORDER BY RANDOM() LIMIT ?",
            (category, limit)
        )
        return await cur.fetchall()

    async def set_movie_category(self, code: str, category: str) -> bool:
        cur = await self.conn.execute(
            "UPDATE movies SET category = ? WHERE code = ?", (category, code)
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def count_parts(self, movie_id: int) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM movie_parts WHERE movie_id = ?", (movie_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    async def get_part(self, movie_id: int, part_no: int):
        cur = await self.conn.execute(
            "SELECT file_id, COALESCE(content_type, 'video') FROM movie_parts "
            "WHERE movie_id = ? AND part_no = ?", (movie_id, part_no)
        )
        return await cur.fetchone()

    async def movies_count_in_period(self, period_start: str):
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM movies WHERE added_at >= ?", (period_start,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------ #
    #                              PAYMENTS                               #
    # ------------------------------------------------------------------ #
    async def create_payment(self, user_id: int, photo_file_id: str):
        cur = await self.conn.execute(
            "INSERT INTO payments (user_id, photo_file_id, status, created_at) "
            "VALUES (?, ?, 'pending', ?)",
            (user_id, photo_file_id, now_str())
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_pending_payments(self):
        cur = await self.conn.execute(
            "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at ASC"
        )
        return await cur.fetchall()

    async def get_payment(self, payment_id: int):
        cur = await self.conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return await cur.fetchone()

    async def resolve_payment(self, payment_id: int, status: str):
        await self.conn.execute(
            "UPDATE payments SET status = ?, resolved_at = ? WHERE id = ?",
            (status, now_str(), payment_id)
        )
        await self.conn.commit()

    # ------------------------------------------------------------------ #
    #                              STATISTIKA                             #
    # ------------------------------------------------------------------ #
    async def maybe_reset_stats_period(self):
        start = await self.get_setting("stats_period_start")
        if not start:
            await self.set_setting("stats_period_start", now_str())
            return
        start_dt = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        if (datetime.datetime.now() - start_dt).days >= STATS_RESET_DAYS:
            await self.set_setting("stats_period_start", now_str())

    async def compute_stats(self):
        await self.maybe_reset_stats_period()
        period_start = await self.get_setting("stats_period_start")

        # jami obunachilar
        cur = await self.conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cur.fetchone())[0]

        # shu davrda qo'shilganlar
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at >= ?", (period_start,)
        )
        new_users = (await cur.fetchone())[0]

        # shu davrda chiqib ketganlar
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 0 AND left_at >= ?", (period_start,)
        )
        left_users = (await cur.fetchone())[0]

        # shu davrda qo'shilgan kinolar
        movies_added = await self.movies_count_in_period(period_start)

        # shu davrda sotib olingan premiumlar (faqat haqiqiy to'lovlar - manual emas)
        cur = await self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM premium_history "
            "WHERE source = 'check' AND granted_at >= ?",
            (period_start,)
        )
        row = await cur.fetchone()
        premium_bought, revenue = row[0], row[1]

        return {
            "period_start": period_start,
            "total_users": total_users,
            "new_users": new_users,
            "left_users": left_users,
            "movies_added": movies_added,
            "premium_bought": premium_bought,
            "revenue": revenue,
        }

    async def get_cached_stats_text(self, builder_func):
        """
        Statistika har STATS_REFRESH_HOURS soatda bir yangilanadi.
        builder_func - matnni tuzib beruvchi funksiya (stats dict -> str)
        """
        from config import STATS_REFRESH_HOURS
        cache_time = await self.get_setting("stats_cache_time")
        cache_text = await self.get_setting("stats_cache")

        need_refresh = True
        if cache_time and cache_text:
            cache_dt = datetime.datetime.strptime(cache_time, "%Y-%m-%d %H:%M:%S")
            if (datetime.datetime.now() - cache_dt).total_seconds() < STATS_REFRESH_HOURS * 3600:
                need_refresh = False

        if need_refresh:
            stats = await self.compute_stats()
            text = builder_func(stats)
            await self.set_setting("stats_cache", text)
            await self.set_setting("stats_cache_time", now_str())
            return text
        return cache_text
