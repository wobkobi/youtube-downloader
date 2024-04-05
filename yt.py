import os
import re
import subprocess
from pytube import YouTube, Playlist
from collections import defaultdict


class YouTubeDownloader:
    def __init__(self, url):
        self.url = url
        # Set up the base path to include a "youtube videos" subfolder
        self.base_path = os.path.join(os.getcwd(), "youtube videos")
        # Ensure the "youtube videos" folder exists
        os.makedirs(self.base_path, exist_ok=True)

    def on_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage_of_completion = bytes_downloaded / total_size * 100
        print(f"Downloading: {percentage_of_completion:.2f}%", end="\r")

    def list_qualities(self, yt):
        all_streams = list(yt.streams.filter(progressive=True)) + list(
            yt.streams.filter(adaptive=True)
        )

        # Store qualities, initially preferring MP4
        qualities = {}
        for stream in all_streams:
            if stream.resolution:
                # Prioritize adding or updating the entry if the format is MP4
                if stream.mime_type == "video/mp4":
                    qualities[stream.resolution] = {
                        "resolution": stream.resolution,
                        "format": "mp4",
                    }
                elif stream.mime_type == "video/webm":
                    # Add WEBM only if there's no MP4 version or if the WEBM resolution is higher than any MP4
                    if (stream.resolution not in qualities) or (
                        int(stream.resolution[:-1])
                        > int(qualities[stream.resolution]["resolution"][:-1])
                    ):
                        qualities[stream.resolution] = {
                            "resolution": stream.resolution,
                            "format": "webm",
                        }

        # Convert the qualities dict to a sorted list of strings, ensuring highest resolutions are listed first
        sorted_qualities_list = sorted(
            [f"{key} ({value['format']})" for key, value in qualities.items()],
            key=lambda x: int(x.split(" ")[0][:-1]),
            reverse=True,
        )
        return sorted_qualities_list

    def sanitize_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    def is_gpu_available(self):
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
            )
            return "h264_nvenc" in result.stdout or "h264_vaapi" in result.stdout
        except Exception as e:
            print(f"Error checking GPU availability: {e}")
            return False

    def download_video(self, video_url, path, selected_quality):
        yt = YouTube(video_url)

        # Immediately download the highest resolution if 'auto' is selected
        if selected_quality == "auto":
            video_stream = yt.streams.get_highest_resolution()
        else:
            resolution, format_ = (
                selected_quality.split(" ")[0],
                selected_quality.split(" ")[1][1:-1],
            )
            video_stream = yt.streams.filter(
                res=resolution, mime_type=f"video/{format_}"
            ).first()

        if not video_stream:
            print(f"No video stream found for {selected_quality}")
            return

        # Proceed to download the video
        final_filename = (
            f"{self.sanitize_filename(yt.title)}.{video_stream.mime_type.split('/')[1]}"
        )
        print(f"{yt.title} is now downloading...")
        video_stream.download(output_path=path, filename=final_filename)
        print(f"Download completed: {final_filename}")

    def handle_playlist(self, playlist_url, resolution="auto"):
        # Adjustments for handling playlist downloads
        playlist = Playlist(playlist_url)
        playlist_title = self.sanitize_filename(playlist.title)
        # Create a subfolder within "youtube videos" specifically for this playlist
        playlist_path = os.path.join(self.base_path, playlist_title)
        os.makedirs(playlist_path, exist_ok=True)
        for video_url in playlist.video_urls:
            self.download_video(video_url, playlist_path, resolution)

    def prompt_for_quality(self, yt):
        print("Loading available qualities...")
        qualities = self.list_qualities(yt)
        print("Available qualities:")
        for i, quality in enumerate(qualities, start=1):
            print(f"{i}. {quality}")
        print(f"{len(qualities)+1}. Auto (best available)")

        while True:
            choice = input("Select the desired quality: ").strip()
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(qualities) + 1:
                    if choice_num == len(qualities) + 1:
                        selected_quality = "auto"
                        highest_quality = qualities[0].split(" ")[
                            0
                        ]  # Assuming highest quality is first
                        print(f"Auto selected: {highest_quality}")
                    else:
                        selected_quality = qualities[choice_num - 1]
                        print(f"Selected quality: {selected_quality}")
                    return selected_quality
                else:
                    print("Invalid selection. Please choose a valid option.")
            except ValueError:
                print("Please enter a number corresponding to your choice.")

    def is_valid_youtube_url(self, url):
        # Regular expression for validating a YouTube URL
        youtube_regex = (
            r"(https?://)?(www\.)?"
            "(youtube|youtu|youtube-nocookie)\.(com|be)/"
            "(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        return re.match(youtube_regex, url) is not None

    def run(self):
        print("Processing your request...")
        if not self.is_valid_youtube_url(self.url):
            print(
                "The provided input is not a valid YouTube URL. Please try again with a valid link."
            )
            return

        yt = YouTube(self.url)
        selected_quality = self.prompt_for_quality(yt)

        if "playlist?list=" in self.url:
            print(f"playlist download started...")
            self.handle_playlist(self.url, selected_quality)
        else:
            video_title = self.sanitize_filename(yt.title)
            video_path = os.path.join(self.base_path, video_title)
            os.makedirs(video_path, exist_ok=True)
            self.download_video(self.url, video_path, selected_quality)


# The example usage remains unchanged
if __name__ == "__main__":
    url_input = input("Enter the YouTube video or playlist URL: ")
    downloader = YouTubeDownloader(url_input)
    downloader.run()
