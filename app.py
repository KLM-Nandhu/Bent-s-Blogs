import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import pinecone

# Load environment variables
load_dotenv()

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone (Serverless)
pinecone.init(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "youtube-blog-index"
if index_name not in pinecone.list_indexes():
    pinecone.create_index(index_name, dimension=1536)  # OpenAI embeddings are 1536 dimensions
index = pinecone.Index(index_name)

# Function to get video details
def get_video_details(api_key, video_id):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    request = youtube.videos().list(part="snippet,statistics", id=video_id)
    response = request.execute()
    return response['items'][0]

# Function to get video transcript
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

# Function to get video comments
def get_video_comments(api_key, video_id, max_results=10):
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=max_results
    )
    response = request.execute()
    return [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in response['items']]

# Function to process content with OpenAI
def process_with_openai(content, prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ]
    )
    return response.choices[0].message.content

# Function to store data in Pinecone
def store_in_pinecone(video_id, blog_content):
    vector = openai.Embedding.create(input=[blog_content], model="text-embedding-ada-002")["data"][0]["embedding"]
    index.upsert([(video_id, vector, {"blog_content": blog_content})])

# Function to retrieve data from Pinecone
def retrieve_from_pinecone(video_id):
    result = index.fetch([video_id])
    if result and video_id in result['vectors']:
        return result['vectors'][video_id]['metadata']['blog_content']
    return None

# Streamlit app
def main():
    st.title("Enhanced YouTube Blog Post Generator")

    # Input for YouTube API Key
    youtube_api_key = st.text_input("Enter your YouTube API Key", value=os.getenv("YOUTUBE_API_KEY"), type="password")

    # Set default YouTube Channel ID
    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    if youtube_api_key and channel_id:
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
                    transcript = get_video_transcript(video_id)
                    comments = get_video_comments(youtube_api_key, video_id)

                    # Process content with OpenAI
                    summary = process_with_openai(transcript, "Summarize this video transcript in a blog post format:")
                    enhanced_comments = process_with_openai('\n'.join(comments), "Highlight and analyze the most interesting points from these comments:")

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

if __name__ == "__main__":
    main()
