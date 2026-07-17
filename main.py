from voice.input import listen
from planner.graph import build_planner_graph
from langchain_core.messages import HumanMessage
from planner.intent import classify_intent
from tools.actions import open_folder
from tools.search import search_files
from memory.path_resolver import resolve_path_from_text
from memory.context import context
from planner.llm import check_ollama_status
import re
import sys


planner_graph = build_planner_graph()


def is_noise(text: str) -> bool:
    """
    Returns True if input is only filler / punctuation noise
    e.g. '.', '...', ',,,'
    """
    stripped = text.strip()
    if not stripped:
        return True
    return all(c in "., " for c in stripped)


def extract_search_query(text: str) -> str:
    """
    Extract clean filename keywords from natural language.
    Removes verbs, folder references, and punctuation.
    """

    text = text.lower()

    # Remove punctuation
    text = re.sub(r'[^\w\s\.]', ' ', text)

    # Remove search verbs
    verbs = {"search", "find", "look", "for"}
    words = text.split()

    words = [w for w in words if w not in verbs]

    # Remove folder reference words
    stop_words = {
        "in", "inside", "under", "from",
        "folder", "directory",
        "agent", "test"
    }

    words = [w for w in words if w not in stop_words]

    # Remove standalone extensions if separated
    # combine pdf properly
    query = " ".join(words)

    return query.strip()


def main():
    # ============================================================
    # 🚀 STARTUP CHECK (OLLAMA & MODEL)
    # ============================================================
    status, error_msg = check_ollama_status()
    if not status:
        print(error_msg)
        sys.exit(1)

    # ============================================================
    # 🏷️ SAARTHI BANNER
    # ============================================================
    print("\n========================================")
    print("                Saarthi                 ")
    print("     Personal Desktop AI Assistant      ")
    print("========================================\n")
    print("🧠 Saarthi booted. Say something…")

    awaiting_open_target = False

    while True:

        # ===============================
        # 🎙️ PERCEPTION
        # ===============================
        user_text = listen()

        if not user_text:
            print("…")
            continue

        user_text = user_text.strip()

        # ===============================
        # NOISE FILTER
        # ===============================
        if is_noise(user_text):
            print("…")
            continue

        print("Heard:", user_text)

        # ===============================
        # 🧠 INTENT CLASSIFICATION
        # ===============================
        intent = classify_intent(user_text)
        print(f"[Intent] {intent}")

        # ===============================
        # 🔚 EXIT INTENT
        # ===============================
        if intent == "exit":
            print("👋 Shutting down Saarthi.")
            break

        # ===============================
        # NO-ACTION / CHITCHAT
        # ===============================
        if intent == "no_action":
            print("🙂 Got it.")
            continue

        # ===============================
        # UNKNOWN INTENT SAFETY BLOCK
        # ===============================
        if intent == "unknown":
            print("❓ I didn't understand that.")
            continue

        # ===============================
        # CLARIFICATION CONTINUATION
        # ===============================
        if awaiting_open_target:

            path = resolve_path_from_text(user_text)

            if path:
                open_folder(path)
                awaiting_open_target = False
                continue

            print("❓ I still couldn’t identify the folder.")
            continue

        # ===============================
        # OPEN FOLDER INTENT
        # ===============================
        if intent == "open":

            path = resolve_path_from_text(user_text)

            # memory fallback
            if not path:
                path = getattr(context, "last_path", None)

            if not path:
                print("❓ Which folder should I open?")
                awaiting_open_target = True
                continue

            open_folder(path)
            continue

        # ===============================
        # SEARCH INTENT (NEW)
        # ===============================
        if intent == "search":

            path = resolve_path_from_text(user_text)

            # fallback to memory
            if not path:
                path = getattr(context, "last_path", None)

            if not path:
                print("❓ Which folder should I search in?")
                continue

            query = extract_search_query(user_text)

            if not query:
                print("❓ What should I search for?")
                continue

            print(f"Searching for '{query}' in {path}...")

            try:
                results = search_files(path, query)

                if not results:
                    print("No matching files found.")
                else:
                    print(f"\nFound {len(results)} match(es):\n")

                    for result in results[:10]:
                        print(result)

                    if len(results) > 10:
                        print(f"\n...and {len(results) - 10} more")

            except Exception as e:
                print("⚠️ Search failed:", e)

            continue

        # ===============================
        # PLANNER + VALIDATOR + CONFIRMATION + EXECUTION
        # ===============================
        try:

            result = planner_graph.invoke({
                "messages": [HumanMessage(content=user_text)],
                "user_text": user_text,
                "intent": intent,
                "plan": {}
            })

            print("\nGenerated Plan:")
            print(result.get("plan"))

        except Exception as e:
            print("⚠️ Error during execution:", e)


if __name__ == "__main__":
    main()
