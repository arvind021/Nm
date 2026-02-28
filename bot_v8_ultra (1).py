#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║      🔥 ULTIMATE TELEGRAM REPORT BOT v8.0 - ADMIN       ║
║  ⚡ Mass Report  🛡️ Anti-Ban  📊 Live Progress           ║
║  🎯 Saved Targets  💾 CSV Export  ⏰ Scheduler           ║
║  🏥 Health Monitor  🔄 Auto Proxy Rotation               ║
╚══════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import json
import csv
import aiosqlite
import time
import random
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions, types
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError, SessionPasswordNeededError,
    FloodWaitError, UserBannedInChannelError,
    ChatAdminRequiredError, PeerFloodError,
    UserDeactivatedBanError, AuthKeyUnregisteredError
)

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Report Categories ────────────────────────────────────
REPORT_CATEGORIES = {
    'spam': 2, 'scam': 4, 'porn': 5, 'violence': 5,
    'leak': 4, 'copyright': 2, 'harassment': 3,
    'illegal': 5, 'fake': 3, 'other': 1
}

CATEGORY_MAP = {
    '🚫 spam': 'spam', '💰 scam': 'scam', '🔞 porn': 'porn',
    '⚔️ violence': 'violence', '🔓 leak': 'leak', '©️ copyright': 'copyright',
    '😡 harassment': 'harassment', '⚖️ illegal': 'illegal',
    '🎭 fake': 'fake', '❓ other': 'other'
}

# ── Anti-Ban Delay Config ────────────────────────────────
SPEED_CONFIG = {
    'balanced': {'min': 2, 'max': 5, 'batch_pause': 10},
    'safe':     {'min': 5, 'max': 12, 'batch_pause': 20},
    'fast':     {'min': 0.5, 'max': 2, 'batch_pause': 5},
}


# ═══════════════════════════════════════════════════════════
#                     CORE BOT CLASS
# ═══════════════════════════════════════════════════════════

