FROM python:3.13-slim-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /usr/src/bot
COPY . .
RUN pip3 wheel --no-deps -w wheels . && pip3 download -d wheels -r requirements.txt

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/src/bot /root/boozedatabase \
    && ln -sf /root/boozedatabase/.ptnboozebot.json /root/.ptnboozebot.json \
    && ln -sf /root/boozedatabase/.env /root/.env
WORKDIR /usr/src/bot
COPY --from=build /usr/src/bot/wheels wheels
COPY README.md .
COPY pyproject.toml .
COPY requirements.txt .
COPY ptn ptn
RUN pip3 install -f wheels -r requirements.txt && pip3 install -f wheels ptn.boozebot \
    && rm -rf wheels && apt-get remove -y git && apt autoremove -y && apt clean
ENV PTN_BOOZEBOT_DATA_DIR=/root/boozedatabase
WORKDIR /root/boozedatabase
ENTRYPOINT ["/usr/local/bin/booze"]