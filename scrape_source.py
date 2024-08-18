import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import tinycss2
import requests
import cssselect

def clean_css(css):
    # Remove comments
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    # Fix color values
    css = re.sub(r'#([0-9a-fA-F]{3,4})\b', r'#\1\1', css)
    return css

def parse_css(css_content):
    return tinycss2.parse_stylesheet(css_content)

def extract_used_css(html, css_rules):
    soup = BeautifulSoup(html, 'html.parser')
    used_css = []
    
    for rule in css_rules:
        if rule.type == 'qualified-rule':
            try:
                selector = cssselect.parse(''.join(token.serialize() for token in rule.prelude))
                print(selector)
                for sel in selector:
                    if soup.select(sel.canonical()):
                        used_css.append(rule)
                        break
            except cssselect.SelectorError:
                # If the selector is invalid, skip it
                continue
    
    return used_css

def serialize_css(css_rules):
    rules = []
    for rule in css_rules:
        try:
            rules.append(rule.serialize())
        except Exception as e:
            print(f'Error serializing rule: {e}')
    return '\n'.join(rules)

def crawl_and_extract(url):
    # Set up Selenium WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Get the rendered HTML
        html = driver.page_source
        
        # Extract all CSS
        all_css = ''
        
        # Inline styles
        style_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "style"))
        )
        for style in style_elements:
            all_css += style.get_attribute('textContent')
        
        # External stylesheets
        link_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "link"))
        )
        for link in link_elements:
            if link.get_attribute('rel') == 'stylesheet':
                css_url = link.get_attribute('href')
                if css_url:
                    try:
                        response = requests.get(css_url)
                        all_css += response.text
                    except requests.RequestException:
                        print(f"Failed to fetch CSS from {css_url}")
        
        cleaned_css = clean_css(all_css)

        
        # Combine HTML and used CSS
        combined = f"""
        <html>
        <head>
        <style>
        {cleaned_css}
        </style>
        </head>
        <body>
        {html}
        </body>
        </html>
        """
        
        # Save to file
        with open('output.html', 'w', encoding='utf-8') as f:
            f.write(combined)
        
        print("Crawling and extraction completed successfully!")
        return combined    
    
    except TimeoutException:
        print("Timed out waiting for page to load")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()

