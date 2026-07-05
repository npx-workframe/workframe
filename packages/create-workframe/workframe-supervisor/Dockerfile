FROM python:3-alpine

# ponytail: host.setup_public_https and compose restart shell out to docker CLI (socket is mounted).
# set-compose-public-url.mjs needs node on the supervisor image.
RUN apk add --no-cache docker-cli docker-cli-compose bash nodejs npm

WORKDIR /app
COPY server.py profile_secret_policy.py ./

EXPOSE 8090
CMD ["python3", "server.py"]
