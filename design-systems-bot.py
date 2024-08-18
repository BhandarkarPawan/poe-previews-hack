"""

Sample bot that demonstrates how to use OpenAI function calling with the Poe API.

"""

from __future__ import annotations

import json
import re
from typing import AsyncIterable

import fastapi_poe as fp
from modal import App, Image, asgi_app
import requests
from bs4 import BeautifulSoup
import re
import requirements

SYSTEM_PROMPT = """
You are an AI assistant specialising in frontend design that knows about and conforms to the best practices of UI/UX. 
""".strip()

# EXTRACT_DESIGN_TOKENS_PROMPT = """
# From the above html and css, give me a set of design rules.

# Commonly used design tokens include: Typography, Color palette, Spacing and layout, Grid system, Icons and iconography, Buttons and form elements, Navigation components, Cards and containers, Modals and overlays, Responsive design principles, Accessibility standards, Animation and transitions, Imagery and illustrations, Voice and tone guidelines, Component states (hover, active, disabled, etc.), Error handling and feedback, Loading states and indicators, Data visualization elements, Navigation patterns, Information architecture.  
# """

EXTRACT_DESIGN_TOKENS_PROMPT = """
From the above html and css, extract a comprehensive a set of tokens, like what are the colors used (primary, secondary, background, etc.), typography (heading, body, etc.), spacing (padding, margin, etc.) as well as other things like the grid system, borders, shadows, etc. Basically anything that would help a frontend developer implement new components that are consistent with the design system. Do not say anything at the end after you generate the tokens
"""


GENERATE_DESIGN_SYSTEM_PROMPT = """
Design a complete component system using HTML and CSS based on the above design tokens. For now let's start with a button, a sign up form, a list and a card. Keep the components consistent with the design system! Ouput an html file with all components rendered. 
"""


def crawl_and_extract(url):
  print("Crawling and extracting")
  # curl "http://api.scraperapi.com?api_key=cd1c32ccdbe17f5923d0e80db7cd511e&url=http://httpbin.org/ip"
  response = requests.get(f"http://api.scraperapi.com?api_key=cd1c32ccdbe17f5923d0e80db7cd511e&url={url}")
  return combine_html_and_css(response.text)

def combine_html_and_css(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    base_url = soup.find('base')['href'] if soup.find('base') else ''
    
    css_links = soup.find_all('link', rel='stylesheet')
    all_css = []

    for link in css_links:
        css_url = link.get('href')
        if css_url:
            if not css_url.startswith(('http://', 'https://')):
                css_url = base_url + css_url
            try:
                css_response = requests.get(css_url)
                if css_response.status_code == 200:
                    all_css.append(css_response.text)
            except requests.RequestException:
                print(f"Failed to fetch CSS from {css_url}")

    combined_css = '\n'.join(all_css)

    # Basic CSS cleaning (remove comments and minimize whitespace)
    cleaned_css = re.sub(r'/\*.*?\*/', '', combined_css, flags=re.DOTALL)
    cleaned_css = re.sub(r'\s+', ' ', cleaned_css)

    # Remove existing <style> and <link> tags
    for tag in soup(['style', 'link']):
        tag.decompose()

    # Create the combined HTML
    combined = f"""
    <html>
    <head>
    <style>
    {cleaned_css}
    </style>
    </head>
    <body>
    {soup.body.decode_contents() if soup.body else ''}
    </body>
    </html>
    """

    return combined


def determine_url(text):
    """Extract the URL from the given text"""
    print("Determining URL")
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    match = re.search(url_pattern, text)
    if match:
        return match.group(0)
    else:
        return ""




tools_executables = [determine_url, crawl_and_extract]

tools_dict_list = [
    {
        "type": "function",
        "function": {
            "name": "determine_url",
            "description": "Extract the URL from the given text",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract the URL from",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
       "type": "function",
        "function": {
            "name": "crawl_and_extract",
            "description": "Extract the complete HTML and CSS from the given URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The url to extract the HTML and CSS from",
                    },
                },
                "required": ["url"],
            },
        },
    }
]
tools = [fp.ToolDefinition(**tools_dict) for tools_dict in tools_dict_list]

