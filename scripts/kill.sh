#!/bin/sh
echo "SIGTERM"
killall uwsgi;
killall celery;

echo "Waiting politely for uwsgi and celery to clean up before sending the big guns"
sleep 3;

echo "SIGKILL"
killall -9 uwsgi;
killall -9 celery;
