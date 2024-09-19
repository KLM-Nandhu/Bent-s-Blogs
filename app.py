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

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone
try:
    pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment="us-east-1-aws")
    index_name = "youtube-blog-index"
    index = pinecone.Index(index_name)
    st.success("Connected to Pinecone database successfully.")
except Exception as e:
    st.error(f"Failed to connect to Pinecone: {str(e)}")
    index = None

# Function to get video details
def get_video_details(api_key, video_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
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
def get_video_comments(api_key, video_id, max_results=10):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
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
        st.success("Blog post stored in Pinecone successfully.")
    except Exception as e:
        st.error(f"Failed to store blog post in Pinecone: {str(e)}")

# Function to retrieve data from Pinecone
def retrieve_from_pinecone(video_id):
    if index is None:
        st.warning("Pinecone connection not available. Cannot retrieve blog post.")
        return None
    try:
        result = index.fetch(ids=[video_id])
        if result and video_id in result['vectors']:
            st.success("Blog post retrieved from Pinecone successfully.")
            return result['vectors'][video_id]['metadata']['blog_content']
        else:
            st.info("No existing blog post found in Pinecone for this video.")
            return None
    except Exception as e:
        st.error(f"Failed to retrieve blog post from Pinecone: {str(e)}")
        return None

# Streamlit app
def main():
    st.title("Enhanced YouTube Blog Post Generator")

    # Input for YouTube API Key
    youtube_api_key = st.text_input("Enter your YouTube API Key", type="password")

    # Set default YouTube Channel ID
    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    if youtube_api_key and channel_id:
        try:
            # Fetch videos from the channel
            youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=youtube_api_key)
            request = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=50
            )
            response = request.execute()

            # Display videos and generate blog posts
            for item in response['items']:
                video_id = item['id']['videoId']
                video_title = item['snippet']['title']
                
                if st.button(f"Generate Blog Post for: {video_title}"):
                    # Check if blog post already exists in Pinecone
                    existing_blog = retrieve_from_pinecone(video_id)
                    if existing_blog:
                        st.subheader("Retrieved Existing Blog Post")
                        st.write(existing_blog)
                    else:
                        video_details = get_video_details(youtube_api_key, video_id)
                        if video_details:
                            transcript = get_video_transcript(video_id)
                            comments = get_video_comments(youtube_api_key, video_id)

                            if transcript and comments:
                                # Process content with OpenAI
                                summary = process_with_openai(transcript, "Summarize this video transcript in a blog post format:")
                                enhanced_comments = process_with_openai('\n'.join(comments), "Highlight and analyze the most interesting points from these comments:")

                                if summary and enhanced_comments:
                                    # Generate blog post
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

                                    # Store in Pinecone
                                    store_in_pinecone(video_id, blog_post)

                                    st.subheader("Generated Blog Post")
                                    st.write(blog_post)
                                else:
                                    st.error("Failed to generate blog post content.")
                            else:
                                st.error("Failed to fetch video transcript or comments.")
                        else:
                            st.error("Failed to fetch video details.")

        except HttpError as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
