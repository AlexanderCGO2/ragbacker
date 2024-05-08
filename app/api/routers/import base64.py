import base64

def encode_credentials(file_path):
    # Read the contents of the JSON file
    with open(file_path, 'rb') as file:
        file_contents = file.read()
    
    # Encode these contents in base64
    encoded_credentials = base64.b64encode(file_contents).decode('utf-8')
    
    return encoded_credentials

if __name__ == "__main__":
    file_path = 'path/to/your/firebase_credentials.json'  # Replace with your file path
    encoded_credentials = encode_credentials(file_path)
    print("Encoded credentials:", encoded_credentials)
