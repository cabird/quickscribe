import json

# Sample JSON input
data = {
    "source": "https://quickscribestorage.blob.core.windows.net/recordings/test.mp3",
    "timestamp": "2024-10-23T17:23:38Z",
    "durationInTicks": 36465600000,
    "duration": "PT1H46.56S",
    "combinedRecognizedPhrases": [],
    "recognizedPhrases": [
        # Example entries, please add all from the JSON you provided
    ]
}

# Function to generate the transcript
def generate_transcript(data):
    transcript = []
    last_speaker = None
    last_text = []

    for phrase in data["recognizedPhrases"]:
        current_speaker = phrase["speaker"]
        current_text = phrase["nBest"][0]["display"]

        # Combine consecutive text if same speaker
        if current_speaker == last_speaker:
            last_text.append(current_text)
        else:
            if last_text:  # Add the previous speaker's combined text
                transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")
            # Reset for new speaker
            last_speaker = current_speaker
            last_text = [current_text]

    # Append the last speaker's text after the loop
    if last_text:
        transcript.append(f"Speaker {last_speaker}: " + " ".join(last_text) + "\n")

    # Print the formatted transcript
    for line in transcript:
        print(line)

data = json.load(open("azure_diarization.json"))

# Call the function with the JSON data
generate_transcript(data)
