import streamlit as st
from google import genai
from google.genai import types
import requests
import io
from pdf2image import convert_from_bytes
from PIL import Image

# ----------------------------------------------------------
# Streamlit page setup
# ----------------------------------------------------------
st.set_page_config(page_title="Gemini 2.5 Chat + Vision", page_icon="🧠", layout="wide")
st.title("🧠 Gemini 2.5 Chat + Vision (Image + PDF Recognition)")

# ----------------------------------------------------------
# Sidebar: API key input
# ----------------------------------------------------------
with st.sidebar:
    st.header("🔑 API Setup")
    api_key = st.text_input("Enter your Gemini API Key", type="password")
    st.caption("Get it from [Google AI Studio](https://aistudio.google.com/app/apikey).")

# ----------------------------------------------------------
# Configure Gemini client
# ----------------------------------------------------------
if not api_key:
    st.warning("Please provide your Gemini API key in the sidebar to continue.")
    st.stop()

client = genai.Client(api_key=api_key)

# ----------------------------------------------------------
# Upload Section
# ----------------------------------------------------------
st.subheader("📎 Upload an image or a PDF document")

uploaded_file = st.file_uploader(
    "Upload File (Supported: JPG, PNG, PDF)",
    type=["jpg", "jpeg", "png", "pdf"]
)

url_input = st.text_input("Or paste an image URL (optional)")

# ----------------------------------------------------------
# Helper functions
# ----------------------------------------------------------
def image_to_bytes(pil_image):
    buf = io.BytesIO()
    pil_image.save(buf, format="JPEG")
    return buf.getvalue()

def pdf_to_images(pdf_bytes):
    """Convert PDF to list of PIL images."""
    return convert_from_bytes(pdf_bytes)

# ----------------------------------------------------------
# User Question
# ----------------------------------------------------------
prompt = st.text_area(
    "Ask something about the uploaded image or document:",
    "Describe the image or summarize this document."
)

# ----------------------------------------------------------
# Generate Answer
# ----------------------------------------------------------
if st.button("🔍 Analyze with Gemini"):
    content_parts = [prompt]
    file_attached = False

    # Handle uploaded or URL image
    if uploaded_file:
        file_attached = True
        if uploaded_file.type in ["image/jpeg", "image/png"]:
            st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
            image_bytes = uploaded_file.read()
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=uploaded_file.type)
            content_parts.append(image_part)

        elif uploaded_file.type == "application/pdf":
            st.info("Processing PDF pages into images...")
            pdf_bytes = uploaded_file.read()
            pages = pdf_to_images(pdf_bytes)

            for i, page in enumerate(pages):
                st.image(page, caption=f"PDF Page {i+1}", use_container_width=True)
                img_bytes = image_to_bytes(page)
                img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                content_parts.append(img_part)

    elif url_input:
        file_attached = True
        try:
            image_bytes = requests.get(url_input).content
            st.image(io.BytesIO(image_bytes), caption="Image from URL", use_container_width=True)
            img_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            content_parts.append(img_part)
        except Exception as e:
            st.error(f"Could not load image from URL: {e}")

    # ------------------------------------------------------
    # Allow text-only queries (no upload or URL)
    # ------------------------------------------------------
    if not file_attached:
        st.info("💬 Text-only question mode (no image or document attached).")

    # Send content to Gemini
    with st.spinner("Analyzing with Gemini 2.5..."):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=content_parts,
            )
            st.subheader("🧩 Gemini's Response")
            st.write(response.text)
        except Exception as e:
            st.error(f"Gemini API error: {e}")

# ----------------------------------------------------------
# Footer Info
# ----------------------------------------------------------
st.markdown("---")
st.markdown("""
### 🛠️ Requirements
Run the following to install dependencies:
```bash
pip install -U streamlit google-genai pdf2image pillow requests
""")