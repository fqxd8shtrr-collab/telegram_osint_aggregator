import asyncio
import logging
import config
from listener import listener
from queue_manager import queue_manager
from alert_engine import alert_engine
from health_monitor import health_monitor
from database import init_db
import bot

async def main():
    # Initialize database
    await init_db()
    # Start components
    await alert_engine.initialize()
    await queue_manager.start()
    asyncio.create_task(health_monitor.start())
    # Start listener (blocking)
    await listener.start()

if __name__ == "__main__":
    # Run bot in separate thread or asyncio task
    import threading
    bot_thread = threading.Thread(target=bot.main, daemon=True)
    bot_thread.start()
    asyncio.run(main())
