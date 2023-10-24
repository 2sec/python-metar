#!/bin/bash
pip install -r requirements.txt --upgrade

sudo apt install nginx  --upgrade

sudo rm /etc/nginx/sites-enabled/*


sudo cp python-metar.site  /etc/nginx/sites-available/python-metar

sudo ln -s /etc/nginx/sites-available/python-metar /etc/nginx/sites-enabled




sudo cp python-metar.service /etc/systemd/system/

sudo systemctl enable python-metar
sudo systemctl start python-metar
sudo journalctl -u python-metar

sudo nginx -t

