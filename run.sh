#!/bin/bash
$HOME/.local/bin/gunicorn --workers 1 --thread 16 --bind :8000 --access-logfile - --access-logformat "%(h)s %(l)s %(u)s %(t)s '%(r)s' %(s)s %(b)s '%(f)s' '%(a)s' %(M)s" app:app 
