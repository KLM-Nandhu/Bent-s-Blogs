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
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

PROMPTS = {
    1: "Analyze this video transcript and create a detailed blog post. Organize the content into clear headings and subheadings. Focus on the main topics discussed, key insights, and any step-by-step processes explained. Use concise language and bullet points where appropriate:",
    2: "Based on this video transcript, identify and list all tools, materials, or products mentioned. For each item, provide a brief description of its purpose and importance. Format the output as a bulleted list:",
    3: "Extract 5-7 key learning points or tips from this video that would be valuable for viewers. Present these as concise bullet points, focusing on actionable insights:",
    4: "Summarize the main ideas and conclusions from the video transcript. Highlight any calls to action or next steps suggested for viewers. Format this as a concise conclusion paragraph:",
    5: "Based on the content of this video, suggest 3-5 related topics or videos that viewers might find interesting. Briefly explain the connection to the current video. Format this as a bulleted list:"
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
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        st.error(f"An error occurred while fetching the transcript: {e}")
        return None

def get_video_comments(video_id, max_results=10):
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

def search_related_images(query, num_images=3):
    # TODO: Implement image search functionality
    # This is a placeholder function
    # You should replace this with an actual image search API
    return [f"https://via.placeholder.com/300x200.png?text=Related+Image+{i+1}" for i in range(num_images)]

def get_product_url(product_name):
    # TODO: Implement product search functionality
    # This is a placeholder function
    # You should replace this with an actual product search API or web scraping
    return f"https://example.com/shop/{product_name.replace(' ', '-')}"

def resize_image(image_url, max_width=300):
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Calculate the new height while maintaining the aspect ratio
    width_percent = (max_width / float(img.size[0]))
    new_height = int((float(img.size[1]) * float(width_percent)))
    
    img_resized = img.resize((max_width, new_height), Image.LANCZOS)
    
    # Convert the resized image to bytes
    buf = BytesIO()
    img_resized.save(buf, format="PNG")
    return buf.getvalue()

def generate_blog_post(video_id):
    video_details = get_video_details(video_id)
    if not video_details:
        return None

    video_title = video_details['snippet']['title']
    video_description = video_details['snippet']['description']
    transcript = get_video_transcript(video_id)

    if not transcript:
        st.warning("Transcript not available. Generating content based on title and description.")
        transcript = f"{video_title}\n\n{video_description}"

    blog_content = process_with_openai(transcript, PROMPTS[1])
    tools_and_materials = process_with_openai(transcript, PROMPTS[2])
    key_takeaways = process_with_openai(transcript, PROMPTS[3])
    conclusion = process_with_openai(transcript, PROMPTS[4])
    related_topics = process_with_openai(transcript, PROMPTS[5])

    comments = get_video_comments(video_id)
    community_insights = "### Top Comments\n\n"
    for comment in comments[:5]:
        community_insights += f"> {comment['textDisplay']}\n\n— {comment['authorDisplayName']}\n\n"

    # Search for related images
    related_images = search_related_images(video_title)

    blog_post = {
        "title": video_title,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "content": blog_content,
        "tools_and_materials": tools_and_materials,
        "key_takeaways": key_takeaways,
        "conclusion": conclusion,
        "related_topics": related_topics,
        "community_insights": community_insights,
        "related_images": related_images
    }

    return blog_post

def main():
    st.set_page_config(layout="wide")
    st.title("Enhanced YouTube Blog Generator")

    video_id = st.text_input("Enter a YouTube Video ID")

    if st.button("Generate Blog Post"):
        if video_id:
            with st.spinner("Generating enhanced blog post... This may take a while."):
                blog_post = generate_blog_post(video_id)

            if blog_post:
                st.success("Enhanced blog post generated successfully!")

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.header(blog_post["title"])
                    st.video(blog_post["video_url"])
                    st.markdown(blog_post["content"])

                    # Display related images
                    st.subheader("Related Images")
                    image_cols = st.columns(3)
                    for i, image_url in enumerate(blog_post["related_images"]):
                        with image_cols[i]:
                            resized_image = resize_image(image_url)
                            st.image(resized_image, use_column_width=True)

                    if st.button("Show Key Takeaways"):
                        st.markdown(blog_post["key_takeaways"])

                    if st.button("Show Community Insights"):
                        st.markdown(blog_post["community_insights"])

                    st.subheader("Conclusion")
                    st.markdown(blog_post["conclusion"])

                with col2:
                    st.subheader("Tools and Materials")
                    st.markdown(blog_post["tools_and_materials"])

                    # Add product links
                    tools_list = re.findall(r'- (.*?):', blog_post["tools_and_materials"])
                    for tool in tools_list:
                        product_url = get_product_url(tool)
                        st.markdown(f"[Buy {tool}]({product_url})")

                    st.subheader("Related Topics")
                    st.markdown(blog_post["related_topics"])

            else:
                st.warning("Failed to generate blog post. Please check the video ID and try again.")
        else:
            st.error("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
