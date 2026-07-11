import urllib.request
import xml.etree.ElementTree as ET

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
                print(f"Title: {title}")
                desc = item.find('description')
                content_enc = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                print("--- DESCRIPTION ---")
                if desc is not None and desc.text is not None:
                    print(desc.text[:1200])
                print("--- ENCODED ---")
                if content_enc is not None and content_enc.text is not None:
                    print(content_enc.text[:1200])
except Exception as e:
    print(f"Error: {e}")
