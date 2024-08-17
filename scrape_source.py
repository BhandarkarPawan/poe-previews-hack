import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import ssl
import os

def get_and_save_source_code(url, output_file):
    try:
        # Create a session to reuse the same connection
        session = requests.Session()
        
        # Configure session for HTTPS
        session.verify = True  # Verify SSL certificates
        
        # Send a GET request to the URL
        response = session.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Get the HTML content
        html_content = response.text
        
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract CSS content
        css_content = ""
        
        # Find all <style> tags and extract their content
        for style in soup.find_all('style'):
            css_content += style.string + "\n\n" if style.string else ""
        
        # Find all <link> tags with rel="stylesheet" and fetch their content
        for link in soup.find_all('link', rel='stylesheet'):
            if 'href' in link.attrs:
                css_url = urljoin(url, link['href'])
                try:
                    css_response = session.get(css_url, timeout=5)
                    css_response.raise_for_status()
                    css_content += css_response.text + "\n\n"
                except requests.exceptions.RequestException as e:
                    print(f"Failed to fetch CSS from {css_url}: {e}")
        
        # Remove existing <link> tags for stylesheets
        for link in soup.find_all('link', rel='stylesheet'):
            link.decompose()
        
        # Create a new <style> tag with all the CSS content
        new_style = soup.new_tag('style')
        new_style.string = css_content
        
        # Insert the new <style> tag into the <head>
        head = soup.find('head')
        if head:
            head.append(new_style)
        else:
            # If there's no <head>, create one and add it to the beginning of the <html>
            new_head = soup.new_tag('head')
            new_head.append(new_style)
            html = soup.find('html')
            if html:
                html.insert(0, new_head)
            else:
                # If there's no <html>, something is wrong with the structure
                raise ValueError("Invalid HTML structure: no <html> tag found")
        
        # Write the modified HTML (with inlined CSS) to the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        
        print(f"Successfully saved the webpage to {output_file}")
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the URL: {e}")
    except ssl.SSLError as e:
        print(f"An SSL error occurred: {e}")
    except IOError as e:
        print(f"An error occurred while writing to the file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        session.close()

# Example usage
url = "https://sutra.co"
output_file = "webpage_with_css.html"
get_and_save_source_code(url, output_file)