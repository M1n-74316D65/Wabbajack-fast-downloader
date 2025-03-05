import json
import csv
from datetime import datetime

def read_json_file(file_path):
    """Read and return the content of a JSON file."""
    try:
        print(f"Reading JSON file from {file_path}...")
        with open(file_path, 'r') as file:
            data = json.load(file)
        print("Successfully read JSON file.")
        return data
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File not found - {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error: Failed to decode JSON - {str(e)}")

def parse_meta_field(meta_string):
    """Parse the Meta field string into a dictionary."""
    meta_dict = {}
    try:
        for line in meta_string.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                meta_dict[key.strip()] = value.strip()
    except Exception as e:
        print(f"Error parsing Meta field: {str(e)}")
    return meta_dict

def generate_url(entry):
    """Generate a URL from a given entry."""
    try:
        mod_id = entry['State']['ModID']
        file_id = entry['State']['FileID']
        game_name = entry['State']['GameName'].lower()
        return f"https://www.nexusmods.com/{game_name}/mods/{mod_id}?tab=files&file_id={file_id}"
    except (TypeError, KeyError) as e:
        print(f"Error generating URL: {str(e)} - skipping entry")
        return None

def write_to_csv(data_entries, output_file):
    """Write all data to a CSV file."""
    if not data_entries:
        print("No data to write to CSV.")
        return

    print(f"Writing data to CSV file: {output_file}...")
    
    # Define CSV headers
    fieldnames = [
        'URL',
        'Hash',
        'Name',
        'Size',
        'State_Author',
        'State_Description',
        'State_FileID',
        'State_GameName',
        'State_ImageURL',
        'State_IsNSFW',
        'State_ModID',
        'State_Name',
        'State_Version',
        'Meta_gameName',
        'Meta_modID',
        'Meta_fileID'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for entry in data_entries:
            # Parse Meta field
            meta_data = parse_meta_field(entry.get('Meta', ''))

            # Prepare row data
            row = {
                'URL': entry.get('URL', ''),
                'Hash': entry.get('Hash', ''),
                'Name': entry.get('Name', ''),
                'Size': entry.get('Size', ''),
                'State_Author': entry.get('State', {}).get('Author', ''),
                'State_Description': entry.get('State', {}).get('Description', ''),
                'State_FileID': entry.get('State', {}).get('FileID', ''),
                'State_GameName': entry.get('State', {}).get('GameName', ''),
                'State_ImageURL': entry.get('State', {}).get('ImageURL', ''),
                'State_IsNSFW': entry.get('State', {}).get('IsNSFW', ''),
                'State_ModID': entry.get('State', {}).get('ModID', ''),
                'State_Name': entry.get('State', {}).get('Name', ''),
                'State_Version': entry.get('State', {}).get('Version', ''),
                'Meta_gameName': meta_data.get('[General]\ngameName', ''),
                'Meta_modID': meta_data.get('modID', ''),
                'Meta_fileID': meta_data.get('fileID', '')
            }
            writer.writerow(row)

    print("Successfully wrote data to CSV file.")

def main():
    json_file_path = 'modlist'
    output_file_path = 'output.csv'

    # Read and parse the JSON file
    try:
        data = read_json_file(json_file_path)
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return

    # Process each entry and create URLs
    print("Processing JSON data...")
    processed_entries = []
    
    for entry in data.get("Archives", []):
        url = generate_url(entry)
        if url:
            entry_copy = entry.copy()  # Create a copy to avoid modifying original
            entry_copy['URL'] = url
            processed_entries.append(entry_copy)

    print(f"Processed {len(processed_entries)} entries.")

    # Write all data to CSV file
    write_to_csv(processed_entries, output_file_path)

if __name__ == "__main__":
    main()