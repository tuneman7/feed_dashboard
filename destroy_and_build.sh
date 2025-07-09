 
 set +e

 . cleanup-rds-security.sh 
 . destroy.sh 
 . terraform-build.sh 
 . fix-rds-security.sh 
 . deploy.sh
