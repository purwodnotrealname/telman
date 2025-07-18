import logging
import os
import asyncio
from typing import Dict, Callable, Any
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from telegram.error import TimedOut, NetworkError, RetryAfter

# Fixed SNMP imports for pysnmp-lextudio with correct function names
from pysnmp.hlapi.v3arch.asyncio import (
    get_cmd, next_cmd, bulk_cmd,
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, Integer, OctetString, Null
)
from pysnmp.proto.rfc1902 import *
import re

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SNMPManager:
 from pysnmp.hlapi.v3arch.asyncio import (
    get_cmd, next_cmd, bulk_cmd,
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity
)
 
import re
import logging
from typing import Dict, Any

class SNMPManager:
    """SNMP Manager class for handling SNMP operations"""
    
    def __init__(self, target_host: str = "192.168.137.130", community: str = "public", port: int = 161):
        self.target_host = target_host
        self.community = community
        self.port = port
        
    def validate_oid(self, oid: str) -> bool:
        """Validate OID format"""
        pattern = r'^\.?(\d+\.)*\d+$'
        return bool(re.match(pattern, oid))
    
    async def get_snmp_value(self, oid: str) -> Dict[str, Any]:
        """Get SNMP value for a given OID"""
        try:
            # Validate OID format
            if not self.validate_oid(oid):
                return {
                    "success": False,
                    "error": "Invalid OID format. OID should contain only numbers and dots (e.g., 1.3.6.1.2.1.1.1.0)"
                }
            
            # Ensure OID starts with a dot
            if not oid.startswith('.'):
                oid = '.' + oid
            
            # Create SNMP engine and transport target
            snmp_engine = SnmpEngine()
            transport_target = UdpTransportTarget.create((self.target_host, self.port), timeout=5.0, retries=3)
            
            # Perform SNMP GET operation
            cmd_generator = get_cmd(
                snmp_engine,
                CommunityData(self.community),
                transport_target,
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            # Ensure the generator is properly awaited
            try:
                result = await cmd_generator
                async for (errorIndication, errorStatus, errorIndex, varBinds) in result:
                    if errorIndication:
                        logger.error(f"SNMP error indication: {errorIndication}")
                        return {
                            "success": False,
                            "error": f"SNMP Error: {errorIndication}. Check if the target device is reachable and SNMP is enabled."
                        }
                    elif errorStatus:
                        logger.error(f"SNMP error status: {errorStatus.prettyPrint()} at index {errorIndex}")
                        return {
                            "success": False,
                            "error": f"SNMP Error: {errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
                        }
                    else:
                        for varBind in varBinds:
                            oid_result = varBind[0]
                            value = varBind[1]
                            logger.info(f"SNMP query successful for OID {oid_result}")
                            return {
                                "success": True,
                                "oid": str(oid_result),
                                "value": str(value),
                                "type": type(value).__name__
                            }
            except AttributeError as ae:
                logger.error(f"SNMP AttributeError: {ae}")
                return {
                    "success": False,
                    "error": f"SNMP AttributeError: {str(ae)}. Ensure the correct pysnmp version is installed."
                }
            
            logger.warning(f"No data received for OID {oid}")
            return {
                "success": False,
                "error": "No data received from SNMP query. Verify the OID and target configuration."
            }
            
        except TimeoutError as e:
            logger.error(f"SNMP timeout error: {e}")
            return {
                "success": False,
                "error": "SNMP request timed out. Check if the target device is reachable or increase timeout."
            }
        except Exception as e:
            logger.error(f"SNMP Error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Connection error: {str(e)}. Ensure the SNMP target is configured correctly."
            }

    async def walk_snmp_tree(self, oid: str, max_results: int = 10) -> Dict[str, Any]:
        """Walk SNMP tree starting from given OID"""
        try:
            if not self.validate_oid(oid):
                return {
                    "success": False,
                    "error": "Invalid OID format"
                }
            
            # Ensure OID starts with a dot
            if not oid.startswith('.'):
                oid = '.' + oid
            
            results = []
            count = 0
            
            # Create SNMP engine and transport target
            snmp_engine = SnmpEngine()
            transport_target = UdpTransportTarget.create((self.target_host, self.port), timeout=5.0, retries=3)
            
            # Use next_cmd for SNMP walk
            cmd_generator = next_cmd(
                snmp_engine,
                CommunityData(self.community),
                transport_target,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            )
            
            # Ensure the generator is properly awaited
            try:
                result = await cmd_generator
                async for (errorIndication, errorStatus, errorIndex, varBinds) in result:
                    if errorIndication:
                        logger.error(f"SNMP walk error indication: {errorIndication}")
                        return {
                            "success": False,
                            "error": f"SNMP surging: {errorIndication}. Check if the target device is reachable and SNMP is enabled."
                        }
                    elif errorStatus:
                        logger.error(f"SNMP walk error status: {errorStatus.prettyPrint()}")
                        return {
                            "success": False,
                            "error": f"SNMP Error: {errorStatus.prettyPrint()}"
                        }
                    else:
                        for varBind in varBinds:
                            oid_result = str(varBind[0])
                            value = str(varBind[1])
                            logger.info(f"SNMP walk result: OID {oid_result}, Value {value}")
                            results.append({
                                "oid": oid_result,
                                "value": value
                            })
                            
                            count += 1
                            if count >= max_results:
                                break
                        
                        if count >= max_results:
                            break
            except AttributeError as ae:
                logger.error(f"SNMP AttributeError: {ae}")
                return {
                    "success": False,
                    "error": f"SNMP AttributeError: {str(ae)}. Ensure the correct pysnmp version is installed."
                }
            
            logger.info(f"SNMP walk completed with {count} results")
            return {
                "success": True,
                "results": results,
                "count": count
            }
            
        except TimeoutError as e:
            logger.error(f"SNMP walk timeout error: {e}")
            return {
                "success": False,
                "error": "SNMP walk timed out. Check if the target device is reachable or increase timeout."
            }
        except Exception as e:
            logger.error(f"SNMP Walk Error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Connection error: {str(e)}. Ensure the SNMP target is configured correctly."
            }

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.application = None
        self.commands: Dict[str, Callable] = {}
        self.snmp_manager = SNMPManager()
        self.is_running = False
        
    def _build_application(self):
        """Build the application with proper configuration"""
        # Use the new ApplicationBuilder approach with proper timeout settings
        builder = Application.builder().token(self.token)
        
        # Configure timeouts using the new method
        builder = builder.get_updates_read_timeout(30)
        builder = builder.get_updates_write_timeout(30)
        builder = builder.get_updates_connect_timeout(30)
        builder = builder.get_updates_pool_timeout(30)
        
        # Set connection pool timeout
        builder = builder.connection_pool_size(8)
        
        return builder.build()
    
    def _setup_handlers(self):
        """Setup default handlers"""
        if not self.application:
            return
            
        # Error handler
        self.application.add_error_handler(self._error_handler)
        
        # Message handler for unrecognized commands
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
    
    def register_command(self, command: str, handler: Callable):
        """Register a new command handler"""
        if not self.application:
            self.application = self._build_application()
            self._setup_handlers()
            
        self.commands[command] = handler
        self.application.add_handler(CommandHandler(command, handler))
        logger.info(f"Registered command: /{command}")
    
    def update_snmp_config(self, host: str, community: str = "public", port: int = 161):
        """Update SNMP configuration"""
        self.snmp_manager = SNMPManager(host, community, port)
        logger.info(f"Updated SNMP config: {host}:{port} with community '{community}'")
    
    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors with better error handling"""
        error = context.error
        
        if isinstance(error, TimedOut):
            logger.warning(f"Request timed out: {error}")
            return
        elif isinstance(error, NetworkError):
            logger.warning(f"Network error: {error}")
            # Don't sleep in error handler, just log
            return
        elif isinstance(error, RetryAfter):
            logger.warning(f"Rate limited. Retry after {error.retry_after} seconds")
            return
        else:
            logger.error(f"Update {update} caused error {error}", exc_info=True)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (non-commands)"""
        try:
            user_message = update.message.text
            chat_id = update.effective_chat.id
            logger.info(f"Received message from {chat_id}: {user_message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def start_bot(self):
        """Start the bot asynchronously"""
        try:
            if not self.application:
                self.application = self._build_application()
                self._setup_handlers()
            
            logger.info("Initializing bot...")
            await self.application.initialize()
            
            logger.info("Starting bot polling...")
            await self.application.start()
            
            self.is_running = True
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            logger.info("Bot is running. Press Ctrl+C to stop.")
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def stop_bot(self):
        """Stop the bot gracefully"""
        try:
            if self.application and self.is_running:
                logger.info("Stopping bot...")
                self.is_running = False
                
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                
                logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    def run(self):
        """Run the bot with proper event loop handling"""
        async def run_bot():
            try:
                await self.start_bot()
                # Keep the bot running
                while self.is_running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
            except Exception as e:
                logger.error(f"Bot error: {e}", exc_info=True)
            finally:
                await self.stop_bot()
        
        # Handle event loop properly
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an event loop, create a task
                task = loop.create_task(run_bot())
                return task
            else:
                # If no event loop is running, run until complete
                loop.run_until_complete(run_bot())
        except RuntimeError:
            # If no event loop exists, create a new one
            asyncio.run(run_bot())

class CommandHandlers:
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user = update.effective_user
            welcome_message = (
                f"Hello {user.first_name}! 👋\n\n"
                "I'm your SNMP monitoring bot. Here are available commands:\n\n"
                "📊 **SNMP Commands:**\n"
                "/snmp <OID> - Get SNMP value for specific OID\n"
                "/snmpwalk <OID> - Walk SNMP tree from OID\n"
                "/snmpconfig <host> [community] [port] - Configure SNMP settings\n"
                "/snmpstatus - Show current SNMP configuration\n"
                "/commonoids - Show common Cisco OIDs\n\n"
                "🔧 **General Commands:**\n"
                "/start - Show this welcome message\n"
                "/help - Get detailed help information\n"
                "/echo <message> - Echo your message\n"
                "/info - Get your user information\n\n"
                "💡 **Examples:**\n"
                "`/snmp 1.3.6.1.2.1.1.1.0` - Get system description\n"
                "`/snmpconfig 192.168.1.1 public 161` - Set SNMP target"
            )
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
            logger.info(f"Sent welcome message to {user.first_name} (ID: {user.id})")
        except Exception as e:
            logger.error(f"Error in start command: {e}")
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            help_text = (
                "🤖 **SNMP Monitoring Bot Help**\n\n"
                "**SNMP Commands:**\n"
                "• `/snmp <OID>` - Query specific SNMP OID\n"
                "  Example: `/snmp 1.3.6.1.2.1.1.1.0`\n\n"
                "• `/snmpwalk <OID>` - Walk SNMP tree (max 10 results)\n"
                "  Example: `/snmpwalk 1.3.6.1.2.1.2.2.1.2`\n\n"
                "• `/snmpconfig <host> [community] [port]` - Configure SNMP\n"
                "  Example: `/snmpconfig 192.168.1.1 public 161`\n\n"
                "• `/snmpstatus` - Show current configuration\n"
                "• `/commonoids` - Show common Cisco OIDs\n\n"
                "**General Commands:**\n"
                "• `/start` - Welcome message\n"
                "• `/help` - This help message\n"
                "• `/echo <text>` - Echo your text\n"
                "• `/info` - Your user information\n\n"
                "**OID Format:**\n"
                "OIDs should be in format: `1.3.6.1.2.1.1.1.0`\n"
                "Leading dot is optional.\n\n"
                "**Note:** Make sure your SNMP target is reachable and configured properly!"
            )
            await update.message.reply_text(help_text, parse_mode='Markdown')
            logger.info(f"Sent help message to user ID: {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error in help command: {e}")
    
    @staticmethod
    async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /echo command"""
        try:
            if context.args:
                echo_text = " ".join(context.args)
                await update.message.reply_text(f"🔄 Echo: {echo_text}")
            else:
                await update.message.reply_text("Please provide text to echo. Usage: /echo <your message>")
            logger.info(f"Echo command used by user ID: {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error in echo command: {e}")
    
    @staticmethod
    async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            info_text = (
                f"👤 **User Information:**\n"
                f"Name: {user.first_name} {user.last_name or ''}\n"
                f"Username: @{user.username or 'None'}\n"
                f"User ID: {user.id}\n"
                f"Chat ID: {chat.id}\n"
                f"Chat Type: {chat.type}"
            )
            await update.message.reply_text(info_text, parse_mode='Markdown')
            logger.info(f"Info command used by user ID: {user.id}")
        except Exception as e:
            logger.error(f"Error in info command: {e}")
    
    @staticmethod
    async def snmp_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snmp command - Get SNMP value for specific OID"""
        try:
            if not context.args:
                help_text = (
                    "📊 **SNMP Get Command**\n\n"
                    "Usage: `/snmp <OID>`\n\n"
                    "**Examples:**\n"
                    "• `/snmp 1.3.6.1.2.1.1.1.0` - System description\n"
                    "• `/snmp 1.3.6.1.2.1.1.3.0` - System uptime\n"
                    "• `/snmp 1.3.6.1.2.1.1.5.0` - System name\n\n"
                    "Use `/commonoids` to see more common OIDs."
                )
                await update.message.reply_text(help_text, parse_mode='Markdown')
                return
            
            oid = context.args[0]
            await update.message.reply_text("🔄 Querying SNMP... Please wait.")
            
            # Get bot instance and perform SNMP query
            bot = context.bot_data.get('bot_instance')
            if not bot:
                await update.message.reply_text("❌ Bot instance not found. Please restart the bot.")
                return
            
            result = await bot.snmp_manager.get_snmp_value(oid)
            
            if result["success"]:
                response = (
                    f"✅ **SNMP Query Successful**\n\n"
                    f"**OID:** `{result['oid']}`\n"
                    f"**Value:** `{result['value']}`\n"
                    f"**Type:** {result['type']}\n"
                    f"**Target:** {bot.snmp_manager.target_host}"
                )
            else:
                response = f"❌ **SNMP Query Failed**\n\n**Error:** {result['error']}"
            
            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"SNMP query for OID {oid} by user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in snmp_get command: {e}")
            await update.message.reply_text("❌ An error occurred while processing your request.")
    
    @staticmethod
    async def snmp_walk(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snmpwalk command - Walk SNMP tree from OID"""
        try:
            if not context.args:
                help_text = (
                    "🚶 **SNMP Walk Command**\n\n"
                    "Usage: `/snmpwalk <OID>`\n\n"
                    "**Examples:**\n"
                    "• `/snmpwalk 1.3.6.1.2.1.2.2.1.2` - Interface names\n"
                    "• `/snmpwalk 1.3.6.1.2.1.2.2.1.10` - Interface in-octets\n"
                    "• `/snmpwalk 1.3.6.1.2.1.1` - System info tree\n\n"
                    "**Note:** Limited to 10 results to prevent spam."
                )
                await update.message.reply_text(help_text, parse_mode='Markdown')
                return
            
            oid = context.args[0]
            await update.message.reply_text("🔄 Walking SNMP tree... Please wait.")
            
            # Get bot instance and perform SNMP walk
            bot = context.bot_data.get('bot_instance')
            if not bot:
                await update.message.reply_text("❌ Bot instance not found. Please restart the bot.")
                return
            
            result = await bot.snmp_manager.walk_snmp_tree(oid)
            
            if result["success"]:
                if result["results"]:
                    response = f"✅ **SNMP Walk Results** (Showing {result['count']} results)\n\n"
                    for item in result["results"]:
                        response += f"**OID:** `{item['oid']}`\n**Value:** `{item['value']}`\n\n"
                    response += f"**Target:** {bot.snmp_manager.target_host}"
                else:
                    response = "📭 No results found for the specified OID."
            else:
                response = f"❌ **SNMP Walk Failed**\n\n**Error:** {result['error']}"
            
            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"SNMP walk for OID {oid} by user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in snmp_walk command: {e}")
            await update.message.reply_text("❌ An error occurred while processing your request.")
    
    @staticmethod
    async def snmp_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snmpconfig command - Configure SNMP settings"""
        try:
            if not context.args:
                help_text = (
                    "⚙️ **SNMP Configuration**\n\n"
                    "Usage: `/snmpconfig <host> [community] [port]`\n\n"
                    "**Parameters:**\n"
                    "• `host` - SNMP target IP address (required)\n"
                    "• `community` - SNMP community string (default: public)\n"
                    "• `port` - SNMP port (default: 161)\n\n"
                    "**Examples:**\n"
                    "• `/snmpconfig 192.168.1.1`\n"
                    "• `/snmpconfig 192.168.1.1 public`\n"
                    "• `/snmpconfig 192.168.1.1 private 161`\n\n"
                    "Use `/snmpstatus` to view current configuration."
                )
                await update.message.reply_text(help_text, parse_mode='Markdown')
                return
            
            host = context.args[0]
            community = context.args[1] if len(context.args) > 1 else "public"
            port = int(context.args[2]) if len(context.args) > 2 else 161
            
            # Get bot instance and update configuration
            bot = context.bot_data.get('bot_instance')
            if not bot:
                await update.message.reply_text("❌ Bot instance not found. Please restart the bot.")
                return
            
            bot.update_snmp_config(host, community, port)
            
            response = (
                f"✅ **SNMP Configuration Updated**\n\n"
                f"**Host:** {host}\n"
                f"**Community:** {community}\n"
                f"**Port:** {port}\n\n"
                f"You can now use `/snmp` and `/snmpwalk` commands with this configuration."
            )
            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"SNMP config updated by user {update.effective_user.id}: {host}:{port}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid port number. Port must be a number.")
        except Exception as e:
            logger.error(f"Error in snmp_config command: {e}")
            await update.message.reply_text("❌ An error occurred while updating configuration.")
    
    @staticmethod
    async def snmp_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /snmpstatus command - Show current SNMP configuration"""
        try:
            bot = context.bot_data.get('bot_instance')
            if not bot:
                await update.message.reply_text("❌ Bot instance not found. Please restart the bot.")
                return
            
            response = (
                f"📊 **Current SNMP Configuration**\n\n"
                f"**Host:** {bot.snmp_manager.target_host}\n"
                f"**Community:** {bot.snmp_manager.community}\n"
                f"**Port:** {bot.snmp_manager.port}\n\n"
                f"Use `/snmpconfig` to modify these settings."
            )
            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"SNMP status viewed by user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in snmp_status command: {e}")
            await update.message.reply_text("❌ An error occurred while retrieving status.")
    
    @staticmethod
    async def common_oids(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /commonoids command - Show common Cisco OIDs"""
        try:
            oids_text = (
                "📋 **Common Cisco SNMP OIDs**\n\n"
                "**System Information:**\n"
                "• `1.3.6.1.2.1.1.1.0` - System description\n"
                "• `1.3.6.1.2.1.1.3.0` - System uptime\n"
                "• `1.3.6.1.2.1.1.5.0` - System name\n"
                "• `1.3.6.1.2.1.1.6.0` - System location\n\n"
                "**Interface Information:**\n"
                "• `1.3.6.1.2.1.2.1.0` - Number of interfaces\n"
                "• `1.3.6.1.2.1.2.2.1.2` - Interface names\n"
                "• `1.3.6.1.2.1.2.2.1.8` - Interface status\n"
                "• `1.3.6.1.2.1.2.2.1.10` - Interface in-octets\n"
                "• `1.3.6.1.2.1.2.2.1.16` - Interface out-octets\n\n"
                "**CPU & Memory:**\n"
                "• `1.3.6.1.4.1.9.9.109.1.1.1.1.7` - CPU utilization (5min)\n"
                "• `1.3.6.1.4.1.9.9.48.1.1.1.5` - Memory used\n"
                "• `1.3.6.1.4.1.9.9.48.1.1.1.6` - Memory free\n\n"
                "**Examples:**\n"
                "`/snmp 1.3.6.1.2.1.1.1.0`\n"
                "`/snmpwalk 1.3.6.1.2.1.2.2.1.2`"
            )
            await update.message.reply_text(oids_text, parse_mode='Markdown')
            logger.info(f"Common OIDs viewed by user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error in common_oids command: {e}")
            await update.message.reply_text("❌ An error occurred while retrieving OIDs.")

# Configuration

class Config:
    """Configuration class for bot settings"""
    def __init__(self):
        # Try to get token from environment, fallback to hardcoded value
        self.TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or "YOUR_BOT_TOKEN_HERE"
        self.ADMIN_IDS = self._parse_admin_ids()
        
        # SNMP Configuration
        self.SNMP_HOST = os.getenv('SNMP_HOST', '192.168.137.130')
        self.SNMP_COMMUNITY = os.getenv('SNMP_COMMUNITY', 'public')
        self.SNMP_PORT = int(os.getenv('SNMP_PORT', '161'))
    
    def _parse_admin_ids(self) -> list:
        """Parse admin IDs from environment variable"""
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        if admin_ids_str:
            return [int(id.strip()) for id in admin_ids_str.split(',')]
        return []



def main():
    """Main function to run the bot"""
    config = Config()
    
    if not config.TOKEN:
        logger.error("Please set your bot token in the TELEGRAM_BOT_TOKEN environment variable")
        return
    
    # Create bot instance
    bot = TelegramBot(config.TOKEN)
    
    # Configure SNMP with default settings
    bot.update_snmp_config(config.SNMP_HOST, config.SNMP_COMMUNITY, config.SNMP_PORT)
    
    # Register commands first
    bot.register_command('start', CommandHandlers.start)
    bot.register_command('help', CommandHandlers.help_command)
    bot.register_command('echo', CommandHandlers.echo)
    bot.register_command('info', CommandHandlers.info)
    
    # Register SNMP commands
    bot.register_command('snmp', CommandHandlers.snmp_get)
    bot.register_command('snmpwalk', CommandHandlers.snmp_walk)
    bot.register_command('snmpconfig', CommandHandlers.snmp_config)
    bot.register_command('snmpstatus', CommandHandlers.snmp_status)
    bot.register_command('commonoids', CommandHandlers.common_oids)
    
    # Store bot instance in bot_data for access in command handlers
    if bot.application:
        bot.application.bot_data['bot_instance'] = bot
    
    # Start the bot
    logger.info("Bot is starting up...")
    logger.info(f"Default SNMP target: {config.SNMP_HOST}:{config.SNMP_PORT}")
    bot.run()

if __name__ == '__main__':
    main()