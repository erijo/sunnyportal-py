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
usage: sunnyportal2pvoutput [-h] [-s] [-o] [-c] [-p DAYS_PAST] [-q] [-n] config

Connect Sunny Portal to PVoutput.org

positional arguments:
  config                Configuration file to use

optional arguments:
  -h, --help            show this help message and exit
  -s, --status          Report status(es)
  -o, --output          Report output(s)
  -c, --consumption     Report consumption
  -p DAYS_PAST, --days-past DAYS_PAST
                        number of DAYS in the past to go back -- default: 0 (today only)
  -q, --quiet           Silence output
  -n, --dry-run         Don't send any data
```


# sunnyportal2file
The script [sunnyportal2file](bin/sunnyportal2file) can be used to save data from [Sunny Portal](https://www.sunnyportal.com/) to file/database.
It uses the same config file as in [sunnyportal2pvoutput](bin/sunnyportal2pvoutput) to store the credentials
for Sunny Portal. It will extract the fields (min, mean and max production) which
 are available in unit watt as [numpy.uint32](https://numpy.org/devdocs/user/basics.types.html) along with corresponding timestamps
 and aggregate them into a [pandas DataFrame](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html) from which it will save to file with
 the format specified. One file will be created for each plant your Sunny Portal
 account has access to.

# How to run
1. Clone or download the repository.
2. Enter the directory and run:
    ```PYTHONPATH=. ./bin/sunnyportal2file sunnyportal.config --format csv``` (change --format if you prefer a different format)
3. Enter the requested information and verify that a file was created with the format you specified with the expected content
4. Once it works, you can specify a different start date with --start-date, and end date with --end-date (both defaults to yesterday)
5. If a data file already exists, it will only download new data and append to previously created data file (can override --start-date)
6. Add --quiet to silence the output.


```sh
$ PYTHONPATH=. ./bin/sunnyportal2file -h
usage: sunnyportal2file [-h] -f {json,csv,pickle,feather,parquet,excel,sqlite} [-s START_DATE] [-e END_DATE] [-q] config

Save information from Sunny Portal to file

positional arguments:
  config                Configuration file to use

optional arguments:
  -h, --help            show this help message and exit
  -f {json,csv,pickle,feather,parquet,excel,sqlite}, --format {json,csv,pickle,feather,parquet,excel,sqlite}
                        Format for which the data is to be saved
  -s START_DATE, --start-date START_DATE
                        The start date of data to be saved in the format YYYY-MM-DD (default yesterday)
  -e END_DATE, --end-date END_DATE
                        The end date of data to be saved in the format YYYY-MM-DD (default yesterday)
  -q, --quiet           Silence output
```
