FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY backend/ /app/backend/

RUN useradd --create-home --shell /usr/sbin/nologin vpn-router \
    && mkdir -p /app/backend/data \
    && chown -R vpn-router:vpn-router /app/backend

USER vpn-router

EXPOSE 8080

CMD ["python3", "-m", "app.api.server"]

