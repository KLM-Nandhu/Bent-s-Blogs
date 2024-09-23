import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import openai
from typing import List, Dict

# Use Streamlit secrets for the OpenAI API key
openai.api_key = st.secrets["openai_api_key"]

def get_video_info(video_id: str) -> tuple:
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url)
        return yt.title, yt.thumbnail_url, yt.length
    except Exception as e:
        return f"An error occurred while fetching video info: {str(e)}", None, None

def get_video_transcript_with_timestamps(video_id: str) -> List[Dict]:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        return f"An error occurred while fetching the transcript: {str(e)}"

def format_time(seconds: float) -> str:
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def process_transcript_chunk(chunk: str, video_id: str) -> str:
    prompt = f"""This is a portion of a video transcript. Please organize this content into the following structure:

For each distinct topic or section, include:
Product name (if applicable):
Starting timestamp:
Ending Timestamp:
Transcript:

The goal is to not summarize or alter any information, but just reorganize the existing transcript into this structure. Use the provided timestamps to determine the start and end times for each section.

Here's the transcript chunk:
{chunk}

Please format the response as follows:

[Organized content here]
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that organizes video transcripts without altering their content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred while processing with GPT-4: {str(e)}"

def process_full_transcript(transcript: List[Dict], video_id: str) -> str:
    chunk_size = 10000  # Adjust this value based on your needs
    full_transcript = " ".join([f"{format_time(entry['start'])}: {entry['text']}" for entry in transcript])
    chunks = [full_transcript[i:i+chunk_size] for i in range(0, len(full_transcript), chunk_size)]
    
    processed_chunks = []
    for chunk in chunks:
        processed_chunk = process_transcript_chunk(chunk, video_id)
        processed_chunks.append(processed_chunk)
    
    return "\n\n".join(processed_chunks)

st.title("YouTube Transcript Processor")

video_id = st.text_input("Enter YouTube Video ID")

if st.button("Process Transcript"):
    if video_id:
        with st.spinner("Processing transcript..."):
            title, thumbnail_url, video_length = get_video_info(video_id)
            if thumbnail_url:
                st.image(thumbnail_url, caption=title)
                transcript = get_video_transcript_with_timestamps(video_id)
                if isinstance(transcript, list):
                    processed_transcript = process_full_transcript(transcript, video_id)
                    st.text_area("Processed Transcript:", processed_transcript, height=500)
                else:
                    st.error(transcript)
            else:
                st.error(title)
    else:
        st.error("Please enter a YouTube Video ID.")
