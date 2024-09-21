import streamlit as st
import googleapiclient.discovery
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from PIL import Image
import requests
from io import BytesIO

# Set up API clients
openai.api_key = st.secrets["OPENAI_API_KEY"]
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=st.secrets["YOUTUBE_API_KEY"])

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        st.warning(f"Unable to fetch transcript: {str(e)}")
        return None

def get_video_details(video_id):
    try:
        response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if 'items' in response:
            video = response['items'][0]
            return {
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'thumbnail': video['snippet']['thumbnails']['high']['url'],
                'view_count': video['statistics']['viewCount'],
                'like_count': video['statistics']['likeCount'],
                'comment_count': video['statistics']['commentCount']
            }
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching video details: {str(e)}")
        return None

def generate_blog_post(title, description, transcript=None):
    if transcript:
        prompt = f"""
        Generate a blog post for a woodworking YouTube channel based on the following video transcript. The target audience is 65-year-old people who enjoy woodworking as a hobby and have expendable income.

        Video Title: {title}
        Video Description: {description}
        Transcript: {transcript}

        The blog post should:
        1. Show genuine interest in educating the audience about woodworking techniques, tools, and projects
        2. Use a friendly, conversational tone that resonates with older adults
        3. Include specific, actionable tips that readers can apply to their own woodworking projects
        4. Explain any technical terms or jargon in a clear, easy-to-understand manner
        5. Incorporate relevant keywords for SEO without compromising readability
        6. Be organized into 4-6 main sections with clear, descriptive headings
        7. Have crisp, engaging sentences that maintain the reader's interest
        8. Address common challenges or questions that older woodworking enthusiasts might have
        9. Conclude with a summary of the key points and an encouragement to try the techniques or projects discussed
        """
    else:
        prompt = f"""
        Generate a blog post for a woodworking YouTube channel based on the following video title and description. The target audience is 65-year-old people who enjoy woodworking as a hobby and have expendable income.

        Video Title: {title}
        Video Description: {description}

        The blog post should:
        1. Show genuine interest in educating the audience about woodworking techniques, tools, and projects
        2. Use a friendly, conversational tone that resonates with older adults
        3. Speculate on possible content of the video based on the title and description
        4. Include general tips and advice related to the topic of the video
        5. Explain any technical terms or jargon in a clear, easy-to-understand manner
        6. Incorporate relevant keywords for SEO without compromising readability
        7. Be organized into 3-4 main sections with clear, descriptive headings
        8. Have crisp, engaging sentences that maintain the reader's interest
        9. Address common challenges or questions that older woodworking enthusiasts might have related to the video topic
        10. Conclude with a summary and an encouragement to watch the video for more detailed information
        """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a skilled woodworking blogger and SEO expert."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message['content']

def get_comments(video_id, page_token=None):
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=10,
            pageToken=page_token
        ).execute()

        comments = []
        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'author': comment['authorDisplayName'],
                'text': comment['textDisplay'],
                'likes': comment['likeCount'],
                'published_at': comment['publishedAt']
            })

        next_page_token = response.get('nextPageToken')
        return comments, next_page_token
    except Exception as e:
        st.error(f"Error fetching comments: {str(e)}")
        return [], None

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

                with st.spinner("Fetching transcript..."):
                    transcript = get_transcript(video_id)
                    if transcript:
                        st.success("Transcript fetched successfully!")
                    else:
                        st.warning("No transcript available. Generating blog post based on video title and description.")

                with st.spinner("Generating blog post..."):
                    blog_post = generate_blog_post(video_details['title'], video_details['description'], transcript)
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
                st.error("Failed to fetch video details. Please check the video ID and try again.")
        else:
            st.warning("Please enter a YouTube Video ID.")

if __name__ == "__main__":
    main()
