import streamlit as st
import groq
import os
from dotenv import load_dotenv
from groq import Groq
import json
import requests
from PIL import Image
import io
import base64
from datetime import datetime

# Load environment variables
try:
    # First try from Streamlit secrets
    api_key = st.secrets["general"]["api_key"]
except Exception as e:
    # Fallback to environment variable if needed
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("Error: Groq API key not found. Please set it in Streamlit secrets or as an environment variable.")
        st.stop()

# Initialize Groq client with the API key
client = Groq(api_key=api_key)

# Define fallback models if primary models are unavailable
FALLBACK_MODELS = {
    "mistral-saba-24b": "llama3-8b-8192",       # Fallback to Llama if Mistral is unavailable
    "llama-3.3-70b-versatile": "llama3-8b-8192" # Fallback to smaller Llama if larger is unavailable
}

# Updated primary model to use
DEFAULT_MODEL = "mistral-saba-24b"  # New replacement for mixtral-8x7b-32768
HIGH_QUALITY_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL = "llama3-8b-8192"

# Helper function to validate API messages
def validate_messages(messages):
    """Ensure all message content fields are strings to prevent Groq API errors"""
    for msg in messages:
        if 'content' in msg and msg['content'] is not None and not isinstance(msg['content'], str):
            msg['content'] = str(msg['content'])
    return messages

