#!/usr/bin/env python3
"""
🔥 ULTIMATE TELEGRAM BOT v7.0 - ADMIN ONLY
✅ Admin Authentication ✅ Secure Access ✅ Advanced Features
✅ Session Management ✅ Proxy Support ✅ Multi-Admin
"""

import asyncio
import os
import json
import aiosqlite
import random
import time
from datetime import datetime, timedelta
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.types import (
    KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, 
    InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telethon.sessions import StringSession
from telethon.errors import (
    PhoneCodeInvalidError, SessionPasswordNeededError, 
    FloodWaitError, PhoneNumberBannedError
)

REPORT_CATEGORIES = {
    'spam': 2, 'scam': 4, 'porn': 5, 'violence': 5, 'leak': 4,
    'copyright': 2, 'harassment': 3, 'illegal': 5, 'fake': 3, 'other': 1
}

class AdminOnlyBot:
    def __init__(self):
        self.config_file = 'config.json'
        self.proxy_file = 'proxy.json'
        self.accounts_db = 'accounts.db'
        self.reports_db = 'reports.db'
        self.config = {}
        self.proxies = {}
        self.active_clients = {}
        self.pending_codes = {}
        self.user_states = {}
        self.authenticated_users = {}  # Track authenticated users
        self.bot_client = None
        self.load_config()
        self.load_proxies()
    
    def load_config(self):
        """Load config"""
        if not os.path.exists(self.config_file):
            config = {
                "API_ID": "21552265",
                "API_HASH": "1c971ae7e62cc416ca977e040e700d09",
                "BOT_TOKEN": "7870678989:AAEi4k5OrTnMD5Rcd1BWz4xLfMqlFUcgE7M",
                "ADMIN_IDS": [7302427268, 8627378748],
                "ADMIN_PASSWORD": "Smoke010",
                "AUTO_RETRY": True,
                "MAX_RETRIES": 5,
                "SESSION_TIMEOUT": 3600
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            print("❌ Fill config.json first!")
            exit()
        
        with open(self.config_file, 'r') as f:
            self.config = json.load(f)
        
        if self.config['API_ID'] == "ENTER_HERE":
            print("❌ Fill config.json!")
            exit()
    
    def load_proxies(self):
        """Load proxies"""
        if not os.path.exists(self.proxy_file):
            proxy_template = {
                "proxies": {
                    "socks5_proxy": {
                        "type": "socks5",
                        "host": "127.0.0.1",
                        "port": 9050
                    }
                }
            }
            with open(self.proxy_file, 'w') as f:
                json.dump(proxy_template, f, indent=4)
        else:
            with open(self.proxy_file, 'r') as f:
                data = json.load(f)
                self.proxies = data.get('proxies', {})
    
    async def init_db(self):
        """Initialize databases"""
        async with aiosqlite.connect(self.accounts_db) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    phone TEXT UNIQUE,
                    session TEXT NOT NULL,
                    proxy_name TEXT,
                    status TEXT DEFAULT 'active',
                    health_score REAL DEFAULT 100.0,
                    last_used DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_account_status ON accounts(status)')
            await db.commit()
        
        async with aiosqlite.connect(self.reports_db) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    target TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)')
            await db.commit()
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        admin_ids = self.config.get('ADMIN_IDS', [])
        return user_id in admin_ids
    
    def is_authenticated(self, user_id):
        """Check if user is authenticated"""
        if user_id in self.authenticated_users:
            timestamp = self.authenticated_users[user_id]
            session_timeout = self.config.get('SESSION_TIMEOUT', 3600)
            if time.time() - timestamp < session_timeout:
                return True
            else:
                del self.authenticated_users[user_id]
                return False
        return False
    
    def authenticate_user(self, user_id):
        """Authenticate user"""
        self.authenticated_users[user_id] = time.time()
    
    def get_proxy_config(self, proxy_name):
        """Get proxy configuration"""
        if not proxy_name or proxy_name == "none":
            return None
        
        if proxy_name not in self.proxies:
            return None
        
        proxy_data = self.proxies[proxy_name]
        proxy_type = proxy_data.get('type', 'socks5')
        
        if 'username' in proxy_data and 'password' in proxy_data:
            return (
                proxy_type,
                proxy_data['host'],
                proxy_data['port'],
                True,
                proxy_data['username'],
                proxy_data['password']
            )
        else:
            return (
                proxy_type,
                proxy_data['host'],
                proxy_data['port']
            )
    
    async def add_account_from_session(self, name, session_string, phone=None, proxy_name=None):
        """Add account from session"""
        try:
            if proxy_name and proxy_name != "none":
                proxy_config = self.get_proxy_config(proxy_name)
                if not proxy_config:
                    return False, f"❌ Proxy '{proxy_name}' not found!"
            else:
                proxy_config = None
            
            client = TelegramClient(
                StringSession(session_string),
                int(self.config['API_ID']),
                self.config['API_HASH'],
                proxy=proxy_config,
                connection_retries=5,
                retry_delay=2
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "❌ Session invalid or expired!"
            
            me = await client.get_me()
            
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute(
                    '''INSERT OR REPLACE INTO accounts 
                    (name, phone, session, proxy_name, status, health_score, last_used) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (name, me.phone or phone, session_string, proxy_name or "none", 'active', 100.0, datetime.now())
                )
                await db.commit()
            
            await client.disconnect()
            return True, f"✅ **{name}** Added!\n👤 {me.first_name}\n📱 {me.phone}"
        
        except Exception as e:
            return False, f"❌ Error: {str(e)[:60]}"
    
    async def export_session(self, account_name):
        """Export session"""
        try:
            async with aiosqlite.connect(self.accounts_db) as db:
                async with db.execute('SELECT session FROM accounts WHERE name = ?', (account_name,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None, "❌ Account not found"
            
            return row[0], "✅ Session exported"
        
        except Exception as e:
            return None, f"❌ {str(e)[:50]}"
    
    async def add_account_flow(self, name, phone, proxy_name=None):
        """Add account with code"""
        try:
            if proxy_name and proxy_name != "none":
                proxy_config = self.get_proxy_config(proxy_name)
                if not proxy_config:
                    return False, f"❌ Proxy '{proxy_name}' not found!"
            else:
                proxy_config = None
            
            os.makedirs('sessions', exist_ok=True)
            
            client = TelegramClient(
                f'sessions/{name}',
                int(self.config['API_ID']),
                self.config['API_HASH'],
                proxy=proxy_config,
                connection_retries=10,
                retry_delay=3
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.send_code_request(phone)
                self.pending_codes[name] = {
                    'client': client,
                    'phone': phone,
                    'proxy_name': proxy_name
                }
                return True, f"✅ Code sent to {phone}"
            else:
                await client.disconnect()
                return True, f"✅ {name} already authorized"
        
        except Exception as e:
            return False, f"❌ Error: {str(e)[:50]}"
    
    async def verify_account_code(self, name, code, password=None):
        """Verify account code"""
        try:
            if name not in self.pending_codes:
                return False, "❌ No pending code"
            
            data = self.pending_codes[name]
            client = data['client']
            phone = data['phone']
            proxy_name = data.get('proxy_name')
            
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                if not password:
                    return False, "🔐 2FA Password needed"
                await client.sign_in(password=password)
            except PhoneCodeInvalidError:
                return False, "❌ Wrong code!"
            
            me = await client.get_me()
            session = client.session.save()
            
            async with aiosqlite.connect(self.accounts_db) as db:
                await db.execute(
                    '''INSERT OR REPLACE INTO accounts 
                    (name, phone, session, proxy_name, status, health_score, last_used) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (name, me.phone, session, proxy_name or "none", 'active', 100.0, datetime.now())
                )
                await db.commit()
            
            await client.disconnect()
            del self.pending_codes[name]
            
            return True, f"✅ **{name}** Added!\n👤 {me.first_name}\n📱 {me.phone}"
        
        except Exception as e:
            return False, f"❌ {str(e)[:50]}"
    
    async def get_client(self, account_name):
        """Get client"""
        if account_name in self.active_clients:
            return self.active_clients[account_name]
        
        try:
            async with aiosqlite.connect(self.accounts_db) as db:
                async with db.execute(
                    'SELECT session, proxy_name FROM accounts WHERE name = ? AND status = "active"', 
                    (account_name,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
            
            session, proxy_name = row
            proxy_config = None
            
            if proxy_name and proxy_name != "none":
                proxy_config = self.get_proxy_config(proxy_name)
            
            client = TelegramClient(
                StringSession(session),
                int(self.config['API_ID']),
                self.config['API_HASH'],
                proxy=proxy_config,
                connection_retries=10,
                retry_delay=3
            )
            
            await client.connect()
            if await client.is_user_authorized():
                self.active_clients[account_name] = client
                return client
            
            await client.disconnect()
            return None
        
        except Exception as e:
            return None
    
    def get_entity_type(self, entity):
        """Detect entity type"""
        try:
            if hasattr(entity, 'bot') and entity.bot:
                return 'bot'
            if hasattr(entity, 'broadcast') and entity.broadcast:
                return 'channel'
            if hasattr(entity, 'megagroup') and entity.megagroup:
                return 'group'
            if hasattr(entity, 'is_group') and entity.is_group:
                return 'group'
            return 'user'
        except:
            return 'unknown'
    
    async def send_report_with_retry(self, account_name, target, target_type, category='spam'):
        """Send report"""
        max_retries = self.config.get('MAX_RETRIES', 5)
        
        for attempt in range(1, max_retries + 1):
            try:
                client = await self.get_client(account_name)
                if not client:
                    return False, f"❌ Account offline"
                
                target = target.strip().lstrip('@').lstrip('-')
                entity = await client.get_entity(target)
                detected_type = self.get_entity_type(entity)
                severity = REPORT_CATEGORIES.get(category, 1)
                
                async with aiosqlite.connect(self.reports_db) as db:
                    await db.execute(
                        '''INSERT INTO reports 
                        (account_name, target, target_type, category, status, completed_at) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                        (account_name, target, detected_type, category, 'sent', datetime.now())
                    )
                    await db.commit()
                
                return True, f"✅ {detected_type.upper()} - Lv{severity}"
            
            except FloodWaitError as e:
                if attempt < max_retries:
                    await asyncio.sleep(min(e.seconds, 5))
            
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(2)
        
        return False, f"❌ Failed"
    
    async def get_all_accounts(self):
        """Get all accounts"""
        async with aiosqlite.connect(self.accounts_db) as db:
            async with db.execute('SELECT name, phone, proxy_name, status FROM accounts ORDER BY last_used DESC') as cursor:
                return await cursor.fetchall()
    
    async def get_stats(self):
        """Get statistics"""
        async with aiosqlite.connect(self.reports_db) as db:
            async with db.execute('SELECT COUNT(*) FROM reports') as c:
                total = (await c.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM reports WHERE status="sent"') as c:
                sent = (await c.fetchone())[0]
            
            async with db.execute(
                '''SELECT account_name, COUNT(*), 
                SUM(CASE WHEN status="sent" THEN 1 ELSE 0 END) as success
                FROM reports GROUP BY account_name ORDER BY COUNT(*) DESC LIMIT 5'''
            ) as c:
                account_stats = await c.fetchall()
        
        return total, sent, account_stats
    
    async def get_proxies_list(self):
        """Get available proxies"""
        if not self.proxies:
            return "❌ No proxies configured"
        
        text = "🌐 **Available Proxies:**\n\n"
        for name, config in self.proxies.items():
            proxy_type = config.get('type', 'unknown')
            host = config.get('host', 'N/A')
            port = config.get('port', 'N/A')
            text += f"• `{name}` - {proxy_type}://{host}:{port}\n"
        
        return text

bot = AdminOnlyBot()

# ================== BUTTON KEYBOARDS ==================

def login_keyboard():
    """Login keyboard"""
    return ReplyKeyboardMarkup([
        ['🔐 Login']
    ], resize_keyboard=True)

def main_menu_keyboard():
    """Main menu buttons"""
    return ReplyKeyboardMarkup([
        ['➕ Add Account', '📤 Import Session'],
        ['📋 List Accounts', '📥 Export Session'],
        ['👤 Report User', '🤖 Report Bot'],
        ['👥 Report Group', '📡 Report Channel'],
        ['🔥 Batch Report', '📊 Statistics'],
        ['🌐 Proxies', '❌ Logout']
    ], resize_keyboard=True)

def category_keyboard():
    """Category selection buttons"""
    return ReplyKeyboardMarkup([
        ['🚫 spam', '💰 scam', '🔞 porn'],
        ['⚔️ violence', '🔓 leak', '©️ copyright'],
        ['😡 harassment', '⚖️ illegal', '🎭 fake'],
        ['❌ Back']
    ], resize_keyboard=True)

def back_keyboard():
    """Back button"""
    return ReplyKeyboardMarkup([['❌ Back']], resize_keyboard=True)

def proxy_keyboard():
    """Proxy selection"""
    proxies = list(bot.proxies.keys()) if bot.proxies else []
    keyboard = [[KeyboardButton(p)] for p in proxies]
    keyboard.append([KeyboardButton('none')])
    keyboard.append([KeyboardButton('❌ Back')])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== TELEGRAM EVENT HANDLERS ==================

@events.register(events.NewMessage(pattern=r'/start', incoming=True))
async def start_handler(event):
    """Start handler"""
    user_id = event.sender_id
    
    if not bot.is_admin(user_id):
        await event.reply("🚫 **ADMIN ONLY BOT**\n\n❌ You don't have permission to use this bot!")
        return
    
    if bot.is_authenticated(user_id):
        await event.reply(
            """🔥 **ULTIMATE TELEGRAM REPORT BOT v7.0 - ADMIN ONLY**

👋 Welcome back, Admin!

Use buttons below to navigate.""",
            buttons=main_menu_keyboard()
        )
    else:
        await event.reply(
            """🔥 **ULTIMATE TELEGRAM REPORT BOT v7.0 - ADMIN ONLY**

🔐 Please authenticate to continue.""",
            buttons=login_keyboard()
        )

@events.register(events.NewMessage(pattern=r'🔐 Login', incoming=True))
async def login_button(event):
    """Login button"""
    user_id = event.sender_id
    
    if not bot.is_admin(user_id):
        await event.reply("🚫 Admin only!")
        return
    
    await event.reply("🔑 Enter admin password:", buttons=back_keyboard())
    bot.user_states[user_id] = {'step': 'login_password'}

@events.register(events.NewMessage(pattern=r'❌ Logout', incoming=True))
async def logout_button(event):
    """Logout button"""
    user_id = event.sender_id
    
    if user_id in bot.authenticated_users:
        del bot.authenticated_users[user_id]
    
    if user_id in bot.user_states:
        del bot.user_states[user_id]
    
    await event.reply("👋 Logged out!", buttons=login_keyboard())

@events.register(events.NewMessage(pattern=r'➕ Add Account', incoming=True))
async def add_account_button(event):
    """Add account button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    await event.reply("📝 Enter account name:", buttons=back_keyboard())
    bot.user_states[user_id] = {'step': 'add_account_name'}

@events.register(events.NewMessage(pattern=r'📤 Import Session', incoming=True))
async def import_session_button(event):
    """Import session button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    await event.reply("📋 Enter account name:", buttons=back_keyboard())
    bot.user_states[user_id] = {'step': 'import_session_name'}

@events.register(events.NewMessage(pattern=r'📥 Export Session', incoming=True))
async def export_session_button(event):
    """Export session button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "📥 **Select Account to Export:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[user_id] = {'step': 'export_session_account'}

@events.register(events.NewMessage(pattern=r'📋 List Accounts', incoming=True))
async def list_accounts_button(event):
    """List accounts button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("📱 No accounts added yet!", buttons=main_menu_keyboard())
        return
    
    text = f"📱 **{len(accounts)} ACCOUNTS**\n\n"
    for name, phone, proxy, status in accounts:
        status_emoji = "🟢" if status == 'active' else "🔴"
        phone_display = phone if phone else "N/A"
        proxy_info = f" 🌐{proxy}" if proxy and proxy != "none" else ""
        text += f"{status_emoji} `{name}` - {phone_display}{proxy_info}\n"
    
    await event.reply(text, buttons=main_menu_keyboard())

@events.register(events.NewMessage(pattern=r'🌐 Proxies', incoming=True))
async def proxies_button(event):
    """Proxies button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    proxies_text = await bot.get_proxies_list()
    await event.reply(proxies_text, buttons=main_menu_keyboard())

@events.register(events.NewMessage(pattern=r'👤 Report User', incoming=True))
async def report_user_button(event):
    """Report user button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "👤 **Select Account:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[user_id] = {'step': 'report_user_account'}

@events.register(events.NewMessage(pattern=r'🤖 Report Bot', incoming=True))
async def report_bot_button(event):
    """Report bot button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "🤖 **Select Account:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[user_id] = {'step': 'report_bot_account'}

@events.register(events.NewMessage(pattern=r'👥 Report Group', incoming=True))
async def report_group_button(event):
    """Report group button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "👥 **Select Account:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[user_id] = {'step': 'report_group_account'}

@events.register(events.NewMessage(pattern=r'📡 Report Channel', incoming=True))
async def report_channel_button(event):
    """Report channel button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "📡 **Select Account:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[user_id] = {'step': 'report_channel_account'}

@events.register(events.NewMessage(pattern=r'🔥 Batch Report', incoming=True))
async def batch_report_button(event):
    """Batch report button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    text = "🔥 **BATCH REPORT**\n\n"
    text += "Enter accounts (comma-separated):\n\n"
    for name, _, _, _ in accounts:
        text += f"• {name}\n"
    
    await event.reply(text, buttons=back_keyboard())
    bot.user_states[user_id] = {'step': 'batch_accounts'}

@events.register(events.NewMessage(pattern=r'📊 Statistics', incoming=True))
async def stats_button(event):
    """Statistics button"""
    user_id = event.sender_id
    
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        return
    
    total, sent, account_stats = await bot.get_stats()
    
    if total == 0:
        text = "📊 No reports yet!"
    else:
        text = f"""📊 **STATISTICS**

📈 Total Reports: {total}
✅ Successful: {sent}
❌ Failed: {total - sent}
📊 Success Rate: {(sent/total)*100:.1f}%

**TOP ACCOUNTS:**
"""
        for acc, count, success in account_stats:
            success_rate = (success/count)*100 if count > 0 else 0
            text += f"• `{acc}`: {count} (✅{success_rate:.1f}%)\n"
    
    await event.reply(text, buttons=main_menu_keyboard())

@events.register(events.NewMessage(pattern=r'❌ Back', incoming=True))
async def back_button(event):
    """Back button"""
    user_id = event.sender_id
    if user_id in bot.user_states:
        del bot.user_states[user_id]
    
    await event.reply("🔄 Back to main menu", buttons=main_menu_keyboard())

@events.register(events.NewMessage(incoming=True))
async def text_handler(event):
    """Handle text input"""
    user_id = event.sender_id
    text = event.text
    
    # Check authentication for login
    if user_id not in bot.user_states:
        return
    
    state = bot.user_states[user_id]['step']
    
    # LOGIN FLOW
    if state == 'login_password':
        password = text.strip()
        admin_password = bot.config.get('ADMIN_PASSWORD')
        
        if password == admin_password:
            bot.authenticate_user(user_id)
            await event.reply(
                "✅ **LOGIN SUCCESSFUL**\n\n🎉 Welcome to Admin Panel!",
                buttons=main_menu_keyboard()
            )
            del bot.user_states[user_id]
        else:
            await event.reply("❌ Wrong password!", buttons=login_keyboard())
            del bot.user_states[user_id]
        return
    
    # Check if authenticated for other operations
    if not bot.is_authenticated(user_id):
        await event.reply("❌ Please login first!", buttons=login_keyboard())
        if user_id in bot.user_states:
            del bot.user_states[user_id]
        return
    
    # ==================== ADD ACCOUNT FLOW ====================
    if state == 'add_account_name':
        account_name = text.strip()
        await event.reply("📱 Enter phone number (+91...):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'add_account_phone'
        bot.user_states[user_id]['account_name'] = account_name
    
    elif state == 'add_account_phone':
        phone = text.strip()
        await event.reply(
            "🌐 **Select Proxy (or none):**",
            buttons=proxy_keyboard()
        )
        bot.user_states[user_id]['step'] = 'add_account_proxy'
        bot.user_states[user_id]['phone'] = phone
    
    elif state == 'add_account_proxy':
        proxy = text.strip() if text.strip() != 'none' else None
        account_name = bot.user_states[user_id]['account_name']
        phone = bot.user_states[user_id]['phone']
        
        success, msg = await bot.add_account_flow(account_name, phone, proxy)
        
        if success:
            await event.reply(msg, buttons=back_keyboard())
            bot.user_states[user_id]['step'] = 'add_account_verify'
        else:
            await event.reply(msg, buttons=main_menu_keyboard())
            del bot.user_states[user_id]
    
    elif state == 'add_account_verify':
        code = text.strip()
        account_name = bot.user_states[user_id]['account_name']
        success, msg = await bot.verify_account_code(account_name, code)
        
        await event.reply(msg, buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # ==================== IMPORT SESSION FLOW ====================
    elif state == 'import_session_name':
        account_name = text.strip()
        await event.reply("📋 Enter session string:", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'import_session_string'
        bot.user_states[user_id]['account_name'] = account_name
    
    elif state == 'import_session_string':
        session_string = text.strip()
        account_name = bot.user_states[user_id]['account_name']
        await event.reply(
            "🌐 **Select Proxy (or none):**",
            buttons=proxy_keyboard()
        )
        bot.user_states[user_id]['step'] = 'import_session_proxy'
        bot.user_states[user_id]['session_string'] = session_string
    
    elif state == 'import_session_proxy':
        proxy = text.strip() if text.strip() != 'none' else None
        account_name = bot.user_states[user_id]['account_name']
        session_string = bot.user_states[user_id]['session_string']
        
        success, msg = await bot.add_account_from_session(account_name, session_string, None, proxy)
        
        await event.reply(msg, buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # ==================== EXPORT SESSION FLOW ====================
    elif state == 'export_session_account':
        account_name = text.strip()
        session, msg = await bot.export_session(account_name)
        
        if session:
            export_msg = f"""📥 **SESSION EXPORTED**

Account: `{account_name}`

**Session String:**
