import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "flask_demo_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "flask_demo_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)

# Logging setup
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(message)s")

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

file_handler = RotatingFileHandler("logs/app.log", maxBytes=1_000_000, backupCount=3)
file_handler.setFormatter(formatter)

logger.handlers.clear()
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


@app.before_request
def before_request():
    request.start_time = time.time()


@app.after_request
def after_request(response):
    duration = time.time() - getattr(request, "start_time", time.time())
    endpoint = request.path

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code)
    ).inc()

    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(duration)

    log_line = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": round(duration * 1000, 2),
        "remote_addr": request.remote_addr,
    }
    logger.info(json.dumps(log_line))

    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/hello", methods=["GET"])
def hello():
    name = request.args.get("name", "world")
    return jsonify({"message": f"hello, {name}"}), 200


# Mount /metrics using Prometheus WSGI app
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    "/metrics": make_wsgi_app()
})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)