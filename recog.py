import streamlit as st
import google.generativeai as genai
from google.generativeai import types
import requests
import io

st.set_page_config(page_title="Gemini Chat + Vision", page_icon="🧠", layout="wide")
st.title("🧠 Gemini Chat + Image Recognition (no Cloud Vision)")

# --- Sidebar for API Key --------------------------------------------------
with st.sidebar:
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    st.caption("Get one from https://aistudio.google.com/app/apikey")

# --- Initialize Gemini client --------------------------------------------
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.warning("Please enter your Gemini API key to continue.")
    st.stop()

# --- Upload or link an image ---------------------------------------------
uploaded_img = st.file_uploader("Upload an image (JPG, PNG)", type=["jpg", "jpeg", "png"])
url_input = st.text_input("Or paste an image URL")

image_bytes = None
if uploaded_img is not None:
    image_bytes = uploaded_img.read()
elif url_input:
    try:
        image_bytes = requests.get(url_input).content
    except Exception as e:
        st.error(f"Failed to fetch image from URL: {e}")

# --- Text query -----------------------------------------------------------
prompt = st.text_area("Ask something about this image:", "Describe this image in detail.")

# --- Generate Answer ------------------------------------------------------
if st.button("Generate Answer"):
    if not image_bytes:
        st.warning("Please upload or provide an image URL first.")
    else:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        contents = [prompt, image_part]

        with st.spinner("Analyzing image using Gemini..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                )
                st.image(io.BytesIO(image_bytes), caption="Uploaded Image", use_container_width=True)
                st.markdown("### 🧩 Gemini’s Response")
                st.write(response.text)
            except Exception as e:
                st.error(f"Error from Gemini API: {e}")

st.markdown("---")
st.markdown("""
**Notes:**
- This uses the new `google.genai` SDK (no need for `google.cloud.vision`).
- Works directly with Gemini 2.5 multimodal models.
- Install dependencies:
  ```bash
  pip install google-genai streamlit requests
""")