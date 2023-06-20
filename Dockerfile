FROM stanfordnmbl/opensim-python:4.3

# ENV PYTHONPATH /usr/bin/python3.8/site-packages

ENV API_TOKEN "2782a2e70d14188c6f453ee93171451778f58b14"
ENV API_URL "https://dev.opencap.ai"

# Copy the requirements.txt file to our Docker image
COPY requirements.txt .
RUN pip --no-cache-dir install -r requirements.txt

COPY function.py .
COPY utils.py .
COPY utilsAPI.py .
COPY utilsAuthentication.py .
COPY utilsKinematics.py .
COPY utilsPlotting.py .
COPY utilsProcessing.py .

CMD ["python3", "function.py"]