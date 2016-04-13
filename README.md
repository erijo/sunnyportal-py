# sunnyportal-py
Python module to access PV systems in [Sunny Portal](https://www.sunnyportal.com/).

# sunnyportal2pvoutput
The script [sunnyportal2pvoutput](bin/sunnyportal2pvoutput) can be used to send
data to [PVOutput](http://pvoutput.org/). It uses a config file to store the
credentials for Sunny Portal and the
[API Key and System Id](http://pvoutput.org/account.jsp) for PVOutput.

# How to run
1. Clone or download the repository.
2. Enter the directory and run: 
    ```PYTHONPATH=. ./bin/sunnyportal2pvoutput --dry-run sunnyportal.config```
3. Enter the requested information and verify that the script is able to connect to Sunny Portal.
4. The information is saved in sunnyportal.config and can be edited/deleted if you misstype anything.
5. Once it works, replace --dry-run with e.g. --output to upload the last seven days output data to pvoutput or --status to upload data for the current day.
6. Add --quiet to silence the output.

```sh
$ PYTHONPATH=. ./bin/sunnyportal2pvoutput sunnyportal.config --help
usage: sunnyportal2pvoutput [-h] [-s] [-o] [-q] [-n] config

Connect Sunny Portal to PVoutput.org

positional arguments:
  config         Configuration file to use

optional arguments:
  -h, --help     show this help message and exit
  -s, --status   Report current status
  -o, --output   Report last output(s)
  -q, --quiet    Silence output
  -n, --dry-run  Don't send any data
```
