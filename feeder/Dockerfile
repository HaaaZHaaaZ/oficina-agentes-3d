# Writes the live state of Hermes and Claude into the office container (see feeder.py).
FROM python:3.14-alpine
COPY feeder.py /feeder.py
CMD ["python", "-I", "-u", "/feeder.py"]
