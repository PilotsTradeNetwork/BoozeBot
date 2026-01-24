FROM python:3.13-slim-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /usr/src/bot
COPY .git/ .git/
COPY pyproject.toml .
COPY requirements.txt .
COPY ptn ptn
RUN pip3 wheel --no-deps -w wheels .
RUN pip3 download -d wheels -r requirements.txt

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /usr/src/bot /root/boozedatabase \
    && ln -sf /root/boozedatabase/.ptnboozebot.json /root/.ptnboozebot.json \
    && ln -sf /root/boozedatabase/.env /root/.env
WORKDIR /usr/src/bot
COPY --from=build /usr/src/bot/wheels wheels
COPY README.md .
COPY pyproject.toml .
COPY requirements.txt .
COPY ptn ptn
RUN pip3 install -f wheels -r requirements.txt
RUN pip3 install -f wheels ptn.boozebot
ENV PTN_BOOZEBOT_DATA_DIR=/root/boozedatabase
RUN rm -rf wheels
RUN apt-get remove -y git && apt autoremove -y && apt clean
WORKDIR /root/boozedatabase
ENTRYPOINT ["/usr/local/bin/booze"]