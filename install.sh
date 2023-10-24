#!/bin/bash
pip install -r requirements.txt --upgrade


sudo apt install nginx  --upgrade

sudo rm /etc/nginx/sites-enabled/*


sudo cp python-metar.site  /etc/nginx/sites-available/python-metar

sudo ln -s /etc/nginx/sites-available/python-metar /etc/nginx/sites-enabled



sudo systemctl stop python-metar
sudo systemctl disable python-metar

sudo cp python-metar.service /etc/systemd/system/


sudo systemctl enable python-metar
sudo systemctl start python-metar
sudo systemctl status python-metar
sudo journalctl -u python-metar

sudo systemctl enable nginx
sudo systemctl restart nginx
sudo systemctl status nginx
sudo journalctl -u nginx

sudo nginx -t

