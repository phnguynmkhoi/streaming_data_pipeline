#!bin/bash
/opt/hive/bin/schematool -initSchema -dbType postgres
hive --service metastore