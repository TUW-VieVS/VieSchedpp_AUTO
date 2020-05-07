# VieSched++ AUTO

contact: matthias.schartner@geo.tuwien.ac.at

# Installation

have a look at the `environemt.yml` file. 
It lists all necessary packages to run the scripts. 
You can use the `environment.yml` file to generate a new environment. 
When using anaconda type:

    conda env create -f environment.yml 

to activate the environment type:

    conda activate VieSchedpp_AUTO 
    
# Start 

The software is meant to run as a daily `cronjob`. 

To start VieSched++ AUTO execute the `VieSchedpp_AUTO.py` script while being in the `VieSchedpp_AUTO` environment.

    python VieSchedpp_AUTO.py -h 

shows the help message. 
For testing, it is advisable to use the `-nu` (no upload) and `-ne` (no email) flags to suppress uploading files to the BKG server and sending emails. 

A typical start might look like this: 

    python VieSchedpp_AUTO.py -i "TU Wien" -p INT1 INT2 R1 R4 -e "matthias.schartner@geo.tuwien.ac.at" -s "path/to/VieSchedpp/executable"

# Emails

It might be advisable to use your own `SMTP` server to send Email notifications. 
For testing purposes, I have created a dummy email address `vieschedpp_auto@gmail.com` that can be used. 
Please note that this is not safe since everybody can access this email address. 
Have a look at the `send` function in the `SendMail.py` file to connect to your own `SMTP` server. 

#  How it works

The software is meant to run as a daily `cronjob`. 

At the start, `VieSchedpp_AUTO.py` will download the newest catalog files and session masters unless the `-nd` (no download) flag is passed as an argument. 

The software will look at the `settings.ini` file and read all observing programs listed there and match them with the observing programs passed via the `-p` (observing program) flag. If one matches it will check if a new schedule should be generated. 

1. The schedules are generated based on the templates located in `/Templates/*ObservingProram*/` (You can add as many templates as you like but make sure to use the `version_offset` option to avoid name clashes)
2. The schedules are generated in the `Schedules/*ObservingProgram*/*SessionCode*/` folder
3. The best schedule is stored in the `Schedules/*ObservingProgram*/*SessionCode*/selected` folder and notification emails are send. Internally, `VieSchedpp_AUTO.py` will use the function named in the `settings.ini` file to determine which session is the preferred one. 
4. A note is left in the `upload_scheduler.txt` file when the session should be uploaded
5. After the schedules are generated, the `upload_scheduler.txt` file is used to verify if a schedule should be uploaded to the IVS-BKG server. If so, it is uploaded and notification emails are sent. 

Notes:

- downtimes are automatically taken from IVS intensive master for non-intensive sessions
- if you need to manually enter additional downtimes or add station in tagalong mode use the `./downtimes.txt` and `./tagalong.txt` file
- an easy trick to add more complex parameter changes is to add them via multi-schedling parameters
- if you want to automatically upload files to the IVS BKG server, you have to provide your password to the program. Please save password in a file called `BKG_pw.txt` or insert password in source code (see file `Transfer.py`, line with comment `*** INSERT PASSWORD HERE (replace pw) ***` 

# Template restrictions

There are a few restrictions for the XML-templates:

1. Do not predefine parameters with a shorter duration than full session time span
2. Do not predefine parameters with groups as members (only "__all__" or explicit station name) 


