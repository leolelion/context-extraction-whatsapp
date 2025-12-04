
#### Usage Instructions
1. Export your chats from WhatsApp and add them to a directory named 'raw_chats'.
2. In your terminal, enter into the context-extraction directory and run `python main.py`
3. The final extracted context will the available in the 'out' directory

#### Scripts
clean_raw_chats.py takes your raw WhatsApp text files and returns formated json. The script removes WhatsApp system logs, emojies, sensitive information, links, and short messages like 'ok'.

extract_context takes the cleaned chats and sends them to Grok for context extraction. Grok returns formatted json with information, "about_person", "speaking_style": and "events".

