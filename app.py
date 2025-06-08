import streamlit as st
import pandas as pd
import os
import io
import zipfile
import openai
import requests

st.set_page_config(page_title="VoiceOutReach.ai", layout="centered")
st.title("🎙️ VoiceOutReach.ai v2 – Now with Preview & Variable Suggestions 🚀")
# --- API Keys ---
openai_key = st.text_input("🔑 OpenAI API Key", type="password")
elevenlabs_key = st.text_input("🎤 ElevenLabs API Key", type="password")
voice_id = st.text_input("🗣️ ElevenLabs Voice ID", value="YOUR_DEFAULT_VOICE_ID")

# --- Message Template ---
template = st.text_area(
    "📄 Message Template (use variables like {first_name}, {position}, {quick_jd}, etc.)",
    "Hi {first_name}, I noticed you're hiring for {job_title} at {company_name}. {quick_jd} I'd love to connect and show how I can help. Open to a quick 5-min call?"
)

generate_quick_jd = st.checkbox("✨ Auto-generate {quick_jd} from job description?", value=True)

# --- Follow-Up Settings ---
generate_followup = st.checkbox("🔁 Generate Follow-Up Message?", value=False)

followup_template = st.text_area(
    "📄 Follow-Up Template",
    "Hey {first_name}, just following up on my last message about {job_title}. Would love to connect!",
    disabled=not generate_followup
)

followup_delay = st.selectbox(
    "⏳ Follow-up Delay (in days)",
    options=[i for i in range(1, 11)],
    index=2,
    disabled=not generate_followup
)

# --- Sample CSV ---
sample_csv = """First Name,Position,Hiring for Job Title,Company name,Description
Alice,Founder,Video Editor,MediaCorp,"We’re looking for a creative video editor to join our team."
Bob,Head of Product,UI/UX Designer,Designly,"Seeking a UX designer passionate about user-centric design."
"""
st.download_button(
    label="📥 Download Sample CSV Format",
    data=sample_csv,
    file_name="sample_leads_template.csv",
    mime="text/csv"
)

# --- File Upload ---
uploaded_file = st.file_uploader("📤 Upload Leads CSV", type=["csv"])

if uploaded_file and openai_key and elevenlabs_key:
    df = pd.read_csv(uploaded_file)
    st.success("✅ File uploaded. Ready to generate messages.")

    # Show variable suggestions
    st.markdown("### 🧩 Available Template Variables:")
    column_vars = [col.strip().replace(" ", "_").lower() for col in df.columns]
    if generate_quick_jd:
        column_vars.append("quick_jd")
    st.code(", ".join(f"{{{col}}}" for col in column_vars), language="markdown")

    if st.button("🚀 Generate Voice Notes"):
        output_dir = "voice_notes"
        os.makedirs(output_dir, exist_ok=True)
        openai.api_key = openai_key

        results = []

        for index, row in df.iterrows():
            try:
                row_dict = {
                    k.strip().replace(" ", "_").lower(): str(v).strip()
                    for k, v in row.items()
                }

                # GPT: quick_jd
                job_description = row_dict.get("description", "")
                quick_jd = ""
                if generate_quick_jd and job_description:
                    try:
                        prompt = f"Write a professional, attention-grabbing 1-sentence opening based on this job description:\n\n{job_description}"
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        quick_jd = response.choices[0].message.content.strip()
                    except Exception as e:
                        st.error(f"❌ GPT Error for {row_dict.get('first_name', '')}: {e}")
                        quick_jd = "(quick_jd failed)"
                row_dict["quick_jd"] = quick_jd

                # Main message
                try:
                    message = template.format(**row_dict)
                except KeyError as ke:
                    st.error(f"⚠️ Missing variable in row {index+1}: {ke}")
                    continue

                st.markdown(f"**🔎 Message Preview for {row_dict.get('first_name', '')}:**")
                st.code(message)

                # ElevenLabs TTS
                tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": elevenlabs_key,
                    "Content-Type": "application/json"
                }
                tts_payload = {
                    "text": message,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5
                    }
                }

                response = requests.post(tts_url, headers=headers, json=tts_payload)
                first_name = row_dict.get("first_name", "lead")
                job_title = row_dict.get("hiring_for_job_title", "role")
                audio_path = f"{output_dir}/{first_name}_{job_title}.mp3"

                with open(audio_path, "wb") as f:
                    f.write(response.content)

                st.audio(audio_path, format="audio/mp3")

                # Follow-Up
                followup_message = ""
                followup_audio_path = ""
                if generate_followup:
                    try:
                        followup_message = followup_template.format(**row_dict)
                        tts_payload["text"] = followup_message
                        response = requests.post(tts_url, headers=headers, json=tts_payload)
                        followup_audio_path = f"{output_dir}/{first_name}_{job_title}_followup.mp3"
                        with open(followup_audio_path, "wb") as f:
                            f.write(response.content)
                        st.markdown(f"**📨 Follow-Up Message Preview:**")
                        st.code(followup_message)
                        st.audio(followup_audio_path, format="audio/mp3")
                    except Exception as e:
                        st.error(f"❌ Follow-up Error: {e}")

                results.append({
                    "Name": row_dict.get("first_name", ""),
                    "Job Title": row_dict.get("hiring_for_job_title", ""),
                    "Message": message,
                    "Voice File": os.path.basename(audio_path),
                    "Follow-Up Message": followup_message,
                    "Follow-Up File": os.path.basename(followup_audio_path) if followup_audio_path else "",
                    "Follow-Up Delay (Days)": followup_delay if generate_followup else ""
                })

            except Exception as e:
                st.error(f"❌ Error on row {index+1}: {e}")

        # Save results CSV
        results_df = pd.DataFrame(results)
        csv_buffer = io.StringIO()
        results_df.to_csv(csv_buffer, index=False)
        st.download_button("📄 Download Message CSV", data=csv_buffer.getvalue(), file_name="generated_messages.csv", mime="text/csv")

        # Save audio files ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for file in os.listdir(output_dir):
                zipf.write(os.path.join(output_dir, file), arcname=file)
        zip_buffer.seek(0)
        st.download_button("📦 Download Voice Notes ZIP", data=zip_buffer, file_name="voice_notes.zip", mime="application/zip")

else:
    st.info("👆 Upload your CSV and enter API keys to get started.")
