import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import pinecone

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone
try:
    pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-east-1")
    index_name = "youtube-blog-index"
    index = pinecone.Index(index_name)
    st.success("Connected to Pinecone database successfully.")
except Exception as e:
    st.error(f"Failed to connect to Pinecone: {str(e)}")
    index = None

# Function to get video details
def get_video_details(video_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request.execute()
        return response['items'][0]
    except HttpError as e:
        st.error(f"An error occurred: {e}")
        return None

# Function to get video transcript
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

# Function to get video comments
def get_video_comments(video_id, max_results=10):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results
        )
        response = request.execute()
        return [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in response['items']]
    except HttpError as e:
        st.error(f"An error occurred: {e}")
        return []

# Function to process content with OpenAI
def process_with_openai(content, prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error processing with OpenAI: {str(e)}")
        return None

# Function to store data in Pinecone
def store_in_pinecone(video_id, blog_content):
    if index is None:
        st.warning("Pinecone connection not available. Blog post will not be stored.")
        return
    try:
        vector = openai.Embedding.create(input=[blog_content], model="text-embedding-ada-002")["data"][0]["embedding"]
        index.upsert(vectors=[(video_id, vector, {"blog_content": blog_content})])
        st.success(f"Blog post for video {video_id} stored in Pinecone successfully.")
    except Exception as e:
        st.error(f"Failed to store blog post in Pinecone: {str(e)}")

# Function to generate blog posts
def generate_blog_posts(channel_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            order="date",
            maxResults=50
        )
        response = request.execute()

        blog_posts = []

        for item in response['items']:
            video_id = item['id']['videoId']
            video_title = item['snippet']['title']

            video_details = get_video_details(video_id)
            if video_details:
                transcript = get_video_transcript(video_id)
                comments = get_video_comments(video_id)

                if transcript and comments:
                    summary = process_with_openai(transcript, "Summarize this video transcript in a blog post format:")
                    enhanced_comments = process_with_openai('\n'.join(comments), "Highlight and analyze the most interesting points from these comments:")

                    if summary and enhanced_comments:
                        blog_post = f"""
                        # {video_title}

                        Video URL: https://www.youtube.com/watch?v={video_id}
                        Views: {video_details['statistics']['viewCount']}
                        Likes: {video_details['statistics']['likeCount']}

                        ## Summary
                        {summary}

                        ## Highlighted Comments Analysis
                        {enhanced_comments}
                        """

                        blog_posts.append((video_id, blog_post))
                        store_in_pinecone(video_id, blog_post)

        return blog_posts
    except HttpError as e:
        st.error(f"An error occurred: {e}")
        return []

# Streamlit app
def main():
    st.title("Enhanced YouTube Blog Post Generator")

    # Set default YouTube Channel ID
    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    if st.button("Generate Blog Posts"):
        if channel_id:
            with st.spinner("Generating blog posts... This may take a while."):
                blog_posts = generate_blog_posts(channel_id)
            
            if blog_posts:
                st.success(f"Generated {len(blog_posts)} blog posts!")
                for video_id, post in blog_posts:
                    with st.expander(f"Blog Post for Video {video_id}"):
                        st.markdown(post)
            else:
                st.warning("No blog posts were generated. Please check the channel ID and try again.")
        else:
            st.error("Please enter a YouTube Channel ID.")

if __name__ == "__main__":
    main()
