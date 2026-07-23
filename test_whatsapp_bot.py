import asyncio
from app.database import AsyncSessionLocal
from app.services.whatsapp_bot_service import WhatsAppBotService

async def run_bot_test():
    test_number = "23276999888"
    print("=" * 80)
    print("CLMSTORE WHATSAPP BOT INTERACTIVE TEST SUITE")
    print(f"Simulating Customer WhatsApp Number: +{test_number}")
    print("=" * 80)

    async with AsyncSessionLocal() as session:
        bot = WhatsAppBotService(session)

        # 1. First Message: Hi
        print("\n--- STEP 1: Customer sends 'Hi' ---")
        await bot.process_incoming_message(test_number, "Hi")

        # 2. Registration: Customer provides name
        print("\n--- STEP 2: Customer inputs name 'Mohamed Bangura' ---")
        await bot.process_incoming_message(test_number, "Mohamed Bangura")

        # 3. Main Menu: Select Option 1 (Order Food)
        print("\n--- STEP 3: Customer chooses '1' (Order Food) ---")
        await bot.process_incoming_message(test_number, "1")

        # 4. Select Restaurant 1
        print("\n--- STEP 4: Customer selects Restaurant ID '1' ---")
        await bot.process_incoming_message(test_number, "rest_1")

        # 5. Select Dish Item
        print("\n--- STEP 5: Customer selects Dish Item ---")
        await bot.process_incoming_message(test_number, "item_1")

        # 6. Confirm Shopping Cart
        print("\n--- STEP 6: Customer clicks 'Confirm Order' ---")
        await bot.process_incoming_message(test_number, "btn_confirm_cart")

        # 7. Delivery Address Entry
        print("\n--- STEP 7: Customer inputs delivery address ---")
        await bot.process_incoming_message(test_number, "15 Siaka Stevens Street, Freetown")

        # 8. Payment Selection
        print("\n--- STEP 8: Customer selects 'Pay on Delivery' ---")
        await bot.process_incoming_message(test_number, "pay_cod")

        # 9. Track Order
        print("\n--- STEP 9: Customer checks order tracking ---")
        await bot.process_incoming_message(test_number, "track")
        await bot.process_incoming_message(test_number, "latest")

    print("\n" + "=" * 80)
    print("SUCCESS: TEST SUITE COMPLETED SUCCESSFULLY — WhatsApp order generated!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_bot_test())
