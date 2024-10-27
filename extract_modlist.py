import json

# Read the JSON file
with open('modlist', 'r') as file:
    json_data = file.read()

# Parse the JSON data
try:
    data = json.loads(json_data)
except json.JSONDecodeError as e:
    print(f"Error: Failed to decode JSON - {str(e)}")
    exit()

# Create a list to store the generated URLs
urls = []

# Process each entry and create URLs
entries = data["Archives"]
for entry in entries:
    try:
        mod_id = entry['State']['ModID']
        file_id = entry['State']['FileID']
        game_name = entry['State']['GameName'].lower()
        url = f"https://www.nexusmods.com/{game_name}/mods/{mod_id}?tab=files&file_id={file_id}"
        urls.append(url)
        print(url)
    except TypeError:
        print("Error: Invalid entry format - skipping entry")
    except KeyError:
        print("Error: Missing required keys in entry - skipping entry")

# Write the URLs to an output file
with open('output.txt', 'w') as file:
    for url in urls:
        file.write(url + '\n')
