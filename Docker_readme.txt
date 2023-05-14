# To build a new docker image

$ docker build -t yourname/boozebot:latest .

# To run in a container

Make a local dir to store your .env and database files

$ mkdir /opt/boozebot
$ cp .env /opt/boozebot/
$ cp .ptnboozebot.json /opt/boozebot/
$ mkdir /opt/boozebot/dumps

Run the container:

$ docker run -d --restart unless-stopped --name boozebot -v /opt/boozebot:/root/boozedatabase yourname/boozebot:latest
