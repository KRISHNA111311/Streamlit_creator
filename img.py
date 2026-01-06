import streamlit as st
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import io

# --- PAGE CONFIG ---
st.set_page_config(page_title="PixelCraft Studio", layout="wide")

def main():
    st.title("🎨 PixelCraft: Professional Image Processor")
    st.markdown("Upload an image and use the sidebar to apply transformations.")

    # --- SIDEBAR: UPLOAD & SETTINGS ---
    st.sidebar.header("1. Upload Image")
    uploaded_file = st.sidebar.file_uploader("Choose a file...", type=['jpg', 'jpeg', 'png'])

    if uploaded_file is not None:
        # Load Image
        image = Image.open(uploaded_file)
        img_array = np.array(image.convert('RGB'))

        # Sidebar Navigation
        st.sidebar.markdown("---")
        mode = st.sidebar.selectbox("Choose Category", [
            "Basic Adjustments", 
            "Filters & Effects", 
            "Transformations", 
            "Edge & Feature Detection"
        ])

        processed_img = img_array.copy()

        # --- MODE 1: BASIC ADJUSTMENTS ---
        if mode == "Basic Adjustments":
            st.sidebar.subheader("Fine-tuning")
            brightness = st.sidebar.slider("Brightness", 0.0, 3.0, 1.0)
            contrast = st.sidebar.slider("Contrast", 0.0, 3.0, 1.0)
            sharpness = st.sidebar.slider("Sharpness", 0.0, 5.0, 1.0)
            color = st.sidebar.slider("Color Saturation", 0.0, 5.0, 1.0)

            # Applying PIL Enhancements
            enhancer = ImageEnhance.Brightness(image)
            temp_img = enhancer.enhance(brightness)
            enhancer = ImageEnhance.Contrast(temp_img)
            temp_img = enhancer.enhance(contrast)
            enhancer = ImageEnhance.Sharpness(temp_img)
            temp_img = enhancer.enhance(sharpness)
            enhancer = ImageEnhance.Color(temp_img)
            processed_img = np.array(enhancer.enhance(color))

        # --- MODE 2: FILTERS & EFFECTS ---
        elif mode == "Filters & Effects":
            effect = st.sidebar.radio("Select Effect", [
                "Original", "Grayscale", "Sepia", "Invert", "Blur", "Sketch"
            ])

            if effect == "Grayscale":
                processed_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            elif effect == "Sepia":
                kernel = np.array([[0.393, 0.769, 0.189],
                                   [0.349, 0.686, 0.168],
                                   [0.272, 0.534, 0.131]])
                processed_img = cv2.transform(img_array, kernel)
                processed_img = np.clip(processed_img, 0, 255)
            elif effect == "Invert":
                processed_img = cv2.bitwise_not(img_array)
            elif effect == "Blur":
                blur_rate = st.sidebar.slider("Blur Intensity", 1, 99, 15, step=2)
                processed_img = cv2.GaussianBlur(img_array, (blur_rate, blur_rate), 0)
            elif effect == "Sketch":
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                inv = cv2.bitwise_not(gray)
                blur = cv2.GaussianBlur(inv, (21, 21), 0)
                processed_img = cv2.divide(gray, 255 - blur, scale=256)

        # --- MODE 3: TRANSFORMATIONS ---
        elif mode == "Transformations":
            angle = st.sidebar.slider("Rotate (Degrees)", -180, 180, 0)
            flip = st.sidebar.selectbox("Flip Image", ["None", "Horizontal", "Vertical"])
            
            # Rotation using PIL for easier handling
            temp_img = Image.fromarray(img_array).rotate(angle, expand=True)
            if flip == "Horizontal":
                temp_img = ImageOps.mirror(temp_img)
            elif flip == "Vertical":
                temp_img = ImageOps.flip(temp_img)
            processed_img = np.array(temp_img)

        # --- MODE 4: EDGE DETECTION ---
        elif mode == "Edge & Feature Detection":
            algo = st.sidebar.selectbox("Algorithm", ["Canny Edge", "Thresholding"])
            if algo == "Canny Edge":
                t1 = st.sidebar.slider("Threshold 1", 0, 250, 100)
                t2 = st.sidebar.slider("Threshold 2", 0, 250, 200)
                processed_img = cv2.Canny(img_array, t1, t2)
            else:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                thresh_val = st.sidebar.slider("Threshold Value", 0, 255, 127)
                _, processed_img = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

        # --- DISPLAY AREA ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Original")
            st.image(image, use_container_width=True)
        
        with col2:
            st.subheader("Processed")
            st.image(processed_img, use_container_width=True)

        # --- DOWNLOAD BUTTON ---
        res_img = Image.fromarray(processed_img)
        buf = io.BytesIO()
        res_img.save(buf, format="PNG")
        byte_im = buf.getvalue()
        
        st.sidebar.markdown("---")
        st.sidebar.download_button(
            label="Download Processed Image",
            data=byte_im,
            file_name="processed_image.png",
            mime="image/png"
        )
    else:
        # Welcome Screen if no image
        st.info("Please upload an image in the sidebar to begin.")
        st.image("https://images.unsplash.com/photo-1542038784456-1ea8e935640e?auto=format&fit=crop&q=80&w=1000", caption="Ready to edit?")

if __name__ == "__main__":
    main()