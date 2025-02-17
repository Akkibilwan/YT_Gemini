import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dateutil import parser
import plotly.express as px

# Configure page
st.set_page_config(
    page_title="YouTube Trend Analyzer",
    page_icon="📊",
    layout="wide"
)

# API Keys
YOUTUBE_API_KEY = "AIzaSyCUECZRXFkTkBvtO3g7jVcRxZDjit94ZWU"  # Replace with your YouTube API key
GEMINI_API_KEY = "AIzaSyB3O8mJHTAMWQEKrJwGUaGLY7aDDVvRE0A"    # Replace with your Gemini API key

# Initialize APIs
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_video_details(video_id):
    """Get detailed statistics for a specific video"""
    try:
        stats = youtube.videos().list(
            part='statistics',
            id=video_id
        ).execute()
        return stats['items'][0]['statistics'] if stats.get('items') else None
    except Exception as e:
        st.error(f"Error fetching video stats: {str(e)}")
        return None

def get_channel_recent_videos(channel_id):
    """Get average views for channel's recent videos"""
    try:
        # Get channel's upload playlist
        channel_data = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        if not channel_data.get('items'):
            return 0
            
        uploads_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get recent videos
        videos = youtube.playlistItems().list(
            part='contentDetails',
            playlistId=uploads_id,
            maxResults=10
        ).execute()
        
        if not videos.get('items'):
            return 0
            
        # Get view counts
        video_ids = [item['contentDetails']['videoId'] for item in videos['items']]
        views = []
        
        for vid_id in video_ids:
            stats = get_video_details(vid_id)
            if stats and 'viewCount' in stats:
                views.append(int(stats['viewCount']))
                
        return np.mean(views) if views else 0
    except Exception as e:
        st.error(f"Error fetching channel stats: {str(e)}")
        return 0

def search_videos(keyword, content_type='video'):
    """Search for videos based on keyword and type"""
    try:
        # Use Gemini to enhance search
        prompt = f"Generate 3 relevant YouTube search terms for: {keyword}"
        response = model.generate_content(prompt)
        search_terms = [keyword] + response.text.split('\n')[:2]
        
        all_videos = []
        max_results = 30 if content_type == 'video' else 20
        
        for term in search_terms:
            search_response = youtube.search().list(
                q=term,
                part='snippet',
                type='video',
                videoDuration='any' if content_type == 'video' else 'short',
                maxResults=max_results,
                order='viewCount'
            ).execute()
            
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                stats = get_video_details(video_id)
                
                if not stats:
                    continue
                
                channel_id = item['snippet']['channelId']
                current_views = int(stats.get('viewCount', 0))
                avg_views = get_channel_recent_videos(channel_id)
                
                outlier_score = round((current_views / avg_views if avg_views > 0 else 0) * 10) / 10
                
                video_data = {
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url'],
                    'channel': item['snippet']['channelTitle'],
                    'views': current_views,
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'outlier_score': outlier_score,
                    'url': f"https://youtube.com/watch?v={video_id}",
                    'publish_date': parser.parse(item['snippet']['publishedAt']).strftime('%Y-%m-%d')
                }
                
                all_videos.append(video_data)
        
        # Remove duplicates and sort
        unique_videos = {v['url']: v for v in all_videos}.values()
        return sorted(unique_videos, key=lambda x: x['views'], reverse=True)[:max_results]
        
    except Exception as e:
        st.error(f"Error searching videos: {str(e)}")
        return []

def main():
    st.title("📊 YouTube Trend Analyzer")
    
    # Sidebar
    with st.sidebar:
        st.header("Search Settings")
        keyword = st.text_input("Enter keyword to search", placeholder="e.g., python programming")
        content_type = st.radio("Content Type", ['Videos', 'Shorts'])
        
        if st.button("🔍 Search", use_container_width=True):
            if keyword:
                with st.spinner("Analyzing YouTube trends..."):
                    results = search_videos(keyword, content_type.lower())
                    if results:
                        st.session_state.results = results
                    else:
                        st.error("No results found. Try a different keyword.")
            else:
                st.warning("Please enter a keyword")
    
    # Main content
    if 'results' in st.session_state and st.session_state.results:
        results = st.session_state.results
        
        # Analytics Overview
        st.header("📈 Analytics Overview")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_views = np.mean([v['views'] for v in results])
            st.metric("Average Views", f"{avg_views:,.0f}")
            
        with col2:
            avg_outlier = np.mean([v['outlier_score'] for v in results])
            st.metric("Average Outlier Score", f"{avg_outlier:.1f}x")
            
        with col3:
            trending_channels = len(set([v['channel'] for v in results]))
            st.metric("Trending Channels", trending_channels)
        
        # Results Grid
        st.header("🎥 Trending Content")
        for i in range(0, len(results), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(results):
                    video = results[i + j]
                    with col:
                        st.image(video['thumbnail'], use_column_width=True)
                        st.markdown(f"**{video['title'][:50]}...**")
                        st.write(f"Channel: {video['channel']}")
                        st.write(f"Views: {video['views']:,}")
                        
                        # Color-coded outlier score
                        color = 'green' if video['outlier_score'] > 1.5 else \
                               'orange' if video['outlier_score'] > 1.0 else 'red'
                        st.markdown(f"Outlier Score: <span style='color:{color}'>{video['outlier_score']}x</span>", 
                                  unsafe_allow_html=True)
                        
                        st.markdown(f"[Watch Video]({video['url']})")
                        st.divider()
        
        # Distribution Plot
        st.header("📊 Outlier Score Distribution")
        df = pd.DataFrame(results)
        fig = px.histogram(df, x='outlier_score', nbins=20,
                          title='Distribution of Outlier Scores',
                          labels={'outlier_score': 'Outlier Score', 'count': 'Number of Videos'})
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
