FROM alpine:3.21

RUN apk add --no-cache bash openssh-client netcat-openbsd
COPY services/llm-tunnel/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
