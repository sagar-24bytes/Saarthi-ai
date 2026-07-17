# memory/path_resolver.py

import os
import re
from memory.context import context

KNOWN_FOLDERS = {
    "agent test folder": "B:/agent_test",
    "agent_test": "B:/agent_test",
    "downloads": os.path.expanduser("~/Downloads"),
    "downloads folder": os.path.expanduser("~/Downloads"),
    "documents": os.path.expanduser("~/Documents"),
    "documents folder": os.path.expanduser("~/Documents"),
}

def clean_speech_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    
    # Strip punctuation
    for p in [".", ",", "?", "!", "\"", "'", "`", ":", "\\", "/"]:
        text = text.replace(p, " ")
        
    # Remove filler words
    filler_words = [
        "folder", "directory", "file", "please", "my", "the", "open", "launch", 
        "show", "organize", "sort", "arrange", "cleanup", "clean up", "search", 
        "find", "look for", "in", "inside", "to", "path", "location", "select", 
        "run", "execute", "confirm", "me", "want", "would", "like"
    ]
    words = text.split()
    cleaned_words = [w for w in words if w not in filler_words]
    
    return " ".join(cleaned_words).strip()

def normalize_string(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    # Remove all non-alphanumeric characters (spaces, underscores, dashes, slashes, etc.)
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def is_pronoun(norm_text: str) -> bool:
    """
    Checks if the normalized text represents a pronoun (including repeated ones due to speech recognition duplication).
    """
    base_pronouns = ["it", "that", "this", "thisfolder", "thisfile", "there", "them", "those"]
    if norm_text in base_pronouns:
        return True
    # Support repeated pronoun patterns like "itit", "thatthat"
    for p in ["it", "that", "this", "there", "them", "those"]:
        if norm_text == p + p:
            return True
    return False

def resolve_file_or_folder_in_allowed_folders(target_name: str) -> list[str]:
    """
    Recursively searches allowed folders for any matching folder or file.
    Performs case-insensitive, normalized matching.
    Supports pronouns resolving back to context.last_path.
    """
    cleaned_target = clean_speech_text(target_name)
    norm_target = normalize_string(cleaned_target)
    
    # Pronoun context-aware matching check
    if is_pronoun(norm_target):
        last_path = getattr(context, "last_path", None)
        if last_path:
            print(f"[DEBUG] Resolved pronoun '{norm_target}' to context path: {last_path}")
            return [last_path]
        else:
            print("[INFO] I'm not sure what 'it' refers to. Could you specify which file or folder?")
            return []

    from memory.persistent import get_allowed_folders
    allowed = get_allowed_folders()
    
    print(f"[DEBUG] Loaded allowed folders: {allowed}")
    print(f"[DEBUG] Spoken target: '{target_name}' | Normalized target: '{norm_target}'")
    
    if not norm_target:
        print("[DEBUG] Search target is empty after normalization.")
        return []
        
    matches = []
    
    for root_folder in allowed:
        # Verify allowed folder exists
        if not os.path.exists(root_folder):
            print(f"[DEBUG] Skipped folder (does not exist): {root_folder}")
            continue
            
        print(f"[DEBUG] Searching inside: {root_folder}")
        
        # Check root folder itself
        norm_root_basename = normalize_string(os.path.basename(root_folder))
        if norm_target == norm_root_basename or norm_target in norm_root_basename or norm_root_basename in norm_target:
            matches.append(os.path.abspath(root_folder))
            
        # Recursive walk
        for root, dirs, files in os.walk(root_folder):
            # Check folders
            for d in dirs:
                full_dir_path = os.path.join(root, d)
                norm_dir_basename = normalize_string(d)
                if norm_target == norm_dir_basename or norm_target in norm_dir_basename or norm_dir_basename in norm_target:
                    matches.append(os.path.abspath(full_dir_path))
                    
            # Check files
            for file in files:
                full_file_path = os.path.join(root, file)
                name_part, ext_part = os.path.splitext(file)
                norm_file_name = normalize_string(file)
                norm_name_part = normalize_string(name_part)
                
                if norm_target == norm_file_name or norm_target == norm_name_part or norm_target in norm_file_name or norm_target in norm_name_part:
                    matches.append(os.path.abspath(full_file_path))
                    
    # Deduplicate matches
    unique_matches = list(set(matches))
    print(f"[DEBUG] Number of matches found: {len(unique_matches)}")
    for idx, match in enumerate(unique_matches):
        print(f"[DEBUG] Match {idx + 1}: {match}")
        
    return unique_matches

def resolve_path_from_text(text: str | None) -> str | None:
    if not text:
        return None

    cleaned = clean_speech_text(text)
    norm = normalize_string(cleaned)
    
    # Pronoun context-aware matching check
    if is_pronoun(norm):
        last_path = getattr(context, "last_path", None)
        if last_path:
            print(f"[DEBUG] Resolved pronoun '{norm}' to context path: {last_path}")
            # If context path is a file, return its parent directory
            if os.path.isfile(last_path):
                last_path = os.path.dirname(last_path)
            return last_path
        else:
            print("[INFO] I'm not sure what 'it' refers to. Could you specify which file or folder?")
            return None

    # 1️⃣ First priority: match folders/files inside allowed folders dynamically
    matches = resolve_file_or_folder_in_allowed_folders(text)
    if len(matches) >= 1:
        resolved = os.path.abspath(matches[0])
        # If resolved path is a file, return its parent directory
        if os.path.isfile(resolved):
            resolved = os.path.dirname(resolved)
        print(f"[DEBUG] Final resolved path: {resolved}")
        context.update(path=resolved)
        return resolved

    # 2️⃣ Second priority: KNOWN_FOLDERS semantic mapping
    text_clean = text.lower().strip()
    for key, path in KNOWN_FOLDERS.items():
        if key in text_clean:
            resolved = os.path.abspath(path)
            if os.path.isfile(resolved):
                resolved = os.path.dirname(resolved)
            print(f"[DEBUG] Final resolved path (Known Folder): {resolved}")
            context.update(path=resolved)
            return resolved

    # 3️⃣ Fallback to memory context last path
    last_path = getattr(context, "last_path", None)
    if last_path:
        last_path = os.path.abspath(last_path)
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)
    print(f"[DEBUG] Final resolved path (Memory Fallback): {last_path}")
    return last_path
