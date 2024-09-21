import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import re
import openai

# Set up API client
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Custom CSS (keep your existing CSS here)
st.markdown("""
<style>
    /* Your existing CSS styles */
</style>
<div class="background-design"></div>
<div class="animated-text">Bent's Woodworking</div>
""", unsafe_allow_html=True)

def get_video_info(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url)
        return yt.title, yt.thumbnail_url, yt.description
    except Exception as e:
        return f"An error occurred while fetching video info: {str(e)}", None, None

def get_video_transcript_with_timestamps(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        return f"An error occurred while fetching the transcript: {str(e)}"

def organize_transcript(transcript):
    prompt = """
    This document contains a video transcript. The problem with this document is that the time stamps are in between the content of the transcript. Can you help me organize this content into the following fields:
    Product name:
    Starting timestamp:
    Ending Timestamp:
    Transcript:
    The goal is to not summarize any information but just reorganize into this. For the beginning and ending part of the transcript, you can just categorize it as Intro and Outro where the speech is not specific to any product.
    
    Transcript:
    """
    prompt += str(transcript)

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that organizes video transcripts."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def generate_blog_post(transcript, title, description):
    prompt = f"""
    Write a blog post targeting 65-year-old people who like woodworking as a hobby and have expendable income. The blog post should genuinely show interest in educating the audience while improving SEO performance to gain more visibility in general.

    Use the following video transcript to create the blog post:
    Title: {title}
    Description: {description}
    Transcript: {transcript}

    The blog post should:
    1. Have an engaging introduction
    2. Be divided into 3-5 main sections with clear, descriptive headings
    3. Include specific, actionable tips for woodworking enthusiasts
    4. Explain any technical terms in a clear, easy-to-understand manner
    5. Incorporate relevant keywords for SEO without compromising readability
    6. Have a conclusion summarizing key points and encouraging engagement
    7. Be written in a friendly, conversational tone that resonates with older adults
    8. Address common challenges or questions that older woodworking enthusiasts might have
    9. Suggest tools or products mentioned in the video (if any)

    Format the blog post in Markdown, using appropriate headings, bullet points, and emphasis where necessary.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a skilled woodworking blogger and SEO expert."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def main():
    st.markdown('<div class="title-container"><h1>Woodworking Blog Generator</h1></div>', unsafe_allow_html=True)
    
    video_id = st.text_input("", key="video_id_input", placeholder="Enter YouTube Video ID")
    
    if video_id:
        title, thumbnail_url, description = get_video_info(video_id)
        
        if thumbnail_url:
            st.markdown(f"""
            <div class="video-info">
                <img src="{thumbnail_url}" alt="Video Thumbnail">
                <span class="video-title">{title}</span>
            </div>
            """, unsafe_allow_html=True)
            
            transcript = get_video_transcript_with_timestamps(video_id)
            
            if isinstance(transcript, list):
                if st.button("Generate Blog Post", key="generate_button"):
                    with st.spinner("Generating blog post..."):
                        organized_transcript = organize_transcript(transcript)
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
                        
                        if st.button("Show Transcript"):
                            st.text_area("Original Transcript", str(transcript), height=300)
            else:
                st.error(transcript)  # Display error message if transcript couldn't be fetched
        else:
            st.error(title)  # Display error message if video info couldn't be fetched
    
    st.markdown("---")
    st.markdown('<p class="big-font">Instructions:</p>', unsafe_allow_html=True)
    st.markdown('<p class="medium-font">1. Enter the YouTube Video ID (e.g., \'dQw4w9WgXcQ\' from \'https://www.youtube.com/watch?v=dQw4w9WgXcQ\')</p>', unsafe_allow_html=True)
    st.markdown('<p class="medium-font">2. Click \'Generate Blog Post\' to create a woodworking blog post based on the video content</p>', unsafe_allow_html=True)
    st.markdown('<p class="medium-font">3. Explore the generated blog post, product links, and original transcript</p>', unsafe_allow_html=True)
    st.markdown('<p class="medium-font">Note: This app works best with woodworking-related videos that have available transcripts.</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
