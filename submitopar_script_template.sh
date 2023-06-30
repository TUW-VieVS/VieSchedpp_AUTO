#! /bin/bash
# version 1.1 June 2017 (O.B.)
#
# OPAR Data Center maintained by
# Olivier Becker (olivier.becker@obspm.fr)
# Teddy Carlucci (teddy.carlucci@obspm.fr)
# Christophe Barache (christophe.barache@obspm.fr)
# Sebastien Lambert (sebastien.lambert@obspm.fr)
#

LOGIN=""
PASSWD=""
user=$LOGIN:$PASSWD

function usage_example
{
   echo ""
   echo "USAGE EXAMPLE :"
   echo ""
   echo "submitopar_script -display"
   echo ""
   echo "            display remote directory ssalto"
   echo  ""
   echo "submitopar_script -upload file1 file2 file3"
   echo  ""
   echo "            upload local file1 file2 file3 to ivsopar"
   echo  ""

   exit
}


if [ $# -eq 0 ]
then
   usage_example
fi

mode=$1

if [ $mode != "-display" ] && [ $mode != "-upload" ]
then
   usage_example
fi


case $mode in

   "-display" )

       if [ $# -ne 1 ]
       then
           usage_example
       fi
       curl -u $user -F 'mode=display' https://ivsopar.obspm.fr/upload/
       ;;

   "-upload" )

        for fichier in $@
       do
           if [ $fichier != "$1" ]
           then
               if [ -f $fichier ]
               then
                   curl  -u $user -F "fichier=@"$fichier -F 'mode=upload' https://ivsopar.obspm.fr/upload/
               else
                   echo "Error. Can't upload $fichier"
               fi
           fi
       done
       ;;

esac
