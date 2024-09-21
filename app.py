import streamlit as st
import openai
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import re
import requests

# Set up API clients
openai.api_key = st.secrets["OPENAI_API_KEY"]
youtube = build("youtube", "v3", developerKey=st.secrets["YOUTUBE_API_KEY"])

def get_video_info(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url)
        if response.status_code != 200:
            return None, None, None

        html_content = response.text

        # Extract title
        title_match = re.search(r'<meta name="title" content="(.*?)"', html_content)
        title = title_match.group(1) if title_match else "Unknown Title"

        # Extract description
        description_match = re.search(r'<meta name="description" content="(.*?)"', html_content)
        description = description_match.group(1) if description_match else "No description available"

        # Extract thumbnail URL
        thumbnail_match = re.search(r'<meta property="og:image" content="(.*?)"', html_content)
        thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None

        return title, description, thumbnail_url
    except Exception as e:
        st.error(f"Error fetching video info: {str(e)}")
        return None, None, None

def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

def organize_transcript(transcript):
    prompt = """
    This document contains a video transcript. The problem with this document is that the time stamps are in between the content of the transcript. Can you help me organize this content into the following fields:
    Product name:
    Starting timestamp:
    Ending Timestamp:
    Transcript:
    The goal is to not summarize any information but just reorganize into this. For the beginning and ending part of the transcript, you can just categorize it as Intro and Outro where the speech is not specific to any product.
    
    Transcript:
    """
    prompt += str(transcript)

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that organizes video transcripts."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def generate_blog_post(transcript, title, description):
    prompt = f"""
    Write a blog post targeting 65-year-old people who like woodworking as a hobby and have expendable income. The blog post should genuinely show interest in educating the audience while improving SEO performance to gain more visibility in general.

    Use the following video transcript to create the blog post:
    Title: {title}
    Description: {description}
    Transcript: {transcript}

    The blog post should:
    1. Have an engaging introduction
    2. Be divided into 3-5 main sections with clear, descriptive headings
    3. Include specific, actionable tips for woodworking enthusiasts
    4. Explain any technical terms in a clear, easy-to-understand manner
    5. Incorporate relevant keywords for SEO without compromising readability
    6. Have a conclusion summarizing key points and encouraging engagement
    7. Be written in a friendly, conversational tone that resonates with older adults
    8. Address common challenges or questions that older woodworking enthusiasts might have
    9. Suggest tools or products mentioned in the video (if any)

    Format the blog post in Markdown, using appropriate headings, bullet points, and emphasis where necessary.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a skilled woodworking blogger and SEO expert."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def get_comments(video_id):
    try:
        comments = []
        next_page_token = None
        while len(comments) < 50:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(50 - len(comments), 100),
                pageToken=next_page_token
            ).execute()
            
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment['authorDisplayName'],
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'published_at': comment['publishedAt']
                })
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        return comments
    except Exception as e:
        st.error(f"Error fetching comments: {str(e)}")
        return []

def main():
    st.title("Woodworking Blog Generator")

    video_id = st.text_input("Enter YouTube Video ID")

    if video_id:
        title, description, thumbnail_url = get_video_info(video_id)
        
        if title and description and thumbnail_url:
            st.image(thumbnail_url, use_column_width=True)
            st.subheader(title)
            
            transcript = get_video_transcript(video_id)
            
            if transcript:
                organized_transcript = organize_transcript(transcript)
                
                if st.button("Show Transcript"):
                    st.text_area("Organized Transcript", organized_transcript, height=300)
                
                blog_post = generate_blog_post(organized_transcript, title, description)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("Blog Post")
                    sections = re.split(r'#{1,2}\s', blog_post)
                    for i, section in enumerate(sections):
                        if i == 0:  # This is the introduction
                            st.markdown(section)
                        else:
                            title, content = section.split('\n', 1)
                            with st.expander(title.strip()):
                                st.markdown(content.strip())
                
                with col2:
                    st.subheader("Product Links")
                    products = re.findall(r'([\w\s]+):\s*(https?://\S+)', description)
                    for product, url in products:
                        st.markdown(f"[{product}]({url})")
                    
                    st.subheader("Comments")
                    comments = get_comments(video_id)
                    comment_count = 0
                    for comment in comments[:10]:
                        st.text(f"{comment['author']}: {comment['text'][:100]}...")
                        comment_count += 1
                    
                    if len(comments) > 10:
                        if st.button("Load More Comments"):
                            for comment in comments[10:]:
                                st.text(f"{comment['author']}: {comment['text'][:100]}...")
                                comment_count += 1
                                if comment_count >= 50:
                                    break
        else:
            st.error("Failed to fetch video information. Please check the video ID and try again.")

if __name__ == "__main__":
    main()
