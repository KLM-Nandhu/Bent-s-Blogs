import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import re

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define prompts as numbered messages
PROMPTS = {
    1: "Provide a detailed summary of this video transcript in a blog post format. Include key points, interesting facts, and main takeaways:",
    2: "Based on this video title and description, generate a detailed blog post summary. Include potential key points and main takeaways:",
    3: "Extract 5-7 key points or takeaways from this summary:",
    4: "Analyze these comments and highlight the most insightful, interesting, or frequently mentioned points. Also, identify any questions or concerns raised by viewers:",
    5: "Write a compelling conclusion for this blog post, summarizing the main points and encouraging viewers to watch the video. Also, invite readers to share their thoughts or experiences related to the video content:",
    6:"Don't make a sentence of your own. only i need the blog that inside the videos"
}

# Function to get video details
def get_video_details(video_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(part="snippet,statistics,contentDetails", id=video_id)
        response = request.execute()
        return response['items'][0]
    except HttpError as e:
        st.error(f"An error occurred while fetching video details: {e}")
        return None

# Function to get video transcript
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        return None

# Function to get video comments
def get_video_comments(video_id, max_results=20):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance"
        )
        response = request.execute()
        return [item['snippet']['topLevelComment']['snippet'] for item in response['items']]
    except HttpError as e:
        st.error(f"An error occurred while fetching comments: {e}")
        return []

# Function to process content with OpenAI
def process_with_openai(content, prompt_number):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Prompt {prompt_number}: {PROMPTS[prompt_number]}"},
                {"role": "user", "content": content}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error processing with OpenAI: {str(e)}")
        return None

# Function to extract chapters from video description
def extract_chapters(description):
    chapter_pattern = r'(\d+:\d+)\s+(.+)'
    chapters = re.findall(chapter_pattern, description)
    return chapters

# Function to extract shopping links from video description
def extract_shopping_links(description):
    link_pattern = r'(https?://(?:www\.)?(?:amazon|flipkart)\.com\S+)'
    links = re.findall(link_pattern, description)
    return links

# Function to generate a blog post for a single video
def generate_single_blog_post(video_id):
    video_details = get_video_details(video_id)
    if video_details:
        video_title = video_details['snippet']['title']
        video_description = video_details['snippet']['description']
        transcript = get_video_transcript(video_id)
        comments = get_video_comments(video_id)
        chapters = extract_chapters(video_description)
        shopping_links = extract_shopping_links(video_description)

        blog_sections = [f"# {video_title}", f"\nVideo URL: https://www.youtube.com/watch?v={video_id}"]

        # Add video statistics
        blog_sections.append(f"\nViews: {video_details['statistics']['viewCount']}")
        blog_sections.append(f"Likes: {video_details['statistics']['likeCount']}")

        # Add chapters
        if chapters:
            blog_sections.append("\n## Video Chapters")
            for time, title in chapters:
                blog_sections.append(f"- {time}: {title}")

        # Generate content based on transcript or description
        if transcript:
            full_transcript = ' '.join([entry['text'] for entry in transcript])
            summary = process_with_openai(full_transcript, 1)
            blog_sections.append("\n## Video Summary (Based on Transcript)")
        else:
            summary = process_with_openai(f"Title: {video_title}\n\nDescription: {video_description}", 2)
            blog_sections.append("\n## Video Summary (Based on Title and Description)")
            blog_sections.append("\n*Note: This summary is generated based on the video title and description as the transcript was not available.*")

        blog_sections.append(summary)

        # Add key points or takeaways
        key_points = process_with_openai(summary, 3)
        blog_sections.append("\n## Key Takeaways")
        blog_sections.append(key_points)

        # Add shopping links
        if shopping_links:
            blog_sections.append("\n## Tools and Products")
            blog_sections.append("Here are the tools and products mentioned in the video:")
            for link in shopping_links:
                blog_sections.append(f"- [Product Link]({link})")

        # Add comment analysis if comments are available
        if comments:
            comment_texts = [comment['textDisplay'] for comment in comments]
            enhanced_comments = process_with_openai('\n'.join(comment_texts), 4)
            blog_sections.append("\n## Community Insights")
            blog_sections.append(enhanced_comments)

            # Add highlighted comments
            blog_sections.append("\n### Highlighted Comments")
            for comment in comments[:5]:  # Display top 5 comments
                blog_sections.append(f"\n> {comment['textDisplay']}")
                blog_sections.append(f"\n— {comment['authorDisplayName']}")
        else:
            blog_sections.append("\n## Community Insights")
            blog_sections.append("*No comments available for this video.*")

        # Conclude the blog post
        conclusion = process_with_openai(f"Video title: {video_title}\nSummary: {summary}", 5)
        blog_sections.append("\n## Conclusion")
        blog_sections.append(conclusion)

        return '\n'.join(blog_sections)
    
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
    st.title("Enhanced YouTube Blog Generator")

    # Set default YouTube Channel ID
    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    # Add input for single video ID
    video_id = st.text_input("Enter a Specific YouTube Video ID")

    if st.button("Generate Blog Post(s)"):
        if video_id:
            with st.spinner("Generating enhanced blog post... This may take a while."):
                blog_post = generate_single_blog_post(video_id)
            if blog_post:
                st.success("Enhanced blog post generated successfully!")
                st.markdown(blog_post)
            else:
                st.warning("Failed to generate blog post. Please check the video ID and try again.")
        elif channel_id:
            with st.spinner("Generating enhanced blog posts... This may take a while."):
                blog_posts = generate_channel_blog_posts(channel_id)
            
            if blog_posts:
                st.success(f"Generated {len(blog_posts)} enhanced blog posts!")
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