def get_design_tokens(html_css):
    prompt = f"{html_css}\n\n{EXTRACT_DESIGN_TOKENS_PROMPT}"
    
    
DETERMINE_INTENT_PROMPT = f"""
You are an AI assistant that determines the intent of the user's input. Based on what the user has said select one fo the following options:

Option 0: The user wants to generate a design system from a url 
Option 1: The user wants to use a design system to generate pages or other components that conform to the design system. 

Output only the most appropriate option. if the user's input does not match any of the options, output "none".
""".strip()



def resolve_intent(intent):
  if "0" in intent:
    return 0
  if "1" in intent:
    return 1
  return -1

class GPT35FunctionCallingBot(fp.PoeBot):
    async def get_response(
        self, request: fp.QueryRequest
    ) -> AsyncIterable[fp.PartialResponse]:
        original_query = request.query
        last_message = request.query[-1].content
        determine_intent_prompt = f"{DETERMINE_INTENT_PROMPT}\n\n{last_message}"
        request.query = [
          fp.ProtocolMessage(role="system", content=SYSTEM_PROMPT),
          fp.ProtocolMessage(role="user", content=determine_intent_prompt)
        ]
        intent_response = await fp.get_final_response(request, "Claude-3-Sonnet-200k", api_key=request.access_key)
        intent = resolve_intent(intent_response)
        print("intent determined: ", intent)
        
        if intent == 0:
          url = determine_url(last_message)
          print("Url: ", url)
          yield fp.PartialResponse(text="Extracting the design tokens...", is_replace_response=True)
          html_css = crawl_and_extract(url)
          design_tokens_prompt = f"{html_css}\n\n{EXTRACT_DESIGN_TOKENS_PROMPT}"
          print("design_tokens_prompt: ", design_tokens_prompt)
          request.query = [fp.ProtocolMessage(role="user", content=design_tokens_prompt)]     
          design_tokens_response = await fp.get_final_response(request, "Claude-3-Sonnet-200k", api_key=request.access_key)
          print("design_tokens_response: ", design_tokens_response)
          yield fp.PartialResponse(text="Generating the design system...", is_replace_response=True)
          design_system_prompt = f"{design_tokens_response}\n\n{GENERATE_DESIGN_SYSTEM_PROMPT}"
          
          request.query = [
            fp.ProtocolMessage(role="system", content=SYSTEM_PROMPT),
            fp.ProtocolMessage(role="user", content=design_system_prompt)
          ]
          yield fp.PartialResponse(text="", is_replace_response=True)
          async for msg in fp.stream_request(request, "Claude-3-Sonnet-200k", api_key=request.access_key):
              yield msg
        else: 
          request.query = original_query
          async for msg in fp.stream_request(request, "Claude-3-Sonnet-200k", api_key=request.access_key):
              yield msg
              
    async def get_settings(self, setting: fp.SettingsRequest) -> fp.SettingsResponse:
      return fp.SettingsResponse(
        server_bot_dependencies={"Claude-3-Sonnet-200k": 1, "Claude-3-Haiku": 1}, 
    )


image = Image.debian_slim().pip_install(*requirements.REQUIREMENTS)
app = App("function-calling-poe")


@app.function(image=image)
@asgi_app()
def fastapi_app():
    bot = GPT35FunctionCallingBot()
    # Optionally, provide your Poe access key here:
    # 1. You can go to https://poe.com/create_bot?server=1 to generate an access key.
    # 2. We strongly recommend using a key for a production bot to prevent abuse,
    # but the starter examples disable the key check for convenience.
    # 3. You can also store your access key on modal.com and retrieve it in this function
    # by following the instructions at: https://modal.com/docs/guide/secrets
    # POE_ACCESS_KEY = ""
    # app = make_app(bot, access_key=POE_ACCESS_KEY)
    app = fp.make_app(bot, access_key="kIjGZefz1bJGYonuPRtyb5NH3mFQ6CkP")
    return app


if __name__ == "__main__":
    print(crawl_and_extract("https://sutra.co"))