import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dateutil import parser
import plotly.express as px

# API Keys - Replace with your keys
YOUTUBE_API_KEY = "AIzaSyCUECZRXFkTkBvtO3g7jVcRxZDjit94ZWU"  # Replace with your YouTube API key
GEMINI_API_KEY = "AIzaSyB3O8mJHTAMWQEKrJwGUaGLY7aDDVvRE0A"    # Replace with your Gemini API key

# Initialize APIs
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_channel_stats(channel_id):
    """Get channel statistics for the past 3 months"""
    try:
        # Get channel uploads playlist
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get videos from the past 3 months
        three_months_ago = (datetime.now() - timedelta(days=90)).isoformat() + 'Z'
        
        videos_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=playlist_id,
            maxResults=50
        ).execute()
        
        video_ids = [item['snippet']['resourceId']['videoId'] 
                    for item in videos_response.get('items', [])]
        
        # Get video statistics
        stats_response = youtube.videos().list(
            part='statistics',
            id=','.join(video_ids)
        ).execute()
        
        view_counts = [int(video['statistics']['viewCount']) 
                      for video in stats_response['items']]
        
        return np.mean(view_counts) if view_counts else 0
        
    except Exception as e:
        st.error(f"Error fetching channel stats: {str(e)}")
        return 0

def calculate_outlier_score(avg_views, current_views):
    """Calculate outlier score based on average views"""
    if avg_views == 0:
        return 0
    
    outlier_score = current_views / avg_views
    # Round to nearest 0.1
    return round(outlier_score * 10) / 10

def search_videos(keyword, video_type='video'):
    """Search for videos or shorts based on keyword"""
    try:
        # Use Gemini to understand and expand the keyword
        prompt = f"Suggest relevant search terms for '{keyword}' in the context of YouTube {video_type}s"
        response = model.generate_content(prompt)
        search_terms = response.text.split('\n')[:3]  # Take top 3 suggestions
        
        all_videos = []
        
        for term in search_terms:
            # Search for videos
            search_response = youtube.search().list(
                q=term,
                part='snippet',
                type='video',
                videoDefinition='high',
                maxResults=50,
                videoDuration='any' if video_type == 'video' else 'short'
            ).execute()
            
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                
                # Get video statistics
                video_stats = youtube.videos().list(
                    part='statistics',
                    id=video_id
                ).execute()
                
                if not video_stats.get('items'):
                    continue
                    
                stats = video_stats['items'][0]['statistics']
                channel_id = item['snippet']['channelId']
                
                # Get channel average views
                avg_channel_views = get_channel_stats(channel_id)
                current_views = int(stats.get('viewCount', 0))
                
                outlier_score = calculate_outlier_score(avg_channel_views, current_views)
                
                video_data = {
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['high']['url'],
                    'channel': item['snippet']['channelTitle'],
                    'views': current_views,
                    'outlier_score': outlier_score,
                    'video_id': video_id,
                    'publish_date': parser.parse(item['snippet']['publishedAt']).strftime('%Y-%m-%d')
                }
                
                all_videos.append(video_data)
        
        # Sort by views and take top results
        all_videos.sort(key=lambda x: x['views'], reverse=True)
        return all_videos[:30 if video_type == 'video' else 20]
        
    except Exception as e:
        st.error(f"Error searching videos: {str(e)}")
        return []

def main():
    st.title("YouTube Trend Analyzer")
    
    # Sidebar for inputs
    with st.sidebar:
        keyword = st.text_input("Enter keyword to search")
        video_type = st.radio("Select content type", ['Videos', 'Shorts'])
        
        if st.button("Search"):
            if keyword:
                with st.spinner("Searching and analyzing..."):
                    results = search_videos(keyword, video_type.lower())
                    st.session_state.results = results
            else:
                st.warning("Please enter a keyword")
    
    # Main content area
    if 'results' in st.session_state and st.session_state.results:
        results_df = pd.DataFrame(st.session_state.results)
        
        # Display results in a grid
        cols = st.columns(3)
        for idx, video in enumerate(st.session_state.results):
            with cols[idx % 3]:
                st.image(video['thumbnail'], use_column_width=True)
                st.write(f"**{video['title'][:50]}...**")
                st.write(f"Channel: {video['channel']}")
                st.write(f"Views: {video['views']:,}")
                
                # Color code outlier score
                outlier_color = 'green' if video['outlier_score'] > 1.5 else \
                              'orange' if video['outlier_score'] > 1.0 else 'red'
                st.markdown(f"Outlier Score: <span style='color:{outlier_color}'>{video['outlier_score']}x</span>", 
                          unsafe_allow_html=True)
                st.write("---")
        
        # Add analytics section
        st.header("Analytics")
        
        # Show distribution of outlier scores
        st.subheader("Outlier Score Distribution")
        fig = px.histogram(results_df, x='outlier_score', nbins=20)
        st.plotly_chart(fig)
        
        # Show top channels by average views
        st.subheader("Top Channels")
        top_channels = results_df.groupby('channel')['views'].mean().sort_values(ascending=False).head(5)
        st.bar_chart(top_channels)

if __name__ == "__main__":
    main()
