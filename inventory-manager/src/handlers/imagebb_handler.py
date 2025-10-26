import requests

class ImageBBHandler:
    """
    Handles uploading local images to ImageBB.
    Returns a publicly accessible direct image URL.
    Requires an API key from https://api.imgbb.com/.
    """

    API_UPLOAD_URL = "https://api.imgbb.com/1/upload"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def upload_from_file(self, file_path: str) -> str:
        """
        Upload a local image file to ImageBB and return the direct URL.
        """
        with open(file_path, "rb") as f:
            payload = {
                "key": self.api_key,
            }
            files = {
                "image": f
            }
            response = requests.post(self.API_UPLOAD_URL, data=payload, files=files)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # The 'url' field is a direct link to the image
                return data["data"]["url"]
            else:
                raise Exception(f"ImageBB upload failed: {data}")
        else:
            raise Exception(f"HTTP error {response.status_code}: {response.text}")


# Example usage:
if __name__ == "__main__":
    API_KEY = "YOUR_IMGBB_API_KEY"
    handler = ImageBBHandler(API_KEY)
    direct_url = handler.upload_from_file("SportyThievz.jpg")
    print("Uploaded image URL:", direct_url)
