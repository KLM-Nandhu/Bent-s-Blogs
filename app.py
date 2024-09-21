import streamlit as st
import googleapiclient.discovery
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from PIL import Image
import requests
from io import BytesIO
import json

# Set up API clients
openai.api_key = st.secrets["OPENAI_API_KEY"]
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=st.secrets["YOUTUBE_API_KEY"])

def get_transcript(video_id):
    try:
        # First attempt: Using YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        st.warning(f"Error fetching transcript with YouTubeTranscriptApi: {str(e)}")
        st.info("Attempting to fetch transcript using YouTube Data API...")
        
        try:
            # Second attempt: Using YouTube Data API
            captions = youtube.captions().list(
                part="snippet",
                videoId=video_id
            ).execute()

            if not captions.get('items'):
                st.error("No captions found for this video.")
                return None

            caption_id = captions['items'][0]['id']
            subtitle = youtube.captions().download(
                id=caption_id,
                tfmt='srt'
            ).execute()

            # Process the SRT format to extract text
            lines = subtitle.decode('utf-8').split('\n\n')
            transcript_text = " ".join([" ".join(line.split('\n')[2:]) for line in lines])
            return transcript_text

        except Exception as e:
            st.error(f"Error fetching transcript with YouTube Data API: {str(e)}")
            return None

# ... (rest of the code remains the same)

def main():
    st.title("Woodworking Blog Generator")

    video_id = st.text_input("Enter YouTube Video ID")

    if st.button("Generate Blog Post"):
        if video_id:
            with st.spinner("Fetching video details..."):
                video_details = get_video_details(video_id)

            if video_details:
                st.subheader(video_details['title'])
                col1, col2 = st.columns(2)
                with col1:
                    st.image(video_details['thumbnail'], use_column_width=True)
                with col2:
                    st.write(f"Views: {video_details['view_count']}")
                    st.write(f"Likes: {video_details['like_count']}")
                    st.write(f"Comments: {video_details['comment_count']}")

                with st.spinner("Fetching and processing transcript..."):
                    transcript = get_transcript(video_id)
                    if transcript:
                        st.success("Transcript fetched successfully!")
                        processed_transcript = process_transcript(transcript)
                        if st.button("Show Transcript"):
                            st.text_area("Processed Transcript", processed_transcript, height=300)

                        with st.spinner("Generating blog post..."):
                            blog_post = generate_blog_post(processed_transcript)
                            sections = re.split(r'\n#+\s', blog_post)
                            
                            for i, section in enumerate(sections):
                                if i == 0:  # This is the introduction
                                    st.markdown(section)
                                else:
                                    title, content = section.split('\n', 1)
                                    with st.expander(title.strip()):
                                        st.markdown(content.strip())

                        st.subheader("Product Recommendations")
                        products = re.findall(r'([\w\s]+):\s*(https?://\S+)', video_details['description'])
                        for product, url in products:
                            st.markdown(f"[{product}]({url})")

                        st.subheader("Comments")
                        comments, next_page_token = get_comments(video_id)
                        for comment in comments:
                            st.text(f"{comment['author']}: {comment['text']}")
                        
                        if next_page_token:
                            if st.button("Load More Comments"):
                                more_comments, _ = get_comments(video_id, next_page_token)
                                for comment in more_comments:
                                    st.text(f"{comment['author']}: {comment['text']}")
                    else:
                        st.error("Failed to fetch transcript. Please check if captions are available for this video.")
            else:
                st.error("Failed to fetch video details. Please check the video ID and try again.")
        else:
            st.warning("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
