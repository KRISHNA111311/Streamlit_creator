import streamlit as st
from google import genai
import json
import io
import zipfile
import re

# ------------------------ Utility Functions ------------------------
def init_state():
    defaults = {
        "phase": "collect",
        "user_text": "",
        "uploaded_files": [],
        "planning_response": None,
        "planning_answers": {},
        "design_response": None,
        "design_answers": {},
        "generated_code": None,
        "project_files": {},
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

def clean_json_text(raw: str) -> str:
    """Cleans Gemini output so it's valid JSON."""
    if not raw:
        return raw

    raw = raw.strip()

    # Remove Markdown code fences like ```json ... ```
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE | re.MULTILINE)
    raw = re.sub(r"```$", "", raw.strip(), flags=re.MULTILINE)

    # Remove leading “json” line
    if raw.lower().startswith("json"):
        raw = raw[4:].lstrip("\n\r ")

    # Convert escaped quotes
    raw = raw.replace('\\"', '"')

    # Remove trailing commas before closing braces/brackets
    raw = re.sub(r",\s*([\]}])", r"\1", raw)

    return raw.strip()

def parse_gemini_json(raw_text: str):
    """Try to parse Gemini JSON safely, retry after cleaning."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Empty Gemini response")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned = clean_json_text(raw_text)
        return json.loads(cleaned)

def zip_project(files_dict):
    path = "generated_project.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files_dict.items():
            if isinstance(content, str):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)
    return path

# ------------------------ Streamlit Setup ------------------------
st.set_page_config(page_title="🧠 Streamlit Project Maker", layout="wide")
st.title("🧠 Streamlit Project Maker — Gemini Assisted (Auto JSON Repair + Legacy Compatible)")

init_state()

# Sidebar for API key
with st.sidebar:
    st.header("🔑 Gemini API Setup")
    api_key = st.text_input("Enter your Gemini API key", type="password")
    st.caption("Uses legacy-compatible API (like recog3.py).")
    st.divider()
    st.write("**Phases:** Collect → Planning → Designing → Finalize → Generate")

if not api_key:
    st.warning("⚠️ Enter Gemini API key to continue.")
    st.stop()

client = genai.Client(api_key=api_key)

# ------------------------ Layout ------------------------
col1, col2 = st.columns([1, 2])

# ------------------------ Left: Inputs ------------------------
with col1:
    st.subheader("1️⃣ Project Inputs")
    st.session_state.user_text = st.text_area(
        "Describe your project idea:", st.session_state.user_text, height=200
    )

    uploaded = st.file_uploader(
        "Upload related files (optional):",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "pdf", "py", "txt", "md"],
    )
    if uploaded:
        st.session_state.uploaded_files = [
            {"name": f.name, "type": f.type, "bytes": f.read()} for f in uploaded
        ]

    if st.session_state.uploaded_files:
        st.markdown("**Files uploaded:**")
        for f in st.session_state.uploaded_files:
            st.write(f"- {f['name']} ({f['type']})")

    st.divider()
    if st.session_state.phase == "collect":
        if st.button("➡️ Start Planning Phase"):
            st.session_state.phase = "planning"
            st.rerun()
    else:
        if st.button("⏪ Reset Project"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            init_state()
            st.rerun()

# ------------------------ Right: Phases ------------------------
with col2:
    st.info(f"**Current Phase:** {st.session_state.phase.upper()}")

    # -------- Planning Phase --------
    if st.session_state.phase == "planning":
        st.subheader("📘 Planning Phase")

        if not st.session_state.planning_response:
            planning_prompt = f"""
You are an expert AI planner helping to design a Streamlit project.

User description:
{st.session_state.user_text}

