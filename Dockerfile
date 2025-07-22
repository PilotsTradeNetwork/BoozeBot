FROM python:3.10-slim-bookworm
RUN mkdir -p /usr/src/bot
WORKDIR /usr/src/bot
COPY setup.py .
COPY README.md .
COPY ptn ptn
COPY tests tests
RUN pip3 install .
RUN mkdir /root/boozedatabase
RUN ln -s /root/boozedatabase/.ptnboozebot.json /root/.ptnboozebot.json
RUN ln -s /root/boozedatabase/.env /root/.env
ENV PTN_BOOZEBOT_DATA_DIR=/root/boozedatabase
WORKDIR /root/boozedatabase
ENTRYPOINT ["/usr/local/bin/booze"]
