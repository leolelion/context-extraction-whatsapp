import json
import urllib.request
import urllib.parse
import os
from dotenv import load_dotenv  # Add this import
import getpass  # Keep for fallback

# Load .env file
load_dotenv()
user = "Iomar"

def extract_context(file_path, api_key, model='grok-4-latest'):
    # Step 1: Extract person_name from filename (e.g., 'Alice_chat.json' -> 'Alice')
    filename = os.path.basename(file_path)
    person_name = filename.split('_')[0]  # Assumes format like 'First_Other.json'
    
    # Step 2: Read JSON file
    try:
        with open(file_path, 'r') as f:
            chat = json.load(f)
    except Exception as e:
        return f"Error reading file: {e}"
    
    # Step 3: Filter and format valid messages (handle nested 'dialogue')
    valid_messages = []
    skipped = 0
    if not isinstance(chat, list):
        return "Error: JSON must be a list."
    
    for entry in chat:
        if isinstance(entry, dict) and 'dialogue' in entry:
            for msg in entry['dialogue']:
                if isinstance(msg, dict) and 'role' in msg and 'text' in msg:
                    valid_messages.append(f"{msg['role'].capitalize()}: {msg['text']}")
                else:
                    skipped += 1
                    print(f"Warning: Skipped invalid message in {filename}: {msg}")
        else:
            skipped += 1
            print(f"Warning: Skipped invalid entry in {filename}: {entry}")
    
    if not valid_messages:
        return "Error: No valid messages found in the file."
    
    conversation = '\n'.join(valid_messages)
    if skipped > 0:
        print(f"Warning: Skipped {skipped} invalid items in {filename}.")
    
    # Step 4: Create LLM prompt (generalized for any person)
    system_prompt = f"""
You are an expert at extracting high-quality context from conversations for a communication aid system (VoxAI) for people with ALS. The 'User' is {user} (with ALS), and the 'Assistant' is {person_name} (the person they are talking to). Focus on quality over quantity: only precise, helpful info like specific events, stories, happenings, traits about {person_name}, and how {user} speaks with them (e.g., tone, common phrases).

Extract in structured JSON:
- "about_person": Summary of traits, preferences, background about {person_name}.
- "speaking_style": How {user} communicates with {person_name} (e.g., humor, formality).
- "events": List of specific events/stories mentioned (e.g., "{person_name}'s trip to Paris in 2024").

Be concise and accurate. Output ONLY valid JSON.
"""
    user_prompt = f"Conversation:\n{conversation}\n\nExtract context as JSON."
    
    # Step 5: Prepare API request (xAI compatible with OpenAI format)
    data = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,  # Updated to match working example
        "stream": False  # Explicitly set to match working example
    }).encode('utf-8')
    
    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",  # xAI endpoint
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # Added to prevent 403/1010
        }
    )
    
    # Step 6: Call API and get response (with detailed error handling)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            extracted = result['choices'][0]['message']['content']
            return extracted  # Raw JSON string from LLM
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else "No body"
        return f"API error: {e} - Status: {e.code} - Reason: {e.reason} - Body: {error_body}"
    except Exception as e:
        return f"API error: {e}"

# Usage: Process all files in 'clean chats' and save to 'out'
if __name__ == "__main__":
    # Define directories (assuming relative to script)
    clean_chats_dir = 'cleaned_chats'
    out_dir = 'out'
    
    # Create 'out' directory if it doesn't exist
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    # Load API key from .env (fallback to prompt if not found)
    api_key = os.getenv('XAI_API_KEY')
    if not api_key:
        api_key = getpass.getpass("Enter your xAI API key: ")
    
    # Loop over all .json files in 'clean chats'
    for filename in os.listdir(clean_chats_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(clean_chats_dir, filename)
            print(f"Processing {filename}...")
            
            result = extract_context(file_path, api_key)
            
            # Check if result is error or valid JSON string
            if result.startswith("Error") or result.startswith("API error"):
                print(f"Failed to process {filename}: {result}")
                continue  # Skip saving on error
            
            # Parse the extracted JSON string to validate and save as proper JSON
            try:
                extracted_json = json.loads(result)
                output_filename = f"{filename.replace('.json', '')}_extracted.json"
                output_path = os.path.join(out_dir, output_filename)
                with open(output_path, 'w') as f:
                    json.dump(extracted_json, f, indent=4)
                print(f"Saved extracted context for {filename} to {output_path}")
            except json.JSONDecodeError:
                print(f"Invalid JSON from API for {filename}: {result}")