FROM python:3
COPY . .
RUN pip3 install -r requirements.txt
COPY . .
CMD python3 ./main.py