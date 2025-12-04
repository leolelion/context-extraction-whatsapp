import re
import json
import os
from datetime import datetime
from collections import defaultdict

# === CONFIGURATION ===
USER_NAME = "Iomar"
SOURCE = "whatsapp"
CHAT_FOLDER = "raw_chats"
OUT_FOLDER = "cleaned_chats"
LOGS_FOLDER = "logs"

# Ensure output and log folders exist
os.makedirs(OUT_FOLDER, exist_ok=True)
os.makedirs(LOGS_FOLDER, exist_ok=True)

# === REGEX PATTERNS ===
TIMESTAMP_PATTERN = r"\[(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}:\d{2})\] (.+?): (.*)"
LINK_PATTERN = r"https?://\S+"
MEDIA_PATTERNS = [
    r"image omitted", r"video omitted", r"GIF omitted", r"sticker omitted", r"audio omitted",
    r"document omitted", r"media omitted", r"file omitted", r"Contact card omitted",
    r"Location omitted", r"Live location ended", r"Live location shared",
    r"You deleted this message.", r"This message was deleted.",
    r"Messages and calls are end-to-end encrypted.*"
]
EMOJI_ONLY_PATTERN = r"^[\W\s]+$"
EMOJI_PATTERN = re.compile(
    "[" 
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002700-\U000027BF"  # Dingbats
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002600-\U000026FF"  # Misc symbols
    "]+",
    flags=re.UNICODE,
)


# === HELPER FUNCTIONS ===
def strip_invisible(text):
    return ''.join(c for c in text if c.isprintable()).strip()

# === SENSITIVE DATA PATTERNS ===
IBAN_PATTERN = r"\b[A-Z]{2}[0-9]{2}(?:[ ]?[A-Z0-9]){11,30}\b"
RIB_PATTERN = r"\b[0-9A-Z]{10,34}\b"
CREDIT_CARD_PATTERN = r"\b(?:\d[ -]?){13,19}\d\b"
PHONE_PATTERN = r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}\b"
EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"
BIC_PATTERN = r"\b[A-Z]{4}[ ]?[A-Z]{2}[ ]?[A-Z0-9]{2}([ ]?[A-Z0-9]{3})?\b"


def clean_message(text):
    text = remove_emojis(text)
    text = re.sub(LINK_PATTERN, "", text)
    text = re.sub(r"<This message was edited>", "", text, flags=re.IGNORECASE)

    # Redact in safe order
    text = re.sub(IBAN_PATTERN, "[REDACTED_IBAN]", text)
    text = re.sub(RIB_PATTERN, "[REDACTED_RIB]", text)
    text = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CARD]", text)
    text = re.sub(PHONE_PATTERN, "[REDACTED_PHONE]", text)
    text = re.sub(EMAIL_PATTERN, "[REDACTED_EMAIL]", text)
    text = re.sub(BIC_PATTERN, "[REDACTED_BIC]", text)

    return text.strip()

def is_irrelevant(text):
    stripped = text.strip()
    for pattern in MEDIA_PATTERNS:
        if re.fullmatch(pattern, stripped, re.IGNORECASE):
            return True
    if re.fullmatch(r"(Missed )?(Voice|Video) call(, .*)?", stripped, re.IGNORECASE):
        return True
    # Remove emojis before checking if empty / meaningless
    no_emoji = remove_emojis(stripped)
    if re.fullmatch(EMOJI_ONLY_PATTERN, no_emoji):
        return True
    if stripped.lower() in ["ok", "lol", "👍", "👌", "yes", "no"]:
        return True
    return False

def remove_emojis(text):
    return EMOJI_PATTERN.sub("", text)


def log_skip(reason, block, log_file_path):
    with open(log_file_path, "a", encoding="utf-8") as log:
        log.write(f"[{reason}] {block.strip()}\n\n")

