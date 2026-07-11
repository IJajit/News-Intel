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
                content_enc = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                if content_enc is not None and content_enc.text is not None:
                    # Print the entire content or search for </style>
                    text = content_enc.text
                    print(f"Total length: {len(text)}")
                    print(f"Contains </style>: {'</style>' in text.lower()}")
                    # Let's find index of </style>
                    idx = text.lower().find('</style>')
                    if idx != -1:
                        print(f"Style block: {text[idx-100:idx+50]}")
except Exception as e:
    print(f"Error: {e}")
