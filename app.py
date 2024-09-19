import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import openai

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Try to import Pinecone, but continue if it's not available
try:
    import pinecone
    pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-east-1")
    index_name = "youtube-blog-index"
    index = pinecone.Index(index_name)
    st.success("Connected to Pinecone database successfully.")
    use_pinecone = True
except ImportError:
    st.warning("Pinecone library not found. Running without vector database functionality.")
    use_pinecone = False
except Exception as e:
    st.error(f"Failed to connect to Pinecone: {str(e)}")
    use_pinecone = False

# Function to get video details
def get_video_details(video_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request.execute()
        return response['items'][0]
    except HttpError as e:
        st.error(f"An error occurred while fetching video details: {e}")
        return None

# Function to get video transcript
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        st.warning(f"Transcript not available for video {video_id}. Using video description instead.")
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
        st.error(f"An error occurred while fetching comments: {e}")
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

# Function to store data in Pinecone (if available)
def store_in_pinecone(video_id, blog_content):
    if not use_pinecone:
        return
    try:
        vector = openai.Embedding.create(input=[blog_content], model="text-embedding-ada-002")["data"][0]["embedding"]
        index.upsert(vectors=[(video_id, vector, {"blog_content": blog_content})])
        st.success(f"Blog post for video {video_id} stored in Pinecone successfully.")
    except Exception as e:
        st.error(f"Failed to store blog post in Pinecone: {str(e)}")

# Function to generate a blog post for a single video
def generate_single_blog_post(video_id):
    video_details = get_video_details(video_id)
    if video_details:
        video_title = video_details['snippet']['title']
        video_description = video_details['snippet']['description']
        transcript = get_video_transcript(video_id)
        comments = get_video_comments(video_id)

        if transcript:
            content_for_summary = transcript
            summary_prompt = "Summarize this video transcript in a blog post format:"
        else:
            content_for_summary = f"Title: {video_title}\n\nDescription: {video_description}"
            summary_prompt = "Based on this video title and description, generate a blog post summary:"

        summary = process_with_openai(content_for_summary, summary_prompt)
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

            store_in_pinecone(video_id, blog_post)
            return blog_post
    
    return None

# Function to generate blog posts for a channel
def generate_channel_blog_posts(channel_id):
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
            blog_post = generate_single_blog_post(video_id)
            if blog_post:
                blog_posts.append((video_id, blog_post))

        return blog_posts
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        if error_details.get('reason') == 'accessNotConfigured':
            st.error("YouTube Data API v3 is not enabled for your project. Please follow these steps:")
            st.markdown("""
            1. Go to https://console.developers.google.com/
            2. Select your project from the top dropdown menu.
            3. In the left sidebar, click on "APIs & Services" > "Library"
            4. Search for "YouTube Data API v3"
            5. Click on the API and then click "Enable"
            6. Wait a few minutes for the changes to propagate.
            7. Try again.
            """)
        else:
            st.error(f"An error occurred while accessing the YouTube API: {str(e)}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

# Streamlit app
def main():
    st.title("Enhanced YouTube Blog Post Generator")

    # Set default YouTube Channel ID
    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    # Add input for single video ID
    video_id = st.text_input("Or enter a specific YouTube Video ID (optional)")

    if st.button("Generate Blog Post(s)"):
        if video_id:
            with st.spinner("Generating blog post... This may take a while."):
                blog_post = generate_single_blog_post(video_id)
            if blog_post:
                st.success("Blog post generated successfully!")
                st.markdown(blog_post)
            else:
                st.warning("Failed to generate blog post. Please check the video ID and try again.")
        elif channel_id:
            with st.spinner("Generating blog posts... This may take a while."):
                blog_posts = generate_channel_blog_posts(channel_id)
            
            if blog_posts:
                st.success(f"Generated {len(blog_posts)} blog posts!")
                for video_id, post in blog_posts:
                    with st.expander(f"Blog Post for Video {video_id}"):
                        st.markdown(post)
            else:
                st.warning("No blog posts were generated. Please check the error messages above and try again.")
        else:
            st.error("Please enter either a YouTube Channel ID or a specific Video ID.")

        if st.button("Generate Another"):
            st.experimental_rerun()

if __name__ == "__main__":
    main()