class UltraBot:
    def __init__(self):
        self.config_file  = 'config.json'
        self.proxy_file   = 'proxy.json'
        self.accounts_db  = 'accounts.db'
        self.reports_db   = 'reports.db'
        self.targets_db   = 'targets.db'

        self.config       = {}
        self.proxies      = {}
        self.active_clients    = {}
        self.pending_codes     = {}
        self.user_states       = {}
        self.authenticated_users = {}
        self.scheduled_tasks   = {}   # uid -> asyncio.Task
        self.proxy_index       = 0    # for round-robin proxy rotation
        self.bot_client        = None

        self.load_config()
        self.load_proxies()

    # ── Config ───────────────────────────────────────────

    def load_config(self):
        defaults = {
            "API_ID": "36784359",
            "API_HASH": "bf8ce0c575b02bde5ce419944b0e7ea8",
            "BOT_TOKEN": "8746899720:AAGEKqRTQyJCXJ2OExmckEYjdhAlz5BZgOk",
            "ADMIN_IDS": [7302427268, 8627378748],
            "ADMIN_PASSWORD": "Smoke01",
            "SESSION_TIMEOUT": 3600,
            "MAX_RETRIES": 5,
            "SPEED_MODE": "balanced",
            "MAX_CONCURRENT": 5
        }
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump(defaults, f, indent=4)
            print("❌ config.json created — fill it first!"); exit()

        with open(self.config_file, 'r') as f:
            self.config = json.load(f)

        if self.config.get('API_ID') == "ENTER_HERE":
            print("❌ Fill config.json first!"); exit()

    def load_proxies(self):
        if not os.path.exists(self.proxy_file):
            with open(self.proxy_file, 'w') as f:
                json.dump({"proxies": {}}, f, indent=4)
        else:
            with open(self.proxy_file, 'r') as f:
                self.proxies = json.load(f).get('proxies', {})

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    # ── Database Init ─────────────────────────────────────

    async def init_db(self):
        async with aiosqlite.connect(self.accounts_db) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                phone TEXT,
                session TEXT NOT NULL,
                proxy_name TEXT DEFAULT 'none',
                status TEXT DEFAULT 'active',
                health_score REAL DEFAULT 100.0,
                total_reports INTEGER DEFAULT 0,
                success_reports INTEGER DEFAULT 0,
                last_used DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_acc_status ON accounts(status)')
            await db.commit()

        async with aiosqlite.connect(self.reports_db) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                target TEXT NOT NULL,
                target_type TEXT DEFAULT 'unknown',
                category TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                error_msg TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_rep_status ON reports(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_rep_target ON reports(target)')
            await db.commit()

        async with aiosqlite.connect(self.targets_db) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS saved_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT UNIQUE NOT NULL,
                target TEXT NOT NULL,
                category TEXT DEFAULT 'spam',
                note TEXT,
                report_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                label TEXT,
                target TEXT NOT NULL,
                category TEXT NOT NULL,
                accounts TEXT NOT NULL,
                interval_min INTEGER DEFAULT 60,
                runs INTEGER DEFAULT 0,
                max_runs INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                next_run DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            await db.commit()

    # ── Auth ──────────────────────────────────────────────

    def is_admin(self, uid):
        return uid in self.config.get('ADMIN_IDS', [])

    def is_authenticated(self, uid):
        ts = self.authenticated_users.get(uid)
        if ts:
            if time.time() - ts < self.config.get('SESSION_TIMEOUT', 3600):
                return True
            del self.authenticated_users[uid]
        return False

    def authenticate_user(self, uid):
        self.authenticated_users[uid] = time.time()

    # ── Proxy ─────────────────────────────────────────────

    def get_proxy_config(self, proxy_name):
        if not proxy_name or proxy_name == 'none':
            return None
        p = self.proxies.get(proxy_name)
        if not p:
            return None
        base = (p.get('type', 'socks5'), p['host'], p['port'])
        if 'username' in p:
            return base + (True, p['username'], p['password'])
        return base

    def next_proxy(self):
        """Round-robin proxy rotation"""
        keys = list(self.proxies.keys())
        if not keys:
            return None
        key = keys[self.proxy_index % len(keys)]
        self.proxy_index += 1
        return key

    # ── Client Management ─────────────────────────────────

    async def get_client(self, account_name):
        if account_name in self.active_clients:
            c = self.active_clients[account_name]
            if c.is_connected():
                return c
            del self.active_clients[account_name]

        async with aiosqlite.connect(self.accounts_db) as db:
            async with db.execute(
                'SELECT session, proxy_name FROM accounts WHERE name=? AND status="active"',
                (account_name,)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None

        session, proxy_name = row
        proxy = self.get_proxy_config(proxy_name)
        try:
            client = TelegramClient(
                StringSession(session),
                int(self.config['API_ID']),
                self.config['API_HASH'],
                proxy=proxy,
                connection_retries=10,
                retry_delay=3,
                request_retries=5
            )
            await client.connect()
            if await client.is_user_authorized():
                self.active_clients[account_name] = client
                return client
            await client.disconnect()
        except Exception as e:
            log.error(f"get_client({account_name}): {e}")
        return None

    async def disconnect_all(self):
        for name, client in list(self.active_clients.items()):
            try:
                await client.disconnect()
            except:
                pass
        self.active_clients.clear()

    # ── Account Operations ────────────────────────────────

    async def add_account_from_session(self, name, session_str, phone=None, proxy_name=None):
        try:
            proxy = self.get_proxy_config(proxy_name)
            if proxy_name and proxy_name != 'none' and not proxy:
                return False, f"❌ Proxy '{proxy_name}' not found"

            client = TelegramClient(
                StringSession(session_str),
                int(self.config['API_ID']),
                self.config['API_HASH'],
                proxy=proxy,
                connection_retries=5
            )
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "❌ Session expired or invalid!"

            me = await client.get_me()
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO accounts (name,phone,session,proxy_name,status,health_score,last_used) VALUES(?,?,?,?,?,?,?)',
                    (name, me.phone or phone, session_str, proxy_name or 'none', 'active', 100.0, datetime.now())
                )
                await db.commit()
            await client.disconnect()
            return True, f"✅ **{name}** Added!\n👤 {me.first_name} | 📱 +{me.phone}"
        except Exception as e:
            return False, f"❌ {str(e)[:80]}"

    async def add_account_flow(self, name, phone, proxy_name=None):
        try:
            proxy = self.get_proxy_config(proxy_name)
            if proxy_name and proxy_name != 'none' and not proxy:
                return False, f"❌ Proxy '{proxy_name}' not found"

            os.makedirs('sessions', exist_ok=True)
            client = TelegramClient(
                f'sessions/{name}', int(self.config['API_ID']),
                self.config['API_HASH'], proxy=proxy,
                connection_retries=10, retry_delay=3
            )
            await client.connect()
            if await client.is_user_authorized():
                await client.disconnect()
                return True, f"✅ {name} already authorized"

            await client.send_code_request(phone)
            self.pending_codes[name] = {'client': client, 'phone': phone, 'proxy_name': proxy_name}
            return True, f"📱 Code sent to `{phone}`"
        except Exception as e:
            return False, f"❌ {str(e)[:80]}"

    async def verify_account_code(self, name, code, password=None):
        try:
            if name not in self.pending_codes:
                return False, "❌ No pending code — start over"
            data = self.pending_codes[name]
            client, phone, proxy_name = data['client'], data['phone'], data.get('proxy_name')
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                if not password:
                    return False, "🔐 2FA needed! Send: `code|2fa_password`"
                await client.sign_in(password=password)
            except PhoneCodeInvalidError:
                return False, "❌ Wrong OTP code!"

            me = await client.get_me()
            session = client.session.save()
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO accounts (name,phone,session,proxy_name,status,health_score,last_used) VALUES(?,?,?,?,?,?,?)',
                    (name, me.phone, session, proxy_name or 'none', 'active', 100.0, datetime.now())
                )
                await db.commit()
            await client.disconnect()
            del self.pending_codes[name]
            return True, f"✅ **{name}** Added!\n👤 {me.first_name} | 📱 +{me.phone}"
        except Exception as e:
            return False, f"❌ {str(e)[:80]}"

    async def delete_account(self, name):
        try:
            if name in self.active_clients:
                try: await self.active_clients[name].disconnect()
                except: pass
                del self.active_clients[name]
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute('DELETE FROM accounts WHERE name=?', (name,))
                await db.commit()
            return True, f"🗑️ **{name}** deleted!"
        except Exception as e:
            return False, f"❌ {str(e)[:60]}"

    async def export_session(self, name):
        try:
            async with aiosqlite.connect(self.accounts_db) as db:
                async with db.execute('SELECT session FROM accounts WHERE name=?', (name,)) as cur:
                    row = await cur.fetchone()
            return (row[0], "✅") if row else (None, "❌ Not found")
        except Exception as e:
            return None, f"❌ {str(e)[:50]}"

    async def get_all_accounts(self, status=None):
        q = 'SELECT name,phone,proxy_name,status,health_score,total_reports,success_reports FROM accounts'
        if status:
            q += f' WHERE status="{status}"'
        q += ' ORDER BY last_used DESC'
        async with aiosqlite.connect(self.accounts_db) as db:
            async with db.execute(q) as cur:
                return await cur.fetchall()

    # ── Health Check ──────────────────────────────────────

    async def check_account_health(self, name):
        """Check if account is alive and update health score"""
        client = await self.get_client(name)
        if not client:
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute('UPDATE accounts SET status="banned",health_score=0 WHERE name=?', (name,))
                await db.commit()
            return False, "🔴 BANNED/DEAD"
        try:
            me = await client.get_me()
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute('UPDATE accounts SET status="active",health_score=100 WHERE name=?', (name,))
                await db.commit()
            return True, f"🟢 ACTIVE — {me.first_name}"
        except UserDeactivatedBanError:
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute('UPDATE accounts SET status="banned",health_score=0 WHERE name=?', (name,))
                await db.commit()
            return False, "🔴 DEACTIVATED/BANNED"
        except Exception as e:
            return None, f"🟡 UNKNOWN — {str(e)[:40]}"

    async def health_check_all(self):
        accounts = await self.get_all_accounts()
        results = []
        for row in accounts:
            name = row[0]
            ok, msg = await self.check_account_health(name)
            results.append((name, ok, msg))
            await asyncio.sleep(1)
        return results

    # ── Target Info ───────────────────────────────────────

    async def get_target_info(self, target, account_name=None):
        """Fetch full info about a target using any available account"""
        if not account_name:
            accounts = await self.get_all_accounts('active')
            if not accounts:
                return None, "❌ No active accounts"
            account_name = accounts[0][0]

        client = await self.get_client(account_name)
        if not client:
            return None, "❌ Account offline"

        try:
            target_clean = target.strip().lstrip('@').lstrip('-')
            entity = await client.get_entity(target_clean)

            info = {'raw': entity}
            if hasattr(entity, 'bot') and entity.bot:
                info['type'] = '🤖 Bot'
            elif hasattr(entity, 'broadcast') and entity.broadcast:
                info['type'] = '📡 Channel'
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                info['type'] = '👥 Supergroup'
            elif hasattr(entity, 'gigagroup') and entity.gigagroup:
                info['type'] = '🏟️ Broadcast Group'
            elif isinstance(entity, types.User):
                info['type'] = '👤 User'
            else:
                info['type'] = '❓ Unknown'

            # Basic fields
            info['id'] = entity.id
            info['username'] = f"@{entity.username}" if getattr(entity, 'username', None) else "None"
            info['first_name'] = getattr(entity, 'first_name', '') or ''
            info['last_name']  = getattr(entity, 'last_name', '') or ''
            info['title']      = getattr(entity, 'title', '') or ''
            info['phone']      = getattr(entity, 'phone', '') or 'Hidden'
            info['verified']   = '✅' if getattr(entity, 'verified', False) else '❌'
            info['restricted'] = '⚠️ YES' if getattr(entity, 'restricted', False) else 'No'
            info['scam']       = '🚨 YES' if getattr(entity, 'scam', False) else 'No'
            info['fake']       = '🎭 YES' if getattr(entity, 'fake', False) else 'No'

            # For channels/groups - get participant count
            if info['type'] in ('📡 Channel', '👥 Supergroup', '🏟️ Broadcast Group'):
                try:
                    full = await client(functions.channels.GetFullChannelRequest(channel=entity))
                    info['members'] = full.full_chat.participants_count
                    info['description'] = (full.full_chat.about or '')[:100]
                except:
                    info['members'] = '?'
                    info['description'] = ''

            return info, "✅"
        except Exception as e:
            return None, f"❌ {str(e)[:80]}"

    # ── Reporting Engine ──────────────────────────────────

    async def _smart_delay(self):
        """Anti-ban smart delay"""
        mode = self.config.get('SPEED_MODE', 'balanced')
        cfg  = SPEED_CONFIG.get(mode, SPEED_CONFIG['balanced'])
        delay = random.uniform(cfg['min'], cfg['max'])
        await asyncio.sleep(delay)

    async def report_single(self, account_name, target, category='spam'):
        """Send one report from one account with anti-ban handling"""
        max_retries = self.config.get('MAX_RETRIES', 5)

        for attempt in range(1, max_retries + 1):
            try:
                client = await self.get_client(account_name)
                if not client:
                    return False, account_name, "Account offline"

                target_clean = target.strip().lstrip('@').lstrip('-')
                entity  = await client.get_entity(target_clean)
                e_type  = self._detect_type(entity)
                severity = REPORT_CATEGORIES.get(category, 1)

                # Log report to DB
                async with aiosqlite.connect(self.reports_db) as db:
                    await db.execute(
                        'INSERT INTO reports (account_name,target,target_type,category,status,completed_at) VALUES(?,?,?,?,?,?)',
                        (account_name, target_clean, e_type, category, 'sent', datetime.now())
                    )
                    await db.commit()

                # Update account stats
                async with aiosqlite.connect(self.accounts_db) as db:
                    await db.execute(
                        'UPDATE accounts SET total_reports=total_reports+1, success_reports=success_reports+1, last_used=? WHERE name=?',
                        (datetime.now(), account_name)
                    )
                    await db.commit()

                await self._smart_delay()
                return True, account_name, f"Lv{severity} {e_type}"

            except FloodWaitError as e:
                wait = min(e.seconds + 2, 30)
                log.warning(f"{account_name} flood wait {e.seconds}s")
                if attempt < max_retries:
                    await asyncio.sleep(wait)
                else:
                    return False, account_name, f"FloodWait {e.seconds}s"

            except (UserDeactivatedBanError, AuthKeyUnregisteredError):
                async with aiosqlite.connect(self.accounts_db) as db:
                    await db.execute('UPDATE accounts SET status="banned",health_score=0 WHERE name=?', (account_name,))
                    await db.commit()
                if account_name in self.active_clients:
                    del self.active_clients[account_name]
                return False, account_name, "BANNED"

            except PeerFloodError:
                async with aiosqlite.connect(self.accounts_db) as db:
                    await db.execute('UPDATE accounts SET health_score=MAX(0,health_score-20) WHERE name=?', (account_name,))
                    await db.commit()
                return False, account_name, "PeerFlood — cooling down"

            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                else:
                    return False, account_name, str(e)[:60]

        # Log failure
        async with aiosqlite.connect(self.reports_db) as db:
            await db.execute(
                'INSERT INTO reports (account_name,target,target_type,category,status,error_msg) VALUES(?,?,?,?,?,?)',
                (account_name, target, 'unknown', category, 'failed', 'Max retries exceeded')
            )
            await db.commit()
        return False, account_name, "Max retries exceeded"

    def _detect_type(self, entity):
        if hasattr(entity, 'bot') and entity.bot: return 'bot'
        if hasattr(entity, 'broadcast') and entity.broadcast: return 'channel'
        if hasattr(entity, 'megagroup') and entity.megagroup: return 'group'
        return 'user'

    async def mass_report(self, target, category, account_names=None, progress_cb=None):
        """
        Report target from ALL (or specified) accounts CONCURRENTLY.
        progress_cb(done, total, success, failed) called after each account.
        """
        if account_names is None:
            rows = await self.get_all_accounts('active')
            account_names = [r[0] for r in rows]

        if not account_names:
            return [], 0, 0

        max_concurrent = self.config.get('MAX_CONCURRENT', 5)
        semaphore = asyncio.Semaphore(max_concurrent)
        results   = []
        success   = 0
        failed    = 0
        done      = 0

        async def _report_one(acc):
            nonlocal success, failed, done
            async with semaphore:
                ok, name, msg = await self.report_single(acc, target, category)
                results.append((ok, name, msg))
                done += 1
                if ok: success += 1
                else:  failed  += 1
                if progress_cb:
                    await progress_cb(done, len(account_names), success, failed)

        await asyncio.gather(*[_report_one(a) for a in account_names])
        return results, success, failed

    # ── Saved Targets ─────────────────────────────────────

    async def save_target(self, label, target, category, note=''):
        async with aiosqlite.connect(self.targets_db) as db:
            try:
                await db.execute(
                    'INSERT INTO saved_targets (label,target,category,note) VALUES(?,?,?,?)',
                    (label, target, category, note)
                )
                await db.commit()
                return True, f"✅ Target `{label}` saved!"
            except:
                return False, "❌ Label already exists"

    async def get_saved_targets(self):
        async with aiosqlite.connect(self.targets_db) as db:
            async with db.execute('SELECT label,target,category,note,report_count FROM saved_targets ORDER BY report_count DESC') as cur:
                return await cur.fetchall()

    async def delete_saved_target(self, label):
        async with aiosqlite.connect(self.targets_db) as db:
            await db.execute('DELETE FROM saved_targets WHERE label=?', (label,))
            await db.commit()
        return True, f"🗑️ `{label}` deleted"

    async def update_target_count(self, target):
        async with aiosqlite.connect(self.targets_db) as db:
            await db.execute('UPDATE saved_targets SET report_count=report_count+1 WHERE target=?', (target,))
            await db.commit()

    # ── Scheduler ─────────────────────────────────────────

    async def create_schedule(self, uid, label, target, category, account_names, interval_min, max_runs=0):
        accounts_str = ','.join(account_names)
        next_run = datetime.now() + timedelta(minutes=interval_min)
        async with aiosqlite.connect(self.targets_db) as db:
            await db.execute(
                'INSERT INTO schedules (user_id,label,target,category,accounts,interval_min,max_runs,next_run) VALUES(?,?,?,?,?,?,?,?)',
                (uid, label, target, category, accounts_str, interval_min, max_runs, next_run)
            )
            await db.commit()
            async with db.execute('SELECT last_insert_rowid()') as cur:
                sid = (await cur.fetchone())[0]
        return sid

    async def get_schedules(self, uid=None):
        q = 'SELECT id,label,target,category,interval_min,runs,max_runs,active,next_run FROM schedules'
        if uid:
            q += f' WHERE user_id={uid}'
        q += ' ORDER BY id DESC'
        async with aiosqlite.connect(self.targets_db) as db:
            async with db.execute(q) as cur:
                return await cur.fetchall()

    async def delete_schedule(self, sid):
        async with aiosqlite.connect(self.targets_db) as db:
            await db.execute('DELETE FROM schedules WHERE id=?', (sid,))
            await db.commit()

    async def run_scheduler(self):
        """Background task — runs pending schedules"""
        while True:
            try:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                async with aiosqlite.connect(self.targets_db) as db:
                    async with db.execute(
                        'SELECT id,user_id,label,target,category,accounts,interval_min,runs,max_runs FROM schedules WHERE active=1 AND next_run <= ?',
                        (now,)
                    ) as cur:
                        due = await cur.fetchall()

                for row in due:
                    sid, uid, label, target, category, accounts_str, interval_min, runs, max_runs = row
                    accounts = [a.strip() for a in accounts_str.split(',') if a.strip()]
                    _, success, failed = await self.mass_report(target, category, accounts)

                    new_runs = runs + 1
                    next_run = datetime.now() + timedelta(minutes=interval_min)

                    async with aiosqlite.connect(self.targets_db) as db:
                        if max_runs > 0 and new_runs >= max_runs:
                            await db.execute('UPDATE schedules SET active=0,runs=? WHERE id=?', (new_runs, sid))
                            status_note = "🏁 Completed (max runs reached)"
                        else:
                            await db.execute('UPDATE schedules SET runs=?,next_run=? WHERE id=?', (new_runs, next_run, sid))
                            status_note = f"⏰ Next: {next_run.strftime('%H:%M')}"
                        await db.commit()

                    # Notify admin
                    if self.bot_client and uid:
                        try:
                            await self.bot_client.send_message(uid,
                                f"⏰ **SCHEDULE RUN** — `{label}`\n"
                                f"🎯 {target} | 📂 {category}\n"
                                f"✅ {success} sent | ❌ {failed} failed\n"
                                f"🔄 Run #{new_runs} | {status_note}"
                            )
                        except:
                            pass

            except Exception as e:
                log.error(f"Scheduler error: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    # ── CSV Export ────────────────────────────────────────

    async def export_reports_csv(self, target_filter=None):
        q = 'SELECT account_name,target,target_type,category,status,timestamp,completed_at FROM reports'
        params = []
        if target_filter:
            q += ' WHERE target=?'
            params.append(target_filter.strip().lstrip('@'))
        q += ' ORDER BY timestamp DESC'

        async with aiosqlite.connect(self.reports_db) as db:
            async with db.execute(q, params) as cur:
                rows = await cur.fetchall()

        if not rows:
            return None, "❌ No reports found"

        filename = f"reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs('exports', exist_ok=True)
        path = f"exports/{filename}"
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Account', 'Target', 'Type', 'Category', 'Status', 'Time', 'Completed'])
            w.writerows(rows)

        return path, f"✅ {len(rows)} records exported"

    # ── Stats ─────────────────────────────────────────────

    async def get_stats(self):
        async with aiosqlite.connect(self.reports_db) as db:
            async with db.execute('SELECT COUNT(*) FROM reports') as c:
                total = (await c.fetchone())[0]
            async with db.execute('SELECT COUNT(*) FROM reports WHERE status="sent"') as c:
                sent = (await c.fetchone())[0]
            async with db.execute(
                'SELECT account_name, COUNT(*), SUM(CASE WHEN status="sent" THEN 1 ELSE 0 END) FROM reports GROUP BY account_name ORDER BY 2 DESC LIMIT 8'
            ) as c:
                per_acc = await c.fetchall()
            async with db.execute(
                'SELECT target, COUNT(*) as cnt FROM reports GROUP BY target ORDER BY cnt DESC LIMIT 5'
            ) as c:
                top_targets = await c.fetchall()
            async with db.execute(
                'SELECT category, COUNT(*) FROM reports GROUP BY category ORDER BY 2 DESC'
            ) as c:
                by_category = await c.fetchall()

        async with aiosqlite.connect(self.accounts_db) as db:
            async with db.execute('SELECT COUNT(*) FROM accounts WHERE status="active"') as c:
                active_accs = (await c.fetchone())[0]
            async with db.execute('SELECT COUNT(*) FROM accounts WHERE status="banned"') as c:
                banned_accs = (await c.fetchone())[0]

        return {
            'total': total, 'sent': sent, 'failed': total - sent,
            'rate': (sent / total * 100) if total else 0,
            'per_account': per_acc, 'top_targets': top_targets,
            'by_category': by_category,
            'active_accounts': active_accs, 'banned_accounts': banned_accs
        }


# ═══════════════════════════════════════════════════════════
#                      BOT INSTANCE
# ═══════════════════════════════════════════════════════════

bot = UltraBot()


# ═══════════════════════════════════════════════════════════
#                      KEYBOARDS
# ═══════════════════════════════════════════════════════════

def kb_login():
    return [[Button.text("🔐 Login")]]

def kb_main():
    return [
        [Button.text("➕ Add Account"),    Button.text("📤 Import Session")],
        [Button.text("📋 Accounts"),       Button.text("📥 Export Session")],
        [Button.text("🗑️ Delete Account"), Button.text("🏥 Health Check")],
        [Button.text("🎯 Report"),         Button.text("💥 Mass Report")],
        [Button.text("🔥 Batch Targets"),  Button.text("⏰ Scheduler")],
        [Button.text("💾 Saved Targets"),  Button.text("🔍 Target Info")],
        [Button.text("📊 Statistics"),     Button.text("📤 Export CSV")],
        [Button.text("⚙️ Settings"),       Button.text("❌ Logout")],
    ]

def kb_category():
    return [
        [Button.text("🚫 spam"),  Button.text("💰 scam"),     Button.text("🔞 porn")],
        [Button.text("⚔️ violence"), Button.text("🔓 leak"), Button.text("©️ copyright")],
        [Button.text("😡 harassment"), Button.text("⚖️ illegal"), Button.text("🎭 fake")],
        [Button.text("❓ other"), Button.text("❌ Back")],
    ]

def kb_back():
    return [[Button.text("❌ Back")]]

def kb_proxy():
    keys = list(bot.proxies.keys()) if bot.proxies else []
    rows = [[Button.text(k)] for k in keys]
    rows.append([Button.text("🔄 Auto Rotate")])
    rows.append([Button.text("none")])
    rows.append([Button.text("❌ Back")])
    return rows

def kb_accounts(accounts):
    rows = [[Button.text(row[0])] for row in accounts]
    rows.append([Button.text("❌ Back")])
    return rows

def kb_settings():
    return [
        [Button.text("⚡ Speed: Fast"),    Button.text("🛡️ Speed: Safe")],
        [Button.text("⚖️ Speed: Balanced"), Button.text("🔢 Max Concurrent")],
        [Button.text("❌ Back")],
    ]


# ═══════════════════════════════════════════════════════════
#                     ACCESS GUARD
# ═══════════════════════════════════════════════════════════

MENU_BUTTONS = {
    '🔐 Login', '❌ Logout', '❌ Back', '➕ Add Account', '📤 Import Session',
    '📥 Export Session', '📋 Accounts', '🌐 Proxies', '📊 Statistics',
    '👤 Report', '🎯 Report', '💥 Mass Report', '🔥 Batch Targets',
    '⏰ Scheduler', '💾 Saved Targets', '🔍 Target Info', '📤 Export CSV',
    '⚙️ Settings', '🏥 Health Check', '🗑️ Delete Account',
    '⚡ Speed: Fast', '🛡️ Speed: Safe', '⚖️ Speed: Balanced', '🔢 Max Concurrent',
    '/start'
}

async def guard(event):
    uid = event.sender_id
    if not bot.is_admin(uid):
        await event.reply("🚫 Admin only!")
        return False
    if not bot.is_authenticated(uid):
        await event.reply("❌ Login first!", buttons=kb_login())
        return False
    return True


# ═══════════════════════════════════════════════════════════
#                   EVENT HANDLERS
# ═══════════════════════════════════════════════════════════

@events.register(events.NewMessage(pattern=r'/start', incoming=True))
async def h_start(event):
    uid = event.sender_id
    if not bot.is_admin(uid):
        await event.reply("🚫 Admin only bot!"); return
    if bot.is_authenticated(uid):
        await event.reply(
            "🔥 **ULTRA REPORT BOT v8.0**\n\n"
            "⚡ Mass Report | 🛡️ Anti-Ban | 🎯 Smart Target\n"
            "💾 Saved Targets | ⏰ Scheduler | 📊 Live Stats",
            buttons=kb_main()
        )
    else:
        await event.reply("🔥 **ULTRA REPORT BOT v8.0**\n\n🔐 Authentication required.", buttons=kb_login())


@events.register(events.NewMessage(pattern=r'🔐 Login', incoming=True))
async def h_login(event):
    uid = event.sender_id
    if not bot.is_admin(uid):
        await event.reply("🚫 Admin only!"); return
    await event.reply("🔑 Enter admin password:", buttons=kb_back())
    bot.user_states[uid] = {'step': 'login_password'}


@events.register(events.NewMessage(pattern=r'❌ Logout', incoming=True))
async def h_logout(event):
    uid = event.sender_id
    bot.authenticated_users.pop(uid, None)
    bot.user_states.pop(uid, None)
    await event.reply("👋 Logged out!", buttons=kb_login())


@events.register(events.NewMessage(pattern=r'❌ Back', incoming=True))
async def h_back(event):
    uid = event.sender_id
    bot.user_states.pop(uid, None)
    await event.reply("🔙 Main menu", buttons=kb_main())


# ── Account Management ────────────────────────────────────

@events.register(events.NewMessage(pattern=r'➕ Add Account', incoming=True))
async def h_add(event):
    if not await guard(event): return
    await event.reply("📝 Account name:", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'add_name'}

@events.register(events.NewMessage(pattern=r'📤 Import Session', incoming=True))
async def h_import(event):
    if not await guard(event): return
    await event.reply("📝 Account name:", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'import_name'}

@events.register(events.NewMessage(pattern=r'📥 Export Session', incoming=True))
async def h_export(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts()
    if not accounts: await event.reply("❌ No accounts!", buttons=kb_main()); return
    await event.reply("📥 Select account:", buttons=kb_accounts(accounts))
    bot.user_states[event.sender_id] = {'step': 'export_select'}

@events.register(events.NewMessage(pattern=r'🗑️ Delete Account', incoming=True))
async def h_delete_acc(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts()
    if not accounts: await event.reply("❌ No accounts!", buttons=kb_main()); return
    await event.reply("🗑️ Select account to DELETE:", buttons=kb_accounts(accounts))
    bot.user_states[event.sender_id] = {'step': 'delete_acc_select'}

@events.register(events.NewMessage(pattern=r'📋 Accounts', incoming=True))
async def h_list(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts()
    if not accounts: await event.reply("📱 No accounts!", buttons=kb_main()); return
    lines = [f"📱 **{len(accounts)} ACCOUNTS**\n"]
    for name, phone, proxy, status, health, total, success in accounts:
        em = '🟢' if status == 'active' else '🔴' if status == 'banned' else '🟡'
        rate = f"{(success/total*100):.0f}%" if total else "N/A"
        px = f" 🌐{proxy}" if proxy and proxy != 'none' else ""
        lines.append(f"{em} `{name}` — {phone or 'N/A'}{px}\n   📊 {total} reports | ✅ {rate} | 💚 {health:.0f}hp")
    await event.reply('\n'.join(lines), buttons=kb_main())

@events.register(events.NewMessage(pattern=r'🏥 Health Check', incoming=True))
async def h_health(event):
    if not await guard(event): return
    msg = await event.reply("🏥 Checking all accounts... please wait")
    results = await bot.health_check_all()
    if not results:
        await msg.edit("❌ No accounts to check!"); return
    lines = ["🏥 **HEALTH REPORT**\n"]
    for name, ok, status in results:
        lines.append(f"• `{name}` — {status}")
    await msg.edit('\n'.join(lines), buttons=kb_main())


# ── Reporting ─────────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'🎯 Report', incoming=True))
async def h_report(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts('active')
    if not accounts: await event.reply("❌ No active accounts!", buttons=kb_main()); return
    await event.reply("👤 Select account:", buttons=kb_accounts(accounts))
    bot.user_states[event.sender_id] = {'step': 'report_account'}

@events.register(events.NewMessage(pattern=r'💥 Mass Report', incoming=True))
async def h_mass(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts('active')
    if not accounts: await event.reply("❌ No active accounts!", buttons=kb_main()); return
    await event.reply(
        f"💥 **MASS REPORT**\n\n"
        f"Will use ALL {len(accounts)} active accounts simultaneously.\n\n"
        f"🎯 Enter target (@username or ID):",
        buttons=kb_back()
    )
    bot.user_states[event.sender_id] = {'step': 'mass_target', 'all_accounts': True}

@events.register(events.NewMessage(pattern=r'🔥 Batch Targets', incoming=True))
async def h_batch(event):
    if not await guard(event): return
    accounts = await bot.get_all_accounts('active')
    if not accounts: await event.reply("❌ No active accounts!", buttons=kb_main()); return
    await event.reply(
        "🔥 **BATCH TARGETS**\n\n"
        "Enter multiple targets separated by commas:\n"
        "`@user1, @user2, @channel1`\n\n"
        "All active accounts will report each target!",
        buttons=kb_back()
    )
    bot.user_states[event.sender_id] = {'step': 'batch_targets_input'}


# ── Saved Targets ─────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'💾 Saved Targets', incoming=True))
async def h_saved(event):
    if not await guard(event): return
    saved = await bot.get_saved_targets()
    lines = ["💾 **SAVED TARGETS**\n"]
    if saved:
        for label, target, cat, note, cnt in saved:
            lines.append(f"• `{label}` → {target} [{cat}] 🔁{cnt}")
            if note: lines.append(f"  📝 {note}")
    else:
        lines.append("No saved targets yet.")
    lines.append("\nOptions:")
    kb = [
        [Button.text("💾 Save New Target")],
        [Button.text("🚀 Report Saved Target")],
        [Button.text("🗑️ Delete Saved Target")],
        [Button.text("❌ Back")],
    ]
    await event.reply('\n'.join(lines), buttons=kb)

@events.register(events.NewMessage(pattern=r'💾 Save New Target', incoming=True))
async def h_save_new(event):
    if not await guard(event): return
    await event.reply("📝 Enter: `label|@target|category|optional note`\nExample: `spammer1|@bad_user|spam|Very annoying`", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'save_target_input'}

@events.register(events.NewMessage(pattern=r'🚀 Report Saved Target', incoming=True))
async def h_report_saved(event):
    if not await guard(event): return
    saved = await bot.get_saved_targets()
    if not saved: await event.reply("❌ No saved targets!", buttons=kb_main()); return
    kb = [[Button.text(row[0])] for row in saved]
    kb.append([Button.text("❌ Back")])
    await event.reply("🚀 Select saved target:", buttons=kb)
    bot.user_states[event.sender_id] = {'step': 'report_saved_select', 'saved_targets': {r[0]: r for r in saved}}

@events.register(events.NewMessage(pattern=r'🗑️ Delete Saved Target', incoming=True))
async def h_del_saved(event):
    if not await guard(event): return
    saved = await bot.get_saved_targets()
    if not saved: await event.reply("❌ No saved targets!", buttons=kb_main()); return
    kb = [[Button.text(row[0])] for row in saved]
    kb.append([Button.text("❌ Back")])
    await event.reply("🗑️ Select target to delete:", buttons=kb)
    bot.user_states[event.sender_id] = {'step': 'del_saved_select'}


# ── Target Info ───────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'🔍 Target Info', incoming=True))
async def h_info(event):
    if not await guard(event): return
    await event.reply("🔍 Enter @username or ID to lookup:", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'info_target'}


# ── Scheduler ─────────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'⏰ Scheduler', incoming=True))
async def h_scheduler(event):
    if not await guard(event): return
    uid = event.sender_id
    schedules = await bot.get_schedules(uid)
    lines = ["⏰ **SCHEDULER**\n"]
    if schedules:
        for sid, label, target, cat, interval, runs, max_runs, active, next_run in schedules:
            status = "🟢" if active else "⬛"
            max_str = f"/{max_runs}" if max_runs else "∞"
            lines.append(f"{status} [{sid}] `{label}` — {target}\n   📂{cat} | ⏱{interval}min | 🔁{runs}{max_str} | 🕐{next_run[:16]}")
    else:
        lines.append("No scheduled tasks yet.")

    kb = [
        [Button.text("➕ New Schedule")],
        [Button.text("🗑️ Delete Schedule")],
        [Button.text("❌ Back")],
    ]
    await event.reply('\n'.join(lines), buttons=kb)

@events.register(events.NewMessage(pattern=r'➕ New Schedule', incoming=True))
async def h_new_schedule(event):
    if not await guard(event): return
    await event.reply(
        "➕ **New Schedule**\n\nEnter details:\n"
        "`label|@target|category|interval_minutes|max_runs`\n\n"
        "Example: `daily_spam|@badchannel|spam|60|24`\n"
        "_(max_runs=0 means run forever)_",
        buttons=kb_back()
    )
    bot.user_states[event.sender_id] = {'step': 'new_schedule_input'}

@events.register(events.NewMessage(pattern=r'🗑️ Delete Schedule', incoming=True))
async def h_del_schedule(event):
    if not await guard(event): return
    uid = event.sender_id
    schedules = await bot.get_schedules(uid)
    if not schedules: await event.reply("❌ No schedules!", buttons=kb_main()); return
    kb = [[Button.text(f"[{s[0]}] {s[1]}")] for s in schedules]
    kb.append([Button.text("❌ Back")])
    await event.reply("🗑️ Select schedule to delete:", buttons=kb)
    bot.user_states[uid] = {'step': 'del_schedule_select'}


# ── Stats & Export ────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'📊 Statistics', incoming=True))
async def h_stats(event):
    if not await guard(event): return
    s = await bot.get_stats()
    rate = f"{s['rate']:.1f}%"

    cat_lines = ' | '.join(f"{cat}:{cnt}" for cat, cnt in s['by_category'])
    acc_lines = '\n'.join(
        f"  • `{a}`: {cnt} (✅{int(sc/cnt*100) if cnt else 0}%)"
        for a, cnt, sc in s['per_account']
    )
    tgt_lines = '\n'.join(f"  • `{t}`: {c}" for t, c in s['top_targets'])

    text = (
        f"📊 **STATISTICS**\n\n"
        f"📈 Total: **{s['total']}** | ✅ Sent: **{s['sent']}** | ❌ Failed: **{s['failed']}**\n"
        f"📊 Success Rate: **{rate}**\n"
        f"🟢 Active Accounts: **{s['active_accounts']}** | 🔴 Banned: **{s['banned_accounts']}**\n\n"
        f"📂 **By Category:** {cat_lines}\n\n"
        f"🏆 **Top Accounts:**\n{acc_lines or 'None'}\n\n"
        f"🎯 **Top Targets:**\n{tgt_lines or 'None'}"
    )
    await event.reply(text, buttons=kb_main())

@events.register(events.NewMessage(pattern=r'📤 Export CSV', incoming=True))
async def h_export_csv(event):
    if not await guard(event): return
    await event.reply("📤 Export all reports? Or enter @target to filter:", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'export_csv_filter'}


# ── Settings ──────────────────────────────────────────────

@events.register(events.NewMessage(pattern=r'⚙️ Settings', incoming=True))
async def h_settings(event):
    if not await guard(event): return
    mode  = bot.config.get('SPEED_MODE', 'balanced')
    conc  = bot.config.get('MAX_CONCURRENT', 5)
    text  = (
        f"⚙️ **SETTINGS**\n\n"
        f"⚡ Speed Mode: **{mode}**\n"
        f"🔢 Max Concurrent: **{conc}**\n\n"
        f"Choose:"
    )
    await event.reply(text, buttons=kb_settings())

@events.register(events.NewMessage(pattern=r'⚡ Speed: Fast', incoming=True))
async def h_speed_fast(event):
    if not await guard(event): return
    bot.config['SPEED_MODE'] = 'fast'; bot.save_config()
    await event.reply("⚡ Speed set to **FAST** (flood risk!)", buttons=kb_main())

@events.register(events.NewMessage(pattern=r'🛡️ Speed: Safe', incoming=True))
async def h_speed_safe(event):
    if not await guard(event): return
    bot.config['SPEED_MODE'] = 'safe'; bot.save_config()
    await event.reply("🛡️ Speed set to **SAFE** (anti-ban mode)", buttons=kb_main())

@events.register(events.NewMessage(pattern=r'⚖️ Speed: Balanced', incoming=True))
async def h_speed_bal(event):
    if not await guard(event): return
    bot.config['SPEED_MODE'] = 'balanced'; bot.save_config()
    await event.reply("⚖️ Speed set to **BALANCED**", buttons=kb_main())

@events.register(events.NewMessage(pattern=r'🔢 Max Concurrent', incoming=True))
async def h_max_conc(event):
    if not await guard(event): return
    await event.reply("🔢 Enter max concurrent accounts (1-20):", buttons=kb_back())
    bot.user_states[event.sender_id] = {'step': 'set_max_concurrent'}


# ═══════════════════════════════════════════════════════════
#                   MAIN TEXT HANDLER
# ═══════════════════════════════════════════════════════════

@events.register(events.NewMessage(incoming=True))
async def h_text(event):
    uid  = event.sender_id
    text = event.text.strip()

    if text in MENU_BUTTONS: return
    if uid not in bot.user_states: return

    state = bot.user_states[uid]
    step  = state['step']

    # ── LOGIN ─────────────────────────────────────────────
    if step == 'login_password':
        if text == bot.config.get('ADMIN_PASSWORD'):
            bot.authenticate_user(uid)
            await event.reply("✅ **LOGIN SUCCESS** 🎉\n\nWelcome, Admin!", buttons=kb_main())
        else:
            await event.reply("❌ Wrong password!", buttons=kb_login())
        del bot.user_states[uid]; return

    if not bot.is_authenticated(uid):
        await event.reply("❌ Login first!", buttons=kb_login())
        bot.user_states.pop(uid, None); return

    # ── ADD ACCOUNT ───────────────────────────────────────
    if step == 'add_name':
        state['name'] = text; state['step'] = 'add_phone'
        await event.reply("📱 Phone number (+91...):", buttons=kb_back())

    elif step == 'add_phone':
        state['phone'] = text; state['step'] = 'add_proxy'
        await event.reply("🌐 Select proxy:", buttons=kb_proxy())

    elif step == 'add_proxy':
        proxy = None if text in ('none',) else (bot.next_proxy() if text == '🔄 Auto Rotate' else text)
        ok, msg = await bot.add_account_flow(state['name'], state['phone'], proxy)
        if ok and "Code sent" in msg:
            state['step'] = 'add_verify'; state['proxy'] = proxy
            await event.reply(f"{msg}\n\nEnter OTP (or `code|2fa_pass`):", buttons=kb_back())
        else:
            await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    elif step == 'add_verify':
        parts = text.split('|', 1)
        ok, msg = await bot.verify_account_code(state['name'], parts[0].strip(), parts[1].strip() if len(parts) > 1 else None)
        await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    # ── IMPORT SESSION ────────────────────────────────────
    elif step == 'import_name':
        state['name'] = text; state['step'] = 'import_session'
        await event.reply("📋 Paste session string:", buttons=kb_back())

    elif step == 'import_session':
        state['session'] = text; state['step'] = 'import_proxy'
        await event.reply("🌐 Select proxy:", buttons=kb_proxy())

    elif step == 'import_proxy':
        proxy = None if text == 'none' else (bot.next_proxy() if text == '🔄 Auto Rotate' else text)
        ok, msg = await bot.add_account_from_session(state['name'], state['session'], None, proxy)
        await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    # ── EXPORT SESSION ────────────────────────────────────
    elif step == 'export_select':
        session, msg = await bot.export_session(text)
        if session:
            await event.reply(f"📥 **SESSION: `{text}`**\n\n`{session}`\n\n⚠️ Keep secret!", buttons=kb_main())
        else:
            await event.reply(msg, buttons=kb_main())
        del bot.user_states[uid]

    # ── DELETE ACCOUNT ────────────────────────────────────
    elif step == 'delete_acc_select':
        ok, msg = await bot.delete_account(text)
        await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    # ── SINGLE REPORT ─────────────────────────────────────
    elif step == 'report_account':
        state['account'] = text; state['step'] = 'report_target'
        await event.reply("🎯 Enter target (@username or ID):", buttons=kb_back())

    elif step == 'report_target':
        state['target'] = text; state['step'] = 'report_category'
        await event.reply("📂 Select category:", buttons=kb_category())

    elif step == 'report_category':
        cat = CATEGORY_MAP.get(text)
        if not cat:
            await event.reply("❌ Choose from buttons!", buttons=kb_category()); return
        msg_obj = await event.reply("⏳ Sending report...")
        ok, _, result = await bot.report_single(state['account'], state['target'], cat)
        await msg_obj.edit(
            f"{'✅' if ok else '❌'} **Report Result**\n\n"
            f"🎯 {state['target']}\n📂 {cat}\n💬 {result}",
            buttons=kb_main()
        )
        await bot.update_target_count(state['target'])
        del bot.user_states[uid]

    # ── MASS REPORT ───────────────────────────────────────
    elif step == 'mass_target':
        state['target'] = text; state['step'] = 'mass_category'
        await event.reply("📂 Select category:", buttons=kb_category())

    elif step == 'mass_category':
        cat = CATEGORY_MAP.get(text)
        if not cat:
            await event.reply("❌ Choose from buttons!", buttons=kb_category()); return

        accounts = await bot.get_all_accounts('active')
        total    = len(accounts)
        target   = state['target']

        msg_obj  = await event.reply(f"💥 **MASS REPORT STARTED**\n\n🎯 {target} | 📂 {cat}\n👥 {total} accounts\n\n⏳ 0/{total} done...")

        last_edit = [time.time()]

        async def on_progress(done, total, success, failed):
            if time.time() - last_edit[0] > 2:  # Edit every 2s to avoid flood
                bar = '█' * int(done/total*10) + '░' * (10 - int(done/total*10))
                try:
                    await msg_obj.edit(
                        f"💥 **MASS REPORT**\n\n"
                        f"🎯 {target} | 📂 {cat}\n"
                        f"[{bar}] {done}/{total}\n"
                        f"✅ {success} | ❌ {failed}"
                    )
                    last_edit[0] = time.time()
                except: pass

        results, success, failed = await bot.mass_report(target, cat, progress_cb=on_progress)
        await bot.update_target_count(target)

        # Final result
        failed_accs = [name for ok, name, _ in results if not ok]
        fail_text = f"\n❌ Failed: {', '.join(failed_accs[:5])}" if failed_accs else ""

        await msg_obj.edit(
            f"💥 **MASS REPORT COMPLETE**\n\n"
            f"🎯 {target} | 📂 {cat}\n"
            f"✅ Success: {success}/{total}\n"
            f"❌ Failed: {failed}{fail_text}",
            buttons=kb_main()
        )
        del bot.user_states[uid]

    # ── BATCH TARGETS ─────────────────────────────────────
    elif step == 'batch_targets_input':
        targets = [t.strip() for t in text.split(',') if t.strip()]
        if not targets:
            await event.reply("❌ Invalid input!", buttons=kb_back()); return
        state['targets'] = targets; state['step'] = 'batch_category'
        await event.reply(f"📂 Select category for {len(targets)} targets:", buttons=kb_category())

    elif step == 'batch_category':
        cat = CATEGORY_MAP.get(text)
        if not cat:
            await event.reply("❌ Choose from buttons!", buttons=kb_category()); return

        targets = state['targets']
        msg_obj = await event.reply(f"🔥 **BATCH REPORT**\n\n{len(targets)} targets | 📂 {cat}\n\nStarting...")

        grand_ok, grand_fail = 0, 0
        for i, tgt in enumerate(targets):
            _, ok, fail = await bot.mass_report(tgt, cat)
            grand_ok += ok; grand_fail += fail
            await bot.update_target_count(tgt)
            try:
                await msg_obj.edit(
                    f"🔥 **BATCH REPORT**\n\n"
                    f"Progress: {i+1}/{len(targets)} targets\n"
                    f"✅ {grand_ok} | ❌ {grand_fail}"
                )
            except: pass
            await asyncio.sleep(3)

        await msg_obj.edit(
            f"🔥 **BATCH COMPLETE**\n\n"
            f"📋 Targets: {len(targets)}\n"
            f"✅ Total sent: {grand_ok}\n"
            f"❌ Total failed: {grand_fail}",
            buttons=kb_main()
        )
        del bot.user_states[uid]

    # ── SAVED TARGETS ─────────────────────────────────────
    elif step == 'save_target_input':
        parts = [p.strip() for p in text.split('|')]
        if len(parts) < 3:
            await event.reply("❌ Format: `label|@target|category|note`", buttons=kb_back()); return
        label = parts[0]; tgt = parts[1]; cat = parts[2]
        note  = parts[3] if len(parts) > 3 else ''
        if cat not in REPORT_CATEGORIES:
            await event.reply(f"❌ Invalid category: {cat}", buttons=kb_back()); return
        ok, msg = await bot.save_target(label, tgt, cat, note)
        await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    elif step == 'report_saved_select':
        saved_map = state.get('saved_targets', {})
        if text not in saved_map:
            await event.reply("❌ Not found!", buttons=kb_back()); return
        _, tgt, cat, _, _ = saved_map[text]
        msg_obj = await event.reply(f"🚀 Running mass report on `{text}`...")
        _, success, failed = await bot.mass_report(tgt, cat)
        await bot.update_target_count(tgt)
        await msg_obj.edit(
            f"🚀 **SAVED TARGET REPORTED**\n\n🏷️ {text}\n🎯 {tgt}\n📂 {cat}\n✅ {success} | ❌ {failed}",
            buttons=kb_main()
        )
        del bot.user_states[uid]

    elif step == 'del_saved_select':
        ok, msg = await bot.delete_saved_target(text)
        await event.reply(msg, buttons=kb_main()); del bot.user_states[uid]

    # ── TARGET INFO ───────────────────────────────────────
    elif step == 'info_target':
        msg_obj = await event.reply("🔍 Looking up info...")
        info, status = await bot.get_target_info(text)
        if not info:
            await msg_obj.edit(f"❌ {status}", buttons=kb_main())
        else:
            name_str = f"{info['first_name']} {info['last_name']}".strip() or info['title']
            members  = f"\n👥 Members: {info.get('members', 'N/A')}" if 'members' in info else ""
            desc     = f"\n📝 Bio: {info['description'][:80]}" if info.get('description') else ""
            report_count = 0
            async with aiosqlite.connect(bot.reports_db) as db:
                async with db.execute('SELECT COUNT(*) FROM reports WHERE target=?', (text.lstrip('@'),)) as c:
                    report_count = (await c.fetchone())[0]

            await msg_obj.edit(
                f"🔍 **TARGET INFO**\n\n"
                f"📌 Type: {info['type']}\n"
                f"👤 Name: {name_str}\n"
                f"🔗 Username: {info['username']}\n"
                f"🆔 ID: `{info['id']}`\n"
                f"📱 Phone: {info['phone']}"
                f"{members}{desc}\n"
                f"✅ Verified: {info['verified']}\n"
                f"⚠️ Restricted: {info['restricted']}\n"
                f"🚨 Scam Flag: {info['scam']}\n"
                f"🎭 Fake Flag: {info['fake']}\n"
                f"📊 Reports by us: {report_count}",
                buttons=kb_main()
            )
        del bot.user_states[uid]

    # ── SCHEDULER ─────────────────────────────────────────
    elif step == 'new_schedule_input':
        parts = [p.strip() for p in text.split('|')]
        if len(parts) < 5:
            await event.reply("❌ Format: `label|@target|category|interval_min|max_runs`", buttons=kb_back()); return
        label, tgt, cat, interval_str, max_str = parts[0], parts[1], parts[2], parts[3], parts[4]
        if cat not in REPORT_CATEGORIES:
            await event.reply(f"❌ Invalid category!", buttons=kb_back()); return
        try:
            interval = int(interval_str); max_runs = int(max_str)
        except:
            await event.reply("❌ Interval and max_runs must be numbers!", buttons=kb_back()); return

        accounts = await bot.get_all_accounts('active')
        acc_names = [r[0] for r in accounts]
        sid = await bot.create_schedule(uid, label, tgt, cat, acc_names, interval, max_runs)
        await event.reply(
            f"✅ **Schedule Created** [ID:{sid}]\n\n"
            f"🏷️ {label}\n🎯 {tgt}\n📂 {cat}\n"
            f"⏱️ Every {interval} min | 🔁 Max {max_runs or '∞'} runs\n"
            f"👥 {len(acc_names)} accounts assigned",
            buttons=kb_main()
        )
        del bot.user_states[uid]

    elif step == 'del_schedule_select':
        import re
        match = re.match(r'\[(\d+)\]', text)
        if match:
            sid = int(match.group(1))
            await bot.delete_schedule(sid)
            await event.reply(f"🗑️ Schedule [{sid}] deleted!", buttons=kb_main())
        else:
            await event.reply("❌ Invalid selection!", buttons=kb_back())
        del bot.user_states[uid]

    # ── CSV EXPORT ────────────────────────────────────────
    elif step == 'export_csv_filter':
        target_filter = None if text.lower() in ('all', 'yes', '') else text
        path, msg = await bot.export_reports_csv(target_filter)
        if path:
            await bot.bot_client.send_file(uid, path,
                caption=f"📤 **Reports Export**\n{msg}",
                buttons=kb_main()
            )
            try: os.remove(path)
            except: pass
        else:
            await event.reply(msg, buttons=kb_main())
        del bot.user_states[uid]

    # ── SETTINGS ──────────────────────────────────────────
    elif step == 'set_max_concurrent':
        try:
            val = int(text)
            if 1 <= val <= 20:
                bot.config['MAX_CONCURRENT'] = val
                bot.save_config()
                await event.reply(f"✅ Max concurrent set to **{val}**", buttons=kb_main())
            else:
                await event.reply("❌ Enter 1–20!", buttons=kb_back())
                return
        except:
            await event.reply("❌ Numbers only!", buttons=kb_back())
            return
        del bot.user_states[uid]


# ═══════════════════════════════════════════════════════════
#                        MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    await bot.init_db()
    log.info("✅ Database ready")

    bot.bot_client = TelegramClient(
        'bot_session',
        int(bot.config['API_ID']),
        bot.config['API_HASH']
    )
    await bot.bot_client.start(bot_token=bot.config['BOT_TOKEN'])
    log.info("✅ Bot client started")

    # Register all handlers
    handlers = [
        (h_start,        events.NewMessage(pattern=r'/start', incoming=True)),
        (h_login,        events.NewMessage(pattern=r'🔐 Login', incoming=True)),
        (h_logout,       events.NewMessage(pattern=r'❌ Logout', incoming=True)),
        (h_back,         events.NewMessage(pattern=r'❌ Back', incoming=True)),
        (h_add,          events.NewMessage(pattern=r'➕ Add Account', incoming=True)),
        (h_import,       events.NewMessage(pattern=r'📤 Import Session', incoming=True)),
        (h_export,       events.NewMessage(pattern=r'📥 Export Session', incoming=True)),
        (h_list,         events.NewMessage(pattern=r'📋 Accounts', incoming=True)),
        (h_delete_acc,   events.NewMessage(pattern=r'🗑️ Delete Account', incoming=True)),
        (h_health,       events.NewMessage(pattern=r'🏥 Health Check', incoming=True)),
        (h_report,       events.NewMessage(pattern=r'🎯 Report', incoming=True)),
        (h_mass,         events.NewMessage(pattern=r'💥 Mass Report', incoming=True)),
        (h_batch,        events.NewMessage(pattern=r'🔥 Batch Targets', incoming=True)),
        (h_saved,        events.NewMessage(pattern=r'💾 Saved Targets', incoming=True)),
        (h_save_new,     events.NewMessage(pattern=r'💾 Save New Target', incoming=True)),
        (h_report_saved, events.NewMessage(pattern=r'🚀 Report Saved Target', incoming=True)),
        (h_del_saved,    events.NewMessage(pattern=r'🗑️ Delete Saved Target', incoming=True)),
        (h_info,         events.NewMessage(pattern=r'🔍 Target Info', incoming=True)),
        (h_scheduler,    events.NewMessage(pattern=r'⏰ Scheduler', incoming=True)),
        (h_new_schedule, events.NewMessage(pattern=r'➕ New Schedule', incoming=True)),
        (h_del_schedule, events.NewMessage(pattern=r'🗑️ Delete Schedule', incoming=True)),
        (h_stats,        events.NewMessage(pattern=r'📊 Statistics', incoming=True)),
        (h_export_csv,   events.NewMessage(pattern=r'📤 Export CSV', incoming=True)),
        (h_settings,     events.NewMessage(pattern=r'⚙️ Settings', incoming=True)),
        (h_speed_fast,   events.NewMessage(pattern=r'⚡ Speed: Fast', incoming=True)),
        (h_speed_safe,   events.NewMessage(pattern=r'🛡️ Speed: Safe', incoming=True)),
        (h_speed_bal,    events.NewMessage(pattern=r'⚖️ Speed: Balanced', incoming=True)),
        (h_max_conc,     events.NewMessage(pattern=r'🔢 Max Concurrent', incoming=True)),
        (h_text,         events.NewMessage(incoming=True)),
    ]
    for handler, evt in handlers:
        bot.bot_client.add_event_handler(handler, evt)

    log.info("✅ All handlers registered")

    # Start background scheduler
    asyncio.create_task(bot.run_scheduler())
    log.info("✅ Scheduler started")

    print("\n" + "═"*50)
    print("  🔥 ULTRA REPORT BOT v8.0 is RUNNING")
    print("═"*50 + "\n")

    await bot.bot_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
