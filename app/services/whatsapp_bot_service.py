"""
CLMStore — WhatsApp Bot State Machine & Conversation Service
Orchestrates customer registration, interactive food ordering, order placement via OrderService,
payment selection, and live order tracking over WhatsApp.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.whatsapp import WhatsAppCustomer, WhatsAppSession, WhatsAppSessionState
from app.models.restaurant import Restaurant
from app.models.menu import MenuItem
from app.models.order import Order
from app.models.user import User
from app.services.whatsapp_service import WhatsAppService
from app.services.order_service import OrderService
from app.auth.password import hash_password
import random
from datetime import datetime
from app.utils.constants import UserRole, OrderStatus, PaymentProvider, PaymentStatus, RestaurantStatus

def generate_order_number() -> str:
    now_str = datetime.utcnow().strftime("%Y%m%d")
    rand_seq = random.randint(1000, 9999)
    return f"CLM-{now_str}-{rand_seq}"

logger = logging.getLogger("clmstore.whatsapp_bot")


class WhatsAppBotService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.wa_service = WhatsAppService()

    async def get_or_create_customer(self, whatsapp_number: str) -> WhatsAppCustomer:
        """Finds existing WhatsApp customer or returns None if unregistered."""
        stmt = select(WhatsAppCustomer).where(WhatsAppCustomer.whatsapp_number == whatsapp_number)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_session(self, whatsapp_number: str) -> WhatsAppSession:
        """Retrieves or creates active conversation session."""
        stmt = select(WhatsAppSession).where(WhatsAppSession.whatsapp_number == whatsapp_number)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            session = WhatsAppSession(
                whatsapp_number=whatsapp_number,
                current_state=WhatsAppSessionState.WELCOME,
                cart_items={"items": []},
            )
            self.db.add(session)
            await self.db.flush()

        return session

    async def process_incoming_message(self, whatsapp_number: str, message_text: str, payload_id: Optional[str] = None) -> None:
        """Main entrypoint for processing incoming customer WhatsApp messages/button clicks."""
        text = (payload_id or message_text or "").strip()
        session = await self.get_or_create_session(whatsapp_number)
        customer = await self.get_or_create_customer(whatsapp_number)

        # Update last message audit
        session.last_message = text
        self.db.add(session)

        # Reset command check
        if text.lower() in ("hi", "hello", "menu", "start", "restart", "home"):
            if not customer:
                session.current_state = WhatsAppSessionState.AWAITING_NAME
                await self.db.commit()
                await self.wa_service.send_text_message(
                    whatsapp_number,
                    "👋 Welcome to *CLMStore Delivery*! 🇸🇱\n\nBefore placing your first order, please tell us your *Full Name*:"
                )
                return
            else:
                session.current_state = WhatsAppSessionState.MAIN_MENU
                await self.db.commit()
                await self._send_main_menu(customer, whatsapp_number)
                return

        # State Machine Dispatcher
        state = session.current_state

        if state == WhatsAppSessionState.AWAITING_NAME:
            await self._handle_registration(session, whatsapp_number, text)
        elif state == WhatsAppSessionState.MAIN_MENU:
            await self._handle_main_menu_choice(session, customer, whatsapp_number, text)
        elif state == WhatsAppSessionState.SELECT_RESTAURANT:
            await self._handle_restaurant_selection(session, whatsapp_number, text)
        elif state == WhatsAppSessionState.SELECT_MENU_ITEM:
            await self._handle_menu_selection(session, whatsapp_number, text)
        elif state == WhatsAppSessionState.CART_VIEW:
            await self._handle_cart_actions(session, whatsapp_number, text)
        elif state == WhatsAppSessionState.ENTER_ADDRESS:
            await self._handle_address_entry(session, customer, whatsapp_number, text)
        elif state == WhatsAppSessionState.SELECT_PAYMENT:
            await self._handle_payment_selection(session, customer, whatsapp_number, text)
        elif state == WhatsAppSessionState.TRACKING:
            await self._handle_order_tracking(session, customer, whatsapp_number, text)
        else:
            await self._send_main_menu(customer, whatsapp_number)

    # ── HANDLERS ─────────────────────────────────────────────────────────────

    async def _handle_registration(self, session: WhatsAppSession, whatsapp_number: str, name_input: str) -> None:
        """Registers new WhatsApp customer and links to a User record."""
        # Create User if phone not existing
        phone = "+" + whatsapp_number.replace("+", "")
        stmt_u = select(User).where(User.phone == phone)
        res_u = await self.db.execute(stmt_u)
        user = res_u.scalar_one_or_none()

        if not user:
            name_parts = name_input.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else "Customer"
            email = f"wa_{whatsapp_number}@clmstore.sl"

            user = User(
                email=email,
                phone=phone,
                password_hash=hash_password("CLMStoreWA@2026!"),
                first_name=first_name,
                last_name=last_name,
                role=UserRole.CUSTOMER,
                is_active=True,
                is_phone_verified=True,
            )
            self.db.add(user)
            await self.db.flush()

        # Create WhatsAppCustomer
        customer = WhatsAppCustomer(
            whatsapp_number=whatsapp_number,
            name=name_input,
            user_id=user.id,
        )
        self.db.add(customer)

        session.customer_id = customer.id
        session.current_state = WhatsAppSessionState.MAIN_MENU
        await self.db.commit()

        await self.wa_service.send_text_message(
            whatsapp_number,
            f"🎉 Account registered successfully, *{name_input}*!"
        )
        await self._send_main_menu(customer, whatsapp_number)

    async def _send_main_menu(self, customer: Optional[WhatsAppCustomer], whatsapp_number: str) -> None:
        """Displays main menu options to customer."""
        name = customer.name if customer else "there"
        body = f"Welcome back, *{name}*! 🇸🇱\nWhat would you like to do today?"
        buttons = [
            {"id": "btn_order", "title": "🛒 Order Food"},
            {"id": "btn_track", "title": "📦 Track Order"},
            {"id": "btn_history", "title": "📋 Order History"},
        ]
        await self.wa_service.send_interactive_buttons(whatsapp_number, body, buttons)

    async def _handle_main_menu_choice(self, session: WhatsAppSession, customer: Optional[WhatsAppCustomer], whatsapp_number: str, choice: str) -> None:
        """Handles main menu selections."""
        c = choice.lower()
        if "order" in c or choice == "btn_order" or c == "1":
            await self._show_restaurant_list(session, whatsapp_number)
        elif "track" in c or choice == "btn_track" or c == "2":
            session.current_state = WhatsAppSessionState.TRACKING
            await self.db.commit()
            await self.wa_service.send_text_message(
                whatsapp_number,
                "🔎 Please enter your *Order Tracking Number* (e.g. `CLM-20260722-00001`) or type `latest` to view your last order:"
            )
        elif "history" in c or choice == "btn_history" or c == "3":
            await self._show_order_history(customer, whatsapp_number)
        else:
            await self._send_main_menu(customer, whatsapp_number)

    async def _show_restaurant_list(self, session: WhatsAppSession, whatsapp_number: str) -> None:
        """Fetches active approved restaurants and displays interactive list."""
        stmt = select(Restaurant).where(Restaurant.status != RestaurantStatus.REJECTED).limit(10)
        res = await self.db.execute(stmt)
        restaurants = res.scalars().all()

        if not restaurants:
            await self.wa_service.send_text_message(whatsapp_number, "🍽️ No active restaurants currently available in Freetown. Check back shortly!")
            return

        session.current_state = WhatsAppSessionState.SELECT_RESTAURANT
        await self.db.commit()

        rows = [
            {
                "id": f"rest_{r.id}",
                "title": r.name[:24],
                "description": (r.cuisine_type or r.address or "Freetown Store")[:72],
            }
            for r in restaurants
        ]

        sections = [{"title": "Select Restaurant", "rows": rows}]

        await self.wa_service.send_interactive_list(
            whatsapp_number,
            header_text="Freetown Restaurants 🇸🇱",
            body_text="Choose a restaurant below to view their menu and order delicious food:",
            button_label="Choose Store",
            sections=sections,
        )

    async def _handle_restaurant_selection(self, session: WhatsAppSession, whatsapp_number: str, text: str) -> None:
        """Stores selected restaurant and displays menu items."""
        rest_id = None
        if text.startswith("rest_"):
            try: rest_id = int(text.replace("rest_", ""))
            except ValueError: pass
        else:
            try: rest_id = int(text)
            except ValueError: pass

        if not rest_id:
            await self.wa_service.send_text_message(whatsapp_number, "❌ Invalid selection. Please select a valid restaurant from the list.")
            return

        stmt = select(Restaurant).where(Restaurant.id == rest_id)
        res = await self.db.execute(stmt)
        restaurant = res.scalar_one_or_none()

        if not restaurant:
            await self.wa_service.send_text_message(whatsapp_number, "❌ Restaurant not found. Please try again.")
            return

        session.selected_restaurant_id = restaurant.id
        session.cart_items = {"items": []} # Reset cart for new store
        session.current_state = WhatsAppSessionState.SELECT_MENU_ITEM
        await self.db.commit()

        await self._show_menu_items(restaurant, whatsapp_number)

    async def _show_menu_items(self, restaurant: Restaurant, whatsapp_number: str) -> None:
        """Displays available menu items for selected restaurant."""
        stmt = select(MenuItem).where(MenuItem.restaurant_id == restaurant.id, MenuItem.is_available == True).limit(10)
        res = await self.db.execute(stmt)
        items = res.scalars().all()

        if not items:
            await self.wa_service.send_text_message(whatsapp_number, f"📋 No menu items available for *{restaurant.name}*.")
            return

        rows = [
            {
                "id": f"item_{item.id}",
                "title": item.name[:24],
                "description": f"Le {item.price:,.0f} — {item.description or ''}"[:72],
            }
            for item in items
        ]

        sections = [{"title": f"Menu — {restaurant.name[:16]}", "rows": rows}]

        await self.wa_service.send_interactive_list(
            whatsapp_number,
            header_text=restaurant.name[:60],
            body_text="Select a dish to add to your order cart:",
            button_label="View Dishes",
            sections=sections,
        )

    async def _handle_menu_selection(self, session: WhatsAppSession, whatsapp_number: str, text: str) -> None:
        """Adds selected menu item to WhatsApp shopping cart."""
        item_id = None
        if text.startswith("item_"):
            try: item_id = int(text.replace("item_", ""))
            except ValueError: pass
        else:
            try: item_id = int(text)
            except ValueError: pass

        if not item_id:
            await self._show_cart_summary(session, whatsapp_number)
            return

        stmt = select(MenuItem).where(MenuItem.id == item_id)
        res = await self.db.execute(stmt)
        item = res.scalar_one_or_none()

        if not item:
            await self.wa_service.send_text_message(whatsapp_number, "❌ Menu item not found.")
            return

        # Add to cart
        cart = session.cart_items or {"items": []}
        cart_list = cart.get("items", [])

        # Check existing
        existing = next((i for i in cart_list if i["menu_item_id"] == item.id), None)
        if existing:
            existing["quantity"] += 1
        else:
            cart_list.append({
                "menu_item_id": item.id,
                "name": item.name,
                "price": float(item.price),
                "quantity": 1,
            })

        session.cart_items = {"items": cart_list}
        session.current_state = WhatsAppSessionState.CART_VIEW
        await self.db.commit()

        await self.wa_service.send_text_message(whatsapp_number, f"✅ Added *{item.name}* (Le {item.price:,.0f}) to cart!")
        await self._show_cart_summary(session, whatsapp_number)

    async def _show_cart_summary(self, session: WhatsAppSession, whatsapp_number: str) -> None:
        """Displays current shopping cart breakdown with options to confirm or add more."""
        cart = session.cart_items or {"items": []}
        items = cart.get("items", [])

        if not items:
            await self.wa_service.send_text_message(whatsapp_number, "🛒 Your shopping cart is empty.")
            return

        total = sum(i["price"] * i["quantity"] for i in items)
        cart_lines = [f"• {i['quantity']}x *{i['name']}* — Le {i['price'] * i['quantity']:,.0f}" for i in items]
        summary_text = f"🛒 *Your Shopping Cart*:\n\n" + "\n".join(cart_lines) + f"\n\n*Total*: Le {total:,.0f}"

        buttons = [
          {"id": "btn_confirm_cart", "title": "✅ Confirm Order"},
          {"id": "btn_add_more", "title": "➕ Add More Dishes"},
          {"id": "btn_clear_cart", "title": "🗑️ Clear Cart"},
        ]
        await self.wa_service.send_interactive_buttons(whatsapp_number, summary_text, buttons)

    async def _handle_cart_actions(self, session: WhatsAppSession, whatsapp_number: str, text: str) -> None:
        """Processes cart action buttons."""
        if text in ("btn_confirm_cart", "confirm", "1"):
            session.current_state = WhatsAppSessionState.ENTER_ADDRESS
            await self.db.commit()
            await self.wa_service.send_text_message(
                whatsapp_number,
                "📍 Please enter your *Delivery Address in Freetown* (e.g. `15 Lumley Beach Road, Freetown`):"
            )
        elif text in ("btn_add_more", "add"):
            if session.selected_restaurant_id:
                stmt = select(Restaurant).where(Restaurant.id == session.selected_restaurant_id)
                res = await self.db.execute(stmt)
                restaurant = res.scalar_one_or_none()
                if restaurant:
                    session.current_state = WhatsAppSessionState.SELECT_MENU_ITEM
                    await self.db.commit()
                    await self._show_menu_items(restaurant, whatsapp_number)
                    return
            await self._show_restaurant_list(session, whatsapp_number)
        elif text in ("btn_clear_cart", "clear"):
            session.cart_items = {"items": []}
            session.current_state = WhatsAppSessionState.MAIN_MENU
            await self.db.commit()
            await self.wa_service.send_text_message(whatsapp_number, "🗑️ Cart cleared. Returning to main menu.")
            customer = await self.get_or_create_customer(whatsapp_number)
            await self._send_main_menu(customer, whatsapp_number)

    async def _handle_address_entry(self, session: WhatsAppSession, customer: Optional[WhatsAppCustomer], whatsapp_number: str, address: str) -> None:
        """Saves delivery address and moves to payment selection."""
        session.delivery_address = address
        session.current_state = WhatsAppSessionState.SELECT_PAYMENT
        await self.db.commit()

        if customer:
            customer.default_address = address
            self.db.add(customer)
            await self.db.commit()

        cart = session.cart_items or {"items": []}
        items = cart.get("items", [])
        total = sum(i["price"] * i["quantity"] for i in items)

        body = (
            f"📍 Delivery Address: *{address}*\n"
            f"💰 Order Total: *Le {total:,.0f}*\n\n"
            f"Select your Payment Method:"
        )

        buttons = [
            {"id": "pay_orange", "title": "🍊 Orange Money"},
            {"id": "pay_cod", "title": "💵 Pay on Delivery"},
            {"id": "pay_card", "title": "💳 Card / Web Checkout"},
        ]
        await self.wa_service.send_interactive_buttons(whatsapp_number, body, buttons)

    async def _handle_payment_selection(self, session: WhatsAppSession, customer: Optional[WhatsAppCustomer], whatsapp_number: str, payment_choice: str) -> None:
        """Places the order via backend Order model & OrderService."""
        cart = session.cart_items or {"items": []}
        items = cart.get("items", [])

        if not items or not session.selected_restaurant_id or not customer:
            await self.wa_service.send_text_message(whatsapp_number, "❌ Cart session expired. Please start a new order.")
            session.current_state = WhatsAppSessionState.MAIN_MENU
            await self.db.commit()
            return

        total_amount = sum(i["price"] * i["quantity"] for i in items)
        subtotal = total_amount
        delivery_fee = 10000.0
        grand_total = subtotal + delivery_fee

        order_number = generate_order_number()

        # Map payment method
        pay_method = PaymentProvider.CASH
        pay_status = PaymentStatus.PENDING
        if "orange" in payment_choice or payment_choice == "pay_orange":
            pay_method = PaymentProvider.ORANGE_MONEY
        elif "card" in payment_choice or payment_choice == "pay_card":
            pay_method = PaymentProvider.VISA

        # Create Order record directly in existing database
        order = Order(
            order_number=order_number,
            user_id=customer.user_id,
            restaurant_id=session.selected_restaurant_id,
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total_amount=grand_total,
            payment_method=pay_method,
            payment_status=pay_status,
            delivery_address_snapshot={
                "address_line": session.delivery_address,
                "city": "Freetown",
                "country": "Sierra Leone",
            },
        )
        self.db.add(order)
        await self.db.flush()

        session.last_order_id = order.id
        session.cart_items = {"items": []} # Clear cart
        session.current_state = WhatsAppSessionState.MAIN_MENU
        await self.db.commit()

        # Send confirmation message to customer
        msg = (
            f"🎉 *Order Placed Successfully!* 🎉\n\n"
            f"📦 Order Code: *{order_number}*\n"
            f"💰 Total Amount: *Le {grand_total:,.0f}*\n"
            f"💳 Payment: *{pay_method.value.replace('_', ' ').title()}*\n"
            f"📍 Delivery To: *{session.delivery_address}*\n\n"
            f"Your order has been sent directly to the kitchen! You can track status anytime by replying `track`."
        )
        await self.wa_service.send_text_message(whatsapp_number, msg)

    async def _handle_order_tracking(self, session: WhatsAppSession, customer: Optional[WhatsAppCustomer], whatsapp_number: str, text: str) -> None:
        """Looks up order status by order number or customer ID."""
        order = None
        if text.lower() == "latest" or not text:
            if session.last_order_id:
                stmt = select(Order).where(Order.id == session.last_order_id)
                res = await self.db.execute(stmt)
                order = res.scalar_one_or_none()
        else:
            stmt = select(Order).where(Order.order_number == text.strip())
            res = await self.db.execute(stmt)
            order = res.scalar_one_or_none()

        if not order:
            await self.wa_service.send_text_message(whatsapp_number, "❌ Order not found. Please check your tracking number and try again.")
            return

        status_msg = (
            f"📦 *Order Status — {order.order_number}*\n\n"
            f"Status: *{order.status.value.replace('_', ' ').title()}*\n"
            f"Total: *Le {order.total_amount:,.0f}*\n"
            f"Payment: *{order.payment_status.value.title()}*\n"
            f"Placed: *{order.created_at.strftime('%d %b %Y, %I:%M %p')}*"
        )
        await self.wa_service.send_text_message(whatsapp_number, status_msg)

        session.current_state = WhatsAppSessionState.MAIN_MENU
        await self.db.commit()

    async def _show_order_history(self, customer: Optional[WhatsAppCustomer], whatsapp_number: str) -> None:
        """Displays customer's last 5 orders."""
        if not customer or not customer.user_id:
            await self.wa_service.send_text_message(whatsapp_number, "📋 No order history found.")
            return

        stmt = select(Order).where(Order.user_id == customer.user_id).order_by(Order.created_at.desc()).limit(5)
        res = await self.db.execute(stmt)
        orders = res.scalars().all()

        if not orders:
            await self.wa_service.send_text_message(whatsapp_number, "📋 You have not placed any orders yet.")
            return

        lines = [f"• *{o.order_number}* — Le {o.total_amount:,.0f} ({o.status.value.replace('_', ' ').title()})" for o in orders]
        await self.wa_service.send_text_message(whatsapp_number, f"📋 *Your Previous Orders*:\n\n" + "\n".join(lines))
