FROM python:3.11-slim 

RUN apt-get update && apt-get install -y bash

WORKDIR /app

COPY requirements.txt .
COPY app.py .
COPY startup.sh .

RUN pip install --no-cache-dir -r requirements.txt
RUN chmod +x startup.sh

EXPOSE 8501

CMD ["bash", "-c", "./startup.sh && streamlit run app.py --server.port=8501 --server.address=0.0.0.0"]
