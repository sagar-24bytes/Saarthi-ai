import os

def search_files(root_directory, query):

    matches = []

    query_words = query.lower().replace(".", " ").split()

    for root, dirs, files in os.walk(root_directory):

        # Check files
        for file in files:

            filename = file.lower().replace(".", " ")

            if all(word in filename for word in query_words):
                matches.append(os.path.join(root, file))

        # Check folders (NEW)
        for directory in dirs:

            dirname = directory.lower()

            if all(word in dirname for word in query_words):
                matches.append(os.path.join(root, directory))

    return matches