Return STRICT JSON in this format:
{{
  "plan_text": "Planning explanation...",
  "questions": [
    {{"id": 1, "question": "Question text", "options": ["A","B","C"], "note": "why it matters"}}
  ],
  "additional_prompt": "Short open text prompt for user notes"
}}
Return ONLY valid JSON. No markdown or ``` fences.
"""
            with st.spinner("🧠 Asking Gemini for project plan..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[planning_prompt],
                    )
                    raw_text = getattr(resp, "text", "").strip()

                    if not raw_text:
                        st.error("❌ Gemini returned an empty response.")
                        st.stop()

                    try:
                        parsed = parse_gemini_json(raw_text)
                        st.session_state.planning_response = parsed
                        st.rerun()
                    except Exception as e:
                        st.error("⚠️ Gemini returned invalid JSON after repair:")
                        st.code(raw_text, language="json")
                        if st.button("🔁 Retry Planning"):
                            st.session_state.planning_response = None
                            st.rerun()
                        st.stop()
                except Exception as e:
                    st.error(f"Gemini error during planning: {e}")
                    st.stop()

        else:
            data = st.session_state.planning_response
            st.markdown("### 🧭 Project Plan")
            st.write(data.get("plan_text", ""))

            st.markdown("### 📋 Planning Questions")
            for q in data.get("questions", []):
                key = f"plan_q_{q['id']}"
                st.session_state.planning_answers[key] = st.radio(
                    f"{q['id']}. {q['question']}", q.get("options", []), key=key
                )

            st.session_state.planning_answers["plan_additional"] = st.text_area(
                data.get("additional_prompt", "Any other notes?"),
                value=st.session_state.planning_answers.get("plan_additional", ""),
            )

            if st.button("✅ Confirm Planning → Designing"):
                st.session_state.phase = "designing"
                st.rerun()

    # -------- Designing Phase --------
    elif st.session_state.phase == "designing":
        st.subheader("🎨 Designing Phase")

        if not st.session_state.design_response:
            design_prompt = f"""
You are designing a Streamlit implementation for this project.

User idea: {st.session_state.user_text}
Planning Summary: {st.session_state.planning_response.get('plan_text','')}
Planning Answers: {json.dumps(st.session_state.planning_answers)}

Return STRICT JSON:
{{
  "design_text": "3–6 short paragraphs about design and layout",
  "questions": [
    {{"id": 1, "question": "Design choice question", "options": ["A","B","C"]}}
  ],
  "additional_prompt": "Extra notes question"
}}
Return ONLY valid JSON (no markdown fences, no explanations).
"""
            with st.spinner("🎨 Asking Gemini for design suggestions..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[design_prompt],
                    )
                    raw = getattr(resp, "text", "").strip()

                    if not raw:
                        st.error("❌ Gemini returned an empty response.")
                        st.stop()

                    try:
                        parsed = parse_gemini_json(raw)
                        st.session_state.design_response = parsed
                        st.rerun()
                    except Exception as e:
                        st.error("⚠️ Gemini returned invalid JSON after auto-fix:")
                        st.code(raw, language="json")
                        if st.button("🔁 Retry Design Phase"):
                            st.session_state.design_response = None
                            st.rerun()
                        st.stop()
                except Exception as e:
                    st.error(f"Gemini error during designing: {e}")
                    st.stop()

        else:
            data = st.session_state.design_response
            st.markdown("### 💡 Design Summary")
            st.write(data.get("design_text", ""))

            st.markdown("### 🎛️ Design Questions")
            for q in data.get("questions", []):
                key = f"design_q_{q['id']}"
                st.session_state.design_answers[key] = st.radio(
                    f"{q['id']}. {q['question']}", q.get("options", []), key=key
                )

            st.session_state.design_answers["design_additional"] = st.text_area(
                data.get("additional_prompt", "Any other notes?"),
                value=st.session_state.design_answers.get("design_additional", ""),
            )

            if st.button("✅ Confirm Design → Finalize"):
                st.session_state.phase = "finalize"
                st.rerun()

    # -------- Finalize Phase --------
    elif st.session_state.phase == "finalize":
        st.subheader("🧾 Final Review")
        st.write("### User Idea")
        st.write(st.session_state.user_text)
        st.write("### Planning Summary")
        st.write(st.session_state.planning_response.get("plan_text", ""))
        st.write("### Design Summary")
        st.write(st.session_state.design_response.get("design_text", ""))

        if st.button("🚀 Generate Streamlit Project"):
            st.session_state.phase = "generate"
            st.rerun()

    # -------- Generate Phase --------
    elif st.session_state.phase == "generate":
        st.subheader("⚙️ Generating Code")

        if not st.session_state.generated_code:
            code_prompt = f"""
You are a senior Python developer.
Generate a Streamlit project file named `generated_app.py`
using the following context.

User Idea: {st.session_state.user_text}
Planning: {json.dumps(st.session_state.planning_response)}
Design: {json.dumps(st.session_state.design_response)}

Return ONLY valid Python code (no markdown or comments).
"""
            with st.spinner("💻 Asking Gemini to generate code..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[code_prompt],
                    )
                    code = getattr(resp, "text", "").strip()
                    if not code:
                        st.error("Gemini returned an empty code response.")
                        st.stop()

                    st.session_state.generated_code = code
                    files = {
                        "generated_app.py": code,
                        "README.md": "# Auto-generated Streamlit Project\nCreated via Gemini Project Maker.",
                    }
                    for f in st.session_state.uploaded_files:
                        files[f["name"]] = f["bytes"]
                    st.session_state.project_files = files
                    st.rerun()
                except Exception as e:
                    st.error(f"Gemini error during code generation: {e}")
                    st.stop()
        else:
            st.success("✅ Code generated successfully!")
            st.download_button(
                "📄 Download generated_app.py",
                st.session_state.generated_code,
                file_name="generated_app.py",
                mime="text/x-python",
            )
            with st.expander("🔍 Preview Code"):
                st.code(st.session_state.generated_code, language="python")

            zip_path = zip_project(st.session_state.project_files)
            with open(zip_path, "rb") as f:
                st.download_button(
                    "📦 Download Full Project (ZIP)",
                    data=f,
                    file_name="generated_project.zip",
                    mime="application/zip",
                )

            if st.button("🔁 Start New Project"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                init_state()
                st.rerun()

# ------------------------ Footer ------------------------
st.markdown("---")
st.caption("✨ Auto JSON Repair • Legacy Google GenAI Compatible • One-Retry Parser")
