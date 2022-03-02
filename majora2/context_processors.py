import os

# Some people access the file system or us processes to read git
# I think that is a bit creepy so lets just read the ENV
def majora_version(request):
    return {
        "majora_version": os.getenv("CURRENT_MAJORA_VERSION"),
        "majora_commit": os.getenv("CURRENT_MAJORA_HASH"),
        "majora_name": os.getenv("CURRENT_MAJORA_NAME"),
    }
