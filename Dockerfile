FROM python:3.10-alpine
COPY . .
RUN pip3 install -r requirements.txt
COPY . .
CMD python3 ./main.py