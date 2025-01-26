FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
   wget \
   ffmpeg \
   libsndfile1 \
   build-essential \
   python3-dev \
   && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RUN mkdir -p /data/models/base
# RUN wget -O /data/models/base/config.json https://huggingface.co/guillaumekln/faster-whisper-base/resolve/main/config.json
# RUN wget -O /data/models/base/model.bin https://huggingface.co/guillaumekln/faster-whisper-base/resolve/main/model.bin
# RUN wget -O /data/models/base/tokenizer.json https://huggingface.co/guillaumekln/faster-whisper-base/resolve/main/tokenizer.json
# RUN wget -O /data/models/base/vocabulary.txt https://huggingface.co/guillaumekln/faster-whisper-base/resolve/main/vocabulary.txt

# RUN mkdir -p /data/models/small 
# RUN wget -O /data/models/small/config.json https://huggingface.co/guillaumekln/faster-whisper-small/resolve/main/config.json
# RUN wget -O /data/models/small/model.bin https://huggingface.co/guillaumekln/faster-whisper-small/resolve/main/model.bin
# RUN wget -O /data/models/small/tokenizer.json https://huggingface.co/guillaumekln/faster-whisper-small/resolve/main/tokenizer.json
# RUN wget -O /data/models/small/vocabulary.txt https://huggingface.co/guillaumekln/faster-whisper-small/resolve/main/vocabulary.txt

COPY app/ .
WORKDIR /

ENV PORT 8080
CMD ["python", "-m", "app.main"]