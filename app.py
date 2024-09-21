import streamlit as st
import googleapiclient.discovery
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from PIL import Image
import requests
from io import BytesIO

# Set up API clients
openai.api_key = st.secrets["OPENAI_API_KEY"]
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=st.secrets["YOUTUBE_API_KEY"])

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

def process_transcript(transcript):
    prompt = """
    This document contains a video transcript. The problem with this document is that the time stamps are in between the content of the transcript. Can you help me organize this content into the following fields:
    Product name:
    Starting timestamp:
    Ending Timestamp:
    Transcript:
    The goal is to not summarize any information but just reorganize into this. For the beginning and ending part of the transcript, you can just categorize it as Intro and Outro where the speech is not specific to any product.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that organizes video transcripts."},
            {"role": "user", "content": f"{prompt}\n\nTranscript: {transcript}"}
        ]
    )
    return response.choices[0].message['content']

def generate_blog_post(transcript):
    prompt = """
    Generate a blog post for a woodworking YouTube channel. The target audience is 65-year-old people who enjoy woodworking as a hobby and have expendable income. The blog post should:
    1. Show genuine interest in educating the audience
    2. Improve SEO performance to gain more visibility
    3. Be organized into sections with headings
    4. Have crisp, engaging sentences
    5. Include relevant product recommendations with URLs (if applicable)
    6. Conclude with a summary of the content

    Use the following transcript to create the blog post:
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a skilled woodworking blogger and SEO expert."},
            {"role": "user", "content": f"{prompt}\n\nTranscript: {transcript}"}
        ]
    )
    return response.choices[0].message['content']

def get_video_details(video_id):
    try:
        response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if 'items' in response:
            video = response['items'][0]
            return {
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'thumbnail': video['snippet']['thumbnails']['high']['url'],
                'view_count': video['statistics']['viewCount'],
                'like_count': video['statistics']['likeCount'],
                'comment_count': video['statistics']['commentCount']
            }
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching video details: {str(e)}")
        return None

def get_comments(video_id, page_token=None):
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=10,
            pageToken=page_token
        ).execute()

        comments = []
        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'author': comment['authorDisplayName'],
                'text': comment['textDisplay'],
                'likes': comment['likeCount'],
                'published_at': comment['publishedAt']
            })

        next_page_token = response.get('nextPageToken')
        return comments, next_page_token
    except Exception as e:
        st.error(f"Error fetching comments: {str(e)}")
        return [], None

def main():
    st.title("Woodworking Blog Generator")

    video_id = st.text_input("Enter YouTube Video ID")

    if st.button("Generate Blog Post"):
        if video_id:
            with st.spinner("Fetching video details..."):
                video_details = get_video_details(video_id)

            if video_details:
                st.subheader(video_details['title'])
                col1, col2 = st.columns(2)
                with col1:
                    st.image(video_details['thumbnail'], use_column_width=True)
                with col2:
                    st.write(f"Views: {video_details['view_count']}")
                    st.write(f"Likes: {video_details['like_count']}")
                    st.write(f"Comments: {video_details['comment_count']}")

                with st.spinner("Fetching and processing transcript..."):
                    transcript = get_transcript(video_id)
                    if transcript:
                        processed_transcript = process_transcript(transcript)
                        if st.button("Show Transcript"):
                            st.text_area("Processed Transcript", processed_transcript, height=300)

                        with st.spinner("Generating blog post..."):
                            blog_post = generate_blog_post(processed_transcript)
                            sections = re.split(r'\n#+\s', blog_post)
                            
                            for i, section in enumerate(sections):
                                if i == 0:  # This is the introduction
                                    st.markdown(section)
                                else:
                                    title, content = section.split('\n', 1)
                                    with st.expander(title.strip()):
                                        st.markdown(content.strip())

                        st.subheader("Product Recommendations")
                        products = re.findall(r'([\w\s]+):\s*(https?://\S+)', video_details['description'])
                        for product, url in products:
                            st.markdown(f"[{product}]({url})")

                        st.subheader("Comments")
                        comments, next_page_token = get_comments(video_id)
                        for comment in comments:
                            st.text(f"{comment['author']}: {comment['text']}")
                        
                        if next_page_token:
                            if st.button("Load More Comments"):
                                more_comments, _ = get_comments(video_id, next_page_token)
                                for comment in more_comments:
                                    st.text(f"{comment['author']}: {comment['text']}")

            else:
                st.error("Failed to fetch video details. Please check the video ID and try again.")
        else:
            st.warning("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
