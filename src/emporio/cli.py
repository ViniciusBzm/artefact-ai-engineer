"""Text interface suitable for local demonstrations and interviews."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from .agent import EmporioAgent
from .security import Authenticator


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Empório da Música AI customer-service case study")
    parser.add_argument("--data-dir", type=Path, default=repo / "data" / "demo",
                        help="Directory containing six CSV files and the policies PDF or demo policy JSON")
    parser.add_argument("--llm", action="store_true", help="Enable OpenAI function-call intent routing (requires OPENAI_API_KEY)")
    parser.add_argument("--debug", action="store_true", help="Show tool routing and data provenance")
    parser.add_argument("--question", type=str, help="Answer one question and exit")
    parser.add_argument("--auth-file", type=Path, default=os.environ.get('EMPORIO_AUTH_FILE'), help="Private JSON file mapping token SHA256 hashes to customer IDs")
    parser.add_argument("--login", action="store_true", help="Prompt for a support token locally (never pass tokens as command arguments)")
    parser.add_argument("--allow-fallback", action="store_true", help="Explicitly allow labeled offline fallback when LLM routing fails")
    args = parser.parse_args()
    if args.llm and not os.getenv("OPENAI_API_KEY"):
        parser.error("--llm requires OPENAI_API_KEY (API billing is separate from ChatGPT subscriptions)")
    try:
        agent = EmporioAgent(args.data_dir, use_llm=args.llm,
                             authenticator=Authenticator.from_file(args.auth_file), allow_fallback=args.allow_fallback)
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(f"Unable to load project inputs ({type(error).__name__}). Check datasets, policy version and auth configuration.")
    mode = "OpenAI tool routing" if args.llm else "deterministic offline demo (NO LLM)"
    print(f"Empório da Música | {mode}")
    print("Commands: /exit, /login, /logout, /reset. Provenance: --debug\n")

    def login():
        success = agent.authenticate(getpass.getpass("Support token (hidden): "))
        print("Signed in." if success else "Sign-in failed; no order access granted.")

    if args.login:
        login()

    def answer(text: str) -> None:
        result = agent.reply(text)
        if 'offline fallback' in result.route:
            print('[mode] LLM request failed; using the explicitly enabled offline fallback (NO LLM answer).')
        print("\nAssistant:", result.text)
        if args.debug:
            print("[route]", result.route)
            print("[source]", result.source or "none")
        print()
        return result

    if args.question:
        result = answer(args.question)
        agent.close()
        if result.route.startswith('llm_error'):
            raise SystemExit(2)
        return
    while True:
        try:
            text = input("Customer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if text.lower() in {"/exit", "/quit", "/q"}:
            break
        if text == '/login':
            login()
            continue
        if text in {'/logout', '/reset'}:
            agent.reset()
            print('Session cleared and signed out.')
            continue
        answer(text)
    agent.close()


if __name__ == "__main__":
    main()
