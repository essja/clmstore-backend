import asyncio
from app.database import engine, Base
from app.models.whatsapp import WhatsAppCustomer, WhatsAppSession

async def init_whatsapp_tables():
    async with engine.begin() as conn:
        print("Creating WhatsApp database tables (whatsapp_customers, whatsapp_sessions)...")
        await conn.run_sync(Base.metadata.create_all)
    print("SUCCESS: WhatsApp database tables initialized successfully!")

if __name__ == "__main__":
    asyncio.run(init_whatsapp_tables())
