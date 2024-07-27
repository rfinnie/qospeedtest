FROM python:3.10

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn .

USER nobody
ENV PYTHONPATH=/usr/local/lib/python
CMD [ "gunicorn", "-b", "0.0.0.0:8000", "-k", "gthread", "--error-logfile", "-", "--capture-output", "qospeedtest.wsgi:application" ]
EXPOSE 8000/tcp
