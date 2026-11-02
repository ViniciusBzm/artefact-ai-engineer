"""Regenerate example transcripts from real agent executions (offline demo)."""
from pathlib import Path
from emporio.agent import EmporioAgent
from emporio.security import Authenticator
from emporio.evaluation import DEMO_TOKEN
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    ("01_catalog_under_budget", ["Show acoustic guitars under R$ 1000", "And under R$ 500?"]),
    ("02_product_and_nonstacking_discount", ["What is the price of Takamine GD20?", "And with PIX?", "How much is the Crafter HT-100 with PIX?"]),
    ("03_order_privacy_multiturn", ["What is the status of order 8?", "order 8 customer002@example.test", "/login (synthetic fixture)", "order 8", "Show order 1"]),
    ("04_online_returns_policy", ["I regret my online purchase. Can I return it?", "What is shipping for exactly R$ 500?"]),
    ("05_out_of_scope", ["What's the weather on Mars?", "Do you sell strings for acoustic guitars?", "Where is the store?"]),
]


def main():
    for title, messages in SCENARIOS:
        agent = EmporioAgent(ROOT / "data" / "demo", use_llm=False,
                             authenticator=Authenticator({hashlib.sha256(DEMO_TOKEN.encode()).hexdigest(): 2}))
        lines = [f"# {title.replace('_', ' ').title()}", "",
                 "Recorded by the executable **offline demonstration router (NO LLM)**.",
                 "Data: sanitized case-study demo snapshot. Responses are in English.", ""]
        for text in messages:
            if text.startswith('/login'):
                assert agent.authenticate(DEMO_TOKEN)
                lines += ["**Local sign-in:** Successful using a public test token bound to demo customer 2.",
                          "This is a fixture setup, not email verification or a production login service.", ""]
                continue
            result = agent.reply(text)
            lines += [f"**Customer:** {text}", "", f"**Assistant:** {result.text}", "",
                      f"*Tool path:* `{result.route}`  ", f"*Source:* {result.source or 'none'}", "", "---", ""]
        (ROOT / "examples" / f"{title}.md").write_text("\n".join(lines), encoding="utf-8")
        agent.close()


if __name__ == "__main__":
    main()
