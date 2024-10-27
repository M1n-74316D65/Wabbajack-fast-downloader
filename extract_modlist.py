import json

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

def generate_url(entry):
    """Generate a URL from a given entry."""
    try:
        mod_id = entry['State']['ModID']
        file_id = entry['State']['FileID']
        game_name = entry['State']['GameName'].lower()
        return f"https://www.nexusmods.com/{game_name}/mods/{mod_id}?tab=files&file_id={file_id}"
    except (TypeError, KeyError) as e:
        print(f"Error: {str(e)} - skipping entry")
        return None

def write_urls_to_file(urls, output_file):
    """Write a list of URLs to an output file."""
    print(f"Writing URLs to {output_file}...")
    with open(output_file, 'w') as file:
        file.write('\n'.join(urls) + '\n')
    print("Successfully wrote URLs to file.")

def main():
    json_file_path = 'modlist'
    output_file_path = 'output.txt'

    # Read and parse the JSON file
    try:
        data = read_json_file(json_file_path)
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return

    # Process each entry and create URLs
    print("Generating URLs from JSON data...")
    urls = [url for entry in data.get("Archives", []) if (url := generate_url(entry))]
    print(f"Generated {len(urls)} URLs.")

    # Write the URLs to an output file
    write_urls_to_file(urls, output_file_path)

if __name__ == "__main__":
    main()
