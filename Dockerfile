FROM stanfordnmbl/opensim-python:4.3

COPY . .
RUN pip --no-cache-dir install -r requirements.txt

CMD ["python3", "function.py"]