import streamlit as st
import openai
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import re
import requests

# Set up API clients
openai.api_key = st.secrets["OPENAI_API_KEY"]
youtube = build("youtube", "v3", developerKey=st.secrets["YOUTUBE_API_KEY"])

def get_video_info(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url)
        if response.status_code != 200:
            return None, None, None

        html_content = response.text

        # Extract title
        title_match = re.search(r'<meta name="title" content="(.*?)"', html_content)
        title = title_match.group(1) if title_match else "Unknown Title"

        # Extract description
        description_match = re.search(r'<meta name="description" content="(.*?)"', html_content)
        description = description_match.group(1) if description_match else "No description available"

        # Extract thumbnail URL
        thumbnail_match = re.search(r'<meta property="og:image" content="(.*?)"', html_content)
        thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None

        return title, description, thumbnail_url
    except Exception as e:
        st.error(f"Error fetching video info: {str(e)}")
        return None, None, None

# ... (rest of the code remains the same)

def main():
    st.title("Woodworking Blog Generator")

    video_id = st.text_input("Enter YouTube Video ID")

    if video_id:
        title, description, thumbnail_url = get_video_info(video_id)
        
        if title and description and thumbnail_url:
            st.image(thumbnail_url, use_column_width=True)
            st.subheader(title)
            
            transcript = get_video_transcript(video_id)
            
            if transcript:
                organized_transcript = organize_transcript(transcript)
                
                if st.button("Show Transcript"):
                    st.text_area("Organized Transcript", organized_transcript, height=300)
                
                blog_post = generate_blog_post(organized_transcript, title, description)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("Blog Post")
                    sections = re.split(r'#{1,2}\s', blog_post)
                    for i, section in enumerate(sections):
                        if i == 0:  # This is the introduction
                            st.markdown(section)
                        else:
                            title, content = section.split('\n', 1)
                            with st.expander(title.strip()):
                                st.markdown(content.strip())
                
                with col2:
                    st.subheader("Product Links")
                    products = re.findall(r'([\w\s]+):\s*(https?://\S+)', description)
                    for product, url in products:
                        st.markdown(f"[{product}]({url})")
                    
                    st.subheader("Comments")
                    comments = get_comments(video_id)
                    comment_count = 0
                    for comment in comments[:10]:
                        st.text(f"{comment['author']}: {comment['text'][:100]}...")
                        comment_count += 1
                    
                    if len(comments) > 10:
                        if st.button("Load More Comments"):
                            for comment in comments[10:]:
                                st.text(f"{comment['author']}: {comment['text'][:100]}...")
                                comment_count += 1
                                if comment_count >= 50:
                                    break
        else:
            st.error("Failed to fetch video information. Please check the video ID and try again.")

if __name__ == "__main__":
    main()
