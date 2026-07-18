FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /app app

COPY --chown=app:app . /app

RUN DJANGO_SECRET_KEY=build-only-static-key \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS=api.ladyshelf.site \
    python manage.py collectstatic --noinput

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/api/v1/health', headers={'Host': 'api.ladyshelf.site', 'X-Forwarded-Proto': 'https'}); urllib.request.urlopen(request, timeout=3)"]

CMD ["gunicorn", "config.wsgi:application", "--config", "python:config.gunicorn"]
