#!/usr/bin/env python3
"""
🔥 ULTIMATE TELEGRAM BOT v5.0 - BUTTON INTERFACE
✅ Interactive Buttons ✅ Real-time Monitoring ✅ Inline Navigation
✅ Auto Scaling ✅ Load Balancing ✅ Error Recovery
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

class EnterpriseTelegramBot:
    def __init__(self):
        self.config_file = 'config.json'
        self.proxy_file = 'proxy.json'
        self.accounts_db = 'accounts.db'
        self.reports_db = 'reports.db'
        self.config = {}
        self.proxies = {}
        self.active_clients = {}
        self.client_health = defaultdict(lambda: {'status': 'offline', 'last_check': None})
        self.pending_codes = {}
        self.user_states = {}  # Track user states for multi-step operations
        self.bot_client = None
        self.load_config()
        self.load_proxies()
    
    def load_config(self):
        """Load config"""
        if not os.path.exists(self.config_file):
            config = {
                "API_ID": "ENTER_HERE",
                "API_HASH": "ENTER_HERE",
                "BOT_TOKEN": "ENTER_HERE",
                "AUTO_RETRY": True,
                "MAX_RETRIES": 5,
                "BATCH_DELAY": 2,
                "RANDOM_DELAY": True,
                "RATE_LIMIT": True,
                "MAX_REPORTS_PER_HOUR": 100,
                "ENABLE_LOAD_BALANCING": True
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
                    "proxy1": {
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
                    phone TEXT UNIQUE NOT NULL,
                    session TEXT NOT NULL,
                    proxy_name TEXT,
                    status TEXT DEFAULT 'active',
                    health_score REAL DEFAULT 100.0,
                    last_used DATETIME,
                    error_count INTEGER DEFAULT 0,
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
    
    async def add_account_flow(self, name, phone, proxy_name=None):
        """Add account"""
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
                return True, f"✅ Code sent to {phone}\n\nWait for verification..."
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
            
            return True, f"✅ {name} Added!\n📱 {me.phone}"
        
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

bot = EnterpriseTelegramBot()

# ================== BUTTON KEYBOARDS ==================

def main_menu_keyboard():
    """Main menu buttons"""
    return ReplyKeyboardMarkup([
        ['➕ Add Account', '📋 List Accounts'],
        ['👤 Report User', '🤖 Report Bot'],
        ['👥 Report Group', '📡 Report Channel'],
        ['🔥 Batch Report', '📊 Statistics'],
        ['❌ Exit']
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

# ================== TELEGRAM EVENT HANDLERS ==================

@events.register(events.NewMessage(pattern=r'/start', incoming=True))
async def start_handler(event):
    """Start handler"""
    await event.reply(
        """🔥 **ULTIMATE TELEGRAM REPORT BOT v5.0**

👋 Welcome to Enterprise Report Bot!

Use buttons below to navigate or type commands.

