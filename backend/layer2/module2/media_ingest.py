import os
import subprocess
import shutil

class MediaIngestor:
    def __init__(self, upload_dir="layer2/module2/uploads"):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def process_upload(self, file_path: str) -> dict:
        """
        Takes an uploaded video file, splits the audio and video streams using FFmpeg.
        Returns the paths to the isolated video and audio files.
        """
        filename = os.path.basename(file_path)
        base_name = os.path.splitext(filename)[0]
        
        # We no longer split the video, we just pass the original path to the vision processor.
        # But we still extract the audio.
        audio_only_path = os.path.join(self.upload_dir, f"{base_name}_audio.wav")
        
        # Probe for video stream
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", 
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", file_path
        ]
        
        # Split Audio Stream (Strip video, convert to 16kHz for RawNet2)
        audio_cmd = [
            "ffmpeg", "-y", "-i", file_path, 
            "-q:a", "0", "-map", "a", 
            "-ac", "1", "-ar", "16000", audio_only_path
        ]
        
        try:
            output = subprocess.check_output(probe_cmd, stderr=subprocess.DEVNULL).decode().strip()
            has_video = (output == "video")
            video_only_path = file_path if has_video else None
        except (subprocess.CalledProcessError, FileNotFoundError):
            has_video = False
            video_only_path = None
            
        try:
            subprocess.run(audio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            has_audio = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            has_audio = False
            audio_only_path = None
            
        return {
            "original": file_path,
            "video_only": video_only_path,
            "audio_only": audio_only_path,
            "has_video": has_video,
            "has_audio": has_audio
        }