def parse_message_block(block, log_file_path):
    line = strip_invisible(block[0])
    match = re.match(TIMESTAMP_PATTERN, line)
    if not match:
        log_skip("No match", "\n".join(block), log_file_path)
        return None

    date_str, time_str, sender, first_line = match.groups()
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")

    lines = [first_line] + block[1:]

    filtered_lines = []
    for l in lines:
        stripped = strip_invisible(l)
        # Drop any accidental timestamp lines
        if re.match(TIMESTAMP_PATTERN, stripped):
            continue
        cleaned = clean_message(stripped)
        if cleaned:
            filtered_lines.append(cleaned)

    full_text = "\n".join(filtered_lines)

    # Extra safeguard: remove any trailing timestamp pattern if it slipped through
    full_text = re.sub(r"\n?\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\].+?:\s*$", "", full_text).strip()

    if not full_text:
        log_skip("Empty after cleaning", "\n".join(block), log_file_path)
        return None
    if is_irrelevant(full_text):
        log_skip("Irrelevant content", "\n".join(block), log_file_path)
        return None

    role = "user" if sender.strip() == USER_NAME else "assistant"
    peer = sender.strip() if role == "assistant" else USER_NAME

    return {
        "role": role,
        "text": full_text,
        "date": dt.date().isoformat(),
        "peer": peer
    }


# === MAIN PROCESSING ===
def process_chat_file(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    log_file_path = os.path.join(LOGS_FOLDER, f"{base_name}_skipped.log")
    open(log_file_path, "w").close()  # Clear previous log

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    message_blocks = []
    current_block = []

    for line in lines:
        if re.match(TIMESTAMP_PATTERN, strip_invisible(line)):
             # Start a new block
            if current_block:
                message_blocks.append(current_block)
            current_block = [line]
        else:
        # Only add if it's not a new timestamp line
            if current_block:
                current_block.append(line)
    if current_block:
        message_blocks.append(current_block)

    daily_conversations = defaultdict(list)
    peers_by_date = {}
    peer_name = None

    for block in message_blocks:
        parsed = parse_message_block(block, log_file_path)
        if not parsed:
            continue
        date = parsed["date"]
        peer = parsed["peer"]
        if parsed["role"] == "assistant" and not peer_name:
            peer_name = peer
        if parsed["role"] == "assistant" and date not in peers_by_date:
            peers_by_date[date] = peer
        daily_conversations[date].append({
            "role": parsed["role"],
            "text": parsed["text"]
        })

    conversations = []
    for date, messages in sorted(daily_conversations.items()):
        peer = peers_by_date.get(date, peer_name or "Unknown")
        conversations.append({
            "dialogue": messages,
            "meta": {
                "source": SOURCE,
                "date": date,
                "peer": peer
            }
        })

    return conversations, peer_name or "Unknown"

# === BATCH PROCESSING ===
def process_all_chats():
    all_conversations = []  # collect everything here

    for filename in os.listdir(CHAT_FOLDER):
        # Accept files like "_chat 2.txt" or "chat_1.txt"
        if filename.endswith(".txt") and ("chat" in filename.lower()):
            file_path = os.path.join(CHAT_FOLDER, filename)
            conversations, peer_name = process_chat_file(file_path)

            # Add to master list
            all_conversations.extend(conversations)

            # Write per-peer JSON
            safe_name = re.sub(r"[^\w\s-]", "", peer_name).strip().replace(" ", "_")
            output_file = os.path.join(OUT_FOLDER, f"{safe_name}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(conversations, f, indent=2, ensure_ascii=False)
            print(f"✅ Parsed {filename} → saved as {output_file}")

    # Write master file with all conversations
    # master_file = os.path.join(OUT_FOLDER, "all_chats.json")
    # with open(master_file, "w", encoding="utf-8") as f:
    #     json.dump(all_conversations, f, indent=2, ensure_ascii=False)
    # print(f"📦 All conversations combined → saved as {master_file}")


# === RUN ===
if __name__ == "__main__":
    process_all_chats()
