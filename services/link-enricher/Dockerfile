FROM golang:1.26 AS builder

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/link-enricher

FROM alpine:3.20
RUN apk add --no-cache ca-certificates && adduser -D -u 1000 appuser

COPY --from=builder /bin/link-enricher /bin/link-enricher

USER appuser

ENTRYPOINT ["/bin/link-enricher"]
