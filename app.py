import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

PROMPTS = {
    1: "Analyze this video transcript and create a detailed blog post. Focus on the specific techniques, tools used, and key steps in the project. Highlight any unique or innovative approaches:",
    2: "Based on this video transcript, identify and list all tools and materials used in the project. For each item, briefly explain its purpose and importance in the process:",
    3: "Extract 5-7 key learning points or tips from this video that would be valuable for both beginners and experienced viewers. Emphasize safety tips and best practices:",
    4: "Based on the tools and materials used in this project, suggest 5-10 related products that viewers might find useful for this or similar projects. Include a brief explanation of how each product could be beneficial:",
    5: "Craft a compelling conclusion for this blog post. Summarize the main project steps, emphasize key learning points, and encourage readers to try the project. Also, invite readers to share their own experiences or variations of this technique:"
}

def get_video_details(video_id):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(part="snippet,statistics,contentDetails", id=video_id)
        response = request.execute()
        return response['items'][0]
    except HttpError as e:
        st.error(f"An error occurred while fetching video details: {e}")
        return None

def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        return None

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

def extract_chapters(description):
    chapter_pattern = r'(\d+:\d+)\s+(.+)'
    chapters = re.findall(chapter_pattern, description)
    return chapters

def extract_shopping_links(description):
    # This regex pattern looks for product names followed by URLs
    pattern = r'(.*?)\s*-\s*(https?://\S+)'
    matches = re.findall(pattern, description)
    return matches

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

        blog_sections.append(f"\nViews: {video_details['statistics']['viewCount']}")
        blog_sections.append(f"Likes: {video_details['statistics']['likeCount']}")

        if chapters:
            blog_sections.append("\n## Video Chapters")
            for time, title in chapters:
                blog_sections.append(f"- {time}: {title}")

        if transcript:
            full_transcript = ' '.join([entry['text'] for entry in transcript])
            summary = process_with_openai(full_transcript, PROMPTS[1])
            blog_sections.append("\n## Video Summary (Based on Transcript)")
            blog_sections.append(summary)
        else:
            summary = process_with_openai(f"Title: {video_title}\n\nDescription: {video_description}", PROMPTS[2])
            blog_sections.append("\n## Video Summary (Based on Title and Description)")
            blog_sections.append("\n*Note: This summary is generated based on the video title and description as the transcript was not available.*")
            blog_sections.append(summary)

        key_points = process_with_openai(summary, PROMPTS[3])
        blog_sections.append("\n## Key Takeaways")
        blog_sections.append(key_points)

        if comments:
            comment_texts = [comment['textDisplay'] for comment in comments]
            enhanced_comments = process_with_openai('\n'.join(comment_texts), PROMPTS[4])
            blog_sections.append("\n## Community Insights")
            blog_sections.append(enhanced_comments)

            blog_sections.append("\n### Highlighted Comments")
            for comment in comments[:5]:
                blog_sections.append(f"\n> {comment['textDisplay']}")
                blog_sections.append(f"\n— {comment['authorDisplayName']}")
        else:
            blog_sections.append("\n## Community Insights")
            blog_sections.append("*No comments available for this video.*")

        conclusion = process_with_openai(f"Video title: {video_title}\nSummary: {summary}", PROMPTS[5])
        blog_sections.append("\n## Conclusion")
        blog_sections.append(conclusion)

        # Add product links at the end
        if shopping_links:
            blog_sections.append("\n## Links to Products Mentioned")
            for product_name, link in shopping_links:
                blog_sections.append(f"{product_name}: {link}")

        # Add sponsorship and social media sections
        blog_sections.append("\n## Sponsored By:")
        # Add sponsored links here if available

        blog_sections.append("\n## Partnered With:")
        # Add partner links here if available

        blog_sections.append("\n## Affiliate For:")
        # Add affiliate links here if available

        blog_sections.append("\n## Find me on social media!")
        # Add social media links here if available

        return '\n'.join(blog_sections)
    
    return None

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
            st.error("YouTube Data API v3 is not enabled for your project. Please enable it in the Google Developers Console.")
        else:
            st.error(f"An error occurred while accessing the YouTube API: {str(e)}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

def main():
    st.title("Flexible YouTube Blog Generator")

    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    video_id = st.text_input("Or enter a specific YouTube Video ID (optional)")

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
