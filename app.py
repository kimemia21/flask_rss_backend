import os
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import feedparser
import datetime
import xml.etree.ElementTree as ET
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Ensure a directory exists for storing RSS feeds
FEED_STORAGE_DIR = 'generated_feeds'
os.makedirs(FEED_STORAGE_DIR, exist_ok=True)

def generate_rss_feed(urls, feed_title='Generated RSS Feed'):
    """
    Generate an RSS feed from a list of URLs.
    
    :param urls: List of URLs to include in the feed
    :param feed_title: Title of the RSS feed
    :return: Path to the generated RSS file
    """
    # Create a unique filename for the feed
    feed_filename = f"{uuid.uuid4()}.xml"
    feed_path = os.path.join(FEED_STORAGE_DIR, feed_filename)

    # Create the RSS feed XML structure
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    
    # Add channel metadata
    ET.SubElement(channel, 'title').text = feed_title
    ET.SubElement(channel, 'link').text = 'http://example.com'
    ET.SubElement(channel, 'description').text = 'Dynamically Generated RSS Feed'
    
    # Process each URL and add as an item
    for url in urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise error for HTTP issues
            
            # Parse feed using feedparser
            parsed_feed = feedparser.parse(response.content)
            
            # Check if valid feed
            if parsed_feed.feed and parsed_feed.entries:
                for entry in parsed_feed.entries[:5]:  # Limit to 5 entries per source
                    item = ET.SubElement(channel, 'item')
                    ET.SubElement(item, 'title').text = entry.get('title', 'No Title')
                    ET.SubElement(item, 'link').text = entry.get('link', url)
                    
                    # Use description or summary if available
                    description = entry.get('description') or entry.get('summary', 'No description')
                    ET.SubElement(item, 'description').text = description
                    
                    # Add publication date if available
                    pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
                    if pub_date:
                        date_str = datetime.datetime(*pub_date[:6]).strftime('%a, %d %b %Y %H:%M:%S GMT')
                        ET.SubElement(item, 'pubDate').text = date_str
            else:
                # Fallback for non-feed URLs
                raise ValueError("Invalid or empty RSS feed.")
        
        except Exception as e:
            print(f"Error processing {url}: {e}")
            item = ET.SubElement(channel, 'item')
            ET.SubElement(item, 'title').text = f"Error processing URL: {url}"
            ET.SubElement(item, 'link').text = url

    # Write the XML to file
    tree = ET.ElementTree(rss)
    tree.write(feed_path, encoding='utf-8', xml_declaration=True)
    
    return feed_filename

@app.route('/generate_feed', methods=['POST'])
def create_feed():
    """
    Endpoint to generate an RSS feed from a list of URLs.
    
    Expected JSON payload:
    {
        "urls": ["http://example1.com/rss", "http://example2.com/feed"],
        "title": "Optional Feed Title" (optional)
    }
    """
    data = request.json
    
    if not data or 'urls' not in data:
        return jsonify({"error": "No URLs provided"}), 400
    
    urls = data['urls']
    feed_title = data.get('title', 'Generated RSS Feed')
    
    try:
        feed_filename = generate_rss_feed(urls, feed_title)
        feed_url = f"/get_feed/{feed_filename}"
        return jsonify({
            "msg": True,
            "feed_url": feed_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_feed/<filename>')
def get_feed(filename):
    """
    Endpoint to retrieve a generated RSS feed.
    """
    try:
        return send_from_directory(FEED_STORAGE_DIR, filename, mimetype='application/rss+xml')
    except FileNotFoundError:
        return jsonify({"error": "Feed not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
