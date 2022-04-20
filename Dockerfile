FROM python:3.8.2
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y cron
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install gunicorn[gevent]

COPY crontab.txt /opt
RUN crontab /opt/crontab.txt
CMD ["cron", "-f"]
EXPOSE 5000
RUN python src/utils.py &
ENTRYPOINT gunicorn --worker-class gevent --workers 8 --bind 0.0.0.0:5000 app:app --log-level info