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
    .stButton>button {
        background-color: #8d6e63;
        color: white;
        font-family: 'Open Sans', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

PROMPTS = {
    1: "Analyze this woodworking video title and description. Create a detailed blog post focusing on the likely techniques, tools used, and key steps in the project. Highlight any unique or innovative approaches you can infer:",
    2: "Based on this video title and description, identify and list all tools and materials likely used in the project. For each item, briefly explain its probable purpose and importance in the woodworking process:",
    3: "Extract 5-7 key learning points or tips that would be valuable for both beginners and experienced woodworkers, based on the video's topic. Emphasize likely safety tips and best practices:",
    4: "Based on the inferred tools and materials used in this project, suggest 5-10 related products that viewers might find useful for this or similar woodworking projects. Include a brief explanation of how each product could be beneficial:",
    5: "Craft a compelling conclusion for this woodworking blog post. Summarize the main project steps, emphasize key learning points, and encourage readers to watch the video and try the project. Also, invite readers to share their own experiences or variations of this woodworking technique:"
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

def extract_chapters(description):
    chapter_pattern = r'(\d+:\d+)\s+(.+)'
    chapters = re.findall(chapter_pattern, description)
    return chapters

def extract_shopping_links(description):
    link_pattern = r'(https?://(?:www\.)?(?:amazon|homedepot|lowes|rockler|woodcraft)\.com\S+)'
    links = re.findall(link_pattern, description)
    return links

def generate_single_blog_post(video_id):
    video_details = get_video_details(video_id)
    if video_details:
        video_title = video_details['snippet']['title']
        video_description = video_details['snippet']['description']
        comments = get_video_comments(video_id)
        chapters = extract_chapters(video_description)
        shopping_links = extract_shopping_links(video_description)

        blog_sections = [f"<h1 class='title'>{video_title}</h1>", f"<p class='text'>Video URL: https://www.youtube.com/watch?v={video_id}</p>"]

        # Add video statistics
        blog_sections.append(f"<p class='text'>Views: {video_details['statistics']['viewCount']}</p>")
        blog_sections.append(f"<p class='text'>Likes: {video_details['statistics']['likeCount']}</p>")

        # Add chapters
        if chapters:
            blog_sections.append("<h2 class='subtitle'>Video Chapters</h2>")
            for time, title in chapters:
                blog_sections.append(f"<p class='text'>- {time}: {title}</p>")

        # Generate content based on title and description
        content_for_analysis = f"Title: {video_title}\n\nDescription: {video_description}"
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

        # Add comment analysis if comments are available
        if comments:
            comment_texts = [comment['textDisplay'] for comment in comments[:5]]  # Use top 5 comments
            enhanced_comments = process_with_openai('\n'.join(comment_texts), 4)
            blog_sections.append("<h2 class='subtitle'>Community Insights</h2>")
            blog_sections.append(f"<p class='text'>{enhanced_comments}</p>")

            # Add highlighted comments
            blog_sections.append("<h3 class='subtitle'>Highlighted Comments</h3>")
            for comment in comments[:5]:
                blog_sections.append(f"<blockquote class='text'>{comment['textDisplay']}</blockquote>")
                blog_sections.append(f"<p class='text'>— {comment['authorDisplayName']}</p>")
        else:
            blog_sections.append("<h2 class='subtitle'>Community Insights</h2>")
            blog_sections.append("<p class='text'>No comments available for this video.</p>")

        # Conclude the blog post
        conclusion = process_with_openai(f"Video title: {video_title}\nSummary: {summary}", 5)
        blog_sections.append("<h2 class='subtitle'>Conclusion</h2>")
        blog_sections.append(f"<p class='text'>{conclusion}</p>")

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
        st.error(f"An error occurred while accessing the YouTube API: {str(e)}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        return []

def main():
    st.markdown("<h1 class='title'>Enhanced Woodworking YouTube Blog Generator</h1>", unsafe_allow_html=True)

    default_channel_id = "UCiQO4At218jezfjPqDzn1CQ"
    channel_id = st.text_input("Enter your YouTube Channel ID", value=default_channel_id)

    video_id = st.text_input("Or enter a specific YouTube Video ID (optional)")

    if st.button("Generate Blog Post(s)"):
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
                st.success("Enhanced blog post generated successfully!")
                st.markdown(blog_post, unsafe_allow_html=True)
            else:
                st.warning("Failed to generate blog post. Please check the video ID and try again.")
        elif channel_id:
            with st.spinner("Generating enhanced blog posts... This may take a while. 🪚"):
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
                    <div class="saw-animation">Crafting multiple woodworking blog posts</div>
                    """, unsafe_allow_html=True)
                blog_posts = generate_channel_blog_posts(channel_id)
            
            if blog_posts:
                st.success(f"Generated {len(blog_posts)} enhanced blog posts!")
                for video_id, post in blog_posts:
                    with st.expander(f"Blog Post for Video {video_id}"):
                        st.markdown(post, unsafe_allow_html=True)
            else:
                st.warning("No blog posts were generated. Please check the error messages above and try again.")
        else:
            st.error("Please enter either a YouTube Channel ID or a specific Video ID.")

if __name__ == "__main__":
    main()
