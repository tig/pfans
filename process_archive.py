import os
import re
from datetime import datetime, timezone
import json
from pathlib import Path
from collections import defaultdict
import yaml
from bs4 import BeautifulSoup
import glob
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

def parse_date(date_str):
    """Parse various date formats into ISO format"""
    date_formats = [
        '%a, %d %b %Y %H:%M:%S %z',      # 'Sat, 25 May 1996 08:59:18 +0100'
        '%a, %d %b %Y %H:%M:%S %Z',      # 'Sat, 25 May 1996 08:59:18 GMT'
        '%d %b %Y %H:%M:%S %z',          # '25 May 1996 08:59:18 +0100'
        '%d %b %Y %H:%M:%S %Z',          # '25 May 1996 08:59:18 GMT'
        '%a, %d %b %Y %H:%M %z',         # 'Sat, 25 May 1996 08:59 +0100'
        '%a, %d %b %Y %H:%M %Z',         # 'Sat, 25 May 1996 08:59 GMT'
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Convert to UTC if timezone info exists
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    
    print(f"Warning: Could not parse date '{date_str}'")
    return None

def parse_email_file(file_path, base_dir):
    """Parse email file into structured data"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract headers and body
    headers, body = content.split('\n\n', 1)
    
    # Parse headers
    header_dict = {}
    for line in headers.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            header_dict[key.strip().lower()] = value.strip()
    
    # Get relative path from base_dir
    rel_path = os.path.relpath(file_path, base_dir)
    
    # Get filename components (e.g., "960529-005.htm" -> year=96, month=05, day=29)
    filename = os.path.basename(file_path)
    year = '19' + filename[0:2]  # Assume 19xx for now
    month = filename[2:4]
    day = filename[4:6]
    sequence = filename.split('-')[1].split('.')[0]
    
    # Try to parse date from headers first
    date = parse_date(header_dict.get('date', ''))
    if not date:
        # Use date from filename as fallback
        date = f"{year}-{month}-{day}T00:00:00+00:00"
    
    return {
        'subject': header_dict.get('subject', ''),
        'from': header_dict.get('from', ''),
        'date': date,
        'body': body.strip(),
        'thread_subject': clean_title(header_dict.get('subject', '')),
        'original_file': filename,
        'original_path': rel_path.replace('/', '\\')
    }

def organize_threads(email_data):
    """Organize emails into threads"""
    threads = defaultdict(list)
    
    # First pass: group by cleaned subject
    for email in email_data:
        threads[email['thread_subject']].append(email)
    
    # Sort messages within each thread by date
    for thread_subject in threads:
        threads[thread_subject].sort(key=lambda x: x['date'])
    
    return threads

def init_storage_client():
    """Initialize Azure Blob Storage client"""
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connect_str:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not found in environment")
    
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_name = "pfans-archive"
    
    try:
        container_client = blob_service_client.get_container_client(container_name)
        container_client.get_container_properties()  # Verify it exists
        print(f"Using existing container: {container_name}")
    except Exception:
        container_client = blob_service_client.create_container(
            container_name,
            public_access='blob'
        )
        print(f"Created new container: {container_name}")
    
    return container_client

def upload_messagebodies_to_azure(messages, container_client):
    """Upload message bodies to Azure blob storage"""
    print("\nUploading message bodies to Azure...")
    
    for message in messages:
        # Extract model from original_path (e.g., "356\1996\05\960529-005.htm" -> "356")
        model = message['original_path'].split('\\')[0]
        
        date = datetime.fromisoformat(message['date'].replace('Z', '+00:00'))
        year = date.strftime('%Y')
        month = date.strftime('%m')
        
        # Get sequence from original_file (e.g., "960529-005.htm" -> "005")
        sequence = message['original_file'].split('-')[1].split('.')[0]
        base_filename = date.strftime('%y%m%d') + '-' + sequence
        
        # Upload actual message text to Azure
        blob_path = f"{model}/{year}/{month}/{base_filename}.txt"
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.upload_blob(message['body'], overwrite=True)
        print(f"Uploaded {blob_path}")

def generate_hugo_frontmatter(messages, output_dir):
    """Generate Hugo content files with frontmatter"""
    print("\nGenerating Hugo content files...")
    
    # First, create model indexes for all unique models
    models = set(msg['original_path'].split('\\')[0] for msg in messages)
    for model in models:
        model_dir = Path(output_dir) / model
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Create model index if it doesn't exist and we're not in pfans root
        if model_dir.name != 'pfans':
            model_index = model_dir / '_index.md'
            with model_index.open('w', encoding='utf-8') as f:
                f.write(f'''---
title: 'Porsche {model} Discussions'
type: 'porsche'
layout: 'pfans-model'
model: '{model}'
---

Archive of {model}-related discussions from the PorscheFans mailing list.
''')
    
    # Then process each message
    for message in messages:
        # Extract model from original_path
        model = message['original_path'].split('\\')[0]
        
        date = datetime.fromisoformat(message['date'].replace('Z', '+00:00'))
        year = date.strftime('%Y')
        month = date.strftime('%m')
        
        # Get sequence from original_file
        sequence = message['original_file'].split('-')[1].split('.')[0]
        base_filename = date.strftime('%y%m%d') + '-' + sequence
        
        # Create directory structure
        message_dir = Path(output_dir) / model / year / month
        message_dir.mkdir(parents=True, exist_ok=True)
        
        # Create message file
        md_file = message_dir / f"{base_filename}.md"
        print(f"Creating {md_file}")
        
        # Generate frontmatter
        with md_file.open('w', encoding='utf-8') as f:
            f.write('---\n')
            f.write(f"title: \"{message['subject']}\"\n")
            f.write(f"date: '{message['date']}'\n")
            f.write(f"author: '{message['from']}'\n")
            f.write('type: "porsche"           # Use porsche base styling\n')
            f.write('layout: "pfans/pfans-message"   # Use pfans-message template\n')
            f.write(f"model: '{model}'\n")
            f.write(f"thread_subject: \"{message['thread_subject']}\"\n")
            f.write(f"original_file: '{base_filename}.htm'\n")
            f.write(f"original_path: '{message['original_path']}'\n")
            blob_path = f"{model}/{year}/{month}/{base_filename}.txt"
            f.write(f"body_url: https://pfans.blob.core.windows.net/pfans-archive/{blob_path}\n")
            f.write('---\n\n')
        
        # Create index files (but not root)
        create_index_files(message_dir, model, year, month)

def clean_title(title):
    # Remove any quotes that might interfere with YAML
    return title.replace('"', '').replace("'", "")

def clean_author(author):
    # Clean up author field, removing any special characters
    return author.replace('"', '').replace("'", "").strip()

def escape_yaml_value(value, key):
    """Properly escape YAML string values"""
    if isinstance(value, str):
        # Date should just have single quotes
        if key == 'date':
            return f"'{value}'"
        # For values containing single quotes, use double quotes
        if "'" in value:
            return f'"{value}"'
        # For everything else, use single quotes
        return f"'{value}'"
    return value

def process_archive(archive_file, output_dir, limit=1000):
    # Initialize Azure Storage
    container_client = init_storage_client()
    
    with open(archive_file, 'r', encoding='utf-8') as f:
        messages = json.load(f)

    messages.sort(key=lambda x: x['date'])
    messages = messages[:limit]
    print(f"Processing {len(messages)} messages...")
    
    # First upload all message bodies to Azure
    upload_messagebodies_to_azure(messages, container_client)
    
    # Then generate Hugo content
    generate_hugo_frontmatter(messages, output_dir)
    
    print(f"\nWebsite content generated in: {output_dir}")

def create_index_files(message_dir, model, year, month):
    """Create model, year, and month _index.md files, but never touch pfans root"""
    # Get model directory path
    model_dir = Path(message_dir).parent.parent.parent  # /content/porsche/pfans/356
    year_dir = message_dir.parent                      # /content/porsche/pfans/356/1996
    month_dir = message_dir                            # /content/porsche/pfans/356/1996/05
    
    # Create model index if it doesn't exist
    if model_dir.name != 'pfans':  # Only if we're not in the pfans root
        model_index = model_dir / '_index.md'
        with model_index.open('w', encoding='utf-8') as f:
            f.write(f'''---
title: 'Porsche {model} Discussions'
type: 'porsche'
layout: 'pfans-model'
model: '{model}'
---

Archive of {model}-related discussions from the PorscheFans mailing list.
''')

    # Create year index
    year_index = year_dir / '_index.md'
    with year_index.open('w', encoding='utf-8') as f:
        f.write(f'''---
title: '{model} Discussions - {year}'
type: 'porsche'
layout: 'pfans-year'
model: '{model}'
year: '{year}'
---
''')

    # Create month index
    month_index = month_dir / '_index.md'
    month_name = datetime.strptime(month, '%m').strftime('%m/%Y')
    with month_index.open('w', encoding='utf-8') as f:
        f.write(f'''---
title: '{model} Discussions - {month_name}'
type: 'porsche'
layout: 'pfans-month'
model: '{model}'
year: '{year}'
month: '{month}'
---
''')

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Azure Storage
    container_client = init_storage_client()
    
    # Get absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(script_dir, 'PorscheFans')
    output_dir = os.path.join(script_dir, '..', 'kindelwww', 'content', 'porsche', 'pfans')
    
    print(f"Script directory: {script_dir}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    
    # For testing, just process 356/1996/05 directory
    test_dir = os.path.join(input_dir, '356', '1996', '05')
    print(f"\nProcessing test directory: {test_dir}")
    
    # Find .htm files in test directory only
    input_files = []
    if os.path.exists(test_dir):
        for file in os.listdir(test_dir):
            if file.endswith('.htm'):
                input_files.append(os.path.join(test_dir, file))
    
    if not input_files:
        print("ERROR: No .htm files found in test directory")
        return
    
    print(f"Found {len(input_files)} .htm files")
    print("Files to process:")
    for file in input_files:
        print(f"  {os.path.relpath(file, input_dir)}")

    # Process test files
    email_data = []
    files_processed = 0
    for file in input_files:
        print(f"Processing {os.path.relpath(file, input_dir)}...")
        try:
            email_data.append(parse_email_file(file, input_dir))
            files_processed += 1
        except Exception as e:
            print(f"Error processing {file}: {e}")
    
    print(f"\nProcessed {files_processed} files")
    
    # Upload to Azure and generate Hugo content
    upload_messagebodies_to_azure(email_data, container_client)
    generate_hugo_frontmatter(email_data, output_dir)

if __name__ == "__main__":
    main() 