FROM python:3.9.12-slim
COPY requirements.txt .

# install psycopg2 dependencies
RUN apt-get update
RUN apt-get install -y libpq-dev gcc

RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
ENTRYPOINT ["python", "app/app.py"]