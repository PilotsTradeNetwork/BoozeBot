FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /usr/src/bot /root/boozedatabase \
    && ln -sf /root/boozedatabase/.ptnboozebot.json /root/.ptnboozebot.json \
    && ln -sf /root/boozedatabase/.env /root/.env
WORKDIR /usr/src/bot
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY pyproject.toml .
COPY README.md .
COPY ptn ptn
RUN pip3 install .
ENV PTN_BOOZEBOT_DATA_DIR=/root/boozedatabase
WORKDIR /root/boozedatabase
ENTRYPOINT ["/usr/local/bin/booze"]
