import re
import os
import time
import asyncio
import aiohttp
import aiofiles
from tqdm import tqdm
import requests

def get_nexusmods_download_url(url, cookie_str):
    """Get direct download URL from a Nexus Mods page URL."""
    # Extract file_id using regex
    file_id = re.search(r'file_id=(\d+)', url).group(1)

    # Set up session with cookies
    session = requests.Session()
    for cookie in cookie_str.split(';'):
        if cookie.strip():
            name, value = cookie.strip().split('=', 1)
            session.cookies.set(name, value, domain='.nexusmods.com', path='/')

    # Generate download URL
    response = session.post(
        'https://www.nexusmods.com/Core/Libs/Common/Managers/Downloads?GenerateDownloadUrl',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={'fid': file_id, 'game_id': 1704}
    )

    if response.status_code == 200:
        return response.json().get('url')
    return f"Error: {response.status_code}"

class DownloadManager:
    def __init__(self):
        self.downloads = {}
        self.progress_bars = {}
        self.success_status = {}
        self.running = False
        self.loop = None
        self.current_tasks = []
        
    async def download_file(self, gid, url, filepath):
        """Download a file asynchronously with progress tracking."""
        output_dir = os.path.dirname(filepath)
        os.makedirs(output_dir, exist_ok=True)
        
        display_name = os.path.basename(filepath)
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
            
        pbar = tqdm(
            total=100,
            unit='%',
            desc=f"{display_name}",
            position=len(self.progress_bars),
            leave=True,
            bar_format='{desc:<30} |{bar}| {percentage:3.0f}% {rate_fmt}{postfix}'
        )
        
        self.progress_bars[gid] = pbar
        self.success_status[gid] = False
        
        try:
            timeout = aiohttp.ClientTimeout(total=None, connect=1, sock_connect=1, sock_read=10)
            connector = aiohttp.TCPConnector(limit=16, force_close=True, enable_cleanup_closed=True)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        pbar.set_postfix_str(f"Failed: HTTP {response.status}")
                        return False
                    
                    # Get file size
                    total_size = int(response.headers.get('content-length', 0)) or None
                    if total_size:
                        downloaded = 0
                        chunk_size = 1024 * 1024  # 1MB chunks
                        
                        # Open file for writing
                        async with aiofiles.open(filepath, 'wb') as f:
                            start_time = time.time()
                            async for chunk in response.content.iter_chunked(chunk_size):
                                await f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress bar
                                if total_size:
                                    progress = int(downloaded / total_size * 100)
                                    elapsed = time.time() - start_time
                                    if elapsed > 0:
                                        speed = downloaded / elapsed / 1024 / 1024  # MB/s
                                        pbar.update(progress - pbar.n)
                                        pbar.set_postfix_str(f"Speed: {speed:.2f} MB/s")
                    else:
                        # If content-length is not available, download without progress
                        async with aiofiles.open(filepath, 'wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                            pbar.update(100)
                    
                    pbar.update(100 - pbar.n)  # Ensure we reach 100%
                    pbar.set_postfix_str("Complete")
                    self.success_status[gid] = True
                    return True
                    
        except Exception as e:
            pbar.set_postfix_str(f"Failed: {str(e)}")
            return False
        finally:
            pbar.close()
            # Remove from active downloads
            if gid in self.downloads:
                del self.downloads[gid]
            if gid in self.progress_bars:
                del self.progress_bars[gid]

    def add_download(self, url, filepath):
        """Add a download with specific filepath."""
        gid = f"download_{len(self.downloads) + 1}"
        self.downloads[gid] = {
            'url': url,
            'filepath': filepath,
            'display_name': os.path.basename(filepath)
        }
        return gid
        
    def start_monitor(self):
        """Start downloading all queued files."""
        if self.running:
            return
            
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Start all downloads
        tasks = []
        for gid, info in self.downloads.items():
            task = self.loop.create_task(self.download_file(gid, info['url'], info['filepath']))
            tasks.append(task)
            
        self.current_tasks = tasks
        
        # Run downloads in a separate thread
        import threading
        def run_loop():
            self.loop.run_until_complete(asyncio.gather(*tasks))
            self.running = False
            
        threading.Thread(target=run_loop, daemon=True).start()
        
    def wait_for_downloads(self):
        """Wait for all downloads to complete."""
        while self.running:
            time.sleep(0.5)
            
    def shutdown(self):
        """Shutdown the download manager."""
        self.running = False
        
        # Cancel any remaining tasks
        if self.loop and self.current_tasks:
            for task in self.current_tasks:
                if not task.done():
                    task.cancel()
                    
        # Close all progress bars
        for pbar in self.progress_bars.values():
            pbar.close()
            
    def get_success_status(self):
        """Get success status of all downloads."""
        return [self.success_status[gid] for gid in self.success_status]

def download_nexus_mods(urls, filepaths, cookie_str):
    """
    Download multiple Nexus mods in parallel with specific filepaths.

    Args:
        urls (list): List of Nexus Mods URLs
        filepaths (list): List of complete filepaths where files should be saved
        cookie_str (str): Cookie string for authentication

    Returns:
        dict: Dictionary mapping download IDs to filepaths
        list: List of success statuses (True/False) for each download
    """
    if len(urls) != len(filepaths):
        raise ValueError("Number of URLs must match number of filepaths")

    # Get all download URLs first
    download_urls = []
    for url in urls:
        download_url = get_nexusmods_download_url(url, cookie_str)
        if download_url and not download_url.startswith("Error"):
            download_urls.append(download_url)
        else:
            print(f"Error getting download URL for {url}: {download_url}")
            download_urls.append(None)

    manager = DownloadManager()

    download_info = {}
    for i, download_url in enumerate(download_urls):
        if download_url:
            download_id = manager.add_download(download_url, filepaths[i])
            download_info[download_id] = {
                'original_url': urls[i],
                'download_url': download_url,
                'filepath': filepaths[i]
            }

    manager.start_monitor()

    try:
        manager.wait_for_downloads()
        print("\nAll downloads completed.")
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    finally:
        manager.shutdown()

    # Get success statuses
    success_list = manager.get_success_status()

    return download_info, success_list