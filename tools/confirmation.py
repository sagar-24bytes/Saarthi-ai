# tools/confirmation.py

import os
import fnmatch
import time
from voice.input import listen


# ============================================================
# FILE COUNT ESTIMATION
# ============================================================

def count_matching_files(directory, pattern):
    try:
        return len([
            f for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
            and fnmatch.fnmatch(f.lower(), pattern.lower())
        ])
    except Exception:
        return 0


# ============================================================
# CONFIRMATION LISTENER WITH RETRIES
# ============================================================

def get_confirmation(max_attempts=3, wait_seconds=1.5):
    """
    Waits for clear yes/no voice confirmation.
    Retries on silence or unclear input.
    Falls back to keyboard if needed.
    """

    for attempt in range(max_attempts):

        print("\nSpeak YES or NO...")

        # Give user time to prepare before recording
        time.sleep(wait_seconds)

        answer = listen().lower().strip().rstrip(".!?, ")

        if answer:
            print("Heard:", answer)

            if answer in ("yes", "y"):
                return True

            if answer in ("no", "n"):
                return False

            print("Didn't understand confirmation.")

        else:
            print("No speech detected.")

    # Keyboard fallback (safety net)
    answer = input("\nType yes/no: ").strip().lower().rstrip(".!?, ")
    return answer in ("yes", "y")


# ============================================================
# MAIN CONFIRMATION NODE (LangGraph — CLI)
# ============================================================

def confirmation_node(state):

    plan = state.get("plan", {})
    steps = plan.get("steps", [])

    if not steps:
        print("Nothing to execute.")
        state["approved"] = False
        return state

    print("\n--- PLAN PREVIEW ---")

    total_files = 0
    breakdown = []
    affected_locations = set()

    for step in steps:

        tool = step.get("tool")
        args = step.get("args", {})

        # Track affected locations
        if "path" in args:
            affected_locations.add(args["path"])

        if "source_directory" in args:
            affected_locations.add(args["source_directory"])

        if "destination_directory" in args:
            affected_locations.add(args["destination_directory"])

        # File impact estimation
        if tool == "move_file":
            src = args.get("source_directory")
            pattern = args.get("file_pattern", "*")

            count = count_matching_files(src, pattern)

            total_files += count

            if count > 0:
                breakdown.append((pattern, count))

    # ========================================================
    # SHOW IMPACT SUMMARY
    # ========================================================

    operation_count = len(steps)

    print(f"\nThis will execute {operation_count} operation(s).")

    if total_files > 0:
        print(f"It will move {total_files} file(s).")
    else:
        print("No files will be moved (folders may still be created).")

    if breakdown:
        print("\nBreakdown:")
        for pattern, count in breakdown:
            print(f"  {pattern} → {count} file(s)")

    print("\nAffected locations:")
    for loc in sorted(affected_locations):
        print(f"  {loc}")

    print("\nConfirmation required.")

    # ========================================================
    # GET USER CONFIRMATION
    # ========================================================

    approved = get_confirmation()

    state["approved"] = approved

    if approved:
        print("Approved. Executing plan...")
    else:
        print("Execution cancelled.")

    return state


# ============================================================
# GUI CONFIRMATION NODE (LangGraph — GUI only)
# Uses interrupt() to pause the graph and yield control back
# to the GUI.  The GUI resumes by calling graph.stream()
# with Command(resume=True) or Command(resume=False).
# ============================================================

def gui_confirmation_node(state):
    """
    LangGraph node used exclusively by the GUI graph.

    Pauses execution via interrupt() and passes the current validated
    plan as the interrupt payload.  The GUI receives this payload,
    displays the plan, and resumes the graph with the user's decision.

    The return value of interrupt() is whatever the GUI passes as the
    Command(resume=...) value — True (approved) or False (cancelled).
    """
    from langgraph.types import interrupt

    plan = state.get("plan", {})
    steps = plan.get("steps", [])

    if not steps:
        print("[LANGGRAPH] Confirmation node: plan is empty — skipping execution.")
        return {"approved": False}

    print("[LANGGRAPH] Confirmation node: pausing graph for GUI confirmation...")

    # interrupt() suspends the graph here and sends `plan` as the
    # payload.  Execution will only continue when the GUI calls
    # graph.stream(Command(resume=approved), config=same_thread_config)
    approved = interrupt(plan)

    print(f"[LANGGRAPH] Confirmation node: resumed with approved={approved}")

    if approved:
        print("[LANGGRAPH] Approved. Proceeding to executor...")
    else:
        print("[LANGGRAPH] Cancelled. Graph will terminate without executing.")

    return {"approved": approved}
