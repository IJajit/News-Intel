import urllib.request
import xml.etree.ElementTree as ET
import re
import html

url = "https://www.deccanherald.com/feed/"

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            title = title_elem.text if title_elem is not None else ""
            if 'Anthropic' in title:
                content_enc = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                raw_content = content_enc.text if content_enc is not None else ""
                
                # Apply the stripping regex
                raw_content = re.sub(r'<style\b[^>]*>([\s\S]*?)<\/style>', ' ', raw_content, flags=re.IGNORECASE)
                raw_content = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', ' ', raw_content, flags=re.IGNORECASE)
                
                desc_clean = re.sub('<[^<]+?>', '', raw_content)
                print(f"Title: {title}")
                print("--- CLEANED CONTENT ---")
                print(desc_clean[:1000])
except Exception as e:
    print(f"Error: {e}")
