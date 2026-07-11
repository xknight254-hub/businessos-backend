"""AI Business Partner — conversational agent using LangChain.

Provides business advice, answers questions, and takes actions using
BusinessOS data (Memory, DNA, reports) as context.

Works in mock mode without an LLM API key for development/testing.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.services.memory import BusinessMemory
from app.services.dna import BusinessDNA
from app.services.observation import ObservationEngine
import logging

logger = logging.getLogger(__name__)

# In-memory conversation store (replace with Redis in production)
_conversations: dict = {}


class BusinessPartner:
    """AI Business Partner — conversational business assistant.

    Uses LangChain when OPENAI_API_KEY is configured, otherwise operates
    in mock mode with rule-based responses.
    """

    def __init__(self, db: AsyncSession, business_id: str):
        self.db = db
        self.business_id = business_id
        self.memory = BusinessMemory(db, business_id)
        self.dna = BusinessDNA(db, business_id)
        self.observation = ObservationEngine(db, business_id)
        self._use_llm = bool(settings.OPENAI_API_KEY)

    def _get_conversation(self, conversation_id: Optional[str]) -> tuple:
        """Get or create conversation history."""
        if not conversation_id or conversation_id not in _conversations:
            cid = conversation_id or str(uuid.uuid4())
            _conversations[cid] = {
                "messages": [
                    {"role": "system", "content": self._system_prompt()}
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return cid, _conversations[cid]
        return conversation_id, _conversations[conversation_id]

    def _system_prompt(self) -> str:
        return (
            "You are BusinessOS AI Business Partner — a friendly, knowledgeable assistant "
            "for Kenyan small business owners. You speak English and Swahili. "
            "You help with:\n"
            "- Business insights (sales, revenue, trends)\n"
            "- Inventory management (low stock, fast movers)\n"
            "- Customer relationships (credit, loyalty)\n"
            "- Business health (score, improvement areas)\n"
            "- Financial decisions (pricing, expenses)\n\n"
            "Rules:\n"
            "1. Be concise. Business owners are busy.\n"
            "2. Use Swahili words naturally (pole, asante, karibu).\n"
            "3. Never give financial advice without data.\n"
            "4. If unsure, say so. Don't guess.\n"
            "5. Suggest actions, never auto-execute.\n"
            "6. Keep responses under 3 sentences.\n"
            "7. Use KES for money amounts.\n"
            "8. Be warm but professional."
        )

    async def _gather_context(self) -> dict:
        """Gather business context for the assistant."""
        context = {}
        try:
            health = await self.dna.health_score()
            context["health"] = health.get("score", "N/A")
            context["health_trend"] = health.get("trend", "stable")
        except Exception:
            context["health"] = "unavailable"

        try:
            obs = await self.observation.get_insights(3)
            context["recent_observations"] = [
                {"title": o.get("title"), "body": o.get("body")} for o in obs
            ]
        except Exception:
            context["recent_observations"] = []

        return context

    async def chat(self, message: str, conversation_id: Optional[str] = None) -> dict:
        """Process a chat message and return a response."""
        cid, conversation = self._get_conversation(conversation_id)

        # Add user message
        conversation["messages"].append({"role": "user", "content": message})

        if self._use_llm:
            reply, tool = await self._llm_response(conversation)
        else:
            reply, tool = await self._mock_response(message)

        # Add assistant response
        conversation["messages"].append({"role": "assistant", "content": reply})

        # Generate suggestions
        suggestions = self._generate_suggestions(message, reply)

        # Store in Business Memory
        await self.memory.store(
            content=f"Owner asked: '{message[:100]}'. Assistant replied: '{reply[:100]}'",
            source="conversation",
            memory_type="episodic",
            tags=["chat", tool or "general"],
            confidence=0.7,
        )

        return {
            "reply": reply,
            "conversation_id": cid,
            "tool_used": tool,
            "confidence": 0.9 if tool else 0.7,
            "suggestions": suggestions,
        }

    async def _mock_response(self, message: str) -> tuple:
        """Rule-based response when no LLM is configured."""
        msg_lower = message.lower()

        # Greetings
        if any(g in msg_lower for g in ["hello", "hi", "hey", "habari", "sasa", "mambo"]):
            return "Habari! I'm BusinessOS AI Partner. I can help you check sales, inventory, customers, or business health. What would you like to know?", "greeting"

        # Health score
        if any(w in msg_lower for w in ["health", "score", "how is my business", "how am i doing"]):
            try:
                health = await self.dna.health_score()
                score = health.get("score", 0)
                trend = health.get("trend", "stable")
                return (f"Your Business Health Score is {score}/100. "
                       f"Trend: {trend}. "
                       f"Revenue: {health.get('components', {}).get('revenue_health', 0)}/30, "
                       f"Retention: {health.get('components', {}).get('retention', 0)}/25. "
                       f"Asante for checking!"), "health_score"
            except Exception:
                return "I need more sales data before I can calculate your health score. Keep recording transactions!", "health_score"

        # Sales / revenue
        if any(w in msg_lower for w in ["sale", "revenue", "income", "how much", "today"]):
            try:
                from app.api.reports.routes import revenue_summary
                rev = await revenue_summary(self.db, type("User", (), {"business_id": self.business_id})())
                if isinstance(rev, dict) and rev.get("today"):
                    return (f"Today: KES {rev['today']:,}. "
                           f"This week: KES {rev['this_week']:,}. "
                           f"Trend: {rev['trend']} ({rev['trend_percent']:.0f}%). "
                           f"Pole — that's{' a good' if rev['trend'] == 'up' else ''} day!"), "revenue"
            except Exception:
                pass
            return "I can check your sales summary. Head to Reports > Revenue for the full picture.", "revenue"

        # Low stock
        if any(w in msg_lower for w in ["stock", "inventory", "low", "reorder", "run out"]):
            try:
                movers = await self.observation.detect_fast_movers()
                low = [m for m in movers if m.get("days_until_out", 99) <= 3]
                if low:
                    items = ", ".join([f"{m['product_name']} ({m['days_until_out']} days)" for m in low[:3]])
                    return f"⚠️ Low stock alert: {items}. Would you like me to create purchase orders?", "low_stock"
                return "All stock levels look good! I'll alert you when anything runs low.", "low_stock"
            except Exception:
                pass

        # Customers
        if any(w in msg_lower for w in ["customer", "credit", "who owes"]):
            return "You have customer credit tracking enabled. Check Customers > Credit to see who hasn't paid.", "customers"

        # Help
        if any(w in msg_lower for w in ["help", "what can you", "features", "menu"]):
            return ("I can help with:\n"
                   "• 📊 Business health score\n"
                   "• 💰 Sales & revenue summary\n"
                   "• 📦 Low stock alerts\n"
                   "• 👥 Customer insights\n"
                   "• 📈 Top products\n"
                   "• ⚠️ Anomaly detection\n\n"
                   "What would you like to know?"), "help"

        return ("Asante for your message! I'm still learning about your business. "
               "Try asking about sales, stock, customers, or your business health score. "
               "Or type 'help' to see what I can do."), "fallback"

    async def _llm_response(self, conversation: list) -> tuple:
        """LangChain-powered response with tool calling."""
        try:
            from langchain_openai import ChatOpenAI
            from langchain.agents import create_openai_functions_agent, AgentExecutor
            from langchain import hub
            from langchain.tools import tool

            llm = ChatOpenAI(
                model="gpt-4o-mini",  # or use settings
                temperature=0.3,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )

            messages = conversation["messages"][-10:]  # Last 10 for context

            # Build tools
            tools = await self._build_tools()

            # Simple direct response for now
            response = await llm.ainvoke(messages)
            return response.content, "llm"
        except Exception as e:
            logger.warning(f"LLM response failed, falling back to mock: {e}")
            return await self._mock_response(conversation[-1]["content"])

    async def _build_tools(self) -> list:
        """Build LangChain tools for the agent."""
        from langchain.tools import tool

        @tool
        async def get_health_score() -> str:
            """Get the business health score (0-100)."""
            health = await self.dna.health_score()
            return json.dumps(health)

        @tool
        async def get_recent_observations() -> str:
            """Get recent AI observations and insights."""
            obs = await self.observation.get_insights(5)
            return json.dumps(obs)

        @tool
        async def search_memory(query: str) -> str:
            """Search business memory for past conversations and patterns."""
            results = await self.memory.search(query, limit=5)
            return json.dumps(results)

        @tool
        async def get_fast_movers() -> str:
            """Get fast-moving products and low stock alerts."""
            movers = await self.observation.detect_fast_movers()
            return json.dumps(movers)

        return [get_health_score, get_recent_observations, search_memory, get_fast_movers]

    def _generate_suggestions(self, message: str, reply: str) -> List[str]:
        """Generate follow-up suggestions based on context."""
        suggestions = []
        msg_lower = message.lower()
        if "health" in msg_lower or "score" in msg_lower:
            suggestions.extend(["What's my top-selling product?", "Do I have any low stock?"])
        elif "sale" in msg_lower or "revenue" in msg_lower:
            suggestions.extend(["How is my business health?", "Which customers haven't paid?"])
        elif "stock" in msg_lower or "inventory" in msg_lower:
            suggestions.extend(["What are my top products?", "Show me sales for today"])
        elif "customer" in msg_lower or "credit" in msg_lower:
            suggestions.extend(["What's my revenue this week?", "Check my low stock"])
        else:
            suggestions.extend(["How is my business doing?", "What's my health score?", "Do I have low stock?"])
        return suggestions[:3]
