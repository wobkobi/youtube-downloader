import os
import yt_dlp
import asyncio
import shutil
import re
import signal

class DownloadInfo:
    def __init__(self, title, url):
        self.title = title
        self.url = url
        self.status = "pending"
        self.final_file = None

class SimpleDownloader:
    def __init__(self, download_dir, final_dir):
        self.download_dir = download_dir
        self.final_dir = final_dir

    def get_video_info(self, info):
        try:
            ydl_opts = {
                'quiet': True,  # Suppress output
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                video_info = ydl.extract_info(info.url, download=False)
            return video_info
        except yt_dlp.utils.YoutubeDLError as e:
            print(f"Error: {e}")
            return None

    def list_formats(self, video_info):
        return video_info.get('formats', [])

    def download_video(self, info, format_id, height):
        try:
            ydl_opts = self._generate_ydl_options(format_id, height)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(info.url, download=True)
                video_title = info_dict.get('title', 'Video')
                video_path = ydl.prepare_filename(info_dict)
                final_filename = self._generate_final_filename(video_title, height)
                final_path = os.path.join(self.download_dir, final_filename)

                if not os.path.exists(final_path):
                    final_path = video_path

            sanitized_final_path = re.sub(r'[<>:"/\\|?*\$]', '_', final_filename)
            sanitized_final_path = os.path.join(self.final_dir, sanitized_final_path)

            os.makedirs(self.final_dir, exist_ok=True)
            shutil.move(final_path, sanitized_final_path)
            info.status = "finished"
            info.final_file = sanitized_final_path
            print(f"Moved to final directory: {sanitized_final_path}")
        except yt_dlp.utils.YoutubeDLError as e:
            print(f"Error: {e}")
            info.status = "error"
        except FileNotFoundError:
            print("File not found after conversion, possibly already moved or deleted.")
            info.status = "error"

    def _generate_ydl_options(self, format_id, height):
        common_opts = {
            'format': f"{format_id}+bestaudio[protocol^=m3u8]",
            'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'no_warnings': True,
            'force_generic_extractor': True,
            'rm_cachedir': True,
            'concurrent_fragments': 4,
            'retries': 20,
            'fragment_retries': 20,
            'retry_sleep': 'exp=1:120:2',
            'xattr_set_filesize': True,
            'hls_use_mpegts': True,
            'keep_fragments': False,
            'http_chunk_size': 10485760,
            'prefer_free_formats': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'buffer_size': 32 * 1024,
        }

        if height == 'audio':
            common_opts['format'] = f"{format_id}"
            common_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            common_opts['outtmpl'] = os.path.join(self.download_dir, '%(title)s_audio.%(ext)s')

        return common_opts

    def _generate_final_filename(self, title, height):
        if height == 'audio':
            return f"{title}_audio.mp3"
        return f"{title}_{height}p.mp4"

    def filter_formats(self, formats):
        seen_resolutions = set()
        filtered_formats = []

        for f in formats:
            resolution = f.get('resolution')
            ext = f.get('ext')
            if resolution and resolution != 'audio only' and ext != 'mhtml' and resolution not in seen_resolutions:
                filtered_formats.append(f)
                seen_resolutions.add(resolution)

        return sorted(filtered_formats, key=lambda x: int(x['height']) if x['height'] else 0, reverse=True)

    def best_audio_format(self, formats):
        return max(
            (f for f in formats if f.get('vcodec') == 'none' and f.get('abr') is not None),
            key=lambda x: x.get('abr', 0),
            default=None
        )

    def cleanup_temp_dir(self):
        for filename in os.listdir(self.download_dir):
            file_path = os.path.join(self.download_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

async def main():
    downloader = SimpleDownloader(download_dir, final_dir)

    while True:
        url = input("Enter the video or playlist URL: ")
        info = DownloadInfo("Video", url)
        video_info = await asyncio.get_running_loop().run_in_executor(None, downloader.get_video_info, info)

        if video_info:
            break
        else:
            print("Invalid URL or failed to retrieve video information. Please enter a valid URL.")
    
    video_title = video_info.get('title', 'Unknown Title')
    print(f"Video Title: {video_title}")

    formats = downloader.list_formats(video_info)
    filtered_formats = downloader.filter_formats(formats)
    best_audio_format = downloader.best_audio_format(formats)

    if not filtered_formats and not best_audio_format:
        print("No valid formats found for the provided video. Please check the URL and try again.")
        return

    print("Available formats:")
    numbered_formats = []
    for i, f in enumerate(filtered_formats, start=1):
        resolution = f.get('resolution', 'unknown')
        print(f"{i}: {f['ext']} - {resolution}")
        numbered_formats.append((f['format_id'], f.get('height', 'audio')))

    if best_audio_format:
        i += 1
        print(f"{i}: {best_audio_format['ext']} - audio")
        numbered_formats.append((best_audio_format['format_id'], 'audio'))

    while True:
        try:
            format_number = int(input("Enter the number of the format you want to download: "))
            if format_number < 1 or format_number > len(numbered_formats):
                print(f"Invalid format selection. Please enter a number between 1 and {len(numbered_formats)}.")
            else:
                break
        except ValueError:
            print(f"Invalid input. Please enter a number between 1 and {len(numbered_formats)}.")

    selected_format_id, height = numbered_formats[format_number - 1]

    await asyncio.get_running_loop().run_in_executor(None, downloader.download_video, info, selected_format_id, height)

    if info.status == "finished":
        print(f"Download and move completed: {info.final_file}")
    else:
        print("Download failed.")

    downloader.cleanup_temp_dir()
    print("Temporary files cleared.")

def handle_exit(downloader):
    downloader.cleanup_temp_dir()
    print("Temporary files cleared.")

if __name__ == "__main__":
    download_dir = './temp'
    final_dir = './YouTube Videos'
    downloader = SimpleDownloader(download_dir, final_dir)

    signal.signal(signal.SIGINT, lambda s, f: handle_exit(downloader))
    signal.signal(signal.SIGTERM, lambda s, f: handle_exit(downloader))

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        handle_exit(downloader)
