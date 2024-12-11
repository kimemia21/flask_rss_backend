import os
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import feedparser
import datetime
import xml.etree.ElementTree as ET
from flask_cors import CORS
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Ensure a directory exists for storing RSS feeds
FEED_STORAGE_DIR = 'generated_feeds'
os.makedirs(FEED_STORAGE_DIR, exist_ok=True)

def is_xml_content(content):
    """
    Check if the content appears to be XML.
    
    :param content: Content to check
    :return: Boolean indicating if content is XML
    """
    # Check for XML declaration or RSS/Atom tags
    xml_patterns = [
        r'<\?xml.*\?>', 
        r'<rss\b', 
        r'<feed\b', 
        r'<channel\b'
    ]
    
    # Convert to string if it's bytes
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='ignore')
    
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in xml_patterns)

def generate_rss_feed(urls, feed_title='Generated RSS Feed'):
    """
    Generate an RSS feed from multiple URLs, handling both XML and HTML pages.
    
    :param urls: List of URLs to generate the feed from
    :param feed_title: Title of the RSS feed
    :return: Path to the generated RSS file
    """
    # HIGHLIGHT_START
    # Modification: Change to handle multiple URLs
    if not isinstance(urls, list):
        urls = [urls]  # Ensure urls is a list
    
    # Create the RSS feed XML structure
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    
    # Add channel metadata
    ET.SubElement(channel, 'title').text = feed_title
    ET.SubElement(channel, 'link').text = ', '.join(urls)
    ET.SubElement(channel, 'description').text = f'RSS feed generated from {len(urls)} URL(s)'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Process each URL
        for url in urls:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            content = response.content
            
            # If it's an XML file, use it directly
            if is_xml_content(content):
                # Parse the XML content and add items to the channel
                xml_root = ET.fromstring(content)
                for item in xml_root.findall('.//item'):
                    channel.append(item)
            
            # Otherwise, try parsing the content as a webpage
            else:
                # Parse the content using feedparser
                parsed_feed = feedparser.parse(content)
                
                # Add entries from the parsed feed
                for entry in parsed_feed.entries[:5]:  # Limit to 5 entries per URL
                    item = ET.SubElement(channel, 'item')
                    ET.SubElement(item, 'title').text = f"{entry.get('title', 'No Title')} (from {url})"
                    ET.SubElement(item, 'link').text = entry.get('link', url)
                    
                    # Use description or summary if available
                    description = entry.get('description') or entry.get('summary', 'No description')
                    ET.SubElement(item, 'description').text = description
                    
                    # Add publication date if available
                    pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
                    if pub_date:
                        date_str = datetime.datetime(*pub_date[:6]).strftime('%a, %d %b %Y %H:%M:%S GMT')
                        ET.SubElement(item, 'pubDate').text = date_str
    except Exception as e:
        logger.error(f"Error generating RSS feed from URLs {urls}: {e}")
        raise ValueError(f"Error generating RSS feed: {e}")

    # Create a unique filename for the feed
    feed_filename = f"{uuid.uuid4()}.xml"
    feed_path = os.path.join(FEED_STORAGE_DIR, feed_filename)
    
    # Write the XML to file
    tree = ET.ElementTree(rss)
    tree.write(feed_path, encoding='utf-8', xml_declaration=True)
    
    return feed_filename
    # HIGHLIGHT_END

@app.route('/generate_feed', methods=['POST'])
def create_feed():
    """
    Endpoint to generate an RSS feed from URL(s).
    
    Expected JSON payload:
    {
        "url": ["https://www.ft.com/search?q=tea", "https://example.com/rss"],
        "title": "Optional Feed Title" (optional)
    }
    """
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({
            "error": "No URL(s) provided",
            "msg": False
        }), 400
    
    # HIGHLIGHT_START
    # Modification: Support both single URL and list of URLs
    urls = data['url']
    if isinstance(urls, str):
        urls = [urls]  # Convert single URL to list
    # HIGHLIGHT_END
    
    feed_title = data.get('title', 'Generated RSS Feed')
    
    try:
        feed_filename = generate_rss_feed(urls, feed_title)
        feed_url = f"{request.host_url.rstrip('/')}/get_feed/{feed_filename}"
        return jsonify({
            "msg": True,
            "feed_url": feed_url,
            "processed_urls": urls
        })
    except Exception as e:
        logger.error(f"Feed generation error: {e}")
        return jsonify({
            "error": str(e),
            "msg": False,
            "urls": urls
        }), 500
@app.route('/get_feed/<filename>', methods=['GET'])
def get_feed(filename):
    """
    Endpoint to retrieve a previously generated RSS feed.
    
    :param filename: Name of the XML feed file to retrieve
    :return: XML file or error response
    """
    try:
        # Ensure the filename is secure and within the intended directory
        secure_name = secure_filename(filename)
        
        # Check if file exists
        feed_path = os.path.join(FEED_STORAGE_DIR, secure_name)
        if not os.path.exists(feed_path):

            return jsonify({
                "error": "Feed not found",
                "msg": False
            }), 404
        
        # Serve the XML file
        return send_from_directory(
            FEED_STORAGE_DIR, 
            secure_name, 
            mimetype='application/rss+xml'
        )
    except Exception as e:
        logger.error(f"Error serving feed {filename}: {e}")
        return jsonify({
            "error": "Could not retrieve feed",
            "msg": False
        }), 500    

# Rest of the code remains the same
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)