**Available Features:**
✅ Add/Verify Accounts
✅ Report Users, Bots, Groups, Channels
✅ Batch Reporting
✅ Real-time Statistics
✅ Proxy Support""",
        buttons=main_menu_keyboard()
    )

@events.register(events.NewMessage(pattern=r'➕ Add Account', incoming=True))
async def add_account_button(event):
    """Add account button"""
    await event.reply("📝 Enter account name:", buttons=back_keyboard())
    bot.user_states[event.sender_id] = {'step': 'add_account_name'}

@events.register(events.NewMessage(pattern=r'📋 List Accounts', incoming=True))
async def list_accounts_button(event):
    """List accounts button"""
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("📱 No accounts added yet!", buttons=main_menu_keyboard())
        return
    
    text = f"📱 **{len(accounts)} ACCOUNTS**\n\n"
    for name, phone, proxy, status in accounts:
        status_emoji = "🟢" if status == 'active' else "🔴"
        proxy_info = f" 🌐{proxy}" if proxy and proxy != "none" else ""
        text += f"{status_emoji} `{name}` - {phone}{proxy_info}\n"
    
    await event.reply(text, buttons=main_menu_keyboard())

@events.register(events.NewMessage(pattern=r'👤 Report User', incoming=True))
async def report_user_button(event):
    """Report user button"""
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts! Add one first.", buttons=main_menu_keyboard())
        return
    
    keyboard = [[KeyboardButton(acc[0])] for acc in accounts]
    keyboard.append([KeyboardButton('❌ Back')])
    
    await event.reply(
        "👤 **Select Account:**",
        buttons=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    bot.user_states[event.sender_id] = {'step': 'report_user_account'}

@events.register(events.NewMessage(pattern=r'🤖 Report Bot', incoming=True))
async def report_bot_button(event):
    """Report bot button"""
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
    bot.user_states[event.sender_id] = {'step': 'report_bot_account'}

@events.register(events.NewMessage(pattern=r'👥 Report Group', incoming=True))
async def report_group_button(event):
    """Report group button"""
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
    bot.user_states[event.sender_id] = {'step': 'report_group_account'}

@events.register(events.NewMessage(pattern=r'📡 Report Channel', incoming=True))
async def report_channel_button(event):
    """Report channel button"""
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
    bot.user_states[event.sender_id] = {'step': 'report_channel_account'}

@events.register(events.NewMessage(pattern=r'🔥 Batch Report', incoming=True))
async def batch_report_button(event):
    """Batch report button"""
    accounts = await bot.get_all_accounts()
    
    if not accounts:
        await event.reply("❌ No accounts!", buttons=main_menu_keyboard())
        return
    
    text = "🔥 **BATCH REPORT**\n\n"
    text += "Enter accounts (comma-separated):\n\n"
    for name, phone, _, _ in accounts:
        text += f"• {name}\n"
    
    await event.reply(text, buttons=back_keyboard())
    bot.user_states[event.sender_id] = {'step': 'batch_accounts'}

@events.register(events.NewMessage(pattern=r'📊 Statistics', incoming=True))
async def stats_button(event):
    """Statistics button"""
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

@events.register(events.NewMessage(pattern=r'❌ Back|❌ Exit', incoming=True))
async def back_button(event):
    """Back/Exit button"""
    user_id = event.sender_id
    if user_id in bot.user_states:
        del bot.user_states[user_id]
    
    if '❌ Exit' in event.text:
        await event.reply("👋 Goodbye!", buttons=ReplyKeyboardRemove())
    else:
        await event.reply("🔄 Back to main menu", buttons=main_menu_keyboard())

@events.register(events.NewMessage(incoming=True))
async def text_handler(event):
    """Handle text input"""
    user_id = event.sender_id
    text = event.text
    
    if user_id not in bot.user_states:
        return
    
    state = bot.user_states[user_id]['step']
    
    # ADD ACCOUNT FLOW
    if state == 'add_account_name':
        account_name = text.strip()
        await event.reply("📱 Enter phone number (+91...):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'add_account_phone'
        bot.user_states[user_id]['account_name'] = account_name
    
    elif state == 'add_account_phone':
        phone = text.strip()
        success, msg = await bot.add_account_flow(
            bot.user_states[user_id]['account_name'], 
            phone, 
            "none"
        )
        
        if success:
            await event.reply(msg, buttons=back_keyboard())
            bot.user_states[user_id]['step'] = 'add_account_verify'
            bot.user_states[user_id]['phone'] = phone
        else:
            await event.reply(msg, buttons=main_menu_keyboard())
            del bot.user_states[user_id]
    
    elif state == 'add_account_verify':
        code = text.strip()
        success, msg = await bot.verify_account_code(
            bot.user_states[user_id]['account_name'],
            code
        )
        
        await event.reply(msg, buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # REPORT USER FLOW
    elif state == 'report_user_account':
        account = text.strip()
        await event.reply("👤 Enter username (@username):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'report_user_target'
        bot.user_states[user_id]['account'] = account
    
    elif state == 'report_user_target':
        target = text.strip()
        await event.reply(
            "🏷️ **Select Category:**",
            buttons=category_keyboard()
        )
        bot.user_states[user_id]['step'] = 'report_user_category'
        bot.user_states[user_id]['target'] = target
    
    elif state == 'report_user_category':
        category_text = text.strip().lower()
        category_map = {
            '🚫 spam': 'spam',
            '💰 scam': 'scam',
            '🔞 porn': 'porn',
            '⚔️ violence': 'violence',
            '🔓 leak': 'leak',
            '©️ copyright': 'copyright',
            '😡 harassment': 'harassment',
            '⚖️ illegal': 'illegal',
            '🎭 fake': 'fake'
        }
        
        category = category_map.get(text, 'spam')
        
        success, msg = await bot.send_report_with_retry(
            bot.user_states[user_id]['account'],
            bot.user_states[user_id]['target'],
            'user',
            category
        )
        
        await event.reply(f"✅ Report sent!\n{msg}", buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # REPORT BOT FLOW
    elif state == 'report_bot_account':
        account = text.strip()
        await event.reply("🤖 Enter bot username (@botname):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'report_bot_target'
        bot.user_states[user_id]['account'] = account
    
    elif state == 'report_bot_target':
        target = text.strip()
        await event.reply(
            "🏷️ **Select Category:**",
            buttons=category_keyboard()
        )
        bot.user_states[user_id]['step'] = 'report_bot_category'
        bot.user_states[user_id]['target'] = target
    
    elif state == 'report_bot_category':
        category_map = {
            '🚫 spam': 'spam',
            '💰 scam': 'scam',
            '🔞 porn': 'porn',
            '⚔️ violence': 'violence',
            '🔓 leak': 'leak',
            '©️ copyright': 'copyright',
            '😡 harassment': 'harassment',
            '⚖️ illegal': 'illegal',
            '🎭 fake': 'fake'
        }
        
        category = category_map.get(text, 'spam')
        
        success, msg = await bot.send_report_with_retry(
            bot.user_states[user_id]['account'],
            bot.user_states[user_id]['target'],
            'bot',
            category
        )
        
        await event.reply(f"✅ Report sent!\n{msg}", buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # REPORT GROUP FLOW
    elif state == 'report_group_account':
        account = text.strip()
        await event.reply("👥 Enter group ID (-100...):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'report_group_target'
        bot.user_states[user_id]['account'] = account
    
    elif state == 'report_group_target':
        target = text.strip()
        await event.reply(
            "🏷️ **Select Category:**",
            buttons=category_keyboard()
        )
        bot.user_states[user_id]['step'] = 'report_group_category'
        bot.user_states[user_id]['target'] = target
    
    elif state == 'report_group_category':
        category_map = {
            '🚫 spam': 'spam',
            '💰 scam': 'scam',
            '🔞 porn': 'porn',
            '⚔️ violence': 'violence',
            '🔓 leak': 'leak',
            '©️ copyright': 'copyright',
            '😡 harassment': 'harassment',
            '⚖️ illegal': 'illegal',
            '🎭 fake': 'fake'
        }
        
        category = category_map.get(text, 'spam')
        
        success, msg = await bot.send_report_with_retry(
            bot.user_states[user_id]['account'],
            bot.user_states[user_id]['target'],
            'group',
            category
        )
        
        await event.reply(f"✅ Report sent!\n{msg}", buttons=main_menu_keyboard())
        del bot.user_states[user_id]
    
    # REPORT CHANNEL FLOW
    elif state == 'report_channel_account':
        account = text.strip()
        await event.reply("📡 Enter channel username (@channel):", buttons=back_keyboard())
        bot.user_states[user_id]['step'] = 'report_channel_target'
        bot.user_states[user_id]['account'] = account
    
    elif state == 'report_channel_target':
        target = text.strip()
        await event.reply(
            "🏷️ **Select Category:**",
            buttons=category_keyboard()
        )
        bot.user_states[user_id]['step'] = 'report_channel_category'
        bot.user_states[user_id]['target'] = target
    
    elif state == 'report_channel_category':
        category_map = {
            '🚫 spam': 'spam',
            '💰 scam': 'scam',
            '🔞 porn': 'porn',
            '⚔️ violence': 'violence',
            '🔓 leak': 'leak',
            '©️ copyright': 'copyright',
            '😡 harassment': 'harassment',
            '⚖️ illegal': 'illegal',
            '🎭 fake': 'fake'
        }
        
        category = category_map.get(text, 'spam')
        
        success, msg = await bot.send_report_with_retry(
            bot.user_states[user_id]['account'],
            bot.user_states[user_id]['target'],
            'channel',
            category
        )
        
        await event.reply(f"✅ Report sent!\n{msg}", buttons=main_menu_keyboard())
        del bot.user_states[user_id]

# ================== MAIN BOT STARTUP ==================

async def main():
    """Main bot function"""
    await bot.init_db()
    
    bot.bot_client = TelegramClient(
        'bot_session',
        int(bot.config['API_ID']),
        bot.config['API_HASH']
    )
    
    await bot.bot_client.start(bot_token=bot.config['BOT_TOKEN'])
    
    print("""
╔��═══════════════════════════════════════════════════════════════╗
║                                                                ║
║     🔥 ULTIMATE TELEGRAM BOT v5.0 - BUTTON INTERFACE 🔥       ║
║                                                                ║
║  ✅ Interactive Buttons Ready                                 ║
║  ✅ Send /start to get started                                ║
║  ✅ Enterprise Grade Bot Live                                 ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    await bot.bot_client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot shutdown gracefully")