# Helper function to attempt API call with fallback models
def safe_completion_create(messages, model, temperature, max_tokens, **kwargs):
    """Try to create a completion with fallback to alternative models if needed"""
    try:
        return client.chat.completions.create(
            messages=validate_messages(messages),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    except Exception as primary_error:
        # If we have a fallback model for this one, try it
        fallback_model = FALLBACK_MODELS.get(model)
        if fallback_model:
            try:
                st.warning(f"Primary model {model} unavailable. Using fallback model {fallback_model}.")
                return client.chat.completions.create(
                    messages=validate_messages(messages),
                    model=fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as fallback_error:
                # Both primary and fallback failed
                raise Exception(f"Primary error: {str(primary_error)}. Fallback error: {str(fallback_error)}")
        else:
            # No fallback available, raise the original error
            raise primary_error

# Set page config
st.set_page_config(
    page_title="Bob Buster - AI Comedy Agent",
    page_icon="🎭",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        color: #1a1a1a;
    }
    .stButton>button {
        background-color: #ff6b6b;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 20px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #ff5252;
        transform: translateY(-2px);
    }
    .stTextInput>div>div>input {
        background-color: #f8f9fa;
        color: #1a1a1a;
        border: 1px solid #dee2e6;
    }
    .stSelectbox>div>div>select {
        background-color: #f8f9fa;
        color: #1a1a1a;
    }
    .stSlider>div>div>div>div {
        background-color: #ff6b6b;
    }
    .stMarkdown {
        color: #1a1a1a;
    }
    .stHeader {
        color: #1a1a1a;
    }
    .meme-container {
        display: flex;
        flex-wrap: wrap;
        gap: 20px;
        justify-content: center;
        padding: 20px;
    }
    .meme-item {
        flex: 1;
        min-width: 300px;
        max-width: 400px;
        text-align: center;
    }
    .meme-image {
        max-width: 100%;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# Title and description
st.title("🎭 Bob Buster - AI Comedy Agent")
st.markdown("""
    Welcome to Bob Buster, Hollywood's most ruthless AI comedy agent. 
    Get ready for some savage roasts and sharp wit!
    """)

# Sidebar for settings
with st.sidebar:
    st.header("Comedy Settings")
    intensity = st.slider("Roast Intensity", 1, 5, 3)
    style = st.selectbox(
        "Comedy Style",
        ["Savage Roast", "Witty One-liner", "Dark Humor", "Sarcastic", "Improv", "Visual Comedy"]
    )
    temperature = st.slider("Creativity Level", 0.0, 1.0, 0.9, 0.1)
    max_tokens = st.slider("Response Length", 100, 1000, 500, 50)
    meme_count = st.slider("Number of Memes", 1, 5, 2)

def create_system_prompt(style, intensity):
    return f"""You are Bob Buster, Hollywood's most ruthless comedy agent. Your style is {style} with an intensity of {intensity}/5.
    You are known for:
    - Sharp, witty comebacks
    - Brutally honest observations
    - Dark humor that pushes boundaries
    - Quick improvisation skills
    - Cultural awareness and topical references
    - Visual humor and meme creation
    
    Guidelines:
    1. Keep jokes concise and impactful
    2. Use appropriate language based on intensity
    3. Include relevant cultural references
    4. Maintain character consistency
    5. Adapt tone based on context
    6. For visual comedy, describe memes and visual elements vividly"""

def generate_meme_prompt(topic, style, intensity):
    return f"""Create a funny meme about {topic}.
    Style: {style}
    Intensity: {intensity}/5
    
    Respond with a JSON object containing:
    {{
        "top_text": "short text for top of meme (max 50 chars)",
        "bottom_text": "short text for bottom of meme (max 50 chars)",
        "meme_template": "one of: drake, distracted, change_my_mind, two_buttons, expanding_brain, this_is_fine, stonks, surprised_pikachu",
        "description": "brief description of the meme"
    }}
    
    Keep texts short and punchy. No hashtags or special characters."""

def get_meme_templates():
    return {
        "drake": "https://api.memegen.link/images/drake/{top}/{bottom}",
        "distracted": "https://api.memegen.link/images/distracted/{top}/{bottom}",
        "change_my_mind": "https://api.memegen.link/images/changemy/{top}/{bottom}",
        "two_buttons": "https://api.memegen.link/images/buttons/{top}/{bottom}",
        "expanding_brain": "https://api.memegen.link/images/brain/{top}/{bottom}",
        "this_is_fine": "https://api.memegen.link/images/fine/{top}/{bottom}",
        "stonks": "https://api.memegen.link/images/stonks/{top}/{bottom}",
        "surprised_pikachu": "https://api.memegen.link/images/pikachu/{top}/{bottom}"
    }

def sanitize_text(text):
    # More thorough text sanitization
    text = text.replace("'", "").replace('"', "")  # Remove quotes
    text = text.replace("\n", " ").replace("\r", " ")  # Remove newlines
    text = " ".join(text.split())  # Remove extra spaces
    return text.replace(" ", "-").replace("?", "~q").replace("/", "~s").replace("#", "~h").replace("&", "~a")

def get_meme_image(template_name, top_text, bottom_text):
    try:
        templates = get_meme_templates()
        template = template_name.lower() if template_name.lower() in templates else "drake"
        url_template = templates[template]
        
        # Sanitize and truncate text
        top = sanitize_text(top_text)[:50]  # Limit length
        bottom = sanitize_text(bottom_text)[:50]  # Limit length
        
        return url_template.format(top=top, bottom=bottom)
    except Exception as e:
        st.error(f"Error generating meme: {str(e)}")
        return templates["drake"].format(top="Error", bottom="generating-meme")

def create_comedy_team_prompt(style, intensity):
    return {
        "writer": {
            "role": "system",
            "content": f"""You are a professional comedy writer with {style} style.
            Your role is to create the initial joke structure and setup.
            Intensity: {intensity}/5
            Focus on crafting clever setups and unexpected twists.
            Keep responses concise and impactful."""
        },
        "roaster": {
            "role": "system",
            "content": f"""You are a savage roast master with {style} style.
            Your role is to add brutal but funny punchlines.
            Intensity: {intensity}/5
            Focus on clever observations and witty comebacks.
            Keep responses concise and sharp."""
        },
        "refiner": {
            "role": "system",
            "content": f"""You are a comedy refiner with {style} style.
            Your role is to polish jokes and make them sharper.
            Intensity: {intensity}/5
            Focus on timing, word choice, and delivery.
            Keep responses concise and polished."""
        }
    }

def generate_team_comedy(topic, style, intensity, temperature):
    # Define model assignments for each role
    model_assignments = {
        "writer": "llama3-8b-8192",      # Fast, creative setup generation
        "roaster": DEFAULT_MODEL, # Strong reasoning for punchlines
        "refiner": "llama3-70b-8192"     # High-quality output refinement
    }
    
    team_prompts = create_comedy_team_prompt(style, intensity)
    results = {}
    
    try:
        # Writer creates setup using llama3-8b
        writer_messages = [
            team_prompts["writer"],
            {"role": "user", "content": f"Create a clever setup for a joke about {topic}. Keep it under 50 words."}
        ]
        writer_completion = safe_completion_create(
            messages=writer_messages,
            model=model_assignments["writer"],
            temperature=temperature,
            max_tokens=100
        )
        setup = writer_completion.choices[0].message.content
        results["setup"] = setup
        
        # Roaster adds punchline using mixtral-8x7b
        roaster_messages = [
            team_prompts["roaster"],
            {"role": "user", "content": f"Add a savage punchline to this setup:\n{setup}\nMake it sharp and memorable."}
        ]
        roaster_completion = safe_completion_create(
            messages=roaster_messages,
            model=model_assignments["roaster"],
            temperature=temperature,
            max_tokens=150
        )
        raw_joke = roaster_completion.choices[0].message.content
        results["raw_joke"] = raw_joke
        
        # Refiner polishes using llama3-70b
        refiner_messages = [
            team_prompts["refiner"],
            {"role": "user", "content": f"Polish this joke to perfection:\n{raw_joke}\nMake it concise and impactful."}
        ]
        refiner_completion = safe_completion_create(
            messages=refiner_messages,
            model=model_assignments["refiner"],
            temperature=temperature,
            max_tokens=200
        )
        final_joke = refiner_completion.choices[0].message.content
        results["final_joke"] = final_joke
        
        return {
            "final_joke": final_joke,
            "development_stages": {
                "setup": setup,
                "raw_joke": raw_joke
            },
            "models_used": model_assignments
        }
        
    except Exception as e:
        st.error(f"Error in comedy team generation: {str(e)}")
        return None

# Main content
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 Generate Jokes", "🔥 Personal Roast", "🎭 Comedy Show", "🖼️ Visual Comedy", "👥 Comedy Team"])

with tab1:
    st.header("Generate Jokes")
    topic = st.text_input("Enter a topic for jokes:")
    
    if st.button("Generate Jokes"):
        if topic:
            with st.spinner("Crafting some savage humor..."):
                messages = [
                    {"role": "system", "content": create_system_prompt(style, intensity)},
                    {"role": "user", "content": f"Generate 3 jokes about {topic}. Make them sharp, witty, and slightly savage."}
                ]
                
                try:
                    chat_completion = safe_completion_create(
                        messages=messages,
                        model=DEFAULT_MODEL,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=0.9
                    )
                    
                    jokes = chat_completion.choices[0].message.content
                    st.markdown(jokes)
                except Exception as e:
                    st.error(f"Error generating jokes: {str(e)}")
                    st.write("Please try again with a different topic or settings.")
        else:
            st.warning("Please enter a topic!")

with tab2:
    st.header("Personal Roast")
    name = st.text_input("Enter a name to roast:")
    context = st.text_area("Add some context (optional):")
    
    if st.button("Generate Roast"):
        if name:
            with st.spinner("Preparing a savage roast..."):
                messages = [
                    {"role": "system", "content": create_system_prompt(style, intensity)},
                    {"role": "user", "content": f"Create a savage roast for {name}. Context: {context}"}
                ]
                
                try:
                    chat_completion = safe_completion_create(
                        messages=messages,
                        model=DEFAULT_MODEL,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=0.9
                    )
                    
                    roast = chat_completion.choices[0].message.content
                    st.markdown(roast)
                except Exception as e:
                    st.error(f"Error generating roast: {str(e)}")
                    st.write("Please try again with a different name or settings.")
        else:
            st.warning("Please enter a name to roast!")

with tab3:
    st.header("Comedy Show")
    st.markdown("""
        Experience a full comedy show with Bob Buster! 
        Get ready for a mix of jokes, roasts, and improv.
    """)
    
    if st.button("Start Comedy Show"):
        with st.spinner("Preparing your comedy show..."):
            messages = [
                {"role": "system", "content": create_system_prompt(style, intensity)},
                {"role": "user", "content": "Create a 5-minute comedy show with a mix of jokes, roasts, and improv. Include transitions and audience interactions."}
            ]
            
            try:
                chat_completion = safe_completion_create(
                    messages=messages,
                    model=DEFAULT_MODEL,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=0.9
                )
                
                show = chat_completion.choices[0].message.content
                st.markdown(show)
            except Exception as e:
                st.error(f"Error generating comedy show: {str(e)}")
                st.write("Please try again with different settings.")

with tab4:
    st.header("Visual Comedy & Memes")
    st.markdown("""
        Experience Bob Buster's visual humor with custom memes and visual jokes!
        Choose from popular meme templates or let Bob pick one for you!
    """)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        meme_topic = st.text_input("Enter a topic for meme generation:")
    with col2:
        template_choice = st.selectbox(
            "Choose Template",
            ["Random"] + list(get_meme_templates().keys()),
            format_func=lambda x: x.replace("_", " ").title()
        )
    
    if st.button("Generate Memes"):
        if meme_topic:
            with st.spinner("Creating savage memes..."):
                try:
                    try:
                        messages = [
                            {"role": "system", "content": create_system_prompt(style, intensity)},
                            {"role": "user", "content": generate_meme_prompt(meme_topic, style, intensity)}
                        ]
                        
                        chat_completion = safe_completion_create(
                            messages=messages,
                            model=DEFAULT_MODEL,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format={"type": "json_object"}
                        )
                        
                        try:
                            meme_data = json.loads(chat_completion.choices[0].message.content)
                            
                            for i in range(meme_count):
                                template = template_choice if template_choice != "Random" else meme_data.get('meme_template', 'drake')
                                meme_url = get_meme_image(
                                    template,
                                    meme_data.get('top_text', 'Error'),
                                    meme_data.get('bottom_text', 'generating meme')
                                )
                                
                                st.image(meme_url, caption=meme_data.get('description', ''), use_column_width=True)
                                st.markdown("---")
                        
                        except json.JSONDecodeError:
                            st.error("Failed to parse meme data. Trying again with simplified format...")
                            # Fallback to simpler format
                            meme_url = get_meme_image(
                                template_choice if template_choice != "Random" else "drake",
                                "When the meme",
                                "Doesn't generate properly"
                            )
                            st.image(meme_url, caption="Fallback meme", use_column_width=True)
                    
                    except Exception as e:
                        st.error(f"Error with Groq API: {str(e)}")
                        # Fallback meme on API error
                        meme_url = get_meme_image(
                            "drake",
                            "When Groq API",
                            "Throws an error"
                        )
                        st.image(meme_url, caption="API Error Fallback", use_column_width=True)
                except Exception as e:
                    st.error(f"Critical error: {str(e)}")
        else:
            st.warning("Please enter a topic for meme generation!")

with tab5:
    st.header("Comedy Team")
    st.markdown("""
        Experience collaborative comedy creation powered by multiple Groq models! Watch as our team of specialized AI comedians work together:
        1. **Writer** (Llama-3 8B) - Creates clever setups
        2. **Roaster** (Mixtral-8x7B) - Adds savage punchlines
        3. **Refiner** (Llama-3 70B) - Polishes the final joke
    """)
    
    team_topic = st.text_input("Enter a topic for the comedy team:")
    show_process = st.checkbox("Show joke development process", value=False)
    show_models = st.checkbox("Show models used", value=False)
    
    if st.button("Generate Team Comedy"):
        if team_topic:
            with st.spinner("Comedy team at work..."):
                result = generate_team_comedy(team_topic, style, intensity, temperature)
                
                if result:
                    if show_process:
                        with st.expander("See how the joke evolved"):
                            st.markdown("### Initial Setup (Llama-3 8B)")
                            st.write(result["development_stages"]["setup"])
                            st.markdown("### Raw Joke (Mixtral-8x7B)")
                            st.write(result["development_stages"]["raw_joke"])
                            st.markdown("### Final Polished Version (Llama-3 70B)")
                            st.write(result["final_joke"])
                    else:
                        st.markdown("### Final Joke")
                        st.write(result["final_joke"])
                    
                    if show_models:
                        st.markdown("### Models Used")
                        for role, model in result["models_used"].items():
                            st.write(f"**{role.title()}**: {model}")
        else:
            st.warning("Please enter a topic for the comedy team!") 
