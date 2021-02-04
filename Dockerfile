FROM python:3.7-slim

WORKDIR /

ADD . /

RUN apt-get update && apt-get install -y libgomp1

RUN pip install --trusted-host pypi.python.org -r requirements.txt

ENTRYPOINT ["python"]

CMD ["/index.py"]