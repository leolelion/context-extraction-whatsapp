from extract_context import extract_context
from clean_raw_chats import process_all_chats
import os
from dotenv import load_dotenv
import getpass
import json

process_all_chats()

clean_chats_dir = 'cleaned_chats'
out_dir = 'out'

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

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