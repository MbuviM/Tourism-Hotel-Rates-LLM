# Install Libraries
from openai import OpenAI
from dotenv import load_dotenv
import os 

#Create client
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Upload file
file_ids = []
file = client.files.create(
    file=open("2024_rack_rates.pdf", "rb"),
    purpose='assistants'
)
file_ids.append(file.id)

# Create an assistant
assistant = client.beta.assistants.create(
    model='gpt-4o-mini',  
    name='Tourism Rate Explainer',
    tools=[{'type': 'file_search'}],  
    instructions="You are an assistant. Help your client understand hotel rates using the provided document."
)

# Create a vector store caled "Hotel Rates"
vector_store = client.beta.vector_stores.create(name="Hotel Rates")
 
# Ready the files for upload to OpenAI
file_path = ["2024_rack_rates.pdf"]
file_streams = [open(path, "rb") for path in file_path]
 
# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
  vector_store_id=vector_store.id, files=file_streams
)
 
# You can print the status and the file counts of the batch to see the result of this operation.
print(file_batch.status)
print(file_batch.file_counts)

# Update assistant tool resources
assistant = client.beta.assistants.update(
  assistant_id=assistant.id,
  tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
)

# Save the assistant and vector store IDs for use in the Streamlit app
with open('assistant_config.txt', 'w') as config_file:
    config_file.write(f"ASSISTANT_ID={assistant.id}\n")
    config_file.write(f"VECTOR_STORE_ID={vector_store.id}\n")
    config_file.write(f"FILE_ID={file.id}\n")

# Upload the user provided file to OpenAI
message_file = client.files.create(
  file=open("2024_rack_rates.pdf", "rb"), purpose="assistants"
)

thread = client.beta.threads.create()

#  Create a thread and add a message to thread
thread = client.beta.threads.create(
  messages=[
    {
      "role": "user",
      "content": "As a 30 year old, how much should I have to be able to spend 2 nights in Hemingways Eden Residence?",
      # Attach the new file to the message.
      "attachments": [
        { "file_id": message_file.id, "tools": [{"type": "file_search"}] }
      ],
    }
  ]
)

# Use the create and poll SDK helper to create a run and poll the status of
# the run until it's in a terminal state.

# After creating and polling the run
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id, assistant_id=assistant.id
)

print(f"Run status: {run.status}")
print(f"Run details: {run}")

# Retrieve messages
messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

# Check if there are any messages
if not messages:
    print("Message not found.")
else:
    # Print the number of messages
    print(f"Number of messages: {len(messages)}")
    
    # Try to access the first message (which should be the assistant's response)
    try:
        message_content = messages[0].content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        print(message_content.value)
        print("\n".join(citations))
    except IndexError:
        print("Unexpected message structure. Here's what we received:")
        print(messages)
    except AttributeError:
        print("Unexpected message content structure. Here's what we received:")
        print(messages[0].content if messages else "No content")