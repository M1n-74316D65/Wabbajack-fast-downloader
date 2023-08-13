import webbrowser

# Read the links from the text file
with open('output.txt', 'r') as file:
    links = [line.strip() for line in file.readlines()]

# Open links in batches of 20
batch_size = 20
current_batch = 0
total_links = len(links)

while current_batch < total_links:
    # Determine the range of links to open in this batch
    start_index = current_batch
    end_index = min(current_batch + batch_size, total_links)
    batch_links = links[start_index:end_index]

    # Open each link in the batch
    for link in batch_links:
        webbrowser.open(link)

    # Wait for keyboard input before opening the next batch
    input("Press Enter to continue to the next batch...")

    # Move to the next batch
    current_batch += batch_size