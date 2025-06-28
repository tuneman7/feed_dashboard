#!/bin/bash

# Usage: ./ssh-connect.sh
IP=$(terraform output -raw public_ip)
chmod 400 id_rsa
ssh -i id_rsa ubuntu@$IP
