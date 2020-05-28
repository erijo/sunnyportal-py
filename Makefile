scripts += bin/sunnyportal2file
scripts += bin/sunnyportal2pvoutput
scripts += bin/testclient.py

.PHONY: black
black:
	black $(scripts) sunnyportal/*.py
