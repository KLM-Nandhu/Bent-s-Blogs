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

# Load environment variables
load_dotenv()

# Initialize API keys from environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# Custom CSS for improved fonts and styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&family=Open+Sans:wght@400;600&display=swap');
    
    .title {
        font-family: 'Roboto Slab', serif;
        font-weight: 700;
        color: #3d2b1f;
        font-size: 2.5em;
    }
    .subtitle {
        font-family: 'Roboto Slab', serif;
        font-weight: 400;
        color: #5d4037;
        font-size: 1.8em;
    }
    .text {
        font-family: 'Open Sans', sans-serif;
        font-weight: 400;
        color: #3e2723;
        font-size: 1em;
    }
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 20px;
    }
    .product-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
    }
    .product-image {
        max-width: 100%;
        height: auto;
        border-radius: 4px;
    }
    .stButton>button {
        background-color: #8d6e63;
        color: white;
        font-family: 'Open Sans', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

PROMPTS = {
    1: "Analyze this woodworking video transcript and create a detailed blog post. Focus on the specific techniques, tools used, and key steps in the project. Highlight any unique or innovative approaches:",
    2: "Based on this video transcript, identify and list all tools and materials used in the project. For each item, briefly explain its purpose and importance in the woodworking process:",
    3: "Extract 5-7 key learning points or tips from this woodworking video that would be valuable for both beginners and experienced woodworkers. Emphasize safety tips and best practices:",
    4: "Craft a compelling conclusion for this woodworking blog post. Summarize the main project steps, emphasize key learning points, and encourage readers to try the project. Also, invite readers to share their own experiences or variations of this woodworking technique:"
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
        st.warning(f"Unable to fetch transcript: {e}")
        return None

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

def extract_product_links(description):
    link_pattern = r'(https?://(?:www\.)?(?:amazon|homedepot|lowes|rockler|woodcraft)\.com\S+)'
    links = re.findall(link_pattern, description)
    return links

def get_product_details(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('meta', property='og:title')['content'] if soup.find('meta', property='og:title') else 'Product Title Not Found'
        image = soup.find('meta', property='og:image')['content'] if soup.find('meta', property='og:image') else 'https://via.placeholder.com/150'
        return {'title': title, 'image': image, 'url': url}
    except Exception as e:
        st.warning(f"Error fetching product details: {e}")
        return {'title': 'Product Info Unavailable', 'image': 'https://via.placeholder.com/150', 'url': url}

def generate_single_blog_post(video_id):
    video_details = get_video_details(video_id)
    if not video_details:
        return None

    video_title = video_details['snippet']['title']
    video_description = video_details['snippet']['description']
    transcript = get_video_transcript(video_id)

    if not transcript:
        st.warning("Transcript not available. The blog post may lack detailed information.")
        content_for_analysis = f"Title: {video_title}\n\nDescription: {video_description}"
    else:
        content_for_analysis = transcript

    blog_sections = [f"<h1 class='title'>{video_title}</h1>", f"<p class='text'>Video URL: https://www.youtube.com/watch?v={video_id}</p>"]

    # Add video statistics
    blog_sections.append(f"<p class='text'>Views: {video_details['statistics']['viewCount']}</p>")
    blog_sections.append(f"<p class='text'>Likes: {video_details['statistics']['likeCount']}</p>")

    # Generate content based on transcript or title/description
    summary = process_with_openai(content_for_analysis, 1)
    blog_sections.append("<h2 class='subtitle'>Video Summary</h2>")
    blog_sections.append(f"<p class='text'>{summary}</p>")

    # Add tools and materials
    tools_and_materials = process_with_openai(content_for_analysis, 2)
    blog_sections.append("<h2 class='subtitle'>Tools and Materials</h2>")
    blog_sections.append(f"<p class='text'>{tools_and_materials}</p>")

    # Add key points or takeaways
    key_points = process_with_openai(content_for_analysis, 3)
    blog_sections.append("<h2 class='subtitle'>Key Takeaways</h2>")
    blog_sections.append(f"<p class='text'>{key_points}</p>")

    # Extract and display product links
    product_links = extract_product_links(video_description)
    if product_links:
        blog_sections.append("<h2 class='subtitle'>Products Used in This Video</h2>")
        blog_sections.append("<div class='product-grid'>")
        for link in product_links:
            product = get_product_details(link)
            blog_sections.append(f"""
                <div class='product-card'>
                    <img src="{product['image']}" alt="{product['title']}" class='product-image'>
                    <p class='text'>{product['title']}</p>
                    <a href="{product['url']}" target="_blank" class='text'>Buy Now</a>
                </div>
            """)
        blog_sections.append("</div>")

    # Conclude the blog post
    conclusion = process_with_openai(f"Video title: {video_title}\nSummary: {summary}", 4)
    blog_sections.append("<h2 class='subtitle'>Conclusion</h2>")
    blog_sections.append(f"<p class='text'>{conclusion}</p>")

    return '\n'.join(blog_sections)

def main():
    st.markdown("<h1 class='title'>Woodworking YouTube Blog Generator</h1>", unsafe_allow_html=True)

    video_id = st.text_input("Enter a YouTube Video ID")

    if st.button("Generate Blog Post"):
        if video_id:
            with st.spinner("Crafting your woodworking blog post... 🪚"):
                st.markdown("""
                    <style>
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
                blog_post = generate_single_blog_post(video_id)
            if blog_post:
                st.success("Blog post generated successfully!")
                st.markdown(blog_post, unsafe_allow_html=True)
            else:
                st.warning("Failed to generate blog post. Please check the video ID and try again.")
        else:
            st.error("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
