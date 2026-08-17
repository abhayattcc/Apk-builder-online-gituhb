import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.utils import platform

# Android storage permissions
if platform == "android":
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET])

import yt_dlp

class DownloaderApp(App):
    def build(self):
        self.title = "TG Video Downloader"
        
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        # Header
        self.header = Label(
            text="Telegram Video Downloader", 
            font_size="22sp", 
            size_hint_y=None, 
            height=50,
            bold=True
        )
        layout.add_widget(self.header)
        
        # Input Box
        self.url_input = TextInput(
            hint_text="Paste public Telegram post URL (e.g., https://t.me/...)",
            multiline=False,
            size_hint_y=None,
            height=60,
            font_size="16sp"
        )
        layout.add_widget(self.url_input)
        
        # Download Button
        self.download_btn = Button(
            text="Download Video",
            size_hint_y=None,
            height=60,
            background_color=(0.1, 0.6, 0.9, 1),
            font_size="18sp",
            bold=True
        )
        self.download_btn.bind(on_press=self.start_download_thread)
        layout.add_widget(self.download_btn)
        
        # Status Label
        self.status_label = Label(
            text="Ready", 
            font_size="14sp",
            size_hint_y=None,
            height=40
        )
        layout.add_widget(self.status_label)
        
        return layout

    def start_download_thread(self, instance):
        url = self.url_input.text.strip()
        if not url:
            self.status_label.text = "Please enter a valid Telegram link."
            return

        self.download_btn.disabled = True
        self.status_label.text = "Fetching and downloading..."
        
        # Run download in a background thread to prevent UI freezing
        threading.Thread(target=self.download_video, args=(url,), daemon=True).start()

    def download_video(self, url):
        try:
            # Determine download path on Android / Desktop
            if platform == "android":
                from android.storage import primary_external_storage_path
                download_dir = os.path.join(primary_external_storage_path(), "Download")
            else:
                download_dir = os.path.expanduser("~/Downloads")

            os.makedirs(download_dir, exist_ok=True)
            output_template = os.path.join(download_dir, "%(title)s.%(ext)s")

            ydl_opts = {
                'outtmpl': output_template,
                'format': 'bestvideo+bestaudio/best',
                'quiet': True,
                'no_warnings': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.status_label.text = "Download Complete! Saved to Downloads folder."
        except Exception as e:
            self.status_label.text = f"Error: {str(e)[:60]}..."
        finally:
            self.download_btn.disabled = False

if __name__ == "__main__":
    DownloaderApp().run()
