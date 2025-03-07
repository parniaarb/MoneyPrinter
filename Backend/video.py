import os
import uuid
from datetime import timedelta

import requests
import srt_equalizer
import assemblyai as aai

from typing import List
from moviepy.editor import *
from termcolor import colored
from dotenv import load_dotenv
from moviepy.video.fx.all import crop
from moviepy.video.tools.subtitles import SubtitlesClip

load_dotenv("../.env")

ASSEMBLY_AI_API_KEY = os.getenv("ASSEMBLY_AI_API_KEY")


def save_video(video_url: str, directory: str = "../temp") -> str:
    """
    Saves a video from a given URL and returns the path to the video.

    Args:
        video_url (str): The URL of the video to save.

    Returns:
        str: The path to the saved video.
    """
    video_id = uuid.uuid4()
    video_path = f"{directory}/{video_id}.mp4"
    with open(video_path, "wb") as f:
        f.write(requests.get(video_url).content)

    return video_path


def __generate_subtitles_assemblyai(audio_path: str) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        audio_path (str): The path to the audio file to generate subtitles from.

    Returns:
        str: The generated subtitles
    """

    aai.settings.api_key = ASSEMBLY_AI_API_KEY
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)
    subtitles = transcript.export_subtitles_srt()

    return subtitles


def __generate_subtitles_locally(sentences: list[str], audio_clips: list[AudioFileClip]) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        sentences (list[str]): all the sentences said out loud in the audio clips
        audio_clips (list[AudioFileClip]): all the individual audio clips which will make up the final audio track
    Returns:
        str: The generated subtitles
    """

    def convert_to_srt_time_format(total_seconds):
        # Convert total seconds to the SRT time format: HH:MM:SS,mmm
        if total_seconds == 0:
            return "0:00:00,0"
        return str(timedelta(seconds=total_seconds))[:-3].replace('.', ',')

    start_time = 0
    subtitles = []

    for i, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips), start=1):
        duration = audio_clip.duration
        end_time = start_time + duration

        # Format: subtitle index, start time --> end time, sentence
        subtitle_entry = f"{i}\n{convert_to_srt_time_format(start_time)} --> {convert_to_srt_time_format(end_time)}\n{sentence}\n"
        subtitles.append(subtitle_entry)

        start_time += duration  # Update start time for the next subtitle

    return "\n".join(subtitles)


def generate_subtitles(audio_path: str, sentences: list[str], audio_clips: list[AudioFileClip]) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        audio_path (str): The path to the audio file to generate subtitles from.
        sentences (list[str]): all the sentences said out loud in the audio clips
        audio_clips (list[AudioFileClip]): all the individual audio clips which will make up the final audio track

    Returns:
        str: The path to the generated subtitles.
    """

    def equalize_subtitles(srt_path: str, max_chars: int = 10) -> None:
        # Equalize subtitles
        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    # Save subtitles
    subtitles_path = f"../subtitles/{uuid.uuid4()}.srt"

    if ASSEMBLY_AI_API_KEY is not None and ASSEMBLY_AI_API_KEY != "":
        print(colored("[+] Creating subtitles with assembly ai", "blue"))
        subtitles = __generate_subtitles_assemblyai(audio_path)
    else:
        print(colored("[+] Creating subtitles locally", "blue"))
        subtitles = __generate_subtitles_locally(sentences, audio_clips)

    with open(subtitles_path, "w") as file:
        file.write(subtitles)

    # Equalize subtitles
    equalize_subtitles(subtitles_path)

    print(colored("[+] Subtitles generated.", "green"))

    return subtitles_path


def combine_videos(video_paths: List[str], max_duration: int) -> str:
    """
    Combines a list of videos into one video and returns the path to the combined video.

    Args:
        video_paths (list): A list of paths to the videos to combine.
        max_duration (int): The maximum duration of the combined video.

    Returns:
        str: The path to the combined video.
    """
    video_id = uuid.uuid4()
    combined_video_path = f"../temp/{video_id}.mp4"

    print(colored("[+] Combining videos...", "blue"))
    print(colored(f"[+] Each video will be {max_duration / len(video_paths)} seconds long.", "blue"))

    clips = []
    for video_path in video_paths:
        clip = VideoFileClip(video_path)
        clip = clip.without_audio()
        clip = clip.subclip(0, max_duration / len(video_paths))
        clip = clip.set_fps(30)

        # Not all videos are same size,
        # so we need to resize them
        clip = crop(clip, width=1080, height=1920, \
                    x_center=clip.w / 2, \
                    y_center=clip.h / 2)
        clip = clip.resize((1080, 1920))

        clips.append(clip)

    final_clip = concatenate_videoclips(clips)
    final_clip = final_clip.set_fps(30)
    final_clip.write_videofile(combined_video_path, threads=3)

    return combined_video_path


def generate_video(combined_video_path: str, tts_path: str, subtitles_path: str) -> str:
    """
    This function creates the final video, with subtitles and audio.

    Args:
        combined_video_path (str): The path to the combined video.
        tts_path (str): The path to the text-to-speech audio.
        subtitles_path (str): The path to the subtitles.

    Returns:
        str: The path to the final video.
    """
    # Make a generator that returns a TextClip when called with consecutive
    generator = lambda txt: TextClip(
        txt,
        font="../fonts/bold_font.ttf",
        fontsize=100,
        color="#FFFF00",
        stroke_color="black",
        stroke_width=5,
    )

    # Burn the subtitles into the video
    subtitles = SubtitlesClip(subtitles_path, generator)
    result = CompositeVideoClip([
        VideoFileClip(combined_video_path),
        subtitles.set_pos(("center", "center"))
    ])

    # Add the audio
    audio = AudioFileClip(tts_path)
    result = result.set_audio(audio)

    result.write_videofile("../temp/output.mp4", threads=3)

    return "output.mp4"
