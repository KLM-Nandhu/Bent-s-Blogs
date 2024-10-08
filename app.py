from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
# from fastapi.staticfiles import StaticFiles
from youtube_transcript_api import YouTubeTranscriptApi
import openai
from typing import List, Dict
import asyncio
import requests
from io import BytesIO
from datetime import datetime
import base64
from googleapiclient.discovery import build
import re
import os

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Set your API keys here
openai_api_key = os.environ.get("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def get_video_info(video_id: str) -> Dict:
    try:
        response = youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=video_id
        ).execute()

        video_data = response['items'][0]
        return {
            'id': video_id,
            'title': video_data['snippet']['title'],
            'description': video_data['snippet']['description'],
            'thumbnail_url': video_data['snippet']['thumbnails']['high']['url'],
            'view_count': video_data['statistics']['viewCount'],
            'like_count': video_data['statistics']['likeCount'],
            'duration': video_data['contentDetails']['duration'],
            'published_at': video_data['snippet']['publishedAt']
        }
    except Exception as e:
        return f"An error occurred while fetching video info: {str(e)}"

def get_all_comments(video_id: str) -> List[Dict]:
    try:
        comments = []
        nextPageToken = None
        while True:
            response = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=100,
                pageToken=nextPageToken,
                order='time'
            ).execute()

            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment['authorDisplayName'],
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'published_at': comment['publishedAt']
                })

            nextPageToken = response.get('nextPageToken')
            if not nextPageToken:
                break

        return comments
    except Exception as e:
        return f"An error occurred while fetching comments: {str(e)}"

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

async def process_transcript_chunk(chunk: str, video_id: str) -> str:
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
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that organizes video transcripts without altering their content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred while processing with GPT-4: {str(e)}"

async def process_full_transcript(transcript: List[Dict], video_id: str) -> str:
    chunk_size = 10000  # Adjust this value based on your needs
    full_transcript = " ".join([f"{format_time(entry['start'])}: {entry['text']}" for entry in transcript])
    chunks = [full_transcript[i:i+chunk_size] for i in range(0, len(full_transcript), chunk_size)]
    
    processed_chunks = []
    for chunk in chunks:
        processed_chunk = await process_transcript_chunk(chunk, video_id)
        processed_chunks.append(processed_chunk)
    
    return "\n\n".join(processed_chunks)

async def generate_blog_post(processed_transcript: str, video_info: Dict) -> str:
    prompt = f"""Based on the following processed transcript and video information, create a comprehensive blog post. The blog post should include:

1. Title
2. Introduction
3. Main content with subheadings (including timestamps)
4. Key moments
5. Conclusion
6. Product links (if any mentioned in the video)
7. Affiliate information (if provided)
8. Camera and audio equipment used (if mentioned)

Video Title: {video_info['title']}
Video Description: {video_info['description']}

Processed Transcript:
{processed_transcript}

Please format the blog post accordingly, ensuring all relevant information from the video description is included. Include product links within the main content where relevant.
"""

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates detailed blog posts from video transcripts and information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred while generating the blog post: {str(e)}"

def get_image_html(img_url: str, alt_text: str) -> str:
    return f'<img src="{img_url}" alt="{alt_text}" class="blog-image"/>'

def make_links_clickable(text: str) -> str:
    return re.sub(r'(https?://\S+)', r'<a href="\1" target="_blank">\1</a>', text)

def format_blog_post(blog_post: str, video_info: Dict) -> str:
    lines = blog_post.split('\n')
    formatted_post = f"<h1>{video_info['title']}</h1>"
    formatted_post += f"<div class='blog-meta'>Published on {video_info['published_at']} | {video_info['view_count']} views | {video_info['like_count']} likes</div>"
    formatted_post += get_image_html(video_info['thumbnail_url'], video_info['title'])
    
    for line in lines:
        if line.startswith('Title:'):
            continue  # Skip the title as we've already added it
        elif line.lower().startswith(('introduction', 'conclusion')):
            formatted_post += f"<h2><strong>{line}</strong></h2>"
        elif line.startswith(('###', '##')):
            formatted_post += f"<h3><strong>{line.strip('#').strip()}</strong></h3>"
        elif re.match(r'\d{2}:\d{2}:\d{2}', line):  # Check for timestamp
            timestamp = sum(int(x) * 60 ** i for i, x in enumerate(reversed(line.split(':')[:3])))
            thumbnail_url = f"https://img.youtube.com/vi/{video_info['id']}/{int(timestamp/10)}.jpg"
            formatted_post += f'<img src="{thumbnail_url}" alt="Video thumbnail at {line}" style="width: 320px; height: 180px; object-fit: cover;">'
            formatted_post += f"<p>{make_links_clickable(line)}</p>"
        elif line.strip() == '':
            formatted_post += "<br>"
        else:
            formatted_post += f"<p>{make_links_clickable(line)}</p>"
    
    return formatted_post

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process", response_class=HTMLResponse)
async def process_video(request: Request, video_id: str = Form(...)):
    video_info = get_video_info(video_id)
    if isinstance(video_info, dict):
        transcript = get_video_transcript_with_timestamps(video_id)
        comments = get_all_comments(video_id)
        if isinstance(transcript, list) and isinstance(comments, list):
            processed_transcript = await process_full_transcript(transcript, video_id)
            blog_post = await generate_blog_post(processed_transcript, video_info)
            formatted_blog_post = format_blog_post(blog_post, video_info)
            
            return templates.TemplateResponse("result.html", {
                "request": request,
                "blog_post": formatted_blog_post,
                "comments": comments,
                "video_info": video_info
            })
        else:
            error = transcript if isinstance(transcript, str) else comments
            return templates.TemplateResponse("error.html", {"request": request, "error": error})
    else:
        return templates.TemplateResponse("error.html", {"request": request, "error": video_info})
