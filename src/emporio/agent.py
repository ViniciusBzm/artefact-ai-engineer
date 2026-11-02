"""Agent orchestrator: routing can use an LLM; facts and authorization remain deterministic."""
from __future__ import annotations

from dataclasses import dataclass

from .policy import PolicyBook, topic_from_text
from .router import Router, ProviderError, order_id_from_text, validate_call
from .security import Authenticator, contains_private_data
from .store import Store, brl, discounted, norm


@dataclass
class Reply:
    text: str
    route: str
    source: str


class EmporioAgent:
    def __init__(self, data_dir, use_llm: bool = False, *, authenticator: Authenticator | None = None,
                 allow_fallback: bool = False):
        self.store = Store(data_dir)
        self.policies = PolicyBook(data_dir)
        self.router = Router(use_llm=use_llm, allow_fallback=allow_fallback)
        self.history: list[tuple[str, str]] = []  # in-memory only
        self.pending_order_id: int | None = None
        self.previous_category: str = ""
        self.previous_product: str = ""
        self.authenticator = authenticator or Authenticator()
        self._customer_id: int | None = None

    def authenticate(self, token: str) -> bool:
        self.reset()
        self._customer_id = self.authenticator.authenticate(token)
        return self._customer_id is not None

    def reset(self) -> None:
        self.history.clear()
        self.pending_order_id = None
        self.previous_category = self.previous_product = ""
        self._customer_id = None

    def close(self) -> None:
        self.reset()
        self.store.db.close()

    def _product_line(self, p: dict) -> str:
        original = brl(p["price_brl"])
        current = brl(p["final_price"])
        if p["discount"]:
            price = f"{current} (was {original}, {p['discount']}% active promotion)"
        else:
            price = current
        return f"{p['name']} — {price}; {p['stock_quantity']} in stock"

    def _product(self, query: str) -> Reply:
        p = self.store.match_product(query)
        if p is None:
            return Reply("I couldn't identify that exact instrument in our catalog. Could you share its model or brand?", "get_product", "products.csv")
        self.previous_product = p['name']
        self.previous_category = p['category']
        if p["status"] != "active" or int(p["stock_quantity"]) <= 0:
            alternative = self.store.list_products(category=p["category"], limit=3)
            suggestions = "\n".join(f"- {self._product_line(x)}" for x in alternative if x["product_id"] != p["product_id"])
            states = {'discontinued': 'is discontinued', 'coming_soon': 'is coming soon'}
            state = states.get(p['status'], 'is out of stock')
            response = f"{p['name']} {state} and is not currently available for purchase."
            if suggestions:
                response += " Here are available alternatives:\n" + suggestions
            return Reply(response, "get_product", "products.csv, promotions.csv")
        response = self._product_line(p) + "."
        if "pix" in norm(query):
            if p["discount"]:
                response += " The additional 5% PIX discount cannot be combined with this promotion."
            else:
                response += f" With the standard 5% PIX discount: {brl(discounted(p['price_brl'], 5))}."
        return Reply(response + " Prices and stock reflect the supplied snapshot. Anything else I can help you with?", "get_product", "products.csv, promotions.csv")

    def _products(self, category: str = "", max_price: float | None = None,
                  keywords: str = "") -> Reply:
        if max_price is not None:
            try:
                max_price = float(max_price)
            except (ValueError, TypeError):
                return Reply("Please provide a valid maximum price in BRL.", "find_products", "")
            if max_price <= 0 or max_price > 1_000_000:
                return Reply("Please provide a reasonable maximum price in BRL.", "find_products", "")
        # Standardize category names returned by a model; no direct LLM-to-SQL path.
        t = norm(category)
        aliases = {"violoes": "Violões", "violao": "Violões", "acoustic guitar": "Violões", "classical guitar": "Violões", "ukulele": "Ukuleles",
                   "guitarr": "Guitarras", "electric guitar": "Guitarras", "baixo": "Baixos",
                   "bass": "Baixos", "teclado": "Teclados", "keyboard": "Teclados",
                   "bateria": "Baterias", "drum": "Baterias"}
        category = next((c for token, c in aliases.items() if token in t), category)
        products = self.store.list_products(category=category, max_price=max_price, keywords=keywords)
        if category:
            self.previous_category = category
        if not products:
            return Reply("I couldn't find any currently available instruments matching those filters. Try a different category or price range.",
                         "find_products", "products.csv, promotions.csv")
        self.previous_product = ""
        intro = f"Here are up to {len(products)} matching available option(s) (limited to 8)"
        if category:
            intro += f" in {category}"
        if max_price is not None:
            intro += f" for up to {brl(max_price)}"
        lines = "\n".join(f"- {self._product_line(p)}" for p in products)
        return Reply(f"{intro}:\n{lines}\n\nPrices and stock reflect the supplied dataset snapshot, not a live storefront.",
                     "find_products", "products.csv, categories.csv, promotions.csv")

    def _order(self, order_id: int | str = 0) -> Reply:
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            order_id = 0
        if order_id <= 0:
            return Reply("Please share your order number so I can check its status.", "order_status", "")
        if self._customer_id is None:
            self.pending_order_id = order_id
            return Reply("To protect order details, please sign in through /login using your support token. An email address or claimed customer ID cannot authorize access.",
                         "order_status", "")
        self.pending_order_id = None
        order = self.store.get_order(order_id, self._customer_id)
        if order is None:
            return Reply("I couldn't access that order for this signed-in account. Please check the order number or contact our support team.",
                         "order_status", "orders.csv (ownership check)")
        states = {"delivered": "delivered", "shipped": "shipped", "confirmed": "confirmed",
                  "pending": "pending", "cancelled": "cancelled"}
        answer = (f"Order #{order_id}: {states.get(order['status'], order['status'])}. "
                  f"Recorded total: {brl(order['total_brl'])}. "
                  f"Ordered on {order['order_date']}.")
        if order["tracking_code"]:
            answer += f" Tracking reference: {order['tracking_code']}."
        if order["estimated_delivery"]:
            answer += f" The stored estimated delivery date was {order['estimated_delivery']} (this may be outdated)."
        if order["items"]:
            answer += " Items: " + "; ".join(f"{x['quantity']} × {x['name']}" for x in order["items"]) + "."
        answer += " This is a case-study snapshot, not a live carrier lookup."
        return Reply(answer, "order_status", "orders.csv, order_items.csv, products.csv")

    def _policy(self, topic: str) -> Reply:
        message, source = self.policies.lookup(topic)
        if topic == "returns" and source:
            message += " Was the purchase online, and on what date did you receive the item?"
        return Reply(message, "consult_policy", source)

    def reply(self, message: str) -> Reply:
        message = message.strip()
        if len(message) > 1500:
            return Reply("Please keep the request under 1,500 characters.", "input_rejected", "")
        if not message:
            return Reply("How can I help with musical instruments or store services?", "greeting", "")
        # All explicit order identifiers stay local, including adversarial requests.
        supplied_order = order_id_from_text(message)
        policy_topic = topic_from_text(message)
        if supplied_order and policy_topic not in {'returns', 'defects', 'exchange', 'warranty', 'complaints'}:
            result = self._order(supplied_order)
            result.route += " | local authorization (NO LLM)"
            return result
        if contains_private_data(message):
            return Reply("Please remove personal details or secrets from this message. For order access, use /login; do not send your email, phone, address or token in chat.", "privacy_guard | local (NO LLM)", "")
        try:
            name, args, mode = self.router.route(message, self.history, self.previous_category, self.previous_product)
            validate_call(name, args)
        except ProviderError as error:
            return Reply(f"{error}. Please try again or use the explicit offline mode.", "llm_error (NO tool executed)", "")
        except (ValueError, TypeError):
            return Reply("I couldn't process those details safely. Could you rephrase the request?", "invalid_tool (NO tool executed)", "")
        try:
            if name == "get_product":
                query = args['query'] or message
                if 'pix' in norm(message) and 'pix' not in norm(query):
                    query += ' PIX'
                result = self._product(query)
            elif name == "find_products":
                result = self._products(str(args.get("category") or ""), args.get("max_price"), str(args.get("keywords") or ""))
            elif name == "order_status":
                # Do not let an LLM fabricate a buyer's email or order number.
                result = self._order(supplied_order or 0)
            elif name == "consult_policy":
                result = self._policy(str(args.get("topic") or ""))
            elif name == "greeting":
                result = Reply("Hi! Welcome to Empório da Música — your music starts here. How can I help you today?",
                               "greeting", "")
            else:
                if norm(message) in {"oi", "ola", "hello", "hi", "hey"}:
                    result = Reply("Hi! Welcome to Empório da Música! Looking for an instrument or help with an order?", "greeting", "")
                else:
                    result = Reply("I can help with musical instruments, product availability, orders and store policies. What would you like to know?",
                                   "out_of_scope", "")
        except (ValueError, TypeError):
            result = Reply("I couldn't process those details safely. Could you rephrase the request?", name, "")
        # Do not persist personal information in the LLM prompt/history.
        if name != "order_status":
            # Keep only server-derived tool context. Raw messages and responses are
            # unnecessary for follow-ups and could retain unsolicited personal data.
            self.history.append((name, result.source))
            self.history = self.history[-4:]
        result.route += f" | {mode}"
        return result
