FROM stanfordnmbl/opensim-python:4.3

# Copy the requirements.txt file to our Docker image
ADD requirements.txt .

# Install the requirements.txt
RUN pip install -r requirements.txt
