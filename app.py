import streamlit as st
import os
from dotenv import load_dotenv
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import re
import time

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define improved prompts as numbered messages
PROMPTS = {
    1: "Analyze this woodworking video transcript and create a detailed blog post. Focus on the specific techniques, tools used, and key steps in the project. Highlight any unique or innovative approaches:",
    2: "Based on this video transcript, identify and list all tools and materials used in the project. For each item, briefly explain its purpose and importance in the woodworking process:",
    3: "Extract 5-7 key learning points or tips from this woodworking video that would be valuable for both beginners and experienced woodworkers. Emphasize safety tips and best practices:",
    4: "Based on the tools and materials used in this project, suggest 5-10 related products that viewers might find useful for this or similar woodworking projects. Include a brief explanation of how each product could be beneficial:",
    5: "Craft a compelling conclusion for this woodworking blog post. Summarize the main project steps, emphasize key learning points, and encourage readers to try the project. Also, invite readers to share their own experiences or variations of this woodworking technique:"
}

# Custom CSS for attractive fonts and styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&family=Open+Sans:wght@400;600&display=swap');
    
    .title {
        font-family: 'Roboto Slab', serif;
        font-weight: 700;
        color: #3d2b1f;
    }
    .subtitle {
        font-family: 'Roboto Slab', serif;
        font-weight: 400;
        color: #5d4037;
    }
    .text {
        font-family: 'Open Sans', sans-serif;
        font-weight: 400;
        color: #3e2723;
    }
    </style>
    """, unsafe_allow_html=True)

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

# Function to get video transcript with retries
def get_video_transcript(video_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return ' '.join([entry['text'] for entry in transcript])
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait for 1 second before retrying
            else:
                st.warning(f"Failed to fetch transcript after {max_retries} attempts. Error: {str(e)}")
                return None

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

# Function to extract shopping links from video description
def extract_shopping_links(description):
    link_pattern = r'(https?://(?:www\.)?(?:amazon|homedepot|lowes|rockler|woodcraft)\.com\S+)'
    links = re.findall(link_pattern, description)
    return links

# Function to generate a blog post for a single video
def generate_single_blog_post(video_id, manual_transcript=None):
    video_details = get_video_details(video_id)
    if not video_details:
        st.error("Failed to fetch video details. Please check the video ID and try again.")
        return None

    video_title = video_details['snippet']['title']
    video_description = video_details['snippet']['description']
    
    if manual_transcript:
        transcript = manual_transcript
    else:
        # First attempt to get transcript
        transcript = get_video_transcript(video_id)
        
        # If first attempt fails, inform user and try again
        if not transcript:
            st.warning("Initial attempt to fetch transcript failed. Trying again...")
            transcript = get_video_transcript(video_id, max_retries=2)
        
        # If still no transcript, return None to trigger manual input
        if not transcript:
            return None

    shopping_links = extract_shopping_links(video_description)

    blog_sections = [f"<h1 class='title'>{video_title}</h1>", f"\n<p class='text'>Video URL: https://www.youtube.com/watch?v={video_id}</p>"]

    # Add video statistics
    blog_sections.append(f"<p class='text'>Views: {video_details['statistics']['viewCount']}</p>")
    blog_sections.append(f"<p class='text'>Likes: {video_details['statistics']['likeCount']}</p>")

    # Generate content based on transcript
    summary = process_with_openai(transcript, 1)
    blog_sections.append("<h2 class='subtitle'>Project Overview</h2>")
    blog_sections.append(f"<p class='text'>{summary}</p>")

    # Add tools and materials
    tools_and_materials = process_with_openai(transcript, 2)
    blog_sections.append("<h2 class='subtitle'>Tools and Materials</h2>")
    blog_sections.append(f"<p class='text'>{tools_and_materials}</p>")

    # Add key points or takeaways
    key_points = process_with_openai(summary, 3)
    blog_sections.append("<h2 class='subtitle'>Key Takeaways</h2>")
    blog_sections.append(f"<p class='text'>{key_points}</p>")

    # Add related products
    related_products = process_with_openai(tools_and_materials, 4)
    blog_sections.append("<h2 class='subtitle'>Related Products</h2>")
    blog_sections.append(f"<p class='text'>{related_products}</p>")

    # Add shopping links
    if shopping_links:
        blog_sections.append("<h2 class='subtitle'>Where to Buy</h2>")
        blog_sections.append("<p class='text'>Here are links to some of the tools and materials used in this project:</p>")
        for link in shopping_links:
            blog_sections.append(f"<p class='text'>- <a href='{link}' target='_blank'>Product Link</a></p>")

    # Conclude the blog post
    conclusion = process_with_openai(f"Video title: {video_title}\nSummary: {summary}", 5)
    blog_sections.append("<h2 class='subtitle'>Conclusion</h2>")
    blog_sections.append(f"<p class='text'>{conclusion}</p>")

    return '\n'.join(blog_sections)

# Improved loading animation
def loading_animation():
    col1, col2, col3 = st.columns([1,3,1])
    with col2:
        st.markdown("""
            <style>
                .stSpinner > div > div {
                    border-top-color: #8d6e63 !important;
                }
                @keyframes saw {
                    0% { content: "🪚"; }
                    25% { content: "🪚 "; }
                    50% { content: "🪚  "; }
                    75% { content: "🪚   "; }
                    100% { content: "🪚    "; }
                }
                .saw-animation::after {
                    content: "🪚";
                    animation: saw 1s infinite;
                }
            </style>
            <div class="saw-animation">Crafting your woodworking blog post</div>
            """, unsafe_allow_html=True)

# Streamlit app
def main():
    st.markdown("<h1 class='title'>Comprehensive Woodworking YouTube Blog Generator</h1>", unsafe_allow_html=True)

    video_id = st.text_input("Enter a YouTube Video ID")

    if st.button("Generate Blog Post"):
        if video_id:
            with st.spinner():
                loading_animation()
                blog_post = generate_single_blog_post(video_id)
            
            if blog_post is None:
                st.warning("Unable to automatically fetch the transcript. Please enter the transcript manually.")
                manual_transcript = st.text_area("Enter the video transcript here:", height=300)
                if st.button("Process Manual Transcript"):
                    if manual_transcript:
                        with st.spinner():
                            loading_animation()
                            blog_post = generate_single_blog_post(video_id, manual_transcript)
                        if blog_post:
                            st.success("Comprehensive woodworking blog post generated successfully!")
                            st.markdown(blog_post, unsafe_allow_html=True)
                        else:
                            st.error("Failed to generate blog post from manual transcript. Please try again.")
                    else:
                        st.error("No transcript provided. Unable to generate blog post.")
            elif blog_post:
                st.success("Comprehensive woodworking blog post generated successfully!")
                st.markdown(blog_post, unsafe_allow_html=True)
            else:
                st.warning("Failed to generate blog post. Please check the error messages above and try again.")
        else:
            st.error("